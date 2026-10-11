#!/usr/bin/env python3
"""Tests de vault_sync. stdlib only:

    python3 -m unittest discover -s tests -v

La logica de mayor consecuencia es la frontera de privacidad: que dirs
nunca se escanean y que cada nota cae en el namespace correcto. Un stub
de `ai-memory` (via $AI_MEMORY_BIN) reemplaza al binario real: ningun
test toca el store de produccion.
"""

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_sync as vs


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.vault = Path(self.tmp) / "vault"
        lane = self.vault / "10-Inbox"
        (lane / ".obsidian").mkdir(parents=True)
        (lane / "vendor").mkdir()
        (lane / "nota.md").write_text(
            "---\ntitle: Nota\ntags: [idea, papel]\n---\n\nCuerpo de la nota.\n"
        )
        (lane / ".obsidian" / "cfg.md").write_text("interno\n")
        (lane / "vendor" / "tercero.md").write_text("clonado\n")
        (lane / ".draft.md").write_text("borrador\n")

        self.ext = Path(self.tmp) / "coach-state"
        self.ext.mkdir()
        (self.ext / "coaching.md").write_text("# coaching state\n")

        vs.VAULT = self.vault
        vs.LANES = {"10-Inbox": "obsidian/inbox"}
        vs.EXTERNAL_LANES = {self.ext: "obsidian/coaching"}
        vs.STATE_FILE = Path(self.tmp) / "state" / "state.json"
        self._env = {}

    def set_env(self, **kw):
        for k, v in kw.items():
            self._env[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class ScanTest(Base):
    def test_salta_skip_dirs_y_dotfiles(self):
        rels = sorted(rel for _, _, rel in vs.scan_all())
        self.assertEqual(rels, ["10-Inbox/nota.md", "coach-state/coaching.md"])

    def test_external_lane_relativiza_al_nombre_del_dir(self):
        rels = [rel for _, ns, rel in vs.scan_all() if ns == "obsidian/coaching"]
        self.assertEqual(rels, ["coach-state/coaching.md"])

    def test_lane_inexistente_no_explota(self):
        vs.LANES = {"99-Nada": "obsidian/nada"}
        self.assertEqual(vs.scan_all()[0][2], "coach-state/coaching.md")


class MemoryContractTest(Base):
    def test_note_to_memory_namespace_tags_uri(self):
        path = self.vault / "10-Inbox" / "nota.md"
        mem = vs.note_to_memory(path, "obsidian/inbox", "10-Inbox/nota.md")
        self.assertEqual(mem["namespace"], "obsidian/inbox")
        self.assertEqual(mem["source_uri"], "obsidian://10-Inbox/nota.md")
        self.assertEqual(mem["title"], "Nota")
        self.assertIn("idea", mem["tags"])
        self.assertIn("obsidian", mem["tags"])
        self.assertIn("inbox", mem["tags"])
        self.assertIn("Cuerpo de la nota", mem["content"])
        self.assertNotIn("title:", mem["content"])

    def test_scan_emite_json_con_shape_estable(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            vs.do_scan()
        out = json.loads(buf.getvalue())
        self.assertEqual(out["pending"], 2)
        note = out["notes"][0]
        self.assertIn("path", note)
        self.assertIn("namespace", note)
        self.assertIn("hash", note)
        self.assertIn("memory", note)


class PendingTest(Base):
    def test_hash_igual_no_es_pendiente(self):
        state = {}
        for path, ns, rel in vs.scan_all():
            state[rel] = {"hash": vs.file_hash(path)}
        vs.save_state(state)
        self.assertEqual(vs.pending_notes(state), [])

    def test_nota_editada_vuelve_a_ser_pendiente(self):
        path = self.vault / "10-Inbox" / "nota.md"
        state = {"10-Inbox/nota.md": {"hash": vs.file_hash(path)}}
        path.write_text(path.read_text() + "\ncambio\n")
        pending = vs.pending_notes(state)
        self.assertEqual([p[2] for p in pending],
                         ["10-Inbox/nota.md", "coach-state/coaching.md"])


class SyncTest(Base):
    def _stub(self):
        log = Path(self.tmp) / "stub.log"
        stub = Path(self.tmp) / "ai-memory"
        stub.write_text(
            '#!/bin/sh\necho "$@" >> "$STUB_LOG"\n'
            'echo "stored 12345678-1234-1234-1234-1234567890ab"\n'
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return stub, log

    def test_sync_invoca_store_por_nota_y_guarda_state(self):
        stub, log = self._stub()
        self.set_env(AI_MEMORY_BIN=str(stub), STUB_LOG=str(log))
        vs.do_sync()
        calls = [l for l in log.read_text().splitlines() if l.strip()]
        self.assertEqual(len(calls), 2)
        joined = "\n".join(calls)
        self.assertIn("--namespace obsidian/inbox", joined)
        self.assertIn("--namespace obsidian/coaching", joined)
        self.assertIn("store --title", joined)
        state = json.loads(vs.STATE_FILE.read_text())
        self.assertEqual(len(state), 2)
        self.assertTrue(all(v.get("memory_id") for v in state.values()))

    def test_sync_sin_ai_memory_reporta_error_y_no_marca_state(self):
        self.set_env(AI_MEMORY_BIN="/nonexistent/ai-memory")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            vs.do_sync()
        self.assertIn("ERR", err.getvalue())
        state = json.loads(vs.STATE_FILE.read_text())
        self.assertEqual(state, {})


class ConfigTest(Base):
    def test_main_sin_lanes_sale_1(self):
        missing = Path(self.tmp) / "no-config.json"
        old_cfg, old_argv = vs.CONFIG_PATH, sys.argv
        vs.CONFIG_PATH = missing
        sys.argv = ["vault_sync.py", "sync"]
        try:
            with self.assertRaises(SystemExit) as cm:
                vs.main()
            self.assertEqual(cm.exception.code, 1)
        finally:
            vs.CONFIG_PATH, sys.argv = old_cfg, old_argv

    def test_load_config_expande_home_y_vault_path_env_gana(self):
        cfg = Path(self.tmp) / "config.json"
        cfg.write_text(json.dumps({
            "vault": "/deberia/perder",
            "lanes": {"10-Inbox": "obsidian/inbox"},
            "external_lanes": {"~/ext-x": "obsidian/x"},
            "state_dir": str(Path(self.tmp) / "st"),
        }))
        old_cfg = vs.CONFIG_PATH
        vs.CONFIG_PATH = cfg
        self.set_env(VAULT_PATH=str(self.vault))
        try:
            vs.load_config()
        finally:
            vs.CONFIG_PATH = old_cfg
        self.assertEqual(vs.VAULT, self.vault)
        self.assertEqual(vs.LANES, {"10-Inbox": "obsidian/inbox"})
        self.assertEqual(vs.EXTERNAL_LANES, {Path.home() / "ext-x": "obsidian/x"})


if __name__ == "__main__":
    unittest.main()
