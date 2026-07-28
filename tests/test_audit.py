import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "sudis-aaai-submission-reviewer" / "scripts" / "audit.py"
CITATIONS = ROOT / "sudis-aaai-submission-reviewer" / "scripts" / "citations.py"
GATE_TOOL = ROOT / "sudis-aaai-submission-reviewer" / "scripts" / "gate_tool.py"
INSTALLER = ROOT / "scripts" / "install.sh"
RUN_ROOT = Path(tempfile.mkdtemp(prefix="sudis-aaai-tests-"))


def load_module():
    spec = importlib.util.spec_from_file_location("audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_citations():
    spec = importlib.util.spec_from_file_location("citations_under_test", CITATIONS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_directory(name: str) -> Path:
    path = RUN_ROOT / name
    path.mkdir(parents=True, exist_ok=False)
    return path


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
        root = case_directory("release-evidence")
        project = root / "paper"
        project.mkdir()
        main = project / "main.tex"
        original = "\\usepackage[submission]{aaai2027}\n\\setcounter{secnumdepth}{2}\n"
        main.write_text(original)
        output = root / "audit"
        subprocess.run(["python3", str(SCRIPT), "--mode", "release", "--input", str(project), "--no-compile", "--identity-term", "Example University", "--output", str(output)], check=True)
        self.assertEqual(main.read_text(), original)
        self.assertTrue((output / "AUDIT_REPORT.md").exists())
        self.assertTrue((output / "CITATION_AUDIT.json").exists())
        state = json.loads((output / "GATE_STATE.json").read_text())
        self.assertEqual(state["gates"]["G1"]["status"], "BLOCKED")
        self.assertEqual(state["gates"]["G5"]["status"], "BLOCKED")
        self.assertEqual(state["schema_version"], "1.1")

    def test_quick_is_default_and_never_creates_gate_state(self):
        root = case_directory("quick-default")
        project = root / "paper"
        project.mkdir()
        (project / "main.tex").write_text("\\usepackage[submission]{aaai2027}\n\\setcounter{secnumdepth}{2}\n")
        output = root / "quick"
        subprocess.run(["python3", str(SCRIPT), "--input", str(project), "--output", str(output)], check=True)
        report = (output / "QUICK_REPORT.md").read_text()
        self.assertTrue((output / "FINDINGS.json").exists())
        self.assertFalse((output / "GATE_STATE.json").exists())
        self.assertFalse((output / "APPROVAL_PACKET.md").exists())
        self.assertLessEqual(report.count("\n### "), 5)

    def test_active_source_ignores_unincluded_drafts_and_binds_supplement(self):
        root = case_directory("active-source")
        project = root / "paper"
        project.mkdir()
        (project / "main.tex").write_text("\\usepackage[submission]{aaai2027}\n\\setcounter{secnumdepth}{2}\n\\input{sections/live}\n")
        (project / "draft.tex").write_text("\\resizebox{a}{b}{c}\n")
        sections = project / "sections"
        sections.mkdir()
        (sections / "live.tex").write_text("Live text.\n")
        supplement = root / "supplement.zip"
        supplement.write_bytes(b"supplement")
        checklist = root / "checklist.pdf"
        checklist.write_bytes(b"checklist")
        output = root / "audit"
        subprocess.run(["python3", str(SCRIPT), "--mode", "release", "--input", str(project), "--no-compile", "--identity-term", "Example University", "--supplement", str(supplement), "--checklist", str(checklist), "--output", str(output)], check=True)
        findings = json.loads((output / "FINDINGS.json").read_text())
        self.assertFalse(any(item["rule"] == "Forbidden command" for item in findings))
        state = json.loads((output / "GATE_STATE.json").read_text())
        self.assertIn(str(supplement.resolve()), state["manifest"])
        self.assertIn(str(checklist.resolve()), state["manifest"])

    def test_font_policy_blocks_only_confirmed_hard_errors(self):
        module = load_module()
        output = """name                                 type              encoding         emb sub uni object ID
------------------------------------ ----------------- ---------------- --- --- --- ---------
AAA                                  Type 3            Custom           yes no  no       1  0
BBB                                  TrueType          WinAnsi          no  no  yes      2  0
CCC                                  CID TrueType      Identity-H       yes yes yes      3  0
DDD                                  Type 1            WinAnsi          yes yes yes      4  0
"""
        findings = []
        module.check_font_rows(module.parse_pdffonts(output), findings)
        by_rule = {item["rule"]: item for item in findings}
        self.assertEqual(by_rule["Type 3 font"]["gate_effect"], "FAIL")
        self.assertEqual(by_rule["Unembedded font"]["gate_effect"], "FAIL")
        self.assertEqual(by_rule["Identity-H manual confirmation"]["gate_effect"], "BLOCK")
        self.assertEqual(len(findings), 3)

    def test_approval_requires_all_pass_and_unchanged_manifest(self):
        root = case_directory("approval")
        audit = root / "audit"
        audit.mkdir()
        tracked = root / "paper.pdf"
        tracked.write_bytes(b"paper")
        import hashlib
        manifest = {str(tracked.resolve()): hashlib.sha256(b"paper").hexdigest()}
        state = {"gates": {f"G{i}": {"status": "PASS", "reason": "ok"} for i in range(8)}, "manifest": manifest, "approval": None}
        (audit / "GATE_STATE.json").write_text(json.dumps(state))
        subprocess.run(["python3", str(GATE_TOOL), "approve", "--audit-dir", str(audit), "--approver", "Advisor", "--confirmation", "approved"], check=True)
        self.assertTrue((audit / "FINAL_APPROVAL.md").exists())
        self.assertTrue(any((audit / "history").rglob("GATE_STATE.json")))
        shutil.copy2(tracked, root / "paper.before-change.pdf")
        tracked.write_bytes(b"changed")
        verify = subprocess.run(["python3", str(GATE_TOOL), "verify", "--audit-dir", str(audit)], check=False)
        self.assertNotEqual(verify.returncode, 0)

    def test_visual_gate_requires_structured_evidence(self):
        root = case_directory("visual-gate")
        audit = root / "audit"
        audit.mkdir()
        state = {"gates": {f"G{i}": {"status": "BLOCKED", "reason": "pending"} for i in range(8)}, "manifest": {}, "approval": None}
        (audit / "GATE_STATE.json").write_text(json.dumps(state))
        missing = subprocess.run(["python3", str(GATE_TOOL), "set-gate", "--audit-dir", str(audit), "--gate", "G5", "--status", "PASS", "--evidence", "reviewed"], check=False)
        self.assertNotEqual(missing.returncode, 0)
        evidence = audit / "g5.json"
        evidence.write_text(json.dumps({"reviewer": "Reviewer", "reviewed_at": "2026-07-27", "items": [{"id": "page-01", "status": "pass", "evidence": "readable"}]}))
        subprocess.run(["python3", str(GATE_TOOL), "set-gate", "--audit-dir", str(audit), "--gate", "G5", "--status", "PASS", "--evidence", "reviewed", "--evidence-file", str(evidence)], check=True)
        saved = json.loads((audit / "GATE_STATE.json").read_text())
        self.assertIn("evidence_sha256", saved["gates"]["G5"])
        self.assertTrue(any((audit / "history").rglob("GATE_STATE.json")))

    def test_locked_deterministic_failure_cannot_be_manually_passed(self):
        root = case_directory("locked-failure")
        audit = root / "audit"
        audit.mkdir()
        gates = {f"G{i}": {"status": "PASS", "reason": "ok"} for i in range(8)}
        gates["G2"] = {"status": "FAIL", "reason": "Type 3 font", "locked": True}
        (audit / "GATE_STATE.json").write_text(json.dumps({"gates": gates, "manifest": {}, "approval": None}))
        result = subprocess.run(["python3", str(GATE_TOOL), "set-gate", "--audit-dir", str(audit), "--gate", "G2", "--status", "PASS", "--evidence", "ignore"], check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_citation_structural_checks(self):
        module = load_citations()
        root = case_directory("citation-structural")
        bib = root / "refs.bib"
        bib.write_text(
            "@article{good, title={A Real Paper}, author={Smith, Jane}, year={2020}, doi={10.1000/real}}\n"
            "@article{duplicate, title={A Real Paper}, author={Smith, Jane}, year={2020}, doi={10.1000/real}}\n"
        )
        audit = module.offline_audit("\\cite{good,duplicate,missing}", [bib])
        checks = {item["check"] for item in audit["items"]}
        self.assertIn("missing-key", checks)
        self.assertIn("duplicate-doi", checks)
        self.assertIn("duplicate-title", checks)
        effects = {item["check"]: item["gate_effect"] for item in audit["items"]}
        self.assertEqual(effects["missing-key"], "FAIL")
        self.assertEqual(effects["duplicate-doi"], "BLOCK")
        self.assertEqual(effects["duplicate-title"], "BLOCK")

    def test_only_declared_bibliography_is_checked(self):
        module = load_module()
        root = case_directory("active-bibliography")
        main = root / "main.tex"
        active = root / "active.bib"
        inactive = root / "archived.bib"
        main.write_text("\\bibliography{active}\n")
        active.write_text("@article{used, title={Used}, author={Smith}, year={2020}}\n")
        inactive.write_text("@article{used, title={Archived Duplicate}, author={Other}, year={2019}}\n")
        selected = module.active_bibliography_paths(main.read_text(), main, [active, inactive])
        self.assertEqual(selected, [active.resolve()])

    def test_citation_online_verified_mismatch_and_unavailable(self):
        module = load_citations()
        structural = {
            "cited_keys": ["verified", "mismatch", "offline"],
            "entries": {
                "verified": {"key": "verified", "title": "A Real Paper", "author": "Smith, Jane", "year": "2020", "doi": "10.1000/verified"},
                "mismatch": {"key": "mismatch", "title": "Expected Title", "author": "Lee, Kai", "year": "2021", "doi": "10.1000/mismatch"},
                "offline": {"key": "offline", "title": "Older Unindexed Work", "author": "Doe, Pat", "year": "1950"},
            },
            "items": [],
        }

        def request(url, accept):
            if "verified" in url:
                return json.dumps({"message": {"title": ["A Real Paper"], "author": [{"family": "Smith"}], "issued": {"date-parts": [[2020]]}}}).encode()
            if "mismatch" in url:
                return json.dumps({"message": {"title": ["Different Work"], "author": [{"family": "Other"}], "issued": {"date-parts": [[2010]]}}}).encode()
            raise urllib.error.URLError("offline")

        result = module.full_audit(structural, request_fn=request, delay_seconds=0)
        status = {(item["key"], item["check"]): item["status"] for item in result["items"]}
        self.assertEqual(status[("verified", "online-metadata")], "VERIFIED")
        self.assertEqual(status[("mismatch", "online-metadata")], "MISMATCH")
        self.assertEqual(status[("offline", "online-metadata")], "UNVERIFIED")

    def test_partial_identifier_metadata_difference_is_unverified(self):
        module = load_citations()
        entry = {"title": "A Real Paper Extended", "author": "Smith, Jane", "year": "2020"}
        status, _ = module._metadata_match(entry, "A Real Paper", "2020", "Smith")
        self.assertEqual(status, "UNVERIFIED")

    def test_citation_request_retries_transient_network_failure(self):
        module = load_citations()
        attempts = {"count": 0}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b"ok"

        def flaky(request, timeout):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise urllib.error.URLError("transient")
            return Response()

        with mock.patch.object(module.urllib.request, "urlopen", side_effect=flaky), mock.patch.object(module.time, "sleep"):
            self.assertEqual(module._request("https://example.test", "application/json"), b"ok")
        self.assertEqual(attempts["count"], 2)

    def test_runtime_has_no_automatic_delete_operations(self):
        checked = [SCRIPT, CITATIONS, GATE_TOOL, ROOT / "scripts" / "install.sh"]
        text = "\n".join(path.read_text() for path in checked)
        for forbidden in ("TemporaryDirectory", "shutil.rmtree", ".unlink(", "ln -sfn", "\nrm "):
            self.assertNotIn(forbidden, text)

    def test_installer_refuses_wrong_symlink_without_replacing_it(self):
        root = case_directory("installer-wrong-link")
        target = root / ".agents" / "skills" / "sudis-aaai-submission-reviewer"
        target.parent.mkdir(parents=True)
        target.symlink_to("/tmp/not-the-skill")
        environment = {**os.environ, "HOME": str(root), "SUDIS_SKILLS_DIR": str(root / ".agents" / "skills")}
        result = subprocess.run(["bash", str(INSTALLER)], env=environment, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(target.is_symlink())
        self.assertEqual(os.readlink(target), "/tmp/not-the-skill")


if __name__ == "__main__":
    unittest.main()
