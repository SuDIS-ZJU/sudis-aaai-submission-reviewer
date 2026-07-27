import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "sudis-aaai-submission-reviewer" / "scripts" / "audit.py"
GATE_TOOL = ROOT / "sudis-aaai-submission-reviewer" / "scripts" / "gate_tool.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuditTests(unittest.TestCase):
    def test_detects_required_source_violations(self):
        module = load_module()
        findings = []
        source = r"""
        \usepackage[submission]{aaai2027}
        \setcounter{secnumdepth}{0}
        \usepackage{hyperref}
        \resizebox{\columnwidth}{!}{x}
        \begin{table}\caption{x}\begin{tabular}{c}x\end{tabular}\end{table}
        """
        module.source_checks(source, findings)
        rules = {item["rule"] for item in findings}
        self.assertIn("SuDIS numbered sections", rules)
        self.assertIn("Forbidden package", rules)
        self.assertIn("Forbidden command", rules)
        self.assertIn("Caption placement", rules)

    def test_audit_creates_gate_evidence_without_editing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "paper"
            project.mkdir()
            main = project / "main.tex"
            original = "\\usepackage[submission]{aaai2027}\n\\setcounter{secnumdepth}{2}\n"
            main.write_text(original)
            output = Path(tmp) / "audit"
            subprocess.run(["python3", str(SCRIPT), "--input", str(project), "--no-compile", "--identity-term", "Example University", "--output", str(output)], check=True)
            self.assertEqual(main.read_text(), original)
            self.assertTrue((output / "AUDIT_REPORT.md").exists())
            state = json.loads((output / "GATE_STATE.json").read_text())
            self.assertEqual(state["gates"]["G1"]["status"], "BLOCKED")
            self.assertEqual(state["gates"]["G5"]["status"], "BLOCKED")

    def test_active_source_ignores_unincluded_drafts_and_binds_supplement(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "paper"
            project.mkdir()
            (project / "main.tex").write_text("\\usepackage[submission]{aaai2027}\n\\setcounter{secnumdepth}{2}\n\\input{sections/live}\n")
            (project / "draft.tex").write_text("\\resizebox{a}{b}{c}\n")
            sections = project / "sections"
            sections.mkdir()
            (sections / "live.tex").write_text("Live text.\n")
            supplement = Path(tmp) / "supplement.zip"
            supplement.write_bytes(b"supplement")
            checklist = Path(tmp) / "checklist.pdf"
            checklist.write_bytes(b"checklist")
            output = Path(tmp) / "audit"
            subprocess.run(["python3", str(SCRIPT), "--input", str(project), "--no-compile", "--identity-term", "Example University", "--supplement", str(supplement), "--checklist", str(checklist), "--output", str(output)], check=True)
            findings = json.loads((output / "FINDINGS.json").read_text())
            self.assertFalse(any(item["rule"] == "Forbidden command" for item in findings))
            state = json.loads((output / "GATE_STATE.json").read_text())
            self.assertIn(str(supplement.resolve()), state["manifest"])
            self.assertIn(str(checklist.resolve()), state["manifest"])

    def test_approval_requires_all_pass_and_unchanged_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit"
            audit.mkdir()
            tracked = Path(tmp) / "paper.pdf"
            tracked.write_bytes(b"paper")
            import hashlib
            manifest = {str(tracked.resolve()): hashlib.sha256(b"paper").hexdigest()}
            state = {"gates": {f"G{i}": {"status": "PASS", "reason": "ok"} for i in range(8)}, "manifest": manifest, "approval": None}
            (audit / "GATE_STATE.json").write_text(json.dumps(state))
            subprocess.run(["python3", str(GATE_TOOL), "approve", "--audit-dir", str(audit), "--approver", "Advisor", "--confirmation", "approved"], check=True)
            self.assertTrue((audit / "FINAL_APPROVAL.md").exists())
            tracked.write_bytes(b"changed")
            verify = subprocess.run(["python3", str(GATE_TOOL), "verify", "--audit-dir", str(audit)], check=False)
            self.assertNotEqual(verify.returncode, 0)


if __name__ == "__main__":
    unittest.main()
