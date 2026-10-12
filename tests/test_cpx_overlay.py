import json
import os
import tempfile
import unittest
from pathlib import Path

from kb import KB
from tools.build_cpx_release import DEFAULT_OVERLAY, build


class CpxOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(os.path.expanduser(os.environ.get(
            "MEDAGENT_KB_BASE",
            "/tmp/medagent-kb-cache/kb-2026.10.08.2",
        )))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.tmp.name)
        cls.version = build(base, cls.output, DEFAULT_OVERLAY)
        cls.kb = KB(base=str(cls.output), cache=None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_version_and_tables(self):
        self.assertEqual(self.kb.version, "kb-2026.10.13.1")
        self.assertIn("presentation_component", self.kb.tables())
        self.assertIn("exam_action", self.kb.tables())
        self.assertEqual(self.version["counts"]["exam_actions"], 28)

    def test_composite_presentations_are_decomposed(self):
        components = self.kb.table("presentation_component")
        self.assertEqual(len(components), 45)
        self.assertEqual(len({(r["presentation_id"], r["ordinal"]) for r in components}), 45)
        self.assertTrue(all(r["normalized_ko"] and r["concept_kind"] for r in components))
        vomiting = self.kb.presentation("vomiting")
        self.assertEqual([r["node_id"] for r in vomiting["components"]], ["F|nausea", "F|vomiting"])
        acute = self.kb.presentation("dyspnea_acute")
        self.assertEqual(acute["components"][0]["onset"], "acute")
        self.assertEqual(acute["components"][0]["node_id"], "F|dyspnea")
        chest = self.kb.presentation("chest_pain")["components"][0]
        self.assertEqual(chest["body_site"], "chest")
        self.assertEqual(chest["normalized_ko"], "가슴통증")
        prenatal = self.kb.presentation("prenatal_care")["components"][0]
        self.assertEqual(prenatal["concept_kind"], "care_context")
        self.assertEqual(prenatal["context"], "pregnancy_prenatal_care")

    def test_textbook_mechanisms_and_exam_actions_are_reachable(self):
        self.assertIn("M|cardiomyocyte_necrosis", self.kb._reach_ids("D|I21"))
        self.assertIn("F|rales", self.kb.findings_of("J848"))
        self.assertIn("H|HP:0032546", self.kb.findings_of("K658"))
        exam_ids = {item["id"] for item in self.kb.exams_for_disease("K658")}
        self.assertIn("abdominal_palpation", exam_ids)

    def test_overlay_edges_keep_schema_context(self):
        scoped = self.kb.findings_of("I21")
        global_walk = self.kb.findings_of("I21", schema_scoped=False)
        self.assertNotIn("F|edema", scoped)
        self.assertIn("F|edema", global_walk)

    def test_evidence_is_auditable(self):
        evidence = self.kb.table("cpx_evidence")
        self.assertGreaterEqual(len(evidence), 15)
        self.assertTrue(all(row["source_url"].startswith("https://www.ncbi.nlm.nih.gov/books/") for row in evidence))
        self.assertTrue(all("clinician_pending" in row["review_status"] for row in evidence))

    def test_build_is_deterministic(self):
        version_file = json.loads((self.output / "version.json").read_text(encoding="utf-8"))
        self.assertEqual(version_file, self.version)


if __name__ == "__main__":
    unittest.main()
