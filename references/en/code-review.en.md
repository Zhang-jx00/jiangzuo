
# Booklet: Pre-Commit Review (Self-Review + Peer Review)

> **When to read**: Before every commit/delivery (must read); when the user requests a code review; when reviewing an implementation produced by a subagent.
> **Prerequisites**: The changes are complete and have been self-tested.
> **Output**: A diff that passes review, or a graded issue list sorted into "must-fix / should-fix / ignorable".
> **CRITICAL: read the entire booklet before acting; execute the steps in order, and do not skip any.**

## Self-Review Mindset (Checking your own work means three blind spots)

- **Cooldown**: After finishing, go do something else before coming back to review — after 10 minutes you are looking at "someone else's code".
- **Reorder**: Start from the most dangerous files (those that touched contracts/databases/permissions), not in modification-time order.
- **Presumption of guilt**: Assume this diff definitely hides a bug, and your job is to find it — a glance plus an "LGTM" is not a review.
- **Assume there are problems**: Zero findings on the first pass = you did not look hard enough. Before wrapping up the review, complete at least one round of the "find issues → fix → re-verify" loop.
- **Size alert**: If a single diff carries more than ~400 lines of effective changes, consider splitting the commit — error rates in large diffs are significantly higher, and humans cannot review them well.

### Evidence Matrix (what counts / what does not)

| Counts as verification evidence ✅ | Does not count ❌ |
|---|---|
| Commands run this round + full output | "The code looks fine" |
| Tests targeting the original symptom pass | The tests **once** passed |
| The actual content of the VCS diff | Subagent/subcontractor "done" reports |
| The result of actually operating it in the browser | A passing build (only proves it compiles, not that it is correct) |

## Process

1. First run `python scripts/preflight.py` — whatever a machine can check (secrets, debug leftovers, conflict markers, TODOs) needs no human eyes.
2. **Read the full diff** (`git diff` / `git diff --staged`), and walk the checklist below block by block.
3. Grade findings by severity: 🔴 must-fix (merging will cause an incident) / 🟡 should-fix (worth changing but not blocking) / ⚪ ignorable (a matter of taste; record it, no obligation).
4. After fixing all 🔴, **run the tests and preflight again**, until clean.
5. When subagent output is involved: do not naively trust "done" reports; verify independently with the diff and test output.

## Review Checklist

### Correctness
- [ ] Boundaries: empty, 0, null, single element, extra-long, extreme values
- [ ] Error paths: every call that can fail has handling, and the handling is correct
- [ ] Logic conditions: `>` vs `>=`, and/or, negation, cases that slip through early returns
- [ ] Does the new code assume anything about data that is "missing/empty/deleted"? Do those assumptions hold?

### Concurrency and Transactions
- [ ] Multiple write operations are inside one transaction; on failure everything rolls back
- [ ] Concurrent access to shared mutable state thought through (locks/atomic operations/idempotency)
- [ ] What happens when "two people click at the same time" — duplicate orders, overselling, double spending

### Security (see security.md for details)
- [ ] SQL is parameterized; no string concatenation
- [ ] Resource access carries owner checks (horizontal privilege escalation); admin endpoints have role checks (vertical privilege escalation)
- [ ] No hardcoded secrets/intranet addresses; no sensitive values in logs
- [ ] User input is untrusted along the entire path from input to output (walk through injection/XSS once)

### Performance Pitfalls
- [ ] No SQL/HTTP calls inside loops (N+1)
- [ ] List queries have pagination/limits
- [ ] New queries run acceptably on large tables (EXPLAIN reviewed, or indexes confirmed)
- [ ] No obvious spots where synchronous blocking slows the main flow (large files, external calls)

### Breaking Changes (the easiest to miss; think about this for 2 dedicated minutes)
- [ ] Interfaces: deleted fields/renamed fields/changed types/changed semantics — have all callers (frontend, scripts, third parties) adapted?
- [ ] Databases: is the migration compatible with existing data? Is it compatible with the old code still running (the rolling-release window)?
- [ ] Configuration: a newly required config item — what happens to services that did not set it?
- [ ] Dependency upgrades: has the changelog been read for breaking changes?

### Necessity and Scope (new code passes this gate first)
- [ ] New code has a reuse-ladder conclusion (stopped at level N); rewriting when the repo already has a similar implementation, or building a second copy of what the standard library or framework does natively → send it back
- [ ] Changes do not cross the "freeze list" in the task plan; if crossed, either revise the plan or revert
- [ ] New dependencies were approved by the user (reuse already-installed dependencies instead of introducing new ones)

### Consistency and Leftovers
- [ ] Style consistent with project conventions (naming, directories, error-handling patterns)
- [ ] No debug leftovers: console.log, print, debugger, large commented-out blocks
- [ ] No unused dependencies/imports/variables
- [ ] Every TODO carries context (who, why, when it will be handled)
- [ ] Copy and error messages are worded in language users can understand

### Tests and Documentation
- [ ] Key logic has tests: logic **with branches/loops/parsing/money/permissions/concurrency** — every change leaves at least one test that can fail; every fixed bug has a regression test
- [ ] Interface changes have been written back into the contract docs; config changes have updated the environment docs

### Self-Doubt Loop (make the case first, then try to overturn it)

Before review or delivery, write "I think it is right" as a single **falsifiable claim**, then act as your own opponent and try to overturn it:

1. **CLAIM**: One claim + why it matters. Examples: "The new cache layer is thread-safe under the read-heavy/write-light workload described in the spec" / "There is a race here that silently corrupts data and QA will hardly notice". If you cannot write the claim, you do not yet know what you are delivering.
2. **EXTRACT**: Break the claim into observable predictions — "if it holds, then running `____` should show `____`".
3. **DOUBT**: Hunt specifically for three things: **unstated assumptions**, **unhandled boundaries**, **hidden couplings and shared state**. Assume the author is overconfident — including yourself.
4. **RECONCILE**: Run commands to reconcile each prediction one by one; only what cannot be overturned stays.
5. **STOP**: Stop as soon as any one is met: the next round would only surface trivial or already-considered findings; **3 full rounds have already been run** (round 4 goes back to the user — do not grind on alone); the user explicitly says "ship it as is".

**Classify each finding by taking the first matching category in order (first match wins)**, to avoid spending effort on issues that lead nowhere:

| No. | Category | Handling |
|---|---|---|
| 1 | Contract misreading (the requirements or interface were misunderstood) | Highest priority; align understanding before changing code |
| 2 | Valid and actionable | Fix in this round, and add one test that can fail |
| 3 | Valid but a trade-off | Write it into an ADR or tech debt; **do not force a change** |
| 4 | Noise | Record and discard; do not respond point by point |

## Conclusion Output Format

```
审查结论：通过 / 修复后通过 / 打回
🔴 必须修：
  1. [文件:行号] 问题描述 + 为什么必须修
🟡 建议修：
  1. [文件:行号] 建议 + 理由
⚪ 可忽略：
  ...
验证：pytest 42 passed；preflight 0 critical
```

## Common mistakes

- Reading only the file you just wrote and not updating its callers — compilation/tests catch half for you; for the other half, rely on a global search for "who else references it".
- Treating "all tests green" as a passing review — breaking changes the tests do not cover (config, contracts, data compatibility) will still blow up.
- Reviewing as a formality: the checklist was never truly considered item by item, yet one glance produces an "LGTM".
- Not re-running verification after fixing 🔴, on the assumption that a one-line change cannot affect anything else.
