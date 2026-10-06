# Jiangzuo (将作)

> A senior full-stack engineer and tech lead, always on duty, packed into one Agent Skill.
> Named after the *Jiangzuo Jian* — the imperial office of construction in ancient China: build by engineering discipline.

[中文文档](README.md) ｜ Compatible with the [Agent Skills open standard](https://agentskills.io) ｜ License: MIT

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

## Coverage (17 on-demand booklets)

Project onboarding · requirements clarification (plain-language confirmation + EARS-style acceptance criteria) · architecture & tech-selection with ADRs · API contracts · frontend · UI/UX design system & walkthrough · backend · database migrations with rollback · security (OWASP mindset) · 4-phase systematic debugging · incident response (stop the bleeding first) · layered testing · pre-commit review · test-guarded refactoring & measured optimization · DevOps (12-factor, CI/CD, release checklist) · living documentation & delivery reports · **skill orchestration** — with user consent, coordinates other installed skills (slides, charts, docs, browser walkthrough, images, web research) through a propose → approve → handoff → verify protocol, with standing authorizations and fallbacks.

## Task tiering (L0–L4)

Quick fix (L1), feature (L2), project (L3), production incident (L4), consulting (L0) — each level gets a proportionate process, with a one-way ratchet: complexity found mid-task upgrades the level, never silently downgrades it.

## HARD-GATE: it asks before it builds

Ambiguous requirements, irreversible operations, new dependencies, design choices that need a human call — the agent **stops and asks**: plain language, ≤3 questions at a time, options with a recommendation, then a "here's what I understood / what's out of scope / what done looks like" confirmation before any code.

## Structure

```
jiangzuo/
├── SKILL.md          # Entry: <500 lines. Core loop, tiering, hard gates, router, anti-rationalization table
├── references/       # 16 booklets (progressive disclosure: read the one for your phase)
├── templates/        # 12 fill-in templates (plans, ADR, API contract, postmortem, delivery report…)
├── scripts/          # 4 stdlib-only scripts: project_scan / preflight / new_doc / validate_skill
└── evals/            # Trigger tests, red tests, task evals
```

## Install

Works with any Agent Skills–compatible client (ZCode / Claude Code / Codex / Cursor / Gemini CLI / OpenCode…):

```bash
# user-level (all projects)
cp -r jiangzuo ~/.claude/skills/        # or ~/.zcode/skills/
# project-level (committed with the repo)
cp -r jiangzuo <your-project>/.claude/skills/
# or via skills.sh
npx skills add <you>/jiangzuo
```

No configuration needed afterwards: any software-development request auto-loads it.

## Design basis

Built from a research pass across 155+ sources and 25 top-star repositories — **every rule is traceable to its source**: see [docs/research-notes.md](docs/research-notes.md) for the "conclusion → source → where it landed" mapping table. Key inputs: the [Agent Skills spec](https://agentskills.io), Anthropic's official skill best practices, arXiv 2608.14036 ("Demystifying Agent Skills" — 65.7% of skill value is procedural anchoring), obra/superpowers (iron-law + anti-rationalization tables), planning-with-files (on-disk plans beat memory), GitHub spec-kit & Kiro (EARS acceptance criteria, gated workflows), and Snyk's ToxicSkills audit (supply-chain safety — hence zero-dependency, auditable, offline scripts).

## Compatibility

- Scripts: Python 3.8+ stdlib only, cross-platform; without Python, every booklet has an equivalent manual checklist
- All scripts are read-only toward your project, never touch the network, and never write outside their own skill folder
- SKILL.md is 222 lines (limit 500); description is 373 chars (limit 1024) and trigger-only — it deliberately summarizes no workflow, so agents read the body instead of shortcutting off the description

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `python scripts/validate_skill.py .` before submitting; CI enforces it.

## License

MIT
