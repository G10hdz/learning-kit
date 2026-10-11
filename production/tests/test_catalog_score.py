import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import score_sources as ss

FIXTURE = """# Catálogo de fuentes

| ID | Categoría | Fuente | Acceso | Estado | Notebook | Archivo o URL | Resumen | impact_score | scored_at |
|---|---|---|---|---|---|---|---|---|---|
| vc-05 | Código VC | Jorgenson, *The Almanack of Naval Ravikant* | acceso_abierto | listo_para_ingesta | | https://x/y.pdf | | | |
| inst-01 | Código Institucional | Samuelson, “The Pure Theory of Public Expenditure” | biblioteca | pendiente_manual | | https://jstor.org/stable/1925895 | | 87 | 2026-08-23 |

Valores de `Acceso`: ...
"""


class CatalogScoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        self.tmp.write(FIXTURE)
        self.tmp.close()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_parse_new_fields(self):
        rows = ss.read_catalog(self.path)
        self.assertEqual(rows["vc-05"][8], "")            # sin score -> null
        self.assertEqual(rows["vc-05"][9], "")
        self.assertEqual(rows["inst-01"][8], "87")        # score presente
        self.assertEqual(rows["inst-01"][9], "2026-08-23")

    def test_write_roundtrip_preserves_scores_and_other_rows(self):
        rows = ss.read_catalog(self.path)
        rows["vc-05"][8] = "73"
        rows["vc-05"][9] = "2026-08-24"
        ss.write_catalog(self.path, rows)
        again = ss.read_catalog(self.path)
        self.assertEqual(again["vc-05"][8], "73")
        self.assertEqual(again["vc-05"][7], "")           # resumen intacto
        self.assertEqual(again["inst-01"][8], "87")       # fila no tocada intacta
        self.assertIn("Valores de `Acceso`", self.path.read_text())  # prosa conservada

    def test_title_extraction_prefers_italic(self):
        self.assertEqual(ss.clean_title("Jorgenson, *The Almanack of Naval Ravikant*"),
                         "The Almanack of Naval Ravikant")
        self.assertEqual(ss.clean_title("Samuelson, “The Pure Theory of Public Expenditure”"),
                         "Samuelson, “The Pure Theory of Public Expenditure”")

    def test_title_match_guard(self):
        self.assertTrue(ss.title_matches("Attention Is All You Need", "Attention is All You Need"))
        self.assertFalse(ss.title_matches("The Pure Theory of Public Expenditure",
                                          "Lean-QIT: Towards Formal Infrastructure"))


if __name__ == "__main__":
    unittest.main()
