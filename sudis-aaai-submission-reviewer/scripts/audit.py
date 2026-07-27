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
from datetime import datetime, timezone
from pathlib import Path

PROFILE = {
    "venue": "AAAI-27 Main Technical Track",
    "verified_on": "2026-07-27",
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
OVERCLAIM = [r"\\bwe solve\\b", r"\\bthe first\\b", r"\\bfirst to\\b", r"\\boutperforms all\\b", r"\\bSOTA\\b"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uncomment(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\\\)%.*$", "", line) for line in text.splitlines())


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
    pdf = (tex.with_suffix(".pdf") if tex else path / "main.pdf")
    if not pdf.exists():
        candidates = find_files(path, ".pdf")
        pdf = candidates[0] if candidates else None
    tracked = find_files(path, ".tex") + find_files(path, ".bib")
    if pdf:
        tracked.append(pdf)
    return tex, pdf, tracked


def main_source(tex_files: list[Path]) -> str:
    parts = []
    for path in tex_files:
        try:
            parts.append(f"\n% FILE: {path}\n" + uncomment(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return "\n".join(parts)


def add(findings: list[dict], gate: str, severity: str, rule: str, evidence: str, fix: str, source: str = "official") -> None:
    findings.append({"gate": gate, "severity": severity, "source": source, "rule": rule, "evidence": evidence[:800], "minimum_fix": fix})


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
            add(findings, "G6", "MAJOR", "Potential overclaim", f"Matched `{pattern}`.", "Name the benchmark, comparison set, condition, and supporting evidence, or weaken the claim.", "lab-rule")
    urls = re.findall(r"(?:https?://|www\\.)[^\s}]+", source)
    if re.search(r"\\begin\{links\}|\\link\{(?:Code|Dataset)", source) or urls:
        add(findings, "G3", "CRITICAL", "No web supplementary pointers", "Found a source URL or code/data links environment.", "Remove code/data/project URLs; upload materials as supplementary files instead.")


def pdf_checks(pdf: Path | None, out: Path, findings: list[dict], identities: list[str]) -> dict:
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
        font_rows = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=False).stdout.splitlines()[2:]
        for row in font_rows:
            if "Type 3" in row or re.search(r"\sno\s+no\s+", row):
                add(findings, "G5", "CRITICAL", "Embedded non-Type-3 fonts", "pdffonts: " + row.strip(), "Regenerate the affected figure or font as embedded Type 1, TrueType, or OpenType.")
            if "Identity-H" in row:
                add(findings, "G5", "MAJOR", "CID/Identity-H font", "pdffonts: " + row.strip(), "Convert non-Roman figure text to outlines or remove it.")
    try:
        import fitz
        document = fitz.open(str(pdf))
        screenshots = out / "screenshots"
        screenshots.mkdir(exist_ok=True)
        for index in sorted({0, min(1, len(document) - 1), min(6, len(document) - 1)}):
            page = document[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            target = screenshots / f"page-{index + 1:02d}.png"
            pix.save(str(target))
            result["rendered"].append(str(target.name))
    except (ImportError, RuntimeError):
        add(findings, "G5", "BLOCKED", "Visual rendering", "PyMuPDF is unavailable or could not render the PDF.", "Run bootstrap.py and manually inspect rendered PDF pages.")
    return result


def gate_statuses(findings: list[dict], tex: Path | None, pdf: Path | None, identities: list[str]) -> dict:
    gates = {f"G{i}": {"status": "PASS", "reason": "Deterministic checks passed."} for i in range(8)}
    gates["G5"] = {"status": "BLOCKED", "reason": "Manual teaser and visual-quality review is required."}
    gates["G6"] = {"status": "BLOCKED", "reason": "Manual claim-evidence and adversarial review is required."}
    if not tex:
        gates["G1"] = {"status": "BLOCKED", "reason": "PDF-only input cannot pass source-integrity checks."}
    if not pdf:
        gates["G2"] = {"status": "BLOCKED", "reason": "No compiled PDF is available."}
    if not identities:
        gates["G3"] = {"status": "BLOCKED", "reason": "No identity terms supplied for strict anonymity review."}
    for finding in findings:
        gate = finding["gate"]
        if finding["severity"] == "BLOCKED":
            gates[gate] = {"status": "BLOCKED", "reason": finding["rule"]}
        elif finding["severity"] == "CRITICAL":
            gates[gate] = {"status": "FAIL", "reason": finding["rule"]}
        elif finding["severity"] == "MAJOR" and gates[gate]["status"] == "PASS":
            gates[gate] = {"status": "FAIL", "reason": finding["rule"]}
    return gates


def write_report(out: Path, findings: list[dict], gates: dict, manifest: dict, pdf_result: dict) -> None:
    counts = {level: sum(f["severity"] == level for f in findings) for level in ("CRITICAL", "MAJOR", "MINOR", "BLOCKED")}
    lines = ["# AAAI-27 Submission Audit", "", "## Status", ""]
    for gate, data in gates.items():
        lines.append(f"- {gate}: **{data['status']}** — {data['reason']}")
    lines += ["", "## Findings", "", f"- CRITICAL: {counts['CRITICAL']}", f"- MAJOR: {counts['MAJOR']}", f"- MINOR: {counts['MINOR']}", f"- BLOCKED: {counts['BLOCKED']}", ""]
    for index, finding in enumerate(findings, 1):
        lines += [f"### {index}. [{finding['severity']}] {finding['rule']}", "", f"- Gate: {finding['gate']} ({finding['source']})", f"- Evidence: {finding['evidence']}", f"- Minimum fix: {finding['minimum_fix']}", ""]
    lines += ["## Manual review required", "", "- G5: inspect the teaser and all screenshots for readability, caption meaning, clipped content, raster misuse, and visual overclaim.", "- G6: create a claim-evidence map for the Abstract and Introduction, then run adversarial logic review.", "", "## Approval state", "", "Do not submit. `AWAITING ADVISOR APPROVAL` is available only after G0--G7 are PASS."]
    (out / "AUDIT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "RULES_SNAPSHOT.md").write_text("# Rules snapshot\n\n" + "\n".join(f"- {url}" for url in PROFILE["sources"]) + f"\n\nVerified baseline: {PROFILE['verified_on']}\n", encoding="utf-8")
    (out / "FINDINGS.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "GATE_STATE.json").write_text(json.dumps({"schema_version": "1.0", "gates": gates, "profile": PROFILE, "manifest": manifest, "pdf": pdf_result, "approval": None}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    packet = ["# Advisor Approval Packet", "", "Show this packet and `screenshots/` to the advisor.", "", "| Gate | Status |", "|---|---|"]
    packet += [f"| {gate} | {data['status']} |" for gate, data in gates.items()]
    packet += ["", "Status: `NOT READY` unless every row is PASS. Do not run approval before oral advisor confirmation."]
    (out / "APPROVAL_PACKET.md").write_text("\n".join(packet) + "\n", encoding="utf-8")
    try:
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (1200, 150 + len(gates) * 54), "white")
        draw = ImageDraw.Draw(image)
        draw.text((35, 28), "AAAI-27 SUBMISSION GATE DASHBOARD", fill="#111111")
        for index, (gate, data) in enumerate(gates.items()):
            color = "#0a7d32" if data["status"] == "PASS" else "#b42318" if data["status"] == "FAIL" else "#a15c00"
            draw.text((35, 90 + index * 54), f"{gate}: {data['status']} — {data['reason']}", fill=color)
        image.save(out / "GATE_DASHBOARD.png")
    except ImportError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--main", help="Main TeX filename relative to --input")
    parser.add_argument("--identity-term", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source_root = args.input if args.input.is_dir() else args.input.parent
    out = args.output or source_root / "review" / f"aaai27-audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)
    tex, pdf, tracked = find_input(args.input, args.main)
    tex_files = find_files(args.input, ".tex") if args.input.is_dir() else []
    source = main_source(tex_files)
    findings: list[dict] = []
    source_checks(source, findings)
    for term in args.identity_term:
        if term and term.lower() in source.lower():
            add(findings, "G3", "CRITICAL", "Identity-term leak", f"Found supplied identity term `{term}` in active source.", "Remove or anonymize this term and regenerate the PDF.")
    pdf_result = pdf_checks(pdf, out, findings, args.identity_term)
    manifest = {str(path.resolve()): sha256(path) for path in tracked if path.exists() and path.is_file()}
    gates = gate_statuses(findings, tex, pdf, args.identity_term)
    write_report(out, findings, gates, manifest, pdf_result)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
