# Booklet: Documentation Maintenance and Delivery Report

> **When to read**: Before every delivery; when interfaces/architecture/configuration change; when wrapping up a long task.
> **Prerequisite**: The changes are complete and verified.
> **Output**: Project documentation consistent with the code + delivery report (templates/delivery-report.md).
> **CRITICAL: read the entire booklet before starting; execute the steps in order, do not skip steps.**

## Principles

Documentation is not decoration written after the code is done; it is **part of the deliverable**. Documentation that has not been updated is worse than no documentation — it actively misleads the next person. When documentation and code do not match: **the code is the source of truth, and fix the documentation in passing** (even a one-line change is worth it). Documentation updates go into the **same PR/commit** as the code changes — separating them means "backfill later", and it never gets backfilled.

## Four types of documentation to maintain continuously

| Document | Content | When to update |
|---|---|---|
| README / quick start | What the project is, how to install, how to run, how to test | When dependencies/commands/environment variables change |
| Architecture doc | Layering, module responsibilities, data flow, key trade-offs (link ADRs) | When modules are added/removed or the architecture is adjusted |
| Interface doc | Endpoints, parameters, responses, error codes (or OpenAPI contract) | **Immediately on every interface change** |
| Deployment/environment notes | Environment variables, dependent services, release steps, rollback method | When configuration/release process changes |

Put them in the project's `docs/` or the corresponding README sections; follow the project's current state, and do not force a new structure onto it.

## Delivery report (must be written at the end of every task)

Use templates/delivery-report.md — **four questions + risks** — written so that "the person who takes over next" can understand it too:

1. **What changed**: one sentence from the feature perspective + a list of key files (including added/modified/deleted).
2. **Why it was changed this way**: the key points of the approach and the rejected alternatives (at one-sentence level); link important trade-offs to ADRs.
3. **How it was verified**: the commands actually run and their results (test counts, check items), not just the words "self-tested".
4. **Remaining risks and unfinished items**: boundaries not covered, known minor issues, suggested follow-up actions (link the tech-debt registry).

In lightweight scenarios (L1 small fixes), these four items may be output only in the conversation without writing to disk; L2/L3/L4 must be written to disk under `docs/jiangzuo/reports/`.

## Progress and handover

- For long tasks (L3), update templates/progress-report.md daily/at each stage: what is done, what is in progress, blockers, next step.
- At handover/wrap-up, confirm the contents of `docs/jiangzuo/` are complete: profile, brief, plan (fully ticked), ADRs, contracts, reports — this set of records lets anyone take over.

## learnings write-back rules

When the user corrects you, or you hit a pitfall, append one line to `docs/jiangzuo/learnings.md`:

```
- [YYYY-MM-DD] 情境：…… 教训：…… 置信度：高/低
```

Confidence semantics (instinct-style tiered constraints): **high** = verified across multiple tasks, directly constrains how similar tasks are done; **low** = a single experience, for reference only. Once a lesson is verified again by later tasks, its confidence should be raised.

- Write **reusable behavior changes** ("this API's date parameter takes an end-exclusive range"), not emotions or a blow-by-blow log.
- Before the next similar task starts, read through the learnings first.
- General lessons at the skill level (applicable to all projects) → suggest the user distill them back into the skill itself (open a PR to update the corresponding booklet), and merge them in after human confirmation.

## Self-cleanup (must be done at wrap-up; the gate will check)

Things created temporarily for verification/experiments are not deliverables: probe scripts (`_probe*`, `_verify*`), packet captures and service logs (`*.log`), database copies and temporary files (`*.tmp`, `*.bak`), scratch directories (`scratch/`).

- Delete them **on the spot** when done; do not leave them for "later".
- Leave one line listing what was deleted in the verification record or the delivery report, e.g.: `Deleted: _verify_chain.py, _verify2_shop.db, server.log`.
- Things that genuinely are deliverables (new tests, new tool scripts) go into version control; do not hide them with .gitignore.
- How to check: the output of `git status --porcelain --untracked-files=all` should not contain files of the above forms — `scripts/ship_check.py` has this check built in.

## Checklist

- [ ] Interface docs/contracts are consistent with the code
- [ ] .env.example and the README quick start are still correct
- [ ] Major trade-offs have ADRs
- [ ] The delivery report has all four questions, and the verification evidence is real
- [ ] **The "copy-and-run" expected values in the delivery report match the current actual state** (how many tests run, how many findings detected, how many rules) — either run the numbers on the spot and copy them down, or attach a machine criterion
- [ ] Experiment leftovers have been deleted, and a deleted-items list was left in the verification record
- [ ] Remaining risks and tech debt are recorded somewhere findable
- [ ] learnings has this task's lesson written back

## Common mistakes

- "We'll backfill all the docs later" — they never get backfilled.
- The delivery report says only "completed, self-tested" — no evidence, no risks, no file list.
- **Expected numbers in command blocks hand-copied** — the code changed, the number was forgotten, and the person taking over runs it and assumes the tool is broken;
  a hard-coded number without a machine criterion stays quietly wrong for a long time (measured in this project: a line saying "0 conclusions" was wrong for four versions and nobody noticed,
  because what was wrong was the **control-side baseline** — it would never make any conclusion look better).
- A field changed in the interface while the docs are still three months old — callers develop against the docs and then errors break out across the board.
- ADRs record only "what was decided" and not "why, and what was rejected" — six months later nobody dares touch them.
- Handover moves only the code and not the docs/jiangzuo/ archive, and the person taking over has to figure things out from zero.
