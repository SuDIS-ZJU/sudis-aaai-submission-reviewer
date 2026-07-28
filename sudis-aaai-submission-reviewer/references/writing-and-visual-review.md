# Writing and visual review

## Claim discipline

For each major claim in the Abstract and Introduction, record the exact supporting table, figure, theorem, or measured result. Claims without direct evidence must be weakened, qualified, or removed.

Flag these as MAJOR unless evidence is explicit: unqualified “state of the art”, “first”, “solve”, “superior”, “comprehensive”, “extensive”, “remarkable”, and claims that generalize beyond evaluated settings.

Use neutral verbs: propose, introduce, show, report, observe, measure, and compare. Do not use em dashes. Avoid “innovative”, “revolutionary”, “transformative”, “notably”, “yielding”, “underscore”, “pave the way”, or similar AI-sounding stock language.

## Logic review

- Each contribution must map to a method component and a corresponding evaluation.
- Each paragraph needs a visible topic sentence and one main message.
- Terms and symbols must have one definition and stable meaning.
- Explain anomalous comparisons instead of hiding them.
- Treat missing strong baselines, unfair resource budgets, missing ablations, and unsupported causality as reviewer-facing risks.

## Citation integrity

- Check every active citation key against the active BibTeX files.
- Treat a resolved DOI or arXiv metadata conflict as a must-fix error.
- Treat an inconclusive lookup as `UNVERIFIED`, not a hallucination claim.
- Record publisher, DOI, proceedings, or arXiv evidence for each manually verified entry.

## Figure and table review

- The first sentence of a caption states the finding, then defines setup, metrics, abbreviations, and caveats.
- Use direct labels, units, meaningful ticks, honest axes, colour-blind-safe colours, and non-colour encoding.
- Avoid chartjunk, 3D, decorative gradients, shadows, redundant chart titles, and unexplained bolding.
- A teaser should show the problem, failure or observation, method idea, and evidence-backed outcome in a single visual story.
- Mark human visual checks as `BLOCKED` rather than claiming to inspect details not visible in a PDF or render.
