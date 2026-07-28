# AAAI reviewer mode

## Purpose and boundary

Reviewer mode is an advisory pre-submission stress test. It simulates a skeptical AAAI senior reviewer, but it is not a gate, a prediction of acceptance, or a substitute for real peer review. It must never update `GATE_STATE.json`, run `gate_tool.py`, create approval artifacts, or claim compliance.

## Evidence standard

Every concern must be anchored in one of the following:

- a precise paper location, figure, table, equation, appendix item, or missing expected evidence;
- a mismatch between a stated claim and reported result;
- a concrete alternative explanation that the paper has not ruled out;
- a reproducibility or evaluation ambiguity that would prevent verification.

Do not manufacture missing work. Mark uncertainty explicitly when an appendix, code, raw result, or reviewer-requested artifact was not supplied.

## Five lenses

### 1. Novelty and positioning

Ask whether the problem is distinct, the nearest work is named and differentiated, the claimed novelty exceeds a composition of known components, and the scope of “first”, “general”, or “model-agnostic” is justified.

### 2. Technical soundness

Ask whether each algorithm is fully specified, assumptions are realistic, symbols and definitions agree across the paper and appendix, and the stated mechanism is supported rather than asserted.

### 3. Experiments and evidence

Ask whether strong and directly relevant baselines are included, budgets are matched, ablations isolate each contribution, means and variation are reported when appropriate, metrics are comparable, and automatic evaluators are calibrated or checked.

### 4. Presentation and visuals

Ask whether the first page explains the problem, method, and measured outcome, captions state findings and define the setup, tables use consistent metrics, and a skeptical reader can identify both wins and losses without hunting through the appendix.

### 5. Reproducibility, scope, and limitations

Ask whether default parameters, data splits, preprocessing, compute, and stopping criteria are recoverable; whether cited work is real and accurately characterized; whether scale and robustness are demonstrated; and whether limitations and failure cases match the claimed deployment scope.

## Attack patterns derived from rebuttal case studies

The following patterns were abstracted from successful NeurIPS, ICML, and KDD rebuttal records supplied during skill development. They are anonymized, paraphrased, and not a runtime dependency.

| Pattern | Skeptical question | Minimum evidence that resolves it |
|---|---|---|
| Under-specified method | Could another group reproduce the exact method from the paper? | Algorithm, defaults, tie-breaking, update order, and training or inference protocol. |
| Inconsistent descriptions | Do the main paper and appendix describe the same deployed method? | One reconciled description, corrected terminology, and a location-specific erratum. |
| Incremental novelty | Is the result a new contribution or an untested combination of known ideas? | Nearest-work comparison plus isolated contribution evidence. |
| Missing direct baseline | Was the most relevant alternative omitted or dismissed without evidence? | Faithful baseline, justified incompatibility, or carefully scoped claim. |
| Unfair budget | Does the gain persist under matched compute, memory, parameters, data, and tuning? | Matched protocol and a clear cost table. |
| Unisolated gain | Which component actually causes the result? | Component ablations and interaction analysis. |
| Reliability gap | Is an LLM judge, reward, proxy metric, or heuristic actually measuring the target? | Calibration, agreement, manual check, or counterexample analysis. |
| Generalization gap | Do results cover only a favorable dataset, model, task, or scale? | Additional representative setting or a narrowed scope claim. |
| Anomalous result | Why does a smaller budget, weaker baseline, or unexpected metric win? | Diagnosis, corrected protocol, or explicit limitation. |
| Overclaim | Does the abstract claim consistency, superiority, or generality that tables do not support? | Exact qualification, task-wise reporting, and failure analysis. |
| Citation integrity | Does each cited identifier resolve to the stated paper, and does the prose characterize it accurately? | DOI, publisher, proceedings, or arXiv metadata plus a context check. |
| Opaque presentation | Can the reader decode metrics, symbols, and visual comparisons quickly? | Defined notation, improved caption or table design, and an explanatory figure. |

## Rating and readiness

Use the following advisory interpretation, not an official AAAI score:

| Score | Interpretation |
|---|---|
| 1--3 | Fundamental reject risk |
| 4--5 | Weak reject risk |
| 6 | Borderline |
| 7 | Weak accept potential |
| 8 | Clear accept potential |
| 9--10 | Exceptional evidence and presentation |

The score must follow the cited evidence. Never average five lens scores mechanically when one central flaw dominates the decision.
