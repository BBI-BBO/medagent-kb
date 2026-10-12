import os
import unittest

from kb import KB


class SchemaScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KB(
            version=os.environ.get("MEDAGENT_KB_VERSION", "kb-2026.10.08.2"),
            cache=os.path.expanduser(os.environ.get("MEDAGENT_KB_CACHE", "~/.cache/medagent-kb")),
        )

    def test_scoped_findings_are_subset(self):
        for disease in ("K37", "J45", "E14", "J189"):
            scoped = self.kb.findings_of(disease)
            legacy = self.kb.findings_of(disease, schema_scoped=False)
            self.assertLessEqual(scoped, legacy)

    def test_appendicitis_does_not_cross_infection_hub_to_edema(self):
        scoped = self.kb.findings_of("K37")
        legacy = self.kb.findings_of("K37", schema_scoped=False)
        self.assertNotIn("F|edema", scoped)
        self.assertIn("F|edema", legacy)

    def test_direct_findings_are_preserved(self):
        direct = {
            edge["o"]
            for edge in self.kb.GO["D|J45"]
            if edge["p"] == "has_phenotype" and edge["o"][0] in "FH"
        }
        self.assertLessEqual(direct, self.kb.findings_of("J45"))


if __name__ == "__main__":
    unittest.main()
