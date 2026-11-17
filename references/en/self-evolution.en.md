# Booklet: Skill Self-Evolution (rules retired by evidence, not forgotten)

> **When to read**: when you want to "add one rule" to a skill/project; when the same kind of problem keeps recurring; when a retrospective finds that a rule has stopped working; a health check before a version iteration.
> **Prerequisite**: there is a trail you can look up (learnings, technical debt, evaluation records, git history). Without a trail there is no evolution, only recollection.
> **Output**: one verified rule change (or an explicit "no change" conclusion) + one line in the `docs/jiangzuo/evolution.md` ledger.
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip steps.**

## First, clarify what "self-evolution" is

Not automatically changing yourself — that is called losing control. **Self-evolution = change when there is evidence, must verify after every change, and be able to roll back after verification.**
The most dangerous evolution is not changing something wrong, it is **only adding and never subtracting**: rules pile up more and more → resident context inflates → the binding power of each rule is diluted → the skill looks stricter but is actually weaker. So half of this booklet is about "how to delete".

## Six gates (the order cannot be swapped)

| Gate | What it does | If you cannot pass it |
|---|---|---|
| ① Observe | Run `python scripts/evolve_report.py .`, get the candidate list | If there is no signal, stop — do not change things just for the sake of changing |
| ② Attribute | What is the **root cause** of this candidate? A missing rule, an unclear rule, or the executor never read it? | If you cannot attribute it down to the mechanism layer, do not change it |
| ③ Hypothesis | Write one falsifiable sentence: "after adding/changing X, scenario Y will no longer occur" + how verification is counted | If you cannot write a prediction = you should not change anything |
| ④ Minimal mutation | **Change only one hypothesis at a time**; ≤40 added lines, and give deletable candidates at the same time | Wanting to change three places = three hypotheses, go through them in three separate rounds |
| ⑤ Verify | The regression trio (validate / unittest / preflight) + re-run the relevant red tests | If the red test loses its discriminating power → the change did not take effect, or the scenario is no longer valid |
| ⑥ Record | Write one line in `docs/jiangzuo/evolution.md`: evidence / hypothesis / mutation / result / **KEEP or ROLLBACK** | A change that is not recorded counts as never having happened |

## The four lifecycle exits for a rule

Every rule must eventually land in one of these; "not sure whether it counts" is not an exit:

1. **Promote to a hard constraint**: the same topic in `learnings.md` has "high" confidence and has been verified by ≥2 tasks → move it into the corresponding booklet and record the source in the ledger.
2. **Keep as is**: the evidence is not enough to support a change, but the problem really exists → record it as `WATCH` in the ledger and write down the basis for the next judgment.
3. **Retire**: no routing hits and no delivery references across two consecutive versions → delete it or demote it to an example. **Deleting a rule takes more courage than adding one**: it makes the remaining rules carry more weight.
4. **Merge**: two rules say the same thing → merge them into one, and record the saved lines in the ledger.

## Bloat control (hard metrics you can check)

- Entry body: the token count from `python scripts/validate_skill.py . --stats`. **When it exceeds the target, every addition in this round must come with an equal-amount deletion**, written into the commit message.
- Booklet size: split first, then add, as it approaches 160 lines (`evolve_report.py` will name it).
- Every new rule must answer: "**If this line is deleted, will the agent's behavior change?**" If it will not → do not commit.
- Counter-example quota: for every 3 positive rules added, pair at least 1 "when **not** to do X" rule (to keep the skill from becoming a list that only ever grows).

## Mutation safety (how to break things as little as possible)

- Before changing: `git status` is clean; after changing, commit immediately, one ledger line per commit, and `git revert` is the rollback plan.
- **Forbidden**: in one commit, changing rules and scripts and templates while recording only one hypothesis — rolling back will also undo the parts that were fine.
- Rollback conditions (roll back if any one of them occurs, no negotiation): the regression trio turns red; the relevant red test loses its discriminating power; a new bypass wording appears (the agent uses the new rule to endorse unreasonable behavior).
- After rolling back: mark `ROLLBACK` in the ledger and write clearly **why this attempt did not hold up** — a failed evolution is also data; throwing it away means stepping into the same trap for nothing.

## What cannot be handed to "self-evolution"

- **Safety boundaries**: irreversible operations, secret handling, publishing to the outside, writes outside the workspace — these can only be tightened, and must not be relaxed because "nothing happened this time".
- **User authorization**: the skill may advise, but it must not change the user's project conventions on its own; changing the standard itself must go through an ADR and be signed off by a human.
- **Facts**: evolution can only change the practice, not the facts. If you cannot find it, write "unverified"; do not use rule changes to present the unverified as verified.

## Examples

**Bad evolution**: in one session the agent forgot to clean up the probes → so a rule "cleanup is mandatory at wrap-up" is added → it forgets again → "no delivery without cleanup" is added → then "preflight must check it". Three rules say the same thing, the entry body grows from 5K to 6K, and the binding power actually drops.
**Good evolution**: run `evolve_report.py` → observe that "7 high-confidence lessons are still sitting in learnings" → attribution: there is no **promotion path** from lessons to booklets (not that nobody obeys, but that the path does not exist) → hypothesis: write the promotion action into the learnings write-back rule, and the trace item of red test S2 should keep passing → mutation: one change, 6 lines → regression all green → record `KEEP`.

## Checklist

- [ ] Ran `evolve_report.py`, and the candidates came from evidence rather than impression
- [ ] Only one hypothesis was changed, and a falsifiable prediction was written down
- [ ] The added lines and the deletion candidates appear as a pair (or there is an explicit explanation of why nothing can be deleted)
- [ ] The regression trio + the relevant red tests were re-run, and the result was written into the ledger
- [ ] `docs/jiangzuo/evolution.md` has this line: evidence/hypothesis/mutation/result/KEEP or ROLLBACK
- [ ] The change can be reverted on its own (it was not smuggled into other commits)

## Common mistakes

- Treating "it broke again" as a reason to "add one more rule" — most of the time **the previous rule was never read**, so check the routing and the wording first.
- Recording only the successful evolutions. A failed mutation is not written back to the ledger, and next time the same pit gets stepped into again.
- Using evolution to cover up an execution problem: the rule was already written and the agent did not execute it — that is a gap in discipline and verification, not a gap in the number of rules.
- Letting the reporting tool make the judgment for you: `evolve_report.py` gives candidates, not conclusions; it cannot see your business constraints.
- Changing several hypotheses at once and then being unable to attribute which one worked — that is not evolution, just motion.

## Wrap-up red lines (finished editing the rules ≠ evolution is complete)

- Go back to the Checklist above and tick every item; if any one of them cannot be ticked, roll back this mutation.
- Not written in the ledger = it did not happen; the result without a command run = it was not verified.
- If the entry body got bigger, the commit message must state the net increase and the repayment plan; quietly swallowing the budget is forbidden.
- Adding a rule for the same topic twice in a row → stop; this usually means the attribution was wrong, so go back and re-run gate ②.
