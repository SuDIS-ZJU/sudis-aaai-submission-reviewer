# Gates and advisor approval

## Statuses

`PASS` means every applicable check has evidence. `FAIL` means a verified violation exists. `BLOCKED` means missing input, unresolved authoritative verification, manual inspection, or a required tool. Warnings with Gate effect `NONE` may coexist with PASS.

Every finding declares `gate_effect` as `FAIL`, `BLOCK`, or `NONE`. Deterministic `FAIL` findings lock the Gate until the input is corrected and the release audit is rerun. All G0--G7 must be `PASS` before advisor review.

## Evidence expected per gate

| Gate | Required evidence |
|---|---|
| G0 | Rule snapshot, track/cycle, input inventory |
| G1 | Source checks, build log or compiled-PDF provenance |
| G2 | PDF metadata, font report, page classification, source-format scan |
| G3 | Metadata, identity-term scan, URL/link scan |
| G4 | Appendix reference map, supplementary inventory, checklist status |
| G5 | First-page render, high-risk page renders, figure/font/bitmap report |
| G6 | Claim-evidence map, citation audit, adversarial findings, full style scan |
| G7 | Final manifest and unchanged-hash verification |

## Advisor workflow

1. The student sends `GATE_DASHBOARD.png`, `APPROVAL_PACKET.md`, and the `screenshots/` directory.
2. The advisor checks the actual paper and evidence, then gives oral approval or rejects it.
3. Only after approval may the student run `gate_tool.py approve`.
4. `FINAL_APPROVED.png` is a release token for this exact file manifest, not a substitute for the advisor's judgment and not proof of OpenReview submission.
5. Any changed input hash invalidates the token and requires a new audit and review.

## Citation decisions

- `VERIFIED`: authoritative metadata matches; no additional action is required.
- `MISMATCH`: a DOI or arXiv identifier resolves but conflicts with the cited title, year, or author; correct it and rerun.
- `UNVERIFIED`: lookup failed or no reliable match was found; do not call it hallucinated. Add authoritative manual evidence to G6.
