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

    def test_references_and_scripts_exist(self):
        for name in ("aaai27-main-rules.md", "gates-and-approval.md", "writing-and-visual-review.md"):
            self.assertTrue((SKILL / "references" / name).exists())
        for name in ("audit.py", "gate_tool.py", "bootstrap.py"):
            self.assertTrue((SKILL / "scripts" / name).exists())

    def test_installer_and_evals_are_present(self):
        self.assertTrue((ROOT / "scripts" / "install.sh").stat().st_mode & stat.S_IXUSR)
        data = json.loads((ROOT / "evals" / "evals.json").read_text())
        self.assertGreaterEqual(len(data["evals"]), 8)


if __name__ == "__main__":
    unittest.main()
