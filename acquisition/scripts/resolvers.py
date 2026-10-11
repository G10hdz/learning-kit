"""Resolución de fuentes: fila del catálogo -> candidatos de adquisición.

Un resolver recibe la fila como dict {columna: valor} (ver HEAD) y devuelve
candidatos. `direct=True` marca URLs descargables por `add`; `direct=False`
son hints para el paso humano (búsquedas, catálogos).

Resolvers extra se enchufan como plugins: archivos .py en
$FOUNDER_GUIDE_RESOLVER_DIR (default ~/.config/founder-guide/resolvers)
que definan `resolve(row) -> Iterable[Candidate|dict]`. Los plugins viven
fuera del repo: cada instalación decide qué fuentes resuelve.
"""

import importlib.util
import os
import re
import sys
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

HEAD = ["id", "seccion", "titulo", "autor", "acceso", "estado", "notebook", "archivo", "notas"]

PLUGIN_DIR = Path(os.environ.get(
    "FOUNDER_GUIDE_RESOLVER_DIR",
    Path.home() / ".config" / "founder-guide" / "resolvers")).expanduser()


@dataclass
class Candidate:
    source: str
    url: str
    direct: bool = False
    note: str = ""


def slugify(text, max_len=60):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_len].rstrip("-")


def resolve_direct(row):
    """URL explícita en la fila -> descarga directa por `add`."""
    url = row["archivo"]
    if url.startswith("http") and " " not in url:
        yield Candidate("direct", url, direct=True)


def resolve_open_library(row):
    """Fallback: búsqueda en Open Library para el paso humano."""
    title = re.sub(r"\*+", "", row["titulo"])
    q = urllib.parse.quote_plus(title)
    yield Candidate("open-library", f"https://openlibrary.org/search?q={q}", note="búsqueda")


def _as_candidate(x):
    if isinstance(x, Candidate):
        return x
    if isinstance(x, dict):
        return Candidate(x.get("source", "plugin"), x["url"],
                         x.get("direct", False), x.get("note", ""))
    raise TypeError(f"candidato inválido: {x!r}")


def load_plugins():
    """Importa *.py de PLUGIN_DIR; cada módulo puede exponer resolve(row)."""
    fns = []
    if not PLUGIN_DIR.is_dir():
        return fns
    for path in sorted(PLUGIN_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"fg_resolver_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            print(f"resolver plugin {path.name}: {exc}", file=sys.stderr)
            continue
        fn = getattr(mod, "resolve", None)
        if callable(fn):
            fns.append(fn)
    return fns


def candidates(cells):
    """Cadena: directas -> plugins -> fallback de búsqueda si nadie respondió."""
    row = dict(zip(HEAD, cells))
    out = [_as_candidate(x) for x in (resolve_direct(row) or [])]
    for fn in load_plugins():
        try:
            out.extend(_as_candidate(x) for x in (fn(row) or []))
        except Exception as exc:
            print(f"resolver {getattr(fn, '__module__', fn)}: {exc}", file=sys.stderr)
    if not out:
        out.extend(resolve_open_library(row))
    return out
