#!/usr/bin/env python3
"""Sincroniza notas Markdown a ai-memory via el CLI `ai-memory store`.

Uso:
  vault_sync.py scan              # lista notas pendientes de sync (JSON)
  vault_sync.py sync              # escanea y guarda en ai-memory
  vault_sync.py status            # estado del sync
  vault_sync.py check             # self-check

Config: ~/.config/vault-sync/config.json (o $VAULT_SYNC_CONFIG):

  {
    "vault": "~/Obsidian/MyVault",
    "lanes": {
      "20-Study": "obsidian/study",
      "30-Projects": "obsidian/projects"
    },
    "external_lanes": {
      "~/projects/gio/ai-coach": "obsidian/coaching"
    },
    "state_dir": "~/.cache/vault-sync"
  }

`lanes` mapea subdirectorios del vault a namespaces de ai-memory.
`external_lanes` mapea directorios fuera del vault (sus .md se indexan
directo desde su repo, con prefijo "<nombre-dir>/").
$VAULT_PATH sobreescribe `vault`. State: <state_dir>/state.json.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(
    os.environ.get("VAULT_SYNC_CONFIG", Path.home() / ".config" / "vault-sync" / "config.json")
)

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
SKIP_DIRS = {".obsidian", ".smart-env", "copilot", "graphify-out", ".commandcode",
             "vendor", "node_modules", ".git", "_notebooklm", "Imports"}

VAULT, LANES, EXTERNAL_LANES, STATE_FILE = None, {}, {}, None


def load_config():
    global VAULT, LANES, EXTERNAL_LANES, STATE_FILE
    cfg = {}
    if CONFIG_PATH.is_file():
        cfg = json.loads(CONFIG_PATH.read_text())
    VAULT = Path(os.environ.get("VAULT_PATH", cfg.get("vault", ""))).expanduser()
    LANES = dict(cfg.get("lanes", {}))
    EXTERNAL_LANES = {
        Path(p).expanduser(): ns for p, ns in cfg.get("external_lanes", {}).items()
    }
    state_dir = Path(cfg.get("state_dir", Path.home() / ".cache" / "vault-sync")).expanduser()
    STATE_FILE = state_dir / "state.json"


def parse_frontmatter(text):
    fm = {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return fm, text
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"') for v in val[1:-1].split(",") if v.strip()]
            elif val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            fm[key.strip()] = val
    return fm, text[m.end():]


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:32]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def scan_lane(lane_path, namespace, rel_fn):
    if not lane_path.is_dir():
        return []
    notes = []
    for p in lane_path.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name.startswith("."):
            continue
        notes.append((p, namespace, rel_fn(p)))
    return notes


def scan_all():
    all_notes = []
    for lane, ns in LANES.items():
        all_notes.extend(scan_lane(VAULT / lane, ns, lambda p: str(p.relative_to(VAULT))))
    for lane_path, ns in EXTERNAL_LANES.items():
        all_notes.extend(scan_lane(lane_path, ns,
                                   lambda p, lp=lane_path: f"{lp.name}/{p.relative_to(lp)}"))
    return all_notes


def note_to_memory(path, namespace, rel):
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    title = fm.get("title", path.stem)
    source = fm.get("source", "obsidian")
    tags = []
    if isinstance(fm.get("tags"), list):
        tags = fm["tags"]
    elif isinstance(fm.get("tags"), str):
        tags = [fm["tags"]]
    tags.extend(["obsidian", namespace.split("/")[-1]])

    content = body.strip()[:12000]
    meta = {
        "path": rel,
        "vault": str(VAULT),
        "source": source,
        "frontmatter": fm,
    }
    if "date" in fm:
        meta["date"] = str(fm["date"])
    if "id" in fm:
        meta["granola_id"] = str(fm["id"])
    if "participants" in fm:
        meta["participants"] = fm["participants"]

    return {
        "content": content,
        "title": title,
        "namespace": namespace,
        "tags": tags,
        "kind": "observation",
        "source": "obsidian",
        "source_uri": f"obsidian://{rel}",
        "metadata": meta,
    }


def pending_notes(state):
    out = []
    for path, ns, rel in scan_all():
        h = file_hash(path)
        prev = state.get(rel)
        if prev and prev.get("hash") == h:
            continue
        out.append((path, ns, rel, h))
    return out


def do_scan():
    state = load_state()
    pending = pending_notes(state)
    out = []
    for path, ns, rel, h in pending:
        mem = note_to_memory(path, ns, rel)
        out.append({"path": rel, "namespace": ns, "hash": h, "title": mem["title"], "memory": mem})
    print(json.dumps({"pending": len(out), "notes": out}, ensure_ascii=False, indent=2))


def ai_memory_bin():
    """Resuelve el binario ai-memory: bajo launchd/cron el PATH es mínimo."""
    import shutil
    return (os.environ.get("AI_MEMORY_BIN") or shutil.which("ai-memory")
            or str(Path.home() / ".local" / "bin" / "ai-memory"))


def store_memory(mem):
    """Guarda en ai-memory via CLI directo (no MCP)."""
    tags_str = ",".join(mem["tags"]) if mem["tags"] else ""
    cmd = [
        ai_memory_bin(), "store",
        "--title", mem["title"],
        "--content", mem["content"],
        "--namespace", mem["namespace"],
        "--kind", mem.get("kind", "observation"),
        "--source", "import",
        "--source-uri", mem.get("source_uri", "").replace("obsidian://", "file://"),
        "--tags", tags_str,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    parts = r.stdout.split()
    for part in parts:
        if len(part) == 36 and part.count("-") == 4:
            return part
    return None


def do_sync():
    state = load_state()
    pending = pending_notes(state)
    if not pending:
        return
    stored = 0
    for path, ns, rel, h in pending:
        mem = note_to_memory(path, ns, rel)
        mid = store_memory(mem)
        if mid:
            state[rel] = {"hash": h, "mtime": path.stat().st_mtime, "memory_id": mid}
            stored += 1
        else:
            print(f"  ERR: {rel}", file=sys.stderr)
    save_state(state)
    print(f"synced {stored}/{len(pending)} notes")


def do_status():
    state = load_state()
    notes = scan_all()
    pending = len(pending_notes(state))
    print(f"total notas: {len(notes)}")
    print(f"sincronizadas: {len(state)}")
    print(f"pendientes: {pending}")
    by_ns = {}
    for path, ns, rel in notes:
        by_ns.setdefault(ns, {"synced": 0, "pending": 0})
        key = "synced" if rel in state else "pending"
        by_ns[ns][key] += 1
    for ns, counts in sorted(by_ns.items()):
        print(f"  {ns:30} sync={counts['synced']:3} pending={counts['pending']:3}")


def self_check():
    assert parse_frontmatter("---\ntitle: test\n---\nbody")[0]["title"] == "test", "frontmatter parse roto"
    assert parse_frontmatter("no fm here")[1] == "no fm here", "no-frontmatter roto"
    h1 = hashlib.sha256(b"a").hexdigest()[:32]
    h2 = hashlib.sha256(b"b").hexdigest()[:32]
    assert h1 != h2, "hash roto"
    print("self-check ok")


def main():
    load_config()
    ap = argparse.ArgumentParser(description="Sync notas Markdown -> ai-memory")
    ap.add_argument("command", nargs="?", default="status", choices=["scan", "sync", "status", "check"])
    args = ap.parse_args()
    if args.command == "check":
        return self_check()
    if not LANES and not EXTERNAL_LANES:
        print(f"sin lanes configurados: crea {CONFIG_PATH} (ver config.example.json)", file=sys.stderr)
        sys.exit(1)
    if args.command == "scan":
        return do_scan()
    if args.command == "sync":
        return do_sync()
    if args.command == "status":
        return do_status()


if __name__ == "__main__":
    main()
