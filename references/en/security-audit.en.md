# Booklet: Whole-Project Health Check and Vulnerability Audit

> **When to read**: the user asks to "find bugs across the whole project / security audit / one pre-launch sweep / get a grip on the risks when taking over a repo";
> or asks to quantify the risks (detection rate, false-positive rate, dependency priorities); or wants SARIF for CI.
> **Prerequisite**: able to read the project directory; already graded (such tasks are usually L2/L3, read-only across the whole repo).
> **Output**: the audit report under `docs/jiangzuo/reports/` (Markdown + JSON, optional SARIF 2.1.0)
> + a "retest-point checklist" + a to-do list sorted by severity; **do not modify any file of the scanned project**.
> **CRITICAL: read the entire booklet before acting; execute the steps in order, do not skip steps.**

## Mindset

Tools handle **exhaustive enumeration and verification of locations**; humans handle **judging whether it can be exploited**. The audit chain's product is "candidate findings + evidence chains",
not "vulnerability verdicts". Treating the tool's 0 findings as 0 risk amounts to outsourcing security to regexes.

Run the entire chain with one command (read-only by default; caching must be enabled explicitly):

```bash
python <技能目录>/scripts/audit_scan.py <项目目录> \
    --md 审计报告.md --json findings.json --sarif results.sarif
```

## Ten-step process

1. **Indexing** (`audit_index.py`): produce a **reproducible** file list per gitignore semantics (path/bytes/content sha1/language),
   with binary and oversized files going into `skipped` for the record. For a large repo, run it once standalone first and reuse the same list in the later steps.
2. **Recon map** (`audit_map.py`): language distribution, entries, HTTP routes, auth boundaries, dependencies and lockfiles,
   external connection points. `auth=false` in the map only means **no auth marker was seen inside this file** — global middleware, gateways,
   and decorators registered elsewhere are invisible to it.
3. **Deterministic coarse screening** (inside scan): streaming line-by-line matching of sink/source, recording only "which file hit which rule".
   Hits inside comment lines, triple-quoted blocks, and string literals **do not count as code** (the `ignore_strings` rule strips literals separately).
4. **Semantic deep-dive**: nearby-line verification only for candidate files (`unless_present`: if whitelists, sanitizing libraries, or owner conditions are nearby, let it pass).
5. **Data flow and reachability** (`audit_graph.py`): source→assignment→concatenation→sink hop by hop, with arguments passed across functions and files,
   sanitization points break the chain and are recorded; BFS from routes/entries decides reachability. **Unreachable ones are kept but marked "not exploitable"** — do not silently delete them.
6. **Independent verification step**: before each finding enters the report, reopen the file and check five items — path exists / sink evidence still matches /
   input controllable / sanitization ineffective / reachable. A location mismatch is **discarded outright and counted**.
   This layer intercepts "a reported file:line number that does not exist"; it complements, and does not replace, the self-doubt loop in `code-review.md`.
7. **Grading**: confidence (high/medium/low) × severity (critical/high/medium/low/info);
   dependency vulnerabilities are sorted by **whether they are actually invoked** (package-name vs module-name differences go through `module_alias`).
8. **Reporting**: Markdown (for humans, with data flows and retest points) + JSON (for machines) + SARIF 2.1.0 (for CI/code-scanning platforms).
   The same issue is deduplicated by fingerprint; hit lines are **redacted first, then entered into the report**.
9. **Human confirmation** (cannot be outsourced): for privilege-escalation, race-condition, payment, and business-rule classes, the tool can only supply suspects.
   Go item by item through the two questions in `security.md`: horizontal privilege escalation (can swapping the id fetch someone else's data),
   vertical privilege escalation (can an ordinary role call the admin endpoints).
10. **Persisting and rescanning**: reports go into `docs/jiangzuo/reports/`; confirmed-to-fix items enter the task plan,
    deferred items enter `templates/tech-debt.md`; large repos use `--cache DIR --incremental` to recompute only changed files
    and their call-chain neighbors (the moment a rule or parser version changes, the cache is invalidated automatically).

## Rule governance (switch to that other booklet before changing rules)

Rule fields, language buckets, "why a rule silently fails to take effect", and the six steps plus supporting evidence for adding/pausing a rule all live in
the **Rule Governance and Engine Cost** booklet (the "add a rule / rule not taking effect / scanning got slower" row in the routing table).
This booklet covers only the three boundaries that people who **use** the chain must know:

- Rules are data (`kind`/`severity`/`cwe`/`sinks`/`sources`/`sanitizers`/`unless_present`/`fix`/`retest`),
  so "what this rule reports" is queryable without reading the engine code.
- Disabled rules also stay in the library with their rationale and measured false-positive counts; when reading conclusions, first check clearly whether it is `enabled: false`.
- Sanitizer lists serve only their own category: `intval/is_numeric` is a convergence for command injection, not for XSS.


## How to read the acceptance (`evals/audit-acceptance.md`)

All three denominators must be examined; missing any one leads to self-overestimation (the numbers and item-by-item lists live in the acceptance records; they are not maintained redundantly here):

1. **Detection rate on the vulnerable corpus** — the corpus was written by the author himself, so "100% / 0%" carries the question-setter's bias,
   and its evidentiary power only reaches "these categories can be detected and safe coding styles can be distinguished".
2. **False-positive count on clean repos** — the first version reported 14 findings on its own repo, all false positives; since v0.30 this was switched to
   three repos I did not write (flask / requests / DVWA) with item-by-item manual adjudication. By the conclusions section and by all output,
   **the two calibers are reported separately**; do not declare a pass using the better-looking one.
3. **The detection denominator provided by the target range** — `dvwa_coverage.py` uses DVWA's module directory names as the answer key
   (a same-directory pass-through reporting a different class does not count as a hit, and only hitting the official fixed variant `impossible.*` does not count either);
   measured at v0.33 it went **7/19 → 10/19**; each remaining MISS must state its reason individually — being vague as "insufficient coverage" equals not writing it.

## Repo roles and scope (judge the role before reading conclusions)

- `repo_role()` decides `library` / `app`: "no routes **and** no startup entry **and** a packaging manifest
  **and** no real page files outside docs/examples" must all hold simultaneously to count as a library; the packaging manifest is judged by the **real file names in the index**
  (looking only at `pyproject.toml` misjudges old libraries that only have `setup.py` as apps). Missing a single condition misclassifies a
  procedural PHP application as a library — DVWA was actually misjudged this way, and **7 true vulnerabilities were swallowed as "not applicable"**.
- On the rule side, `scope: "app"` declares "this rule only counts in app repos" (debug switches, session cookies,
  error echo, CSRF, exception details); in library repos they go into the "not applicable" bucket, **counting neither as vulnerabilities nor as fixed**.
- **Configuration-type** hits under `examples/`, `docs/`, and `tests/` likewise turn into not-applicable;
  **injection-class (capability-type) rules still take effect on these paths** — otherwise the real usages in example code would go unpoliced.
- Both the report and stdout give "N not applicable" with item-by-item reasons; writing only "this one does not matter" without being able to say why is not a judgment, it is muting.
- **Context bucket (different from "not applicable")**: hits falling under `tests/ spec/ fixtures/`, `examples/ docs/ samples/`,
  or with file names like `test_*.py` or `*.test.js`, are still reported, still keep `file:line`, and still enter JSON/SARIF; they just **do not count into the conclusions number**
  — "confirmed findings" is the total, and "of which production code" is the batch you actually need to fix; the criterion goes by path segments and file-name shapes, not by the "test" substring.
  When directory names carry qualifying words, they are **split on `-`/`_` and matched as whole words** (`audit-fixtures` → `fixtures` matches; `latest_posts` splits into
  `latest`/`posts`, neither side matches) — v0.41.0 fixed exactly this: a corpus generator was treated as production code, polluting the clean-repo yardstick.
- **Rule-builtin context conditions (the two conditions are "and"; missing one means it still reports)**:
  `console_when_routeless` = the file has no registered route **and** the hit's ±3 lines are console/raise shapes → `console` (the three traceback emissions in flask/cli.py were classified this way; a service-layer `return "失败: " + str(e)` does not count as console and still reports);
  `optout_params` + role=library + the nearest function's parameters carry a switchable opt-out (verify/insecure/…) → `library_feature`
  (requests' `CERT_NONE` lives inside `def cert_verify(self, conn, url, verify, cert)`, i.e. it implements the caller's option;
  in an **app**, `requests.get(url, verify=False)` does not enjoy this exemption).

## Performance and footprint (who should pay the cost)

The layered cost table, the gating seed only taking sinks, "do not use local machine timing as complexity evidence", and the regex-complexity time-limit lock,
all live in the **Rule Governance and Engine Cost** booklet. Users of the chain only need these three:

- For a large repo, first run `audit_index.py` to produce the list and save it to disk, then `audit_scan.py --index 清单.json` to reuse it;
  use `--cache DIR --incremental` for rescans (the moment a rule or parser version changes, the entire cache is invalidated automatically).
- Benchmark re-run: `python evals/audit-fixtures/bench.py --workdir ../eval-runs/bench --files 1500 --repeat 3`,
  **readings are comparable only on a quiet machine** — with a scan running concurrently, the same code reads +30%.
- Budgets must be set at a position where "it passes now and blocks on regression": a gate that is permanently red is no gate at all
  (`bench.py`'s default budget had never been met since measurements began, which effectively teaches everyone to "ignore red lights").


## What to do about false positives: exemption is an exit, not a mute button

We support all three industry layers (Semgrep `# nosemgrep`, Gitleaks `gitleaks:allow`, Trivy `.trivyignore`),
but **a reason must accompany them; exemptions without a written reason do not take effect** — otherwise false positives merely vanish from the report, invisible to whoever takes over next:

```python
q = request.args["q"]      # jiangzuo:ignore JZ-SQLI-001 该服务只跑在内网批处理，无外部输入
```

```
# .jiangzuoignore（每行：路径模式 规则ID 理由）
tests/fixtures/** JZ-CMDI-001 夹具里的坏写法是故意的，用于回归检出能力
```

- The marker can be placed on **any evidence hop** of a finding (for taint-flow findings the reported line is the sink; humans usually note the reason on the source line).
- The report lists "N exempted (with reasons)" in a separate section and notes "X more exemptions lacking reasons did not take effect".
- A rule that gets exempted repeatedly → the rule itself should be tightened or disabled; go through `--validate` + `enabled:false`,
  and do not rely on piling up exemptions until nothing is visible.

## Common mistakes

- "The scan returned 0 findings, therefore it is safe" — 0 findings only means this rule set did not hit; logic flaws, permission models, and race conditions are not among them.
- Writing `auth=false` straight into the report as a vulnerability without checking global middleware and gateways (the top false-positive source measured in this project).
- Pasting the report without verifying the evidence: every finding in the report must allow opening the corresponding `file:line` on the spot to see that code.
- Reporting "bad usages" in test fixtures, example code, or docs as real code (run `--ignore` first before drawing conclusions).
- Using `--strict` as a CI gate without handling known false positives — a gate that is permanently red is no gate at all:
  `bench.py`'s default 3.0 ms/file has never been met since measurements began; **the budget must be set at a position where "it passes now and blocks on regression"**.
- Treating a guard as a data entry: with `if (isset($_POST['Submit']))` there have been cases of source ≠ flowing into the sink;
  the inline fallback only holds when the source and the sink are on the **same line** (`os.system("ls " + request.args['d'])`).
- Reading words inside strings as variables: the placeholder name `:id` in `prepare('… WHERE id = (:id)')`
  colliding with the variable name `id` can drag the official fixed variant all the way into a reflected XSS. Only recognize each language's explicit interpolation syntax.
- The static graph cannot follow `include/require` with "variable paths" (common in PHP), so true vulnerabilities get marked "not exploitable"; two fallbacks: procedural PHP
  pages count as entry roots, and files with variable-path includes share module-level variables across the same-directory subtree. Upon reading "not exploitable", first ask **whether the graph simply failed to connect**.
- Fixing right after scanning: the audit and the fix must be delivered separately (minimal-change principle); fixes go through normal task grading.
