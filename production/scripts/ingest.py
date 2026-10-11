#!/usr/bin/env python3
"""Adquisición e ingesta de fuentes: catálogo <-> archivos <-> NotebookLM <-> Calibre.

Uso:
  ingest.py list                     # estado del catálogo
  ingest.py add <ID> [...]           # URL del catálogo o vault/inbox/<ID>_* -> archivo + Calibre
  ingest.py add --inbox              # procesa todo vault/inbox/
  ingest.py study <ID>               # archivo almacenado -> NotebookLM (libreta por categoría)
  ingest.py pending                  # fuentes pendientes_manual + link de búsqueda para conseguirlas tú
  ingest.py push-calibre <archivo>   # scp + calibredb add en $CALIBRE_HOST
  ingest.py --check                  # self-check rápido (parse catálogo + slug)

Catálogo: vault/sources/_catalogo.md (tabla markdown).
Archivos: vault/sources/files/<id>-<slug>.<ext>. Inbox: vault/inbox/<ID>_<lo que sea>.<ext>.
El inbox no distingue el origen del archivo.
"""

import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path

VAULT = Path(os.environ.get("CAPITAL_CULTURAL_VAULT", Path(__file__).resolve().parent.parent / "vault"))
CATALOGO = VAULT / "sources" / "_catalogo.md"
FILES = VAULT / "sources" / "files"
INBOX = VAULT / "inbox"
CALIBRE_HOST = os.environ.get("CALIBRE_HOST", "localhost")
CALIBRE_INGEST = "cwa/ingest"  # Calibre-Web-Automated: convierte, mete metadata e importa solo
AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

ROW = re.compile(r"^\|\s*([a-z]+-\d+)\s*\|")
FNAME_ID = re.compile(r"^([a-z]+-\d+)[_-]")
HEAD = ["id", "categoria", "fuente", "acceso", "estado", "notebook", "archivo", "resumen",
        "impact_score", "scored_at"]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def slugify(text, max_len=40):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_len].rstrip("-") or "fuente"


def read_catalog(path=None):
    rows = {}
    for line in (path or CATALOGO).read_text().splitlines():
        m = ROW.match(line)
        if m:
            rows[m.group(1)] = [c.strip() for c in line.strip().strip("|").split("|")]
    return rows


def write_catalog(rows):
    out = []
    for line in CATALOGO.read_text().splitlines():
        m = ROW.match(line)
        out.append("| " + " | ".join(rows[m.group(1)]) + " |" if m and m.group(1) in rows else line)
    CATALOGO.write_text("\n".join(out) + "\n")


def set_cell(rows, sid, col, value):
    rows[sid][HEAD.index(col)] = value


def local_file(sid):
    hits = sorted(FILES.glob(f"{sid}-*")) + sorted(INBOX.glob(f"{sid}[-_]*"))
    return hits[0] if hits else None


def download(sid, cells):
    url = cells[HEAD.index("archivo")] if False else cells[6]  # celda URL cruda
    if not url or " " in url:
        return None
    ext = ".pdf" if "cervantesvirtual" in url else (Path(url.split("?")[0]).suffix or ".txt")
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
    remote = f"{CALIBRE_HOST}:{CALIBRE_INGEST}/{path.name}"
    r = run(["scp", "-q", str(path), remote])
    ok = r.returncode == 0
    print("  calibre (CWA ingest): ok" if ok else f"  scp fallo: {r.stderr.strip()[:200]}")
    return ok


def notebook_id(rows, categoria):
    for cells in rows.values():
        if cells[1] == categoria and cells[5]:
            return cells[5]
    r = run(["nlm", "notebook", "create", f"Capital Cultural - {categoria}"])
    nb = next((m.group(1) for line in (r.stdout + r.stderr).splitlines()
               if (m := re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", line))), None)
    if nb:
        for sid, cells in rows.items():
            if cells[1] == categoria:
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
    set_cell(rows, sid, "archivo", str(src.relative_to(VAULT)))
    set_cell(rows, sid, "estado", "calibre")
    return True


def do_study(rows, sid):
    cells = rows[sid]
    if cells[4] == "ingerido":
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


def inbox_ids():
    return sorted({m.group(1) for p in INBOX.glob("*") if (m := FNAME_ID.match(p.name))})


def self_check():
    fixture = "| id | categoria | fuente | acceso | estado | notebook | archivo | resumen |\n" \
              "|---|---|---|---|---|---|---|---|\n" \
              "| vc-05 | Código VC | Jorgenson, *The Almanack of Naval Ravikant* | acceso_abierto | listo_para_ingesta | | https://x.y/z.pdf | |\n"
    p = Path(os.environ.get("TMPDIR", "/tmp")) / "_cat_fixture.md"
    p.write_text(fixture)
    rows = read_catalog(p)
    assert "vc-05" in rows and rows["vc-05"][3] == "acceso_abierto" and rows["vc-05"][4] == "listo_para_ingesta", "parse catálogo roto"
    set_cell(rows, "vc-05", "estado", "ingerido")
    assert rows["vc-05"][4] == "ingerido", "set_cell roto"
    assert slugify("Código VC: Thiel, *Zero to One*") == "codigo-vc-thiel-zero-to-one", "slug roto"
    assert FNAME_ID.match("vc-03_zero.pdf").group(1) == "vc-03", "regex inbox roto"
    assert FNAME_ID.match("inst-05-x.pdf").group(1) == "inst-05", "regex inbox roto 2"
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
            print(f"{sid:8} {c[3]:16} {c[4]:18} {c[2][:48]}")
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
            if c[3] in ("pendiente_manual", "biblioteca") and "calibre" not in c[4]:
                t = re.sub(r"\*+", "", c[2])
                q = urllib.parse.quote_plus(t)
                print(f"{sid:8} {t[:52]:52} buscar: https://openlibrary.org/search?q={q}")
    elif cmd == "study":
        ok = do_study(rows, args[1])
        write_catalog(rows)
        sys.exit(0 if ok else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
