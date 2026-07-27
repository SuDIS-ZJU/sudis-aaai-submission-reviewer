# SuDIS AAAI Submission Gatekeeper

`sudis-aaai-submission-reviewer` is a standalone, gate-based pre-submission audit skill for AAAI-27 Main Technical Track. It helps students prepare a strict evidence packet for an advisor before submission.

It audits format, anonymity, supplementary material, reproducibility, figures, tables, logic, overclaim, and final-file consistency. It does not edit manuscripts, submit to OpenReview, or replace advisor judgment.

## Install locally

```bash
python3 sudis-aaai-submission-reviewer/scripts/bootstrap.py
bash scripts/install.sh --dry-run
bash scripts/install.sh
```

The installer links the skill to the unified `~/.agents/skills/` directory and compatible Codex and Claude Code discovery directories. It refuses to overwrite real directories or files.

## Audit a paper

LaTeX projects are strongly recommended:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/audit.py \
  --input /path/to/paper \
  --supplement /path/to/supplement.pdf \
  --checklist /path/to/ReproducibilityChecklist.pdf \
  --identity-term 'Example University' \
  --identity-term 'example-lab' \
  --output /path/to/paper/review/aaai27-audit
```

Provide all author names, affiliations, labs, handles, email domains, repository names, and grant identifiers as `--identity-term` values. Pass the exact supplementary document/archive and completed checklist so G7 binds them into the approval manifest. A PDF-only audit is supported but cannot pass source-integrity checks.

For LaTeX intake, the audit compiles an isolated temporary copy by default and compares its normalized extracted-text fingerprint to the submitted PDF. This is required for G1 and never writes into the student's project. `--no-compile` is diagnostic-only and leaves G1 blocked.

## Required Gate workflow

| Gate | Check |
|---|---|
| G0 | Inputs and official AAAI-27 profile |
| G1 | Build and source integrity |
| G2 | Format, page limit, captions, fonts, and PDF |
| G3 | Anonymity and web links |
| G4 | Supplementary material and reproducibility |
| G5 | Teaser, visual quality, figures, and tables |
| G6 | Logic, evidence, and overclaim |
| G7 | Final package consistency |

The deterministic script creates G5 and G6 as blocked until an agent or reviewer has inspected visual material and claims. Fill the generated `manual/G5_VISUAL_REVIEW.json` or `manual/G6_CLAIM_EVIDENCE.json`; G5/G6 cannot be marked PASS without one of these structured, hash-bound records:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py set-gate \
  --audit-dir /path/to/audit \
  --gate G5 --status PASS \
  --evidence-file /path/to/audit/manual/G5_VISUAL_REVIEW.json \
  --evidence 'Reviewed page-01.png and all figures: teaser is self-contained; captions, font sizes, and axes are readable.'
```

All G0--G7 must be `PASS`. There are no waivers.

## Advisor approval

Once all gates pass, show `GATE_DASHBOARD.png`, `APPROVAL_PACKET.md`, and `screenshots/` to the advisor. After oral approval, record it against the exact file hashes:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py approve \
  --audit-dir /path/to/audit \
  --approver 'Advisor Name' \
  --confirmation 'Advisor reviewed the gate screenshots and approved submission.'
```

`FINAL_APPROVED.png` is generated only when every Gate is PASS and all audited files remain unchanged. It is an oral, self-recorded approval record, not a cryptographic signature and not proof of submission. Verify immediately before upload:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py verify --audit-dir /path/to/audit
```

## Official authority

This package pins a verified AAAI-27 profile, but final decisions must recheck the current [submission instructions](https://aaai.org/conference/aaai/aaai-27/submission-instructions/), [supplementary-material rules](https://aaai.org/conference/aaai/aaai-27/supplementary-material/), and [Author Kit](https://aaai.org/authorkit27/). If official rules change, they override this package.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 /Users/lihuan/.codex/skills/.system/skill-creator/scripts/quick_validate.py sudis-aaai-submission-reviewer
```

No remote repository is created or contacted by these commands.
