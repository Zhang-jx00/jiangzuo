# Booklet: Taking over an unfamiliar project (reconnaissance)

> **When to read**: First contact with a codebase; taking over someone else's project; before an L3 project begins; returning to a project you have not touched for a long time.
> **Prerequisite**: Access to the project directory.
> **Output**: A project reconnaissance profile under `docs/jiangzuo/profiles/` (templates/project-profile.md).
> **CRITICAL: read the entire booklet before you act; execute the steps in order, do not skip steps.**

## Principles

The purpose of reconnaissance is to build a "map", not to read all of the code. The goal is to be able to answer: **what this is, how to run it, how to verify it, and where a change will ripple**. Skipping reconnaissance and changing code directly is forbidden.

**Legacy systems** (no tests, no docs, nobody understands them): first establish a "smoke verification" — before changing anything, figure out how to confirm the core features have not been broken (even if that just means manually clicking through the main flow once), and only then talk about making changes.

## Executable steps

1. **Automated scan**: `python <技能目录>/scripts/project_scan.py . --out docs/jiangzuo/profiles/project-profile.md` to get a profile draft. If there is no Python, do the following steps manually.
2. **Identify the tech stack**: read the manifest files in the root directory — `package.json` / `pyproject.toml` / `requirements.txt` / `go.mod` / `pom.xml` / `build.gradle` / `Cargo.toml` / `composer.json` / `*.csproj` / `Gemfile`. Record: language, framework and versions, key dependencies (ORM, state management, UI library).
3. **Directory structure**: look at the root and `src/` (or the sibling main code directory) one to two levels deep, and write a one-sentence responsibility for each top-level directory. Identify the layering pattern (e.g. controller/service/model, pages/components/api). For a monorepo, identify the stack and commands of each package/app (`apps/*`, `packages/*`) separately.
4. **How to start and build**: search in order — the README's Quick Start → package.json scripts / Makefile / pyproject scripts → `.github/workflows/` or other CI configuration. Once found, record the commands into the profile (e.g. `npm run dev`, `uvicorn app.main:app --reload`).
5. **How to test**: find the test directories (`tests/`, `__tests__/`, `*.test.*`, `*_test.go`) and the test commands (`npm test`, `pytest`, `go test ./...`). **Run the tests once to confirm they pass**, and record the baseline result. If they cannot be run, record the reason truthfully as well — that itself is an important finding.
6. **Configuration and environment**: find `.env.example` / `config/` / `docker-compose.yml`. List which environment variables and external services (database, cache, third-party APIs) are needed to run.
7. **Key call chain**: pick one core flow (e.g. "user submits an order") and trace it from the entry point: route → controller → service → data layer. The purpose is not to memorize it, but to know "which layers a change to X passes through".
8. **Project conventions**: look at 2-3 existing files of the same kind (e.g. an existing set of endpoints, a component), and note the naming style, error handling approach, comment density, and how tests are written. **Your new code must look like this project's code.**
9. **Recent activity**: use `git log --oneline -20` to see what has been done recently; if there is a `CHANGELOG` or `docs/`, skim it.
10. **Write to disk**: fill the above into templates/project-profile.md and save it under `docs/jiangzuo/profiles/`. Report your understanding of the project to the user in three to five sentences and ask them to correct it.
11. **Standing standard**: if `docs/jiangzuo/constitution.md` does not exist, create it following templates/definition-of-done.md — write the "gate every change must pass" as executable commands (test commands, build/lint commands, contract-sync requirements, reporting requirements). It is used on top of the per-task acceptance criteria, and the delivery gate `ship_check.py` checks that it exists and is filled with 3 entries.

**What to do when it will not run** (this is itself part of reconnaissance, do not skip it):
1. Read the complete error message and determine what is missing: dependencies, environment variables, database, port, versions.
2. Check item by item against `.env.example` and the README's Quick Start section.
3. Dependency versions do not match → reinstall per the lock file; the database will not connect → first confirm the service is running and the connection string is correct.
4. Still not up after 30 minutes: summarize the steps already tried and the errors, then ask the user/team; do not grind on it endlessly.
5. Regardless of the outcome, record the blocker into the reconnaissance profile — "the project currently does not start" is an important fact.

## Criteria for completed reconnaissance (able to answer all of them)

- [ ] Can state the tech stack and the key versions
- [ ] Can give the exact command to start the project (and have actually run it successfully, or explained why it could not run)
- [ ] Can give the exact command to run the tests (and have actually run them once)
- [ ] Can state the code layering and at least one key call chain
- [ ] Can list the required environment variables and external dependencies
- [ ] Can state 2-3 characteristics of the project's code style
- [ ] The standing standard `docs/jiangzuo/constitution.md` has been created, or its existence confirmed
- [ ] The reconnaissance profile has been written to disk

## Examples

**A good reconnaissance report**:
> This is a project with a React 18 + Vite frontend and a FastAPI backend. The frontend starts with `npm run dev`, the backend with `uvicorn app.main:app --reload`; tests use pytest (currently 42, all green) and vitest (3 skipped, reason pending investigation). The layering is router → service → repository, the database uses SQLAlchemy with Alembic migrations. The user order flow: `app/api/orders.py:submit_order` → `services/order.py:create` → `repositories/order_repo.py:insert`. A local Postgres is required, the connection string is in `.env` (see `.env.example`). The reconnaissance profile is saved at `docs/jiangzuo/profiles/project-profile.md`; there are two points I did not understand and want to confirm with you: ...

**A failed reconnaissance**:
> "OK, I will add this feature." (Never ran the project, does not know the test command, never looked at the existing code style, and starts writing right away.)

## Common mistakes

- Claiming to "understand the project" without getting it running and without having run the tests once.
- Ignoring `.env.example` and only discovering missing environment variables after the code is written.
- Treating generic framework knowledge as project facts ("an Express project is surely organized like this") — everything defers to what you actually read.
- Writing the profile and then abandoning it, never returning to update it in the subsequent L2/L3 phases.

## Wrap-up red lines (reconnaissance complete ≠ allowed to start coding)

- Go back to the "Criteria for completed reconnaissance" above and answer each item yourself; any item you cannot answer is one you have not yet gotten clear, and do not get by with a "roughly clear".
- The start command and the test command must have **actually been executed** and left output behind — having read the README does not equal having run them.
- Write the profile to disk (`docs/jiangzuo/profiles/`), and explicitly write out "what I have not verified and which parts are guesses".
- When the documentation and the code disagree, the code is authoritative, and record this discrepancy in the profile (it is usually the next pitfall).
- During reconnaissance, do not touch business code; if you want to make changes, present a plan first and let the user make the final call on the scope.
