# SuDIS AAAI Reviewer & Gatekeeper

A standalone AAAI-27 Main Technical Track skill for Codex and Claude Code. It does not edit or upload manuscripts and does not depend on other research-writing skills.

## Three student workflows

### 1. Quick: daily iteration

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/audit.py \
  --input /path/to/paper
```

Quick is the default. It returns `QUICK_REPORT.md` with at most five next actions and `FINDINGS.json`. It does not create Gate or approval artifacts.

### 2. Release: final submission audit

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/audit.py \
  --mode release --input /path/to/paper \
  --supplement /path/to/supplement.pdf \
  --checklist /path/to/ReproducibilityChecklist.pdf \
  --identity-term 'Example University' \
  --output /path/to/aaai27-release-audit
```

Release performs G0--G7, preserves an isolated build under the audit directory, verifies all active citations, and prepares the advisor evidence packet.

### 3. Reviewer: scientific stress test

```text
Use $sudis-aaai-submission-reviewer in reviewer mode. Score this AAAI paper 1-10,
rank the remaining weaknesses, give the minimum fix for each, and say READY YES, ALMOST, or NO.
```

Reviewer produces one advisory `REVIEW_REPORT.md`, including its Defense Board. It cannot change Gate status or approve submission.

## Installation

```bash
git clone https://github.com/SuDIS-ZJU/sudis-aaai-submission-reviewer.git
cd sudis-aaai-submission-reviewer
python3 sudis-aaai-submission-reviewer/scripts/bootstrap.py
bash scripts/install.sh --dry-run
bash scripts/install.sh
bash scripts/install.sh --check
```

The installer is idempotent for correct symlinks and refuses all replacement or automatic uninstall operations. It links the same standalone skill into `~/.agents/skills/` and compatible Codex and Claude Code discovery paths.

## What blocks a Gate

Findings explicitly declare their Gate effect:

| Student label | Gate effect | Meaning |
|---|---|---|
| MUST FIX | `FAIL` | Verified official or integrity violation |
| CONFIRM | `BLOCK` | Missing evidence or manual confirmation |
| IMPROVE | `NONE` | Non-blocking quality advice |

Type 3 and confirmed unembedded fonts remain hard errors. Identity-H and suspected small visual text require manual G5 confirmation because metadata alone cannot reliably locate a violation. Warnings can coexist with a passing Gate.

## Citation integrity

Quick checks missing citation keys, duplicate DOI or titles, malformed identifiers, implausible years, and placeholder metadata.

Release verifies every active citation using Crossref or arXiv:

- `VERIFIED`: authoritative metadata matches.
- `MISMATCH`: a resolved identifier conflicts with title, year, or author; correct and rerun.
- `UNVERIFIED`: lookup is inconclusive; add publisher, DOI, proceedings, or arXiv evidence to G6.

An unavailable record is never automatically called hallucinated. Online lookup uses Python's standard library and adds no runtime package.

## Gate and advisor workflow

| Gate | Check |
|---|---|
| G0 | Inputs and official AAAI-27 profile |
| G1 | Preserved build and source integrity |
| G2 | Format, page limit, captions, and PDF |
| G3 | Anonymity and external links |
| G4 | Supplementary material and reproducibility |
| G5 | Teaser, fonts, figures, tables, and visual layout |
| G6 | Claims, citations, evidence, and overclaim |
| G7 | Final package consistency |

Every Gate must be `PASS`. Deterministic failures are locked and cannot be manually overridden. After G0--G7 pass, show `GATE_DASHBOARD.png`, `APPROVAL_PACKET.md`, and `screenshots/` to the advisor. Record approval only after explicit oral confirmation:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py approve \
  --audit-dir /path/to/audit \
  --approver 'Advisor Name' \
  --confirmation 'Advisor reviewed the gate screenshots and approved submission.'
```

Every Gate-state mutation creates a timestamped backup under `history/` before an atomic, verified write. Verify the exact manifest immediately before upload:

```bash
sudis-aaai-submission-reviewer/.venv/bin/python sudis-aaai-submission-reviewer/scripts/gate_tool.py verify --audit-dir /path/to/audit
```

## Data safety

The skill does not delete or clean files. Release build evidence is preserved in its output directory. Any later removal requires an exact target list, a backup and recoverability statement, and explicit user permission.

## Official authority

Final decisions must recheck the current [submission instructions](https://aaai.org/conference/aaai/aaai-27/submission-instructions/), [supplementary-material rules](https://aaai.org/conference/aaai/aaai-27/supplementary-material/), and [Author Kit](https://aaai.org/authorkit27/). Official rules override this package.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/skill-creator/scripts/quick_validate.py sudis-aaai-submission-reviewer
bash scripts/install.sh --dry-run
```
