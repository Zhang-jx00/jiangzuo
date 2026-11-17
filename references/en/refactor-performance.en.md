# Booklet: Refactoring and Performance Optimization

> **When to read**: the code gets hard to change and you want to clean it up; users report "slow"; you want to confirm the direction before optimizing.
> **Prerequisite**: the project's tests can run (onboarding.md); the performance problem has an observability mechanism.
> **Output**: refactoring with unchanged behavior / optimizations backed by measurement data.
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip steps.**

## Refactoring: small steps under test protection

Refactoring = **change the code structure, not the behavior**. Before the behavior is locked down, making any change is forbidden.

1. **Build the safety net first**: if the target area has no tests → first add "characterization tests" (lock in the current behavior, including the current quirks), or at least add core-path tests. Refactoring without a safety net = blind changes.
2. **Chesterton's Fence**: before deleting or changing anything, first figure out **why it is there** — `git blame` / `git log -L 起,止:文件` to check the original context, search for the callers, read the related comments and tests. If you cannot say why it exists, do not delete it; if you can, write the reason into the change description.
3. **Small steps, one intent per step**: do only one kind of transformation at a time — rename / extract a function / move a file / merge duplicates / split a branch. Mixing "refactoring" and "adding features" in one diff is forbidden.
4. **Run the tests after every step**: only move to the next step once they are green; if they are red, immediately roll back that step (`git stash` / undo) — do not advance while broken.
5. **Scale threshold**: if a single refactor is expected to touch **>500 lines** → first write a script/codemod to make the change in bulk (AST tooling, regex, `sed`), do not edit by hand — the miss rate grows with scale. The script must be re-runnable, must only change the target structures, must not touch test expectations, and must leave "how many files/lines were changed + the script path" in the delivery report.
6. **Scope discipline**: if you find a bigger mess → record it in templates/tech-debt.md, do not expand the battlefield this time.
7. **Wrap-up**: full test suite + preflight + a delivery report explaining "what changed structurally, why, and how the behavior is guaranteed not to change".

## Performance optimization: measure first, then act

```
Iron rule: any optimization without measurement data is blind guessing.
Flow: measure → locate the bottleneck → optimize one point → measure again and compare → keep it or roll it back
```

### Step 1: Measure

- Define a target metric: which operation, what data volume, how slow it is now, how fast it is expected to be (the performance budget).
- Choose the instrument by scenario: the browser Performance panel / Lighthouse (frontend), a profiler (py-spy, cProfile, pprof), slow-query logs, APM, `time` timing for the simplest version.
- Frontend budget reference: Core Web Vitals — LCP < 2.5s, INP < 200ms, CLS < 0.1; for the backend, set a P95 latency target first and talk about optimization afterwards.
- Keep the baseline numbers from before the optimization.

### Step 2: Locate

Follow the 80/20 rule to find the biggest chunk; the usual order for hunting down bottlenecks:

| Layer | Common traps |
|---|---|
| Database | N+1, missing indexes causing full table scans, pulling the whole table at once, long-lived connections held by large transactions |
| Application | repeated computation inside loops, serial work that could run in parallel, synchronous blocking calls to external services, recomputing the same thing with no cache |
| Frontend | bundle size (importing the whole library), duplicate requests, large lists without virtualization, images neither compressed nor lazily loaded |
| Architecture | re-establishing connections on every request, work that should be asynchronous queued synchronously |

### Step 3: Optimize and verify

- Change only one point at a time, then **re-measure with the same metric**, and produce comparison data (X ms before → Y ms after).
- If it does not work, roll it back; do not keep the added complexity for a "feels faster" impression.
- Optimization must not be paid for with correctness/readability: a cache needs an invalidation strategy, async needs failure-path handling, an index needs its write amplification evaluated.

### Reporting standard

An optimization delivery must contain: baseline data → what was changed → re-measurement data → the conclusion (met / not met / next step). A report that only says "I did some optimization" without numbers is not acceptable.

## Checklist

- [ ] The target area is covered by tests before the refactoring
- [ ] The tests are green after every small step
- [ ] The refactoring diff contains no functional changes
- [ ] The performance optimization has before/after data measured the same way
- [ ] The cache/async approach handles invalidation and failure
- [ ] Out-of-scope problems are recorded as technical debt
- [ ] The full test suite passes

## Common mistakes

- Big refactors without tests, "looks equivalent", but the behavior actually changed.
- New features smuggled into the refactoring PR, so review cannot separate them.
- Optimizing caches/algorithms on intuition, then discovering after measuring that the bottleneck was the network or the database — a wasted round that also introduced cache-invalidation bugs.
- Adding an index without selectivity, dragging down a write-heavy, read-light table.
- Not running regression verification after optimizing — faster, but wrong.
