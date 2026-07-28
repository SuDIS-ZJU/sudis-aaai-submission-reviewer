import json
import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "sudis-aaai-submission-reviewer"


class StructureTests(unittest.TestCase):
    def test_skill_is_standalone_and_under_limit(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: sudis-aaai-submission-reviewer\n"))
        self.assertLessEqual(len(text.splitlines()), 500)
        self.assertNotIn("pre-submission-reviewer", text)
        self.assertNotIn("research-paper-writing", text)
        self.assertIn("## Reviewer mode", text)
        self.assertIn("## Quick workflow", text)
        self.assertIn("## Release workflow", text)
        self.assertIn("Never changes Gates", text)

    def test_references_and_scripts_exist(self):
        for name in ("aaai27-main-rules.md", "gates-and-approval.md", "writing-and-visual-review.md", "reviewer-mode.md"):
            self.assertTrue((SKILL / "references" / name).exists())
        for name in ("audit.py", "citations.py", "gate_tool.py", "bootstrap.py"):
            self.assertTrue((SKILL / "scripts" / name).exists())

    def test_installer_and_evals_are_present(self):
        self.assertTrue((ROOT / "scripts" / "install.sh").stat().st_mode & stat.S_IXUSR)
        data = json.loads((ROOT / "evals" / "evals.json").read_text())
        self.assertGreaterEqual(len(data["evals"]), 14)
        ids = {item["id"] for item in data["evals"]}
        self.assertTrue({"reviewer-score", "quick-default", "identity-h", "citation-unverified", "mixed-mode"}.issubset(ids))
        for name in ("REVIEW_REPORT.template.md", "DEFENSE_BOARD.template.md"):
            self.assertTrue((SKILL / "assets" / name).exists())


if __name__ == "__main__":
    unittest.main()
