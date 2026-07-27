# Maintainer rules

This repository ships one standalone AAAI-27 submission-audit skill. Do not add runtime dependencies on other skills or copy student papers, private reviews, author identities, or raw supplementary archives into this repository.

Official AAAI sources override community advice and bundled heuristics. New venue cycles and tracks require a separate verified profile. Never silently apply AAAI-27 limits to another cycle.

Keep the skill audit-only. It may create review reports and gate records, but must not edit manuscripts, run experiments, upload papers, or claim an advisor approved a paper without an explicit recorded oral confirmation.

Every rule that can be checked deterministically belongs in `scripts/audit.py` with a regression test. G5 and G6 retain manual evidence because visual quality and claim-evidence alignment cannot be reliably reduced to regexes.

Before a release, run unit tests, `quick_validate.py`, a clean installer dry run in a temporary HOME, and a full audit of a non-sensitive fixture. Do not publish until GitHub target and permissions are explicitly confirmed.
