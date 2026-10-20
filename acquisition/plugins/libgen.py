"""Resolver LibGen para founder-guide (plugin de ejemplo).

Genera el link de busqueda por titulo + autor para el paso humano. No
descarga nada: la obtencion del archivo es manual (o via tu herramienta
preferida) y cada instalacion decide que fuentes resuelve.

Nota honesta: LibGen es una biblioteca sombra; descargar libros con copyright
infringe leyes en la mayoria de jurisdicciones. Esto es solo un bookmark de
busqueda; el uso que le des es tu responsabilidad.
"""

import re
import urllib.parse


def resolve(row):
    title = re.sub(r"\*+", "", row["titulo"])
    author = re.sub(r"\*+", "", row.get("autor") or "")
    q = urllib.parse.quote_plus(f"{title} {author}".strip())
    return [{"source": "libgen",
             "url": f"https://libgen.is/search.php?res=100&req={q}",
             "note": "busqueda manual"}]
