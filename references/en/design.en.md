# Booklet: Technology Selection and Architecture Design

> **When to read**: Choosing a tech stack for a new project; adding new modules or new services to an existing system; before a major refactor; when the user asks "how should this be designed".
> **Prerequisite**: Requirements already clarified (requirements.md); initial codebase survey done (onboarding.md).
> **Output**: Technology selection conclusion, layering and module-responsibility diagram, ADRs written to disk (templates/adr.md), a design plan confirmed by the user.
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip steps.**

## Principles

The principle of design is **good enough yet evolvable**: start with the simplest structure that meets the currently explicit needs and leave room for change, but do not pile up abstractions for an imagined future. Write every significant trade-off as an ADR — you six months from now, and whoever takes over, will thank you for this record.

## Executable steps

### 1. Constraint inventory

First list the hard constraints: the existing tech stack (reuse it if it can be reused), team familiarity, deployment environment, performance requirements, deadline. Constraints take precedence over preferences.

### 2. Technology selection (when there is room to choose)

Use a comparison table with **at least 2 candidates**; a single candidate does not count as a selection:

| Dimension | Candidate A | Candidate B |
|---|---|---|
| Fit with requirements | | |
| Compatibility with the existing stack | | |
| Ecosystem and community activity | | |
| Learning cost / team familiarity | | |
| Operations cost | | |
| Main risks | | |

Give a recommendation + a one-sentence reason, and hand the decision to the user (HARD-GATE rule 4).

### 3. System layering and module responsibilities

- Draw the layering (a text diagram is fine): entry layer (routing/UI) → business layer → data layer → external services.
- Define each module's responsibility in one sentence; **a module whose responsibility cannot be stated in one sentence is the signal that it should be split**.
- Make the dependency direction explicit: upper layers may depend on lower layers; the reverse is forbidden. Modules communicate through interfaces/contracts, and do not covertly reach into each other's internal data.

### 4. Key flows and data flow

Pick 1-3 core flows (e.g. placing an order, logging in) and write clearly how the data flows, who writes and who reads which tables/state, and what to do when something fails.

### 5. Contracts and models

- Interface contracts → hand off to api-design.md; write templates/api-contract.md to disk.
- Data models → hand off to database.md.

### 6. Design confirmation gate

Explain the plan to the user (plain language + a structure diagram / bullet list); **coding starts only after confirmation**. When explaining, highlight: why it is divided this way, what the biggest risk is, and which part may need to change later.

### 7. Writing ADRs to disk

For every major trade-off (technology selection, layering pattern, third-party services, data consistency approach), write one templates/adr.md entry to `docs/jiangzuo/adr/`.

## Project type adaptations

| Type | Design considerations |
|---|---|
| Web full-stack | Frontend-backend contract first; frontend state-management selection (server state and client state kept separate); SSR/SPA decided by requirements |
| CLI tools | Argument design (`--help` is the documentation); output for humans to read, `--json` for machines to read; agreed exit codes |
| Desktop/mobile | Offline and sync strategy; platform differences; decide packaging and distribution up front |
| Browser extensions | Minimal permissions; content/background communication boundary; store review rules |
| Scripts/automation | Idempotent (running it twice causes no trouble); dry-run mode; resumable after a failure |

## Reuse ladder (before writing any new code, go top-down and stop at the first row that holds)

| Level | Ask yourself | What to do when it holds |
|---|---|---|
| 1 | Does this thing have to exist? | Do not do it; explain why (the user wants the result, not this feature) |
| 2 | Is there already a similar implementation in the repo? | Reuse or tweak it; **do not write a second copy** |
| 3 | Can the standard library do it? | Use the standard library |
| 4 | Can the framework/platform's native capabilities do it? | Use native capabilities (native HTML controls, DB constraints and unique indexes, framework middleware, ORM built-ins) |
| 5 | Can an already-installed dependency do it conveniently? | Use the installed dependency; do not introduce a new one |
| 6 | Can it be done in one line? | Then it is one line |
| 7 | None of the above holds | Write a minimal working implementation + one small test that can fail |

- **You must state which level you stopped at** — one line in the task plan or delivery report is enough: `Reuse ladder: stopped at 4 — used the native date control, did not introduce flatpickr`. If you cannot produce this line, it means you never walked the ladder.
- The ladder only governs "whether to write and how much to write"; it **does not cut down** input validation, error handling, security, or accessibility: these are not "excess code" and are not among the things that may be omitted.
- The ladder must not be used to bypass requirements: the level-1 "do not do it" must go back to the user for confirmation; do not cut features on your own initiative.

## Complexity self-check (over-engineering alarm)

If any of the following appears, step back and simplify:
- [ ] You built an abstraction layer / plugin system in advance for requirements that "might come later"
- [ ] Three layers of wrapping around a single implementation
- [ ] More configuration options than users
- [ ] A simple CRUD designed as event-driven microservices

## Legacy systems and third-party dependencies

- **Legacy system rework**: first lock in existing behavior with characterization tests, then change the structure; for new features prefer "add new rather than rewrite" (the strangler-fig approach — new code goes down new paths, old modules migrate step by step on the tech-debt cadence); do not both migrate old code and add new code in a single change.
- **Before introducing a third-party service/SDK, run the three checks**:
  1. License: is commercial use compliant (beware of copyleft licenses of the GPL kind)
  2. Activity: commits/releases within the past six months, issues receive responses
  3. Known vulnerabilities: `npm audit` / `pip-audit` / CVE search
  Write the conclusions of the three checks into the ADR's alternatives table.

## Checklist

- [ ] The selection has a comparison table and a recommendation rationale, and the user has signed off
- [ ] All new code carries a reuse-ladder conclusion (stopped at level N, see the table above)
- [ ] Every module's responsibility can be stated in one sentence
- [ ] The dependency direction has no cycles
- [ ] Data flow and failure paths of core flows have been drawn out
- [ ] Interface contracts and data models are settled
- [ ] ADRs have been written to disk
- [ ] The user has confirmed the design plan

## Common mistakes

- Giving the user only one candidate to "confirm" — that is not a choice, it is a notification.
- Going straight to your favorite technology without a constraint inventory.
- Drawing five layers but being unable to state each layer's responsibility.
- Skipping the design confirmation gate — "I designed it following best practices" is not what the user asked for.
- Decisions existing only in chat logs, with no trace to be found in the codebase.
