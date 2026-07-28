#!/usr/bin/env python3
"""Read-only AAAI-27 Main Track audit and gate evidence generator."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from citations import full_audit, offline_audit

PROFILE = {
    "venue": "AAAI-27 Main Technical Track",
    "verified_on": "2026-07-28",
    "sources": [
        "https://aaai.org/conference/aaai/aaai-27/submission-instructions/",
        "https://aaai.org/conference/aaai/aaai-27/supplementary-material/",
        "https://aaai.org/authorkit27/",
    ],
}
EXCLUDED_PARTS = {".git", ".venv", "review", "build", "out", "node_modules"}
FORBIDDEN_PACKAGES = {"hyperref", "navigator", "geometry", "fullpage", "titlesec", "pgfplots", "float", "balance", "flushend", "savetrees", "multicol"}
FORBIDDEN_COMMANDS = {
    "resizebox": "Resize tables by content, column spacing, spanning, or splitting instead.",
    "tiny": "Use permitted 9pt table text only when necessary; never use \\tiny.",
    "newpage": "Let references and floats flow naturally.",
    "clearpage": "Let references and floats flow naturally.",
    "pagebreak": "Let references and floats flow naturally.",
    "pagestyle": "AAAI submissions must not print page numbers, headers, or footers.",
}
HYPE_TERMS = ["innovative", "revolutionary", "transformative", "superior", "remarkable", "unprecedented", "state-of-the-art", "state of the art", "comprehensive", "extensive", "pave the way", "underscore", "notably", "yielding"]
OVERCLAIM = [r"\bwe solve\b", r"\bthe first\b", r"\bfirst to\b", r"\boutperforms all\b", r"\bsota\b"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uncomment(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def find_files(root: Path, suffix: str) -> list[Path]:
    return sorted(path for path in root.rglob(f"*{suffix}") if not any(part in EXCLUDED_PARTS for part in path.parts))


def find_input(path: Path, main_name: str | None) -> tuple[Path | None, Path | None, list[Path]]:
    if path.is_file() and path.suffix.lower() == ".pdf":
        return None, path, [path]
    if not path.is_dir():
        raise FileNotFoundError(path)
    tex = path / main_name if main_name else path / "main.tex"
    if not tex.exists():
        candidates = find_files(path, ".tex")
        tex = candidates[0] if candidates else None
    pdf = tex.with_suffix(".pdf") if tex else path / "main.pdf"
    if not pdf.exists():
        root_pdfs = sorted(candidate for candidate in path.glob("*.pdf") if candidate.is_file())
        pdf = root_pdfs[0] if len(root_pdfs) == 1 else None
    tracked = find_files(path, ".tex") + find_files(path, ".bib")
    if pdf:
        tracked.append(pdf)
    return tex, pdf, tracked


def drop_false_blocks(text: str) -> str:
    """Handle the common template-only \\iffalse ... \\fi construct conservatively."""
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\\iffalse.*?\\fi", "", text, flags=re.S)
    return text


def active_source(main_tex: Path | None) -> tuple[str, list[Path]]:
    """Follow active \\input and \\include paths from the chosen root, once each."""
    if not main_tex:
        return "", []
    visited: set[Path] = set()
    parts: list[str] = []

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in visited or not path.exists() or path.suffix != ".tex":
            return
        visited.add(path)
        text = drop_false_blocks(uncomment(path.read_text(encoding="utf-8", errors="replace")))
        parts.append(f"\n% FILE: {path}\n{text}")
        for target in re.findall(r"\\(?:input|include)\{([^}]+)\}", text):
            candidate = path.parent / target
            if not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            visit(candidate)

    visit(main_tex)
    return "\n".join(parts), sorted(visited)


def active_bibliography_paths(source: str, main_tex: Path | None, tracked: list[Path]) -> list[Path]:
    declarations: list[str] = []
    declarations.extend(re.findall(r"\\bibliography\{([^}]+)\}", source))
    declarations.extend(re.findall(r"\\addbibresource(?:\[[^]]*\])?\{([^}]+)\}", source))
    names = [name.strip() for group in declarations for name in group.split(",") if name.strip()]
    if not names:
        return sorted(path for path in tracked if path.suffix.lower() == ".bib")
    indexed: dict[str, list[Path]] = {}
    for path in tracked:
        if path.suffix.lower() == ".bib":
            indexed.setdefault(path.name, []).append(path)
    selected: list[Path] = []
    for name in names:
        candidate_name = Path(name).name
        if not candidate_name.lower().endswith(".bib"):
            candidate_name += ".bib"
        direct = main_tex.parent / (name if name.lower().endswith(".bib") else name + ".bib") if main_tex else None
        if direct and direct.exists():
            selected.append(direct)
        else:
            selected.extend(indexed.get(candidate_name, []))
    return sorted(dict.fromkeys(path.resolve() for path in selected))


def add(
    findings: list[dict],
    gate: str,
    severity: str,
    rule: str,
    evidence: str,
    fix: str,
    source: str = "official",
    gate_effect: str | None = None,
) -> None:
    if gate_effect is None:
        gate_effect = "BLOCK" if severity == "BLOCKED" else "FAIL" if severity in {"CRITICAL", "MAJOR"} else "NONE"
    findings.append(
        {
            "gate": gate,
            "severity": severity,
            "source": source,
            "rule": rule,
            "evidence": evidence[:800],
            "minimum_fix": fix,
            "gate_effect": gate_effect,
        }
    )


def source_checks(source: str, findings: list[dict]) -> None:
    if not source:
        return
    if not re.search(r"\\usepackage\[submission\]\{aaai2027\}", source):
        add(findings, "G1", "CRITICAL", "AAAI style mode", "Missing `\\usepackage[submission]{aaai2027}`.", "Use the current Author Kit submission mode.")
    depth = re.search(r"\\setcounter\{secnumdepth\}\{(\d+)\}", source)
    if not depth or depth.group(1) not in {"1", "2"}:
        add(findings, "G2", "CRITICAL", "SuDIS numbered sections", "`secnumdepth` is absent or not 1/2.", "Set `\\setcounter{secnumdepth}{2}` in the preamble.", "lab-rule")
    for package in sorted(FORBIDDEN_PACKAGES):
        if re.search(r"\\usepackage(?:\[[^]]*\])?\{" + re.escape(package) + r"\}", source):
            add(findings, "G1", "CRITICAL", "Forbidden package", f"Found `\\usepackage{{{package}}}`.", "Remove the package and use the Author Kit-compatible alternative.")
    for command, fix in FORBIDDEN_COMMANDS.items():
        if re.search(r"\\" + command + r"\b", source):
            add(findings, "G1", "CRITICAL", "Forbidden command", f"Found `\\{command}` in active source.", fix)
    if re.search(r"\\(?:vspace|vskip)\s*\{\s*-", source):
        add(findings, "G1", "CRITICAL", "Negative spacing", "Found negative `\\vspace` or `\\vskip`.", "Remove negative spacing; reduce content instead.")
    if re.search(r"\\includegraphics\s*\[[^]]*(?:trim|clip)", source):
        add(findings, "G1", "CRITICAL", "Fragile figure crop", "Found `trim` or `clip` in `\\includegraphics`.", "Crop the asset outside LaTeX and import the cropped file.")
    if re.search(r"\\bibliography\{[^}]+\}.*?\\appendix", source, re.S):
        add(findings, "G4", "CRITICAL", "Separate supplementary document", "The source appends content after bibliography.", "Move technical appendix to a separately uploaded supplementary PDF.")
    for env in ("figure", "figure*", "table", "table*"):
        for block in re.findall(r"\\begin\{" + re.escape(env) + r"\}.*?\\end\{" + re.escape(env) + r"\}", source, re.S):
            caption = block.find("\\caption")
            object_start = min([x for x in (block.find("\\includegraphics"), block.find("\\begin{tabular")) if x >= 0], default=-1)
            if caption >= 0 and object_start >= 0 and caption < object_start:
                add(findings, "G2", "CRITICAL", "Caption placement", f"A `{env}` caption appears before its visual/table object.", "Move the caption below the figure or table.")
    labels = set(re.findall(r"\\label\{([^}]+)\}", source))
    appendix_labels = {label for label in labels if label.startswith(("app:", "appendix:"))}
    for label in sorted(appendix_labels):
        if not re.search(r"\\(?:ref|autoref|cref)\{" + re.escape(label) + r"\}", source):
            add(findings, "G4", "MAJOR", "Explicit appendix reference", f"Appendix label `{label}` lacks a specific main-text Appendix reference.", "Reference it in main text as `Appendix~\\ref{" + label + "}`.", "lab-rule")
    if "—" in source or "---" in source:
        add(findings, "G6", "MAJOR", "No em dash", "Found an em dash or LaTeX triple dash.", "Replace it with a period, comma, colon, or rewritten sentence.", "lab-rule")
    lowered = source.lower()
    for term in HYPE_TERMS:
        if term in lowered:
            add(findings, "G6", "MINOR", "AI-tone vocabulary", f"Found `{term}`.", "Use a neutral evidence-bearing verb or qualify the claim.", "lab-rule")
    for pattern in OVERCLAIM:
        if re.search(pattern, lowered):
            add(
                findings,
                "G6",
                "MAJOR",
                "Potential overclaim",
                f"Matched `{pattern}`.",
                "Name the benchmark, comparison set, condition, and supporting evidence, or weaken the claim.",
                "lab-rule",
                "BLOCK",
            )
    web_pointer = re.search(
        r"(?:code|data|dataset|project|repository|supplement\w*)[^.\n]{0,100}(?:https?://|www\.)"
        r"|(?:https?://|www\.)[^\s}]*?(?:github|gitlab|huggingface|anonymous)",
        source,
        re.I,
    )
    if re.search(r"\\begin\{links\}|\\link\{(?:Code|Dataset)", source) or web_pointer:
        add(findings, "G3", "CRITICAL", "No web supplementary pointers", "Found a code, data, project, or supplementary web pointer.", "Remove the web pointer; upload the material in the designated supplementary field.")


def parse_pdffonts(output: str) -> list[dict]:
    lines = output.splitlines()
    if len(lines) < 3:
        return []
    header = lines[0]
    names = ("name", "type", "encoding", "emb", "sub", "uni", "object ID")
    positions = [header.find(name) for name in names]
    if any(position < 0 for position in positions):
        return []
    rows: list[dict] = []
    for raw in lines[2:]:
        if not raw.strip():
            continue
        padded = raw + " " * max(0, len(header) - len(raw))
        columns = [
            padded[positions[index]:positions[index + 1]].strip()
            if index + 1 < len(positions)
            else padded[positions[index]:].strip()
            for index in range(len(positions))
        ]
        rows.append(
            {
                "name": columns[0],
                "type": columns[1],
                "encoding": columns[2],
                "embedded": columns[3].lower(),
                "subset": columns[4].lower(),
                "unicode": columns[5].lower(),
                "object_id": columns[6],
                "raw": raw.strip(),
            }
        )
    return rows


def check_font_rows(rows: list[dict], findings: list[dict]) -> None:
    for row in rows:
        if "Type 3" in row["type"]:
            add(findings, "G5", "CRITICAL", "Type 3 font", "pdffonts: " + row["raw"], "Regenerate the affected text or figure using embedded Type 1, TrueType, or OpenType fonts.")
        if row["embedded"] == "no":
            add(findings, "G5", "CRITICAL", "Unembedded font", "pdffonts: " + row["raw"], "Embed the affected font or regenerate the asset with an embedded supported font.")
        if row["encoding"] == "Identity-H":
            add(
                findings,
                "G5",
                "MAJOR",
                "Identity-H manual confirmation",
                "pdffonts: " + row["raw"],
                "Confirm whether this is prohibited non-Roman content or an encoding-only false positive. Record the affected page or figure in G5 evidence.",
                "official-review",
                "BLOCK",
            )


def pdf_checks(
    pdf: Path | None,
    out: Path,
    findings: list[dict],
    identities: list[str],
    release_mode: bool,
) -> dict:
    result = {"pdf": str(pdf) if pdf else None, "pages": None, "rendered": []}
    if not pdf:
        add(findings, "G1", "BLOCKED", "Compiled PDF", "No PDF was supplied or found.", "Compile the current source with PDFLaTeX and rerun.")
        return result
    try:
        from pypdf import PdfReader
    except ImportError:
        add(findings, "G2", "BLOCKED", "PDF inspection dependency", "pypdf is unavailable.", "Run bootstrap.py, then rerun the audit.")
        return result
    reader = PdfReader(str(pdf))
    result["pages"] = len(reader.pages)
    if len(reader.pages) > 9:
        add(findings, "G2", "CRITICAL", "Main-PDF page limit", f"PDF has {len(reader.pages)} pages.", "Keep main content within 7 pages and total main PDF within 9 pages; upload supplement separately.")
    metadata = reader.metadata or {}
    suspicious = [(key, value) for key, value in metadata.items() if value and key == "/Author"]
    if suspicious:
            add(findings, "G3", "MAJOR", "PDF metadata", "PDF metadata present: " + "; ".join(f"{k}={v}" for k, v in suspicious), "Clear identifying metadata with a metadata-cleaning tool.")
    if identities:
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        for term in identities:
            if term and term.lower() in extracted.lower():
                add(findings, "G3", "CRITICAL", "Identity-term leak in PDF", f"Found supplied identity term `{term}` in extracted PDF text.", "Remove or anonymize this term, clear metadata, and regenerate the PDF.")
    annotations = sum(1 for page in reader.pages if page.get("/Annots"))
    if annotations:
        add(findings, "G2", "CRITICAL", "Embedded links or annotations", f"PDF has annotations on {annotations} page(s).", "Remove links, annotations, and bookmarks from source and regenerate PDF.")
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=False).stdout
        if "612 x 792" not in info:
            add(findings, "G2", "CRITICAL", "US Letter", "pdfinfo does not report 612 x 792 points.", "Regenerate using the official US Letter template.")
        version = re.search(r"PDF version:\s*([\d.]+)", info)
        if version and float(version.group(1)) < 1.5:
            add(findings, "G2", "CRITICAL", "PDF version", "PDF version is below 1.5.", "Generate a PDF 1.5 or later file.")
    if shutil.which("pdffonts"):
        font_run = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=False)
        result["fonts"] = parse_pdffonts(font_run.stdout)
        check_font_rows(result["fonts"], findings)
        if font_run.returncode or not result["fonts"]:
            add(findings, "G5", "BLOCKED", "Font inspection result", "`pdffonts` failed or returned no structured font rows.", "Regenerate a text-based PDF and manually confirm all fonts are embedded and non-Type-3.")
    elif release_mode:
        add(findings, "G5", "BLOCKED", "Font inspection tool", "`pdffonts` is unavailable.", "Install Poppler and rerun the release audit.")
    try:
        import fitz
        document = fitz.open(str(pdf))
        screenshots = out / "screenshots"
        screenshots.mkdir(exist_ok=True)
        requested_pages = {0} if not release_mode else {0, min(1, len(document) - 1), min(6, len(document) - 1)}
        for index in sorted(requested_pages):
            page = document[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            target = screenshots / f"page-{index + 1:02d}.png"
            pix.save(str(target))
            result["rendered"].append(str(target.name))
    except (ImportError, RuntimeError):
        add(findings, "G5", "BLOCKED", "Visual rendering", "PyMuPDF is unavailable or could not render the PDF.", "Run bootstrap.py and manually inspect rendered PDF pages.")
    return result


def pdf_text_fingerprint(path: Path) -> str | None:
    try:
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()
    except Exception:
        return None


def compile_check(
    project: Path,
    main_tex: Path | None,
    submitted_pdf: Path | None,
    build_root: Path,
    findings: list[dict],
) -> bool:
    """Compile an isolated copy so a passing G1 proves the source is buildable."""
    if not main_tex:
        return False
    executable = shutil.which("latexmk")
    if not executable:
        add(findings, "G1", "BLOCKED", "Isolated source compilation", "latexmk is unavailable.", "Install a PDFLaTeX/latexmk environment and rerun the audit.")
        return False
    build_root.mkdir(parents=True, exist_ok=False)
    copied = build_root / "paper"
    ignore_names = {
        ".git",
        ".venv",
        "review",
        "build",
        "out",
        "*.aux",
        "*.log",
        "*.bbl",
        "*.blg",
        "*.fls",
        "*.fdb_latexmk",
    }
    try:
        output_relative = build_root.resolve().relative_to(project.resolve())
    except ValueError:
        output_relative = None
    if output_relative and output_relative.parts:
        ignore_names.add(output_relative.parts[0])
    shutil.copytree(project, copied, ignore=shutil.ignore_patterns(*sorted(ignore_names)))
    relative_main = main_tex.resolve().relative_to(project.resolve())
    run = subprocess.run([executable, "-pdf", "-interaction=nonstopmode", "-halt-on-error", str(relative_main)], cwd=copied, capture_output=True, text=True, check=False)
    log_path = build_root / "latexmk-output.log"
    log_path.write_text(run.stdout + "\n" + run.stderr, encoding="utf-8")
    if run.returncode:
        tail = (run.stdout + "\n" + run.stderr)[-1200:]
        add(findings, "G1", "CRITICAL", "Isolated source compilation", "latexmk failed in the preserved isolated copy: " + tail, "Fix the first LaTeX error and rerun until the isolated build succeeds.")
        return False
    compiled_pdf = (copied / relative_main).with_suffix(".pdf")
    if submitted_pdf and compiled_pdf.exists():
        submitted_fingerprint = pdf_text_fingerprint(submitted_pdf)
        compiled_fingerprint = pdf_text_fingerprint(compiled_pdf)
        if not submitted_fingerprint or not compiled_fingerprint:
            add(findings, "G1", "BLOCKED", "Source/PDF fingerprint", "Could not extract comparable text fingerprints from both PDFs.", "Install pypdf and rerun the audit.")
            return False
        if submitted_fingerprint != compiled_fingerprint:
            add(findings, "G1", "CRITICAL", "Source/PDF fingerprint", "The supplied PDF text does not match the preserved isolated build from current source.", "Upload the PDF produced from the audited source, then rerun all gates.")
            return False
    return True


def gate_statuses(findings: list[dict], tex: Path | None, pdf: Path | None, identities: list[str], checklist: Path | None, compiled: bool) -> dict:
    gates = {f"G{i}": {"status": "PASS", "reason": "Deterministic checks passed.", "locked": False} for i in range(8)}
    gates["G5"] = {"status": "BLOCKED", "reason": "Manual teaser and visual-quality review is required."}
    gates["G6"] = {"status": "BLOCKED", "reason": "Manual claim-evidence and adversarial review is required."}
    gates["G4"] = {"status": "BLOCKED", "reason": "Manual reproducibility-checklist and supplementary-material review is required."}
    if not tex:
        gates["G1"] = {"status": "BLOCKED", "reason": "PDF-only input cannot pass source-integrity checks."}
    elif not compiled:
        gates["G1"] = {"status": "BLOCKED", "reason": "Current source was not successfully compiled in isolation."}
    if not pdf:
        gates["G2"] = {"status": "BLOCKED", "reason": "No compiled PDF is available."}
    if not identities:
        gates["G3"] = {"status": "BLOCKED", "reason": "No identity terms supplied for strict anonymity review."}
    if not checklist:
        gates["G4"] = {"status": "BLOCKED", "reason": "No reproducibility checklist was supplied or discovered."}
    for finding in findings:
        gate = finding["gate"]
        effect = finding.get("gate_effect", "NONE")
        if effect == "FAIL":
            gates[gate] = {"status": "FAIL", "reason": finding["rule"], "locked": True}
        elif effect == "BLOCK" and gates[gate]["status"] != "FAIL":
            gates[gate] = {"status": "BLOCKED", "reason": finding["rule"], "locked": False}
    return gates


def finding_label(finding: dict) -> str:
    return "MUST FIX" if finding["gate_effect"] == "FAIL" else "CONFIRM" if finding["gate_effect"] == "BLOCK" else "IMPROVE"


def finding_priority(finding: dict) -> tuple[int, int, str]:
    effect_rank = {"FAIL": 0, "BLOCK": 1, "NONE": 2}
    severity_rank = {"CRITICAL": 0, "BLOCKED": 1, "MAJOR": 2, "MINOR": 3}
    return effect_rank.get(finding["gate_effect"], 3), severity_rank.get(finding["severity"], 4), finding["rule"]


def citation_findings(audit: dict, findings: list[dict]) -> None:
    for item in audit["items"]:
        effect = item["gate_effect"]
        severity = "CRITICAL" if effect == "FAIL" else "BLOCKED" if effect == "BLOCK" else "MINOR"
        fix = (
            "Correct the BibTeX record or citation key, then rerun the audit."
            if effect == "FAIL"
            else "Verify this record against a publisher page, DOI landing page, or arXiv record and document the evidence in G6."
            if effect == "BLOCK"
            else "No action is required unless the record changed."
        )
        add(findings, "G6", severity, "Citation " + item["check"], f"{item['key']}: {item['evidence']}", fix, "citation-check", effect)


def write_quick_report(out: Path, findings: list[dict]) -> None:
    ordered = sorted(findings, key=finding_priority)
    top = ordered[:5]
    counts = {label: sum(finding_label(finding) == label for finding in findings) for label in ("MUST FIX", "CONFIRM", "IMPROVE")}
    lines = [
        "# AAAI-27 Quick Check",
        "",
        "This is a fast iteration report, not a submission approval or complete Gate audit.",
        "",
        "## Summary",
        "",
        f"- MUST FIX: {counts['MUST FIX']}",
        f"- CONFIRM: {counts['CONFIRM']}",
        f"- IMPROVE: {counts['IMPROVE']}",
        "",
        "## Next five actions",
        "",
    ]
    if not top:
        lines.append("No deterministic issue was found. Run `--mode release` before advisor review.")
    for index, finding in enumerate(top, 1):
        lines += [
            f"### {index}. [{finding_label(finding)}] {finding['rule']}",
            "",
            f"- Evidence: {finding['evidence']}",
            f"- Minimum fix: {finding['minimum_fix']}",
            "",
        ]
    if len(ordered) > len(top):
        lines += [f"{len(ordered) - len(top)} additional lower-priority findings remain in `FINDINGS.json`.", ""]
    lines += ["## Next step", "", "Iterate on the items above. Use `--mode release` only for the final submission package."]
    (out / "QUICK_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "FINDINGS.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_release_report(out: Path, findings: list[dict], gates: dict, manifest: dict, pdf_result: dict, citation_audit: dict) -> None:
    counts = {label: sum(finding_label(finding) == label for finding in findings) for label in ("MUST FIX", "CONFIRM", "IMPROVE")}
    lines = ["# AAAI-27 Release Audit", "", "## Gate status", ""]
    for gate, data in gates.items():
        lines.append(f"- {gate}: **{data['status']}**: {data['reason']}")
    lines += ["", "## Findings", "", f"- MUST FIX: {counts['MUST FIX']}", f"- CONFIRM: {counts['CONFIRM']}", f"- IMPROVE: {counts['IMPROVE']}", ""]
    for index, finding in enumerate(sorted(findings, key=finding_priority), 1):
        lines += [f"### {index}. [{finding_label(finding)}] {finding['rule']}", "", f"- Gate: {finding['gate']} ({finding['source']})", f"- Evidence: {finding['evidence']}", f"- Minimum fix: {finding['minimum_fix']}", ""]
    lines += ["## Manual review required", "", "- G5: inspect teaser, rendered pages, Identity-H warnings, visual readability, captions, and raster use.", "- G6: reconcile claims and all UNVERIFIED citations against authoritative evidence.", "", "## Approval state", "", "Do not submit. `AWAITING ADVISOR APPROVAL` is available only after G0--G7 are PASS."]
    (out / "AUDIT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "RULES_SNAPSHOT.md").write_text("# Rules snapshot\n\n" + "\n".join(f"- {url}" for url in PROFILE["sources"]) + f"\n\nVerified baseline: {PROFILE['verified_on']}\n", encoding="utf-8")
    (out / "FINDINGS.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "CITATION_AUDIT.json").write_text(json.dumps(citation_audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    unresolved = sorted({item["key"] for item in citation_audit["items"] if item["status"] == "UNVERIFIED"})
    citation_state = {
        "unresolved_keys": unresolved,
        "mismatch_keys": sorted({item["key"] for item in citation_audit["items"] if item["status"] == "MISMATCH"}),
        "summary": citation_audit["summary"],
    }
    state = {"schema_version": "1.1", "gates": gates, "profile": PROFILE, "manifest": manifest, "pdf": pdf_result, "citation_audit": citation_state, "approval": None}
    (out / "GATE_STATE.json").write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    packet = ["# Advisor Approval Packet", "", "Show this packet and `screenshots/` to the advisor.", "", "| Gate | Status |", "|---|---|"]
    packet += [f"| {gate} | {data['status']} |" for gate, data in gates.items()]
    packet += ["", "Status: `NOT READY` unless every row is PASS. Do not run approval before oral advisor confirmation."]
    (out / "APPROVAL_PACKET.md").write_text("\n".join(packet) + "\n", encoding="utf-8")
    manual = out / "manual"
    manual.mkdir(exist_ok=False)
    g5 = {
        "reviewer": "",
        "reviewed_at": "",
        "items": [
            {"id": "page-01-teaser", "status": "pass/fail", "evidence": ""},
            {"id": "figures-and-tables", "status": "pass/fail", "evidence": ""},
            {"id": "font-warnings", "status": "pass/fail/not_applicable", "evidence": "Locate and resolve or justify each Identity-H/readability warning."},
        ],
    }
    citation_rows = [{"key": key, "status": "manual_verified/corrected", "evidence": ""} for key in unresolved]
    g6 = {
        "reviewer": "",
        "reviewed_at": "",
        "claims": [{"claim": "", "location": "abstract/introduction", "evidence": "table/figure/theorem", "status": "supported/needs_revision"}],
        "citations": citation_rows,
    }
    (manual / "G5_VISUAL_REVIEW.json").write_text(json.dumps(g5, indent=2) + "\n", encoding="utf-8")
    (manual / "G6_CLAIM_EVIDENCE.json").write_text(json.dumps(g6, indent=2) + "\n", encoding="utf-8")
    try:
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (1200, 150 + len(gates) * 54), "white")
        draw = ImageDraw.Draw(image)
        draw.text((35, 28), "AAAI-27 SUBMISSION GATE DASHBOARD", fill="#111111")
        for index, (gate, data) in enumerate(gates.items()):
            color = "#0a7d32" if data["status"] == "PASS" else "#b42318" if data["status"] == "FAIL" else "#a15c00"
            draw.text((35, 90 + index * 54), f"{gate}: {data['status']}: {data['reason']}", fill=color)
        image.save(out / "GATE_DASHBOARD.png")
    except ImportError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--main", help="Main TeX filename relative to --input")
    parser.add_argument("--mode", choices=["quick", "release"], default="quick")
    parser.add_argument("--no-compile", action="store_true", help="Release compatibility option: skip isolated compilation and leave G1 blocked")
    parser.add_argument("--supplement", action="append", type=Path, default=[], help="Supplementary PDF, archive, or directory to bind into the final manifest")
    parser.add_argument("--checklist", type=Path, help="Completed reproducibility checklist to bind into the final manifest")
    parser.add_argument("--identity-term", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    release_mode = args.mode == "release"
    source_root = args.input if args.input.is_dir() else args.input.parent
    label = "release" if release_mode else "quick"
    out = args.output or source_root / "review" / f"aaai27-{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)
    tex, pdf, tracked = find_input(args.input, args.main)
    source, active_tex_files = active_source(tex)
    findings: list[dict] = []
    source_checks(source, findings)
    compiled = False
    if release_mode and args.input.is_dir() and not args.no_compile:
        compiled = compile_check(args.input, tex, pdf, out / "build" / "isolated", findings)
    elif release_mode and args.input.is_dir() and args.no_compile:
        add(findings, "G1", "BLOCKED", "Isolated source compilation", "Compilation was disabled.", "Rerun release mode without `--no-compile`.")
    for term in args.identity_term:
        if term and term.lower() in source.lower():
            add(findings, "G3", "CRITICAL", "Identity-term leak", f"Found supplied identity term `{term}` in active source.", "Remove or anonymize this term and regenerate the PDF.")
    pdf_result = pdf_checks(pdf, out, findings, args.identity_term, release_mode)
    bib_paths = active_bibliography_paths(source, tex, tracked)
    citation_audit = offline_audit(source, bib_paths)
    if release_mode:
        citation_audit = full_audit(citation_audit)
    citation_findings(citation_audit, findings)
    if not release_mode:
        write_quick_report(out, findings)
        print(out)
        return 0
    checklist = args.checklist
    if not checklist and args.input.is_dir():
        candidates = [path for path in args.input.rglob("*") if path.is_file() and "reproducibility" in path.name.lower() and not any(part in EXCLUDED_PARTS for part in path.parts)]
        checklist = candidates[0] if candidates else None
    bound = list(active_tex_files) + [path for path in tracked if path.suffix in {".bib", ".pdf"}]
    for item in [*args.supplement, checklist]:
        if not item:
            continue
        if item.is_dir():
            bound.extend(path for path in item.rglob("*") if path.is_file())
        elif item.exists():
            bound.append(item)
        else:
            add(findings, "G4", "BLOCKED", "Declared supplementary input", f"Declared path does not exist: {item}", "Provide the exact supplementary or checklist file before approval.")
    manifest = {str(path.resolve()): sha256(path) for path in dict.fromkeys(bound) if path.exists() and path.is_file()}
    gates = gate_statuses(findings, tex, pdf, args.identity_term, checklist, compiled)
    write_release_report(out, findings, gates, manifest, pdf_result, citation_audit)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
