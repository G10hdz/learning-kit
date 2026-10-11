#!/usr/bin/env python3
"""Adquisición de fuentes: catálogo <-> archivos <-> Calibre <-> NotebookLM.

Uso:
  acquire.py list                        # estado del catálogo
  acquire.py add <ID> [...]              # URL del catálogo o inbox/<ID>_* -> archivo + Calibre
  acquire.py add --inbox                 # procesa todo vault/inbox/
  acquire.py study <ID>                  # archivo -> NotebookLM (libreta por sección)
  acquire.py pending                     # pendientes + candidatos de resolvers
  acquire.py push-calibre <archivo>      # scp + calibredb add en el host Calibre (env CALIBRE_HOST)
  acquire.py suggest --title "..." --author "..." --section 01-startup-negocio [--type book|video] [--url "..."]
  acquire.py --check                     # self-check rápido

Catálogo: docs/book-candidates.md (tabla markdown).
Archivos: vault/sources/files/<id>-<slug>.<ext>. Inbox: vault/inbox/<ID>_<lo que sea>.<ext>.
"""

import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import resolvers

ROOT = Path(os.environ.get("FOUNDER_GUIDE_HOME", Path(__file__).resolve().parent.parent))
CATALOG = ROOT / "docs" / "book-candidates.md"
FILES = ROOT / "vault" / "sources" / "files"
INBOX = ROOT / "vault" / "inbox"
CALIBRE_HOST = os.environ.get("CALIBRE_HOST", "")  # host ssh con Calibre CWA (docker)
CALIBRE_INGEST = "cwa/ingest"
AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

ROW = re.compile(r"^\|\s*([a-z]+-\d+)\s*\|")
FNAME_ID = re.compile(r"^([a-z]+-\d+)[_-]")
HEAD = ["id", "seccion", "titulo", "autor", "acceso", "estado", "notebook", "archivo", "notas"]

SECTION_PREFIXES = {
    "01-startup-negocio": "bus",
    "02-diseno": "des",
    "03-ai": "ai",
    "04-codigo": "cod",
}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def slugify(text, max_len=40):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_len].rstrip("-") or "fuente"


def read_catalog(path=None):
    rows = {}
    for line in (path or CATALOG).read_text().splitlines():
        m = ROW.match(line)
        if m:
            rows[m.group(1)] = [c.strip() for c in line.strip().strip("|").split("|")]
    return rows


def write_catalog(rows):
    out = []
    for line in CATALOG.read_text().splitlines():
        m = ROW.match(line)
        out.append("| " + " | ".join(rows[m.group(1)]) + " |" if m and m.group(1) in rows else line)
    CATALOG.write_text("\n".join(out) + "\n")


def append_catalog(row):
    with open(CATALOG, "a") as f:
        f.write("| " + " | ".join(row) + " |\n")


def set_cell(rows, sid, col, value):
    rows[sid][HEAD.index(col)] = value


def next_id(section):
    prefix = SECTION_PREFIXES.get(section)
    if not prefix:
        raise ValueError(f"sección desconocida: {section}")
    rows = read_catalog()
    existing = [int(sid.split("-")[1]) for sid in rows if sid.startswith(prefix + "-")]
    n = max(existing, default=0) + 1
    return f"{prefix}-{n:02d}"


def local_file(sid):
    hits = sorted(FILES.glob(f"{sid}-*")) + sorted(INBOX.glob(f"{sid}[-_]*"))
    return hits[0] if hits else None


def download(sid, cells):
    url = cells[HEAD.index("archivo")] if False else cells[7]
    if not url or " " in url:
        return None
    ext = Path(url.split("?")[0]).suffix or ".pdf"
    dest = FILES / f"{sid}-{slugify(cells[2])}{ext}"
    if dest.exists():
        return dest
    if "gutenberg.org/ebooks/" in url:
        gid = url.rstrip("/").split("/")[-1]
        url = f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt"
        ext = ".txt"
    r = run(["curl", "-fsSL", "--retry", "3", "-A", AGENT, "-o", str(dest), url])
    if r.returncode != 0 or not dest.exists() or dest.stat().st_size < 4096:
        dest.unlink(missing_ok=True)
        return None
    return dest


def push_calibre(path):
    if not CALIBRE_HOST:
        print("  calibre: define CALIBRE_HOST (host ssh con CWA corriendo)")
        return False
    remote = f"{CALIBRE_HOST}:{CALIBRE_INGEST}/{path.name}"
    r = run(["scp", "-q", str(path), remote])
    ok = r.returncode == 0
    print("  calibre (CWA ingest): ok" if ok else f"  scp fallo: {r.stderr.strip()[:200]}")
    return ok


def notebook_id(rows, section):
    for cells in rows.values():
        if cells[1] == section and cells[6]:
            return cells[6]
    label = {"01-startup-negocio": "Startup y Negocio", "02-diseno": "Diseno",
             "03-ai": "AI", "04-codigo": "Codigo"}.get(section, section)
    r = run(["nlm", "notebook", "create", f"Founder Guide - {label}"])
    nb = next((m.group(1) for line in (r.stdout + r.stderr).splitlines()
               if (m := re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", line))), None)
    if nb:
        for sid, cells in rows.items():
            if cells[1] == section:
                set_cell(rows, sid, "notebook", nb)
    print(f"  libreta: {nb or 'NO CREADA (nlm login?)'}")
    return nb


def do_add(rows, sid):
    src = local_file(sid) or download(sid, rows[sid])
    if not src:
        print("  sin archivo: ponlo en vault/inbox/ como <ID>_* o revisa la URL")
        return False
    if src.parent == INBOX:
        rest = src.name.split("_", 1)[-1] if "_" in src.name else src.name
        src = src.rename(FILES / f"{sid}-{rest}")
    print(f"  archivo: {src.name}")
    push_calibre(src)
    set_cell(rows, sid, "archivo", str(src.relative_to(ROOT)))
    set_cell(rows, sid, "estado", "calibre")
    return True


def do_study(rows, sid):
    cells = rows[sid]
    if cells[5] == "ingerido":
        print(f"{sid}: ya ingerido (salta)")
        return True
    src = local_file(sid)
    if not src:
        print("sin archivo local: corre 'add' primero")
        return False
    nb = notebook_id(rows, cells[1])
    if not nb:
        return False
    r = run(["nlm", "source", "add", nb, "--file", str(src), "--wait"])
    print((r.stdout or r.stderr).strip()[:300])
    if r.returncode == 0:
        set_cell(rows, sid, "estado", "ingerido")
    return r.returncode == 0


def do_suggest(args):
    section = None
    title = None
    author = ""
    url = ""
    stype = "book"
    i = 0
    while i < len(args):
        if args[i] == "--section":
            section = args[i + 1]; i += 2
        elif args[i] == "--title":
            title = args[i + 1]; i += 2
        elif args[i] == "--author":
            author = args[i + 1]; i += 2
        elif args[i] == "--url":
            url = args[i + 1]; i += 2
        elif args[i] == "--type":
            stype = args[i + 1]; i += 2
        else:
            i += 1
    if not section or not title:
        print("suggest requiere --section y --title")
        return False
    sid = next_id(section)
    acceso = "acceso_abierto" if url and ("gutenberg" in url or "github" in url or "arxiv" in url) else "pendiente_manual"
    notas = f" sugerido: {stype}" + (f", {url}" if url else "")
    row = [sid, section, title, author, acceso, "pendiente", "", url, notas.strip()]
    append_catalog(row)
    print(f"  {sid} | {title} -> {section} ({stype})")
    return True


def inbox_ids():
    return sorted({m.group(1) for p in INBOX.glob("*") if (m := FNAME_ID.match(p.name))})


def self_check():
    fixture = "| id | seccion | titulo | autor | acceso | estado | notebook | archivo | notas |\n" \
              "|---|---|---|---|---|---|---|---|---|\n" \
              "| bus-01 | 01-startup-negocio | The Mom Test | Rob Fitzpatrick | pendiente_manual | pendiente | | | |\n"
    p = Path(os.environ.get("TMPDIR", "/tmp")) / "_fg_cat_fixture.md"
    p.write_text(fixture)
    rows = read_catalog(p)
    assert "bus-01" in rows and rows["bus-01"][4] == "pendiente_manual", "parse catálogo roto"
    set_cell(rows, "bus-01", "estado", "ingerido")
    assert rows["bus-01"][5] == "ingerido", "set_cell roto"
    assert slugify("The Mom Test") == "the-mom-test", "slug roto"
    assert FNAME_ID.match("bus-01_mom-test.epub").group(1) == "bus-01", "regex inbox roto"
    assert re.fullmatch(r"bus-\d+", next_id("01-startup-negocio")), "next_id roto"
    assert SECTION_PREFIXES["03-ai"] == "ai", "section prefix roto"
    cands = list(resolvers.resolve_open_library(dict(zip(resolvers.HEAD, rows["bus-01"]))))
    assert cands and "openlibrary.org" in cands[0].url, "fallback resolver roto"
    row_url = rows["bus-01"][:]
    row_url[7] = "https://gutenberg.org/ebooks/123"
    assert any(c.direct for c in resolvers.candidates(row_url)), "resolver direct roto"
    print("self-check ok")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--check":
        return self_check()
    cmd, rows = args[0], read_catalog()
    if cmd == "list":
        for sid, c in rows.items():
            print(f"{sid:8} {c[1]:22} {c[5]:16} {c[2][:44]}")
    elif cmd == "push-calibre":
        sys.exit(0 if push_calibre(Path(args[1])) else 1)
    elif cmd == "add":
        ids = inbox_ids() if "--inbox" in args else args[1:]
        done = [s for s in ids if do_add(rows, s)]
        if done:
            write_catalog(rows)
        print(f"add: {done or 'nada'}")
    elif cmd == "pending":
        for sid, c in rows.items():
            if c[4] in ("pendiente_manual", "biblioteca") and "calibre" not in c[5]:
                t = re.sub(r"\*+", "", c[2])
                print(f"{sid:8} {t[:52]:52}")
                for cand in resolvers.candidates(c):
                    kind = "descarga" if cand.direct else "búsqueda"
                    print(f"           {cand.source:14} [{kind}] {cand.url}")
    elif cmd == "study":
        ok = do_study(rows, args[1])
        write_catalog(rows)
        sys.exit(0 if ok else 1)
    elif cmd == "suggest":
        do_suggest(args[1:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
