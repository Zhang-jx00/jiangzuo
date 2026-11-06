# Booklet: Testing Strategy

> **When to read**: when a new feature needs tests, a bug fix needs a regression test, a project without tests needs them backfilled, or the user asks for "tests to exist".
> **Prerequisite**: onboarding (onboarding.md) has confirmed the project's testing framework and how to run it.
> **Output**: tests that run, assert effectively, and guard against regressions.
> **CRITICAL: read the entire booklet before starting; execute the steps in order, do not skip any.**

## Principles

- **Follow the project's current state**: if the project uses pytest, use pytest; if it uses vitest, use vitest; copy the directory layout, naming, and fixture style from the existing tests.
- Tests are a **specification of behavior**: test names speak plain language (`test_order_total_includes_discount`, not `test_1`).
- **First verify things run**: when taking over, run the existing tests once to establish a baseline (how many green, skipped, failing); new tests must not make the baseline worse.

## Layers and ratios

| Layer | What is tested | Quantity strategy |
|---|---|---|
| Unit | pure functions, business rules, boundary calculations | many: fast, stable, pinpoints failures |
| Integration | API layer + database + service collaboration | moderate: at least one per core API |
| E2E | real browser / complete user paths | few: keep only the most critical user journeys |

Legacy projects with no tests: **do not chase full coverage**; start accumulating from "the key logic touched by this change" and "every bug you have fixed".

## Writing a good test

1. **Three-part structure**: arrange (build data/state) → act (invoke the object under test) → assert (verify the result).
2. **Assert behavior, not implementation details**: assert "the returned order total is 90", not "discount() was called three times internally".
3. **One test verifies one thing**: when it fails, you can see at a glance what broke.
4. **Boundary checklist** (run through it for every piece of business logic):
   - empty / null / missing fields
   - 0, negative numbers, extremely large values
   - very long strings, special characters, emoji, multiple languages
   - duplicate submissions / concurrency
   - no permission / resource does not exist
   - external dependency failures (timeout, 5xx, network down)
5. **Use test doubles for external dependencies**: inject or mock network, time, random numbers, and the file system — tests must not depend on real third parties, nor wobble with timezone/date.
6. Be restrained with mocks: mock boundaries you do not own (HTTP, DB), **do not mock the logic under test itself** — a test that mocks away half the business logic tests nothing.

## Test data management

- Build test data **near the test** with constructors/factories (each case carries its own setup and consequences); do not rely on magic data that "happens to exist" in a shared database.
- Tests must not depend on one another, must run in any order, and must be rerunnable individually — a test that is green alone and red in the full run is a liability.
- Inject fixed values for time and randomness (fixed clock, fixed seed); only then can results be asserted.

## Tests first (TDD, when applicable)

For bug fixes and L2/L3 new logic, writing the test first is recommended:

```
写失败测试（红）→ 跑一次确认它失败 → 最小实现（绿）→ 跑确认通过 → 重构（保持绿）
```

- The red test for a bug fix = the reproduction steps turned into code; once fixed, it becomes the anti-regression sentinel.
- **Writing the implementation first and adding tests afterward = delete and start over** (superpowers discipline): a test written after the implementation has run, with the answer already in your head, has no diagnostic value.
- **Which logic must have tests** (do not judge "critical or not" by feel): logic with **branches / loops / parsing (regex, dates, serialization) / money / permissions / concurrency** — when changed, leave at least one test that can fail. If such logic has caused an incident, promote it to a regression sentinel.

## Verification discipline

- A new test **must be seen to fail first** (plant a defect on purpose) before it is seen to pass — a test that has never failed may be a tautology.
- Before committing, run the **full** test suite, not only the tests you just wrote.
- Skipped tests must keep a comment explaining the reason and the conditions for restoring them; silent piling up is not allowed.

## Checklist

- [ ] Used the project's existing framework and conventions
- [ ] At least one unit test per business rule; the boundary checklist has been run through
- [ ] Core APIs have integration tests
- [ ] Fixed bugs have regression tests
- [ ] New tests verified to fail first and then pass
- [ ] Full suite passes (baseline not worse); results pasted into the delivery report
- [ ] No real secrets and no external network dependencies in the tests

## Common mistakes

- Tests assert "no exception thrown means pass" — nothing is verified.
- After mocking, the assertions check the mock's own call arguments, while the business logic goes untested.
- Depending on execution order or shared mutable state: green alone, red in the full run.
- Time-related tests use `Date.now()`, and CI turns red at month-end and month-start.
- Chasing coverage numbers yields many tests with hollow assertions — high coverage, zero confidence.
