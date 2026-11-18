# Booklet: Rule Governance and Engine Cost

> **When to read**: adding / changing / disabling an audit rule; troubleshooting a rule that "was written but detects nothing"; scans getting slower or memory creeping up;
> before touching any layer of `audit_rules.py` / `audit_scan.py` / `audit_graph.py`.
> **Prerequisite**: you have a real shape in hand (the line of code that should be detected + the line of code that should not be reported), not something imagined from a category name.
> **Output**: rule JSON + `--validate` green + numbers on both the corpus and the range sides + mutation calibration records (red / green once each);
> **do not change the scanned project**, only change this skill repository.
> **CRITICAL: read the entire booklet before acting; execute the steps in order, do not skip steps.**

## Rules are data, and also executable code

- Location: `scripts/audit-rules/*.json` (currently 3 built-in files: injection class / webapp class / crypto and client class).
  Fields: `kind` (taint/pattern/dependency/auth_gap), `severity`, `cwe`/`owasp`,
  `sinks`/`sources`/`sanitizers`/`unless_present`, `fix`, `retest`, `scope`, `ignore_strings`.
- Every rule carries `fix` (how to fix) and `retest` (which command verifies after the fix); **a rule without these two does not count as qualified** —
  the report can only give points of suspicion, it cannot give an exit.
- Coarse screening buckets by **language**: a rule's pattern is only fed to files of the languages it declares;
  if a language has no relevant pattern at all, that file is **not even opened** (this is why large repos can be scanned).
- Buckets also split into **raw / masked** two kinds: by default matching runs on masked lines where "string literals are stripped";
  to recognize writing inside strings (such as JS inside a PHP heredoc, or variables concatenated into HTML) you must judge for yourself which bucket to use,
  **when a hit lands in the other bucket, the rule looks as if it "is not taking effect"**.

## Four pitfalls of "rules silently not taking effect" found in practice (each has a criterion that turns red)

1. **Two built-in files colliding on the same id = the latter shadows the former entirely**.
   The "same id, later wins" in `load_rules()` was originally meant for `--add` user customization; when I added my own rule in v0.37
   I reused the existing `JZ-CRYPTO-001`, and by filename ordering it was eaten by the other built-in one — **the new rule did not run at all**,
   yet it presented as "my regex was written wrong, so nothing was detected" — the whole troubleshooting direction was led astray.
   Criterion: two built-in files colliding on an id is judged an error directly, naming both files; user overriding built-ins is still allowed (the control group stays locked).
2. **A global flag written in the middle of a branch only emits a DeprecationWarning**. Python merely warns on writing like `A|(?i)B`,
   `--validate` still comes out `RULES-OK`, but on another interpreter version it is a `SyntaxError`.
   Criterion: compile-time warnings are escalated to judged errors. **When running the gate, read stderr together — a warning is not "does not matter", it is "has not blown up yet".**
3. **Regex complexity is a hidden functional defect**. A `[^;]*(?:A[^;]*<|<[^;]*A)` on mismatch rescans from every start point = O(n²):
   a 600KB line takes 106 seconds; but the scan path truncates a single line to 4096 bytes, so **you will never see it locally**.
   Criterion: every pattern must take two 200K adversarial lines without exceeding 500 ms (`TestAuditPatternCost`).
   **One shape is not enough**: anchors concentrated at the end and anchors spread across the whole line are two different complexities; only testing each once can catch them.
   The adversarial size must also be **small enough that "even if it truly is O(n²), it goes red in just a few seconds"** — Python cannot interrupt a regex that is already running,
   too large and the "lock" becomes a "hang".
4. **Incomplete source keys miss an entire class of flows**. `$_REQUEST`/`$_COOKIE` are attacker-controlled just like `$_GET`; writing only GET|POST misses them.
   DVWA command injection was first drowned by a "guard treated as entry" false positive and dropped to zero after tightening — what it exposed was a missing key, not over-tightening.
   Criterion: **after the false positives are fixed, go back and check whether the true positives dropped with them** (on the range side, re-test using module names as the denominator).

## Six steps for adding a rule (the order must not be changed)

1. **Get the real shape**: copy "the line that should be detected" and "the line that should not be reported" out of the scanned repo, and read them line by line.
   A shape made up from a category name usually proves only that I can set exam questions, not that I can grade the papers.
2. **Write the negative half-sentence**: every new sink gets a paired "written this way it should not be reported" (GCM / server-issued tokens / plain concatenation).
   A lock that only tests positive cases teaches the action of "reporting more".
3. **`--validate`**: field completeness + every regex compiles + control-character dud detection + id collision detection.
4. **Widen the denominator on the corpus side**: the new rule must enter both the should-detect group and the safe-contrast group of `gen_corpus.py`.
   When a true positive runs into "the answer list does not have it", **widen the list instead of suppressing the finding** (in v0.37 the bundled JS was at the same time dynamic execution).
5. **Re-test on the range side with zero regression**: `dvwa_coverage.py` for main-category detection; flask / requests / self-scan for whether noise did not rise.
   **If you changed the denominator mapping you must declare it yourself** (when I extended cryptography from 001 to 001/002/003 I wrote it into the acceptance record) —
   without writing it clearly, "the detection rate went up" is just changing your own grading standard.
6. **Mutation calibration**: mutate the key fragment of this rule, and the designated test **must turn red**;
   also do one "over-blocking" mutation, and the negative half-sentence must turn red. A calibration that turns red in the wrong place counts as invalid.

## Disabling, exemption, scope: three different exits

- `"enabled": false` + `note` recording the measured false-positive count = **data-backed disabling** (`JZ-HORZ-001` was disabled exactly this way: fixtures 4/4 all false positives).
  To bring it back use `--enable-all`. Disabling is not deletion; the reason must stay in the repo.
- `scope: "app"` = this rule only counts in application repos; in library repos it goes into "not applicable", **counting as neither a vulnerability nor as fixed**.
- Inline `# jiangzuo:ignore <规则ID> <理由>` and `.jiangzuoignore` are the **exits for humans**;
  an exemption without a written reason does not take effect; a rule repeatedly exempted → it should be tightened or disabled; do not pile up exemptions until it becomes invisible.

## Layered cost table (whichever layer you change, you know whose budget it touches)

| Layer | What it does | Cost accounting basis |
|---|---|---|
| Index | one open computes the content sha1 + binary detection | linear in file count |
| Map | languages / entries / routes / dependencies | linear in file count (only manifests and source lines are scanned) |
| Coarse screen | bucket-by-language matching of sink/source | **irrelevant languages: not one is touched; no relevant pattern: the file is not opened** |
| Deep dig | proximity-line verification only on candidate files | scales with the candidate count |
| Data flow | function bodies + cross-file argument passing | **only "candidates ∪ definition files called by candidates" are parsed** |
| Verify | reopen files and verify the five items | scales with the finding count |

Two lessons from practice:

1. **The gate's seed can only be sink hits**. When source hits were also counted as candidates, bare words like `payload`/`body`
   made all 1500 files candidates, and the gate existed in name only. source patterns must carry a shape (`request.`/`req.`/`$_`/`params[`).
2. **Do not use local timing as evidence of complexity**. The same code run once standalone slowed uniformly 3x across all phases, while one of the layers I had not touched at all.
   The regression locks **structural quantities** (`graph_parsed_files` changes only with the candidate count; repo ×4 leaves it unchanged); milliseconds serve only as a reference in the budget.
   Performance optimization can also **silently narrow the capability surface**: gate-type changes must come with a "capability still there" test (cross-file flows, incremental causality),
   and must not come with only a "faster" test.

### The real shape of memory (re-tested in v0.39.1; do not paper over it with old claims again)

- **Gated path** (real repo, most files have no sink): ×6.3 files → **×1.09 memory**, an increment of 0.38 KB/file — already flat.
- **Candidates saturate** (every file contains a sink, the graph layer must fully parse): strictly linear, **15.4 KB/file (peak) / 7.4 KB/file (resident)**.
  This is not a bug; it is the price of "holding candidate text for cross-function analysis". Whether to pay it — first look at the candidate share of the target repo.
- The graph layer's **artifacts carry no source code**: function entries have only `name/file/lang/start/end/params/calls`.
  This has a lock (carrying `body`/`lines` turns red on the spot) — once breached, every delivered JSON/SARIF balloons to repo size.
- **Negative lesson**: once wanted to add a "resident KB/file budget" lock; measurement showed that storing one extra copy of the line tuples moved residency only 7.4 → 9.0 KB/file
  (strings are shared); the threshold could only be set somewhere it would never be stepped on → **removed the lock**, and wrote the conclusion as the two numbers above.
  A lock that is always green is worse than no lock.

## Capability boundary table (what the engine cannot do · why · the cost)

**First separate "boundary" from "defect"**: what follows is **impossible in principle** (static analysis cannot obtain that evidence);
rules written too wide (`preg_replace` treated as dynamic code execution, `error_reporting(E_ALL)` treated as debug leakage,
one `csrf` word in `unless_present` exempting the whole rule) are **fixable defects**, registered in the §11 todo list, **and do not enter this table**.

**Every boundary must be pinned by a minimal fixture** (`TestAuditCapabilityBoundaries` in `tests/test_scripts.py`):
otherwise, once the engine evolves, this table will start to lie — and a lying boundary table is worse than no boundary table.

| Boundary | Why it cannot be done | Cost (what happens if not fixed) | Measured evidence (2026-10-21) |
|---|---|---|---|
| **Absence-type criteria**: brute force / captcha / rate limiting | to prove "there is no rate limit" you must look at **middleware / gateway / WAF** — those are not in the repo ⇒ static scanning cannot obtain this evidence in principle | such conclusions can only rely on human questions (WAF? `limit_req`? gateway?); **engine not reporting ≠ safe** | DVWA `brute/` and `captcha/` modules, **zero findings** |
| **The ambiguity of `//` in JS** (comment / regex literal / division) | single-pass static scanning cannot tell "the `//` inside a regex" from "a comment" ⇒ **both choices under-report**: treating it as code takes real comments for code, treating it as a comment swallows the code on the same line after the regex | we chose "treat as comment" (division is more common) ⇒ **the whole run of code after a regex literal on the same line is missed** (true positives lost) | fixture `var re = /\/\//; var x = request.query['q']; eval(x);` ⇒ **0 findings**; the same line with the regex literal removed ⇒ **1** (true positive) |
| **Cross-request / stored data flows** (stored XSS, cross-file sessions) | taint chains propagate only within a **single file / single function / called function**; "write in → store → read out on the next request → render" requires modeling the **storage medium** (DB / session / file) and the request boundary | the engine **cannot report** such conclusions; a human can only walk the data flow once | DVWA `xss_s/` module **zero findings**; DVWA main-category coverage **14/19**, 2 of the 5 MISSes in this class |
| **"Missing X"-type rules cannot be written as positive patterns** | "uploads **lack** type/size/filename restrictions" is a **negative** judgment; writing it as "a `$_FILES[…]['type']` check appears" gets the semantics exactly **backwards** (that is **having** a type check = the compliant form) ⇒ a negative-type rule either gets a separate "nearby lines lack X" mechanism or the whole rule is not built | narrowing it **introduces new false positives** (E25 measured: a new false positive on DVWA's **fixed tier** `upload/source/impossible.php`, plus 2 more in self-scan) ⇒ **case-by-case A/B is the only valid verification** | when E25 narrowed `JZ-UPLOAD-001`, case-by-case A/B caught it on the spot ⇒ changed to removing that sink from the whole rule |
| **Rules run on the "masked bucket" by default ⇒ string contents are invisible** | rules with `ignore_strings: true` match lines whose **string literals are stripped** ⇒ any pattern that needs to see **inside strings** (the `/e` modifier, code inside heredocs) **never matches** | to recognize it, the rule has to run on the **raw bucket** (`ignore_strings: false`), which would let every sink match inside strings ⇒ the false-positive surface grows ⇒ it can only be registered as a boundary | E25 measured: wanted to keep "preg_replace with `/e`"; only found it because **the positive case stubbornly never reported** ⇒ **"the pattern is written correctly" ≠ "it can match"**; E26 used the masked bucket in reverse (constants become `''`) to single out "pure-constant innerHTML" |
| **Auth / privilege escalation** ("does this action verify permissions") | authorization is a **cross-file / cross-request** property (routes × middleware × resources), invisible from a single file ⇒ the existing `JZ-HORZ-001` shape had **fixtures 4/4 all false positives** ⇒ already **disabled by data** | auth-type conclusions go to human questions (the owner questions in `security.md`); the engine does not carry that blame | `JZ-HORZ-001` `enabled:false` (`webapp.json`); DVWA `bac/` module **zero findings** |

> ✅ **Closed boundary (archived)**: "**sanitizers take effect according to sink context**" —
> E30 handled the shape on **assignment lines** (escaping-type sanitizers take effect in two tiers, **inside quotes / outside quotes**),
> E33 also handled the shape **interpolated directly in a sink call** (context determination hooked to the **sink line**)
> ⇒ **this row is no longer a boundary** (the E22 fixture was retired along with it, replaced by
> the two cases of `TestAuditSqlQuoteInSink`: inside quotes **not reported** / outside quotes **still reported**).
> ⚠️ The remaining boundaries are **all of the "static analysis cannot get the evidence" kind** (absence-type criteria / cross-request / auth /
> masked bucket / JS `//` ambiguity / block-comment boundary) ⇒ **not one of them is "actually doable"**.

**Why these "zero findings" are not defects**: of the 6 rows above, 3 have DVWA modules where **not a single finding was reported**,
but that is **correct** — those holes either need a cross-request view or a middleware view.
**Treating "cannot be reported" straight as "under-reporting" and patching rules will only produce false positives** (`JZ-HORZ-001` came into being exactly this way).

## Common mistakes

- A rule not added is governed by no one; added, no one verifies it → an uncalibrated rule equals an ornament that will never turn red.
- Saying "the lock works" after running the test once: a new lock must first prove **it can turn red** (break the source / revert to the old HEAD implementation), then prove it is green.
- Treating the sanitizer list as omnipotent: `addslashes` cannot stop attribute injection; for command injection `intval` is what converges — a sanitizer only serves its own class.
- Changing the engine without changing the criteria: if you touch bucketing / shadowing / masking logic, the accompanying gates (`--validate`, cost locks) must add one that turns red in sync.
- **Criteria changing color with the interpreter or platform** (caught live in v0.40.0; CI went red 22 times before it surfaced): the index-path lock normalized the "local absolute path" pin
  into the **forward-slash** form, while on Windows the tool output is in the **backslash** form — the two sides never match; this lock never once held on the local machine;
  another asserted the **Chinese wording** of "global flag written in the wrong position", but the wording comes from CPython (3.8 emits a DeprecationWarning,
  3.11 raises re.error, in English) — green locally, red on Linux CI. Standing rule: **compare the pin once in each of the four forms: as-is / absolute / real / forward-slash**,
  and compare only machine-readable artifacts; **messages for humans are generated by this project**, and the two interpreter branches serve only as the fallback.
- Treating "I changed X" as fact: bulk text replacement must print the hit count, and after the change `grep` the target lines to confirm the new values are in there.
- **Todos expire too**: in each of the two rounds, one "debt" treated an old conclusion as the current state — "the memory curve is not flat, pending chunked graph building" (it is flat after gating,
  the real shape is linear 15.4 KB/file at candidate saturation), and "static `require_once` pending precise edge building"
  (function calls had long been resolved repo-wide by name; what remained was only the single cell of "module-level variable sharing across included files").
  **Before touching a todo, first restate its current real scope with code or measurement**; if the scope has narrowed, re-judge it as "demand-driven"; do not do preventive engineering.
- Hard-coded numbers in the report had no gate: rule counts, entry line counts, and CHANGELOG dates all recurred —
  **rules written into the taboo list must become machine criteria, or they will recur all the same**.
