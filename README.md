# SuDIS AAAI Reviewer & Gatekeeper

`sudis-aaai-submission-reviewer` is a standalone skill for AAAI-27 Main Technical Track papers. It has two deliberately separated modes:

| Mode | Question it answers | Output | Submission authority |
|---|---|---|---|
| Reviewer | “What would a skeptical AAAI reviewer attack?” | Score, ranked weaknesses, minimum fixes, and defense board | Advisory only |
| Gatekeeper | “Does this exact package satisfy our strict submission process?” | G0--G7 evidence, screenshots, and advisor approval packet | Required before advisor approval |

The skill does not edit manuscripts, submit to OpenReview, create public links, or replace advisor judgment. It is designed to run independently after installation in Codex or Claude Code. It does not depend on any external research-writing or review skill.

## Installation

Clone the repository, then install from its root:

```bash
python3 sudis-aaai-submission-reviewer/scripts/bootstrap.py
bash scripts/install.sh --dry-run
bash scripts/install.sh
bash scripts/install.sh --check
```

The installer links the same source directory into the unified `~/.agents/skills/` location and compatible Codex and Claude Code discovery directories. It refuses to replace real files or directories.

## Mode 1: Reviewer simulation

Use this mode before the final compliance pass to identify scientific and presentation risks. It is calibrated as a skeptical AAAI senior reviewer and evaluates five specialist lenses:

1. Novelty and positioning
2. Technical soundness
3. Experiments and evidence
4. Presentation and visuals
5. Reproducibility, scope, and limitations

Example request:

```text
Use $sudis-aaai-submission-reviewer in reviewer mode on this LaTeX project and supplement.
Score it 1-10 for AAAI, list critical weaknesses by severity, give the minimum fix for each,
and prepare reviewer questions that the student must be able to defend.
```

When a review output directory is provided, the skill writes:

- `REVIEW_REPORT.md`: score, `READY: YES | ALMOST | NO`, five-lens assessment, ranked risks, and meta-review.
- `DEFENSE_BOARD.md`: high-signal skeptical questions, evidence, minimum fixes, and defensible responses.

Reviewer `READY` is an advisory assessment, not a Gate result and not permission to submit. The mode never writes `GATE_STATE.json`, runs the approval tool, or creates `FINAL_APPROVED.png`.

## Mode 2: Gatekeeper audit

LaTeX projects are strongly recommended. Supply the compiled PDF, supplementary document or archive, completed reproducibility checklist, and all known identity terms.

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/audit.py \
  --input /path/to/paper \
  --supplement /path/to/supplement.pdf \
  --checklist /path/to/ReproducibilityChecklist.pdf \
  --identity-term 'Example University' \
  --identity-term 'example-lab' \
  --output /path/to/paper/review/aaai27-audit
```

Provide author names, affiliations, labs, handles, email domains, repository names, and grant identifiers as `--identity-term` values. PDF-only intake is supported in limited mode, but cannot pass source-integrity checks.

For LaTeX intake, the audit compiles an isolated temporary copy and compares its normalized extracted-text fingerprint to the supplied PDF. This is required for G1 and never writes into the student's project. `--no-compile` is diagnostic-only and leaves G1 blocked.

| Gate | Check |
|---|---|
| G0 | Inputs and official AAAI-27 profile |
| G1 | Build and source integrity |
| G2 | Format, page limit, captions, fonts, and PDF |
| G3 | Anonymity and external links |
| G4 | Supplementary material and reproducibility |
| G5 | Teaser, visual quality, figures, and tables |
| G6 | Logic, evidence, and overclaim |
| G7 | Final package consistency |

All G0--G7 must be `PASS`. There are no waivers. The deterministic audit starts G5 and G6 as blocked until an agent or reviewer completes structured, hash-bound manual evidence. Example:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py set-gate \
  --audit-dir /path/to/audit \
  --gate G5 --status PASS \
  --evidence-file /path/to/audit/manual/G5_VISUAL_REVIEW.json \
  --evidence 'Reviewed page-01.png and all figures: teaser is self-contained; captions, font sizes, and axes are readable.'
```

## Advisor approval

After all Gates pass, show `GATE_DASHBOARD.png`, `APPROVAL_PACKET.md`, and `screenshots/` to the advisor. Only after oral approval, bind that approval to the exact file manifest:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py approve \
  --audit-dir /path/to/audit \
  --approver 'Advisor Name' \
  --confirmation 'Advisor reviewed the gate screenshots and approved submission.'
```

`FINAL_APPROVED.png` is generated only when every Gate is `PASS` and all audited files remain unchanged. It is an oral, self-recorded approval record, not a cryptographic signature or proof of OpenReview submission. Verify immediately before upload:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py verify --audit-dir /path/to/audit
```

## Scientific review design

The reviewer question bank was abstracted from successful, supplied NeurIPS, ICML, and KDD rebuttal records. It focuses on reproducible attacks rather than generic negativity: under-specified methods, inconsistent main-paper and appendix descriptions, omitted direct baselines, unmatched budgets, unisolated gains, unreliable automatic evaluation, limited generalization, anomalous results, overclaim, and opaque figures or tables.

No raw sample PDFs, review text, names, or private links are included in this repository. Existing samples are development evidence only and are not required at runtime. The reviewer mode is AAAI-calibrated, not a claim to reproduce another venue's rating policy.

## Official authority

This package pins a verified AAAI-27 profile, but final decisions must recheck the current [submission instructions](https://aaai.org/conference/aaai/aaai-27/submission-instructions/), [supplementary-material rules](https://aaai.org/conference/aaai/aaai-27/supplementary-material/), and [Author Kit](https://aaai.org/authorkit27/). Official rules override this package.

## Development and validation

```bash
python3 -m unittest discover -s tests -v
python3 /Users/lihuan/.codex/skills/.system/skill-creator/scripts/quick_validate.py sudis-aaai-submission-reviewer
bash scripts/install.sh --dry-run
```

These validation commands do not contact GitHub.
