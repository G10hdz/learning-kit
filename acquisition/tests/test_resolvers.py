"""Tests del seam de resolvers (scripts/resolvers.py).

El punto del seam es el aislamiento: sin plugin instalado `pending` debe
funcionar con el fallback público; un plugin roto (al importar o al
resolver) no puede tumbar la cadena; y ningún test puede depender del
plugin privado; se crean plugins fixture en tmp_path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import resolvers


def row(**kw):
    base = dict.fromkeys(resolvers.HEAD, "")
    base.update(kw)
    return base


def cells(row_dict):
    return [row_dict.get(c, "") for c in resolvers.HEAD]


@pytest.fixture
def no_plugins(monkeypatch, tmp_path):
    monkeypatch.setattr(resolvers, "PLUGIN_DIR", tmp_path / "sin-dir")
    return tmp_path


@pytest.fixture
def plugin_dir(monkeypatch, tmp_path):
    d = tmp_path / "resolvers"
    d.mkdir()
    monkeypatch.setattr(resolvers, "PLUGIN_DIR", d)
    return d


class TestDirect:
    def test_url_http_es_descarga_directa(self):
        cands = list(resolvers.resolve_direct(row(archivo="https://x.org/a.pdf")))
        assert len(cands) == 1
        assert cands[0].direct is True
        assert cands[0].source == "direct"

    def test_path_local_no_es_descarga(self):
        assert list(resolvers.resolve_direct(row(archivo="/tmp/libro.pdf"))) == []

    def test_vacio_no_es_descarga(self):
        assert list(resolvers.resolve_direct(row())) == []


class TestOpenLibrary:
    def test_fallback_construye_busqueda(self):
        cands = list(resolvers.resolve_open_library(
            row(titulo="*The Mom Test* de Fitzpatrick")))
        assert len(cands) == 1
        assert cands[0].url.startswith("https://openlibrary.org/search?q=")
        assert "Mom+Test" in cands[0].url
        assert cands[0].direct is False


class TestAsCandidate:
    def test_dict_se_normaliza(self):
        c = resolvers._as_candidate({"url": "https://x", "direct": True})
        assert c.source == "plugin"
        assert c.direct is True

    def test_basura_rechazada(self):
        with pytest.raises(TypeError):
            resolvers._as_candidate(42)


class TestPluginChain:
    def test_sin_plugins_cae_al_fallback(self, no_plugins):
        cands = resolvers.candidates(cells(row(titulo="Libro X")))
        assert [c.source for c in cands] == ["open-library"]

    def test_plugin_agrega_candidatos(self, plugin_dir):
        (plugin_dir / "fake.py").write_text(
            "def resolve(row):\n"
            "    return [{'source': 'fake', 'url': 'https://fake/' + row['id'], 'direct': True}]\n"
        )
        cands = resolvers.candidates(cells(row(id="bus-99")))
        assert [c.source for c in cands] == ["fake"]
        assert cands[0].direct is True

    def test_plugin_roto_al_importar_se_salta(self, plugin_dir, capsys):
        (plugin_dir / "broken.py").write_text("raise RuntimeError('boom')\n")
        (plugin_dir / "ok.py").write_text(
            "def resolve(row):\n    return [{'url': 'https://ok/1'}]\n"
        )
        cands = resolvers.candidates(cells(row(id="x")))
        assert [c.url for c in cands] == ["https://ok/1"]
        assert "broken.py" in capsys.readouterr().err

    def test_plugin_que_truena_al_resolver_no_tumba_cadena(self, plugin_dir):
        (plugin_dir / "kaboom.py").write_text(
            "def resolve(row):\n    raise ValueError('nope')\n"
        )
        cands = resolvers.candidates(cells(row(titulo="Y")))
        assert [c.source for c in cands] == ["open-library"]

    def test_archivos_privados_no_cargan(self, plugin_dir):
        (plugin_dir / "_internal.py").write_text(
            "def resolve(row):\n    return [{'url': 'https://nope'}]\n"
        )
        cands = resolvers.candidates(cells(row(titulo="Z")))
        assert all(c.url != "https://nope" for c in cands)

    def test_directa_va_antes_que_plugin(self, plugin_dir):
        (plugin_dir / "p.py").write_text(
            "def resolve(row):\n    return [{'url': 'https://plugin/1'}]\n"
        )
        cands = resolvers.candidates(cells(row(archivo="https://directa.pdf")))
        assert cands[0].source == "direct"
        assert cands[1].url == "https://plugin/1"
