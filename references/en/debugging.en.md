# Booklet: Systematic Debugging (Fixing Bugs)

> **When to read**: any bug, any error message, any behavior that does not match expectations.
> **Prerequisite**: none.
> **Output**: a fix with a clear root cause + anti-regression tests + a bug report (templates/bug-report.md).
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip steps.**

## Iron Rules

```
Do not touch the code before the root cause has been found.
After fixing, you must verify with the original reproduction steps.
```

Guessing at fixes, changing things until they happen to work, being unable to say why it works — all three count as failure, even if the symptom is gone.

## Four-Stage Process

### Stage 1: Reproduce (a stable reproduction is the precondition)

- Write out **deterministic reproduction steps**: what input, what clicks, expected vs actual.
- When it cannot be reproduced stably, gather information first: the complete error message, logs, environment (versions/OS/data), and "what changed between the last time it worked and the first time it failed" (`git log`/release records).
- Record the reproduction rate too ("3 times out of 100 runs" and "always reproduces" are two different diseases).

### Stage 2: Locate (narrow the scope)

- **Read the entire error message**: start from the first line; do not look only at the last one; in the stack trace, start from your own code frames.
- **List 3-5 ranked hypotheses before you start verifying** — grabbing a single hypothesis anchors you to the first explanation that merely sounds plausible. Every hypothesis must be falsifiable: if you cannot say "if it were true, what would I see", discard it or rewrite it into falsifiable form.
- Bisect to narrow down: comment out/skip suspicious code blocks, switch inputs, compare the working and failing environments; each change verifies exactly one hypothesis.
- Add logs/breakpoints: instrument the path "from where it is correct to where it goes wrong", run once, and see at which step the data starts going wrong.
- Check the variable: does this problem **exist all along** (just never noticed), or is it **recent** (look for recent changes: git log, new dependencies, config changes)? For the latter, dig through the diff.

**"It works on my machine" — environment difference checklist** (when it cannot be reproduced locally, check item by item):
- [ ] Do dependency versions match the lockfile? (was the lockfile bypassed during install)
- [ ] Environment variables compared one by one (.env.example, the deployment platform's configuration)
- [ ] Data differences: data volume, dirty data, timezones in the local vs production database
- [ ] Timezone/clock: server timezone, crossing month/year boundaries, daylight saving time
- [ ] Network: proxies, firewalls, intranet domain name resolution
- [ ] Execution identity: file/directory permissions, user differences

### Stage 3: Root Cause (ask down to the mechanism level)

Keep asking "why" until you reach the mechanism level:
> The order amount displays wrong → why? It reads the `price` field → why is the wrong field read? The post-discount amount is stored in `final_price`, and the list API returned `price` → why does the API return the wrong field? A field mapping was missed in the update.

The root cause is "the mapping update was missed", not "the wrong field was written" — fixing the former prevents a whole class of bugs; fixing the latter only repairs this one instance.

- Distinguish: the symptom (wrong amount) / the direct cause (wrong field read) / the root cause (missed mapping update + no field-level test as a safety net).

### Stage 4: Minimal Fix + Verification

- Fix only the root cause, with a minimal diff. The three symptom-papering moves are forbidden: **swallowing errors with try-catch, adding an if to bypass, making the error message vaguer**.
- **Failure circuit breaker (the ≥3 rule)**: if the 3rd fix attempt for the same problem still fails → stop switching tactics, go back to Stage 1 and question the premises — is the reproduction really reliable? Is the root-cause hypothesis itself wrong? Or should this be escalated to a human or the approach changed? A 4th blind attempt is not persistence, it is sunk cost.
- First write a **failing test** to pin this bug (testing.md), then fix it, and the test turns green — the test stays behind as an anti-regression guard.
- Verify fully with the **original reproduction steps**; search the whole codebase for other occurrences of the same pattern ("missed mapping update" — do other APIs have the same omission?).
- Check that the fix introduced no new problems: run the full relevant test suite.

## Bug Report (written to disk as templates/bug-report.md)

Reproduction steps / environment and versions / expected vs actual / root-cause analysis / fix contents and files / verification evidence / impact scope (results of the sweep for similar issues).

## Example

**Failed debugging**: "The page went blank; a component is probably throwing. I'll wrap it in a try-catch and another layer of ErrorBoundary." (No reading of the error, no locating, symptom papering.)
**Acceptable debugging**:
> Reproduce: after clearing the cache, visiting /settings always shows a blank page. The console reports `Cannot read property 'map' of undefined (Settings.jsx:42)`. Locate: `.map` is called directly while `user.permissions` is undefined. Root cause: after this round of API changes, for users without permissions the field changed from `[]` to not being returned at all (backend commit a1b2c3). Fix: the frontend falls back to `[]` per the contract **and** the backend is required to restore the field (the unsynchronized contract change is the real root cause). A test has been written to pin it, verification with the reproduction steps passed, and a site-wide search found the same hazard on the `/profile` page, fixed in the same pass.

## Common mistakes

- Starting to change code without reproducing — "it works on my end", and then you never know whether it has actually been fixed.
- Reading only the last line of the error, skipping the true first cause among the 20 lines above it.
- Changing 3 places at once: when it works you do not know which change did it; when it breaks you do not know which change broke it.
- "It's fixed" but no root-cause explanation can be given — most likely the symptom was papered over, and the problem will resurface elsewhere.
- Not running the full test suite after the fix — "press the gourd down and the ladle floats up" (fixing one problem makes another surface).

## Closing Red Lines (implementation done ≠ ready to deliver)

- Before saying "fixed", you must run the **original reproduction steps** once more and paste the output; if you cannot run them, it is not yet fixed.
- The fix must land at the root-cause layer. Adding a fallback only at the symptom site (try-catch / `?? ''`) does not count as done: either change the upstream together with it, or log a debt entry for "why only this place was changed".
- The same contract / same call shape must be searched site-wide, with the search scope and hit counts written into the bug report; a missed search equals fixing only one spot.
- A regression test must be seen red before being seen green — a test that has only ever been green does not pin the behavior.
- The full test suite must be run and compared against the pre-fix state, confirming no new failures.
