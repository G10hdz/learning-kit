#!/usr/bin/env python3
"""Scorea el catálogo con Paperank (https://paperank.open-moss.com).

Para cada fila con URL/DOI y impact_score vacío: consulta
GET /api/papers/search?limit=1&ranked_only=false&scope=global&query=<titulo>
y si el primer resultado coincide con el título, escribe impact_score (0-100)
y scored_at (ISO). Fail-open: cualquier error deja la fila en null y sigue.

Catálogo: vault/sources/_catalogo.md (columnas ... | Resumen | impact_score | scored_at |;
celdas vacías en las dos últimas = sin score).

Uso:
  score_sources.py            # consulta y escribe
  score_sources.py --dry-run  # imprime sin escribir

Nota: spec pedía requests; no está instalado y urllib de la stdlib basta
(ponytail: cero dependencias nuevas; si se añade requests al repo, migrar el fetch).
"""

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent / "vault"
CATALOGO = VAULT / "sources" / "_catalogo.md"
API = "https://paperank.open-moss.com/api/papers/search"
HEAD = ["id", "categoria", "fuente", "acceso", "estado", "notebook", "archivo", "resumen",
        "impact_score", "scored_at"]
ROW = re.compile(r"^\|\s*([a-z]+-\d+)\s*\|")


def norm(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return set(re.sub(r"[^a-z0-9 ]", " ", text).split())


def title_matches(query, result, min_overlap=0.6):
    q, r = norm(query), norm(result)
    if not q or not r:
        return False
    return len(q & r) / len(q) >= min_overlap


def clean_title(fuente):
    m = re.search(r"\*([^*]+)\*", fuente)
    return (m.group(1) if m else fuente).strip()


def query_paperank(title, timeout=10):
    url = API + "?" + urllib.parse.urlencode({"limit": 1, "ranked_only": "false", "scope": "global", "query": title})
    req = urllib.request.Request(url, headers={"User-Agent": "capital-cultural/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    papers = data.get("papers") or []
    if not papers or not title_matches(title, papers[0].get("title", "")):
        return None
    raw = papers[0].get("ranking_score") or 0.0
    score = raw * 100 if raw <= 1 else raw  # ponytail: la API expone 0-1 o 0-100 según versión; normaliza
    return max(0, min(100, round(score)))


def read_catalog(path):
    rows = {}
    for line in Path(path).read_text().splitlines():
        m = ROW.match(line)
        if m:
            rows[m.group(1)] = [c.strip() for c in line.strip().strip("|").split("|")]
    return rows


def write_catalog(path, rows):
    p = Path(path)
    out = []
    for line in p.read_text().splitlines():
        m = ROW.match(line)
        out.append("| " + " | ".join(rows[m.group(1)]) + " |" if m and m.group(1) in rows else line)
    p.write_text("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--catalogo", default=CATALOGO)
    args = ap.parse_args()
    rows = read_catalog(args.catalogo)
    i_sc, i_at = HEAD.index("impact_score"), HEAD.index("scored_at")
    i_url, i_fuente = HEAD.index("archivo"), HEAD.index("fuente")
    scored = skipped = 0
    for sid, cells in rows.items():
        if cells[i_sc] or not (cells[i_url] or "").strip():
            continue
        title = clean_title(cells[i_fuente])
        try:
            score = query_paperank(title)
        except Exception as e:  # fail-open
            print(f"{sid}: sin score ({type(e).__name__}: {e})")
            skipped += 1
            continue
        if score is None:
            print(f"{sid}: sin coincidencia para '{title}'")
            skipped += 1
            continue
        print(f"{sid}: {score}")
        cells[i_sc] = str(score)
        cells[i_at] = date.today().isoformat()
        scored += 1
    if scored and not args.dry_run:
        write_catalog(args.catalogo, rows)
        print(f"escrito: {scored} score(s), {skipped} sin score")
    else:
        print(f"dry-run: {scored} score(s), {skipped} sin score (no se escribió)")


if __name__ == "__main__":
    sys.exit(main())
