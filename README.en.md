# Jiangzuo (将作)

> A senior full-stack engineer and tech lead, always on duty, packed into one Agent Skill.
> Named after the *Jiangzuo Jian* — the imperial office of construction in ancient China: build by engineering discipline.

[中文文档](README.md) ｜ Compatible with the [Agent Skills open standard](https://agentskills.io) ｜ License: MIT

---

## What is this

**Jiangzuo** is not a snippet collection — it injects a *way of working* into AI coding assistants. It fixes what raw LLMs lack: they write code fast but without engineering discipline — they change code before reading it, start building from vague requirements, claim "done" without verification, and break unrelated things along the way.

Once loaded, the agent works in every software project through one fixed loop:

```
① Read first → ② Think it through → ③ Then act → ④ Always verify → ⑤ Leave docs
```

And three iron laws:

- **No completion claims without fresh verification evidence.** ("It should work" is not evidence.)
- **No bug fixes without a root cause.** (No patching over symptoms.)
- **Minimal diff, task scope only.** (No unsolicited dependencies, no drive-by refactors.)

## Coverage (20 booklets, read on demand)

| Stage | Capability |
|---|---|
| Onboarding | Take over an unfamiliar project: stack, structure, how to run/test it, call chains, conventions (with a scan script) |
| Requirements | Plain-language idea → clarifying questions → restate in plain language → EARS-style acceptance criteria → half-day task breakdown |
| Design | Option comparison, system layering, module responsibilities, ADR decisions, Web/CLI/desktop/mobile fit |
| Interfaces | REST conventions, unified response shape, error-code system, pagination & rate limits, idempotency, integration contracts |
| Frontend | Reuse the project stack and component library, component/state/request layers, four states (loading/empty/error/forbidden), integration check |
| UI/UX | Preference confirmation, design tokens, layout hierarchy, interaction floor, anti-"AI look" checklist, design walkthrough |
| Backend | Layering & ownership, parameter allow-lists, error handling, log redaction, transactions & concurrency, idempotency |
| Database | Table design, rollback-able migrations, destructive-op confirmation, data corrections, EXPLAIN query health |
| Security | Injection / access control / XSS / CSRF, auth & session, secret management, dependency supply chain (OWASP mindset) |
| **Whole-project audit** | **Read-only scanning chain, ten steps:** index → map → coarse screen → deep dive → taint flows → independent verification → grading → report (MD/JSON/SARIF 2.1.0) → human confirmation → resume |
| **Rule governance** | Six steps to add/change/disable an audit rule, the four "a rule that silently never fires" pitfalls, layered cost model & regex complexity time limits |
| Debugging | Four-phase root-cause debugging: reproduce → locate → root cause → minimal fix + regression test |
| Incidents | L4 production firefighting: stop the bleeding first (rollback > kill switch > hotfix), leave a trail, postmortem, action items |
| Testing | Unit/integration/E2E layering, boundary checklist, test-first (red-green), restrained mocks |
| Review | Pre-commit review: correctness / concurrency / security / performance traps / breaking changes / leftovers (with a check script) |
| Refactor & perf | Test-guarded small-step refactors, measure before optimizing, before/after comparison data |
| DevOps | 12-Factor config, containerization, CI gates, release checklist & rollback plan, observability |
| Docs | Four kinds of docs kept alive, the delivery report's four questions, progress/handover, lessons written back |
| Skill orchestration | With the right context and the user's consent, coordinate other installed skills (slides, charts, docs, browser walkthrough, images, web research): propose → approve → handoff → verify; unavailable skills have fallbacks, standing authorizations supported |

## The security audit chain (zero-dependency, read-only)

A ten-step chain that scans a project **without modifying it** and emits findings you can hand to a human:

```
index → map → coarse screen → deep dive → taint flows → independent verification
      → grading → report (Markdown / JSON / SARIF 2.1.0) → human confirmation → resume
```

- **34 declarative rules** (1 disabled by data) covering injection, access control, XSS, CSRF, path traversal, SSRF, secrets, weak crypto, TLS, command execution, …
- **Zero third-party dependencies, zero network calls**, Python 3.8+ stdlib only — auditable in any environment.
- **Every rule is traceable**: the rule library is data, and the "how to add a rule without it silently not firing" playbook ships with it.

### Measured on real repositories

<!-- current-state:begin -->
DVWA **58 findings / 58 conclusions**, flask 13/1, requests 4/0, self-scan 8/0/8 ｜ DVWA main-category coverage **14/19** ｜ corpus **25/25 & 0/19** ｜ BENCH-OK 4.300 ms/file
<!-- current-state:end -->

- On the DVWA target: **14 of 19** main vulnerability categories are detected; the 5 misses are **capability boundaries**, not false negatives — each one is documented with *why it cannot be done statically* and *what it would cost* (see `references/audit-rule-authoring.md`).
- False-positive rate, judged item by item: **4 / 75 ≈ 5.3 %** on all output, and **0 / 59** for the class that a static scanner can actually remove.
- The rule set is **read-only toward your project** and never writes outside the paths you pass in.

## Task tiering (L0–L4)

Quick fix (L1), feature (L2), project (L3), production incident (L4), consulting (L0) — each level gets a proportionate process, with a one-way ratchet: complexity found mid-task upgrades the level, never silently downgrades it.

## HARD-GATE: it asks before it builds

Ambiguous requirements, irreversible operations, new dependencies, design choices that need a human call — the agent **stops and asks**: plain language, ≤3 questions at a time, options with a recommendation, then a "here's what I understood / what's out of scope / what done looks like" confirmation before any code.

## Structure

```
jiangzuo/
├── SKILL.md          # Entry: <500 lines. Core loop, tiering, hard gates, router, anti-rationalization table
├── references/       # 20 booklets (progressive disclosure: read the one for your phase)
├── templates/        # 14 fill-in templates (plans, ADR, API contract, postmortem, delivery report…)
├── scripts/          # 20 stdlib-only scripts
│   ├── audit-rules/  # Built-in rule library: 34 declarative rules (1 disabled by data)
└── evals/            # Trigger tests, red tests, task evals, micro-tests, release-identity truth (E37)
```

## Install

Works with any Agent Skills–compatible client (ZCode / Claude Code / Codex / Cursor / Gemini CLI / OpenCode…):

```bash
# user-level (all projects)
cp -r jiangzuo ~/.claude/skills/        # or ~/.zcode/skills/  ~/.agents/skills/
# project-level (committed with the repo)
cp -r jiangzuo <your-project>/.claude/skills/
# or via skills.sh
npx skills add <you>/jiangzuo
```

No configuration needed afterwards: any software-development request auto-loads it.

⚠️ **But "auto-load" has conditions**: this skill's own trigger test (24 real sessions, data in `evals/trigger-tests.md`) hits its positive cases in a clean environment, while in environments with other process-heavy skills installed (superpowers, domain suites) the measured positive trigger rate is **2/19**, overall **7/24 = 29.2 %**, with **0 false triggers**. So:

- **Want it to work in every project → name it explicitly**: "use Jiangzuo to fix this bug", or `/jiangzuo`.
- **Want the real ceiling of auto-triggering → remove the competing skills and re-run** (that is a measurement-scope question, not a wording question; it is recorded in the decision log).
- Non-engineering tasks (translation, prose) are not falsely triggered — that is the negative set, 5/5 passing.

## Design basis

Built from a research pass across 155+ sources and 25 top-star repositories — **every rule is traceable to its source**: see [docs/research-notes.md](docs/research-notes.md) for the "conclusion → source → where it landed" mapping table. Key inputs: the [Agent Skills spec](https://agentskills.io), Anthropic's official skill best practices, arXiv 2608.14036 ("Demystifying Agent Skills" — 65.7% of skill value is procedural anchoring), obra/superpowers (iron-law + anti-rationalization tables), planning-with-files (on-disk plans beat memory), GitHub spec-kit & Kiro (EARS acceptance criteria, gated workflows), and Snyk's ToxicSkills audit (supply-chain safety — hence zero-dependency, auditable, offline scripts).

## Compatibility

- Scripts: Python 3.8+ stdlib only, cross-platform; without Python, every booklet has an equivalent manual checklist
- All scripts are read-only toward your project, never touch the network, and never write outside their own skill folder
- SKILL.md body is 201 lines (limit 500); description is 241 chars (manifest entry 290 chars total, 299-char visible truncation budget), trigger-only — it deliberately summarizes no workflow, so agents read the body instead of shortcutting off the description
- **Cross-platform hard constraints, adapted** (measured + vendor docs): Claude/ZCode-family skill manifests truncate the entry at ≈299 chars (this skill's is fully visible); Codex/Copilot silently drop descriptions over 1024 chars (this skill's is 241 — safe); Cursor requires the name to match the directory (`jiangzuo` ✓); `.agents/skills/` is the common project-level directory for Codex/Cursor/Gemini/Copilot

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `python scripts/validate_skill.py .` before submitting; CI enforces it.

## License

MIT
