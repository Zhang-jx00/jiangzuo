# Booklet: Deployment, Environments, and CI/CD

> **When to read**: configuring environments, writing deployment scripts/containers, setting up CI, releasing a new version, or when a user reports "it won't run on my machine".
> **Prerequisite**: knowing how the project runs (onboarding.md).
> **Output**: reproducible environments, releases that can be rolled back, and live services that have alerting.
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip steps.**

## Environment configuration

- **12-Factor principle**: configuration is separated from code — every environment difference (database addresses, secrets, feature toggles) goes through environment variables; the code contains only default development values or error messages.
- Maintain `.env.example`: **every newly added environment variable must be synced into it in the same change**, with explanations (who it is for, its format, where to get the value). The number-one root cause of "it won't run" problems is the example lagging behind the code.
- Environment tiers: dev / test / staging (set one up if conditions allow) / prod; make staging resemble prod as much as possible.
- Secret management: keep secrets out of code, out of git, out of images, and out of CI logs (security.md). When a user reports "it won't run", first check against `.env.example` and the README quick-start section for what is missing.

## Containerization (when the project needs it)

- Dockerfile key points: multi-stage builds to control image size; `.dockerignore` excluding `.git` and `node_modules`; pinned base image tags (do not use `latest`); run as non-root inside the container; declare `HEALTHCHECK`.
- docker-compose for starting local dependencies (db/cache/queue) in one command, with versions pinned.
- Reproducible build artifacts: the lockfile must participate in the build.

## CI (use it whenever you have a code hosting platform)

Minimal pipeline, PRs must pass it:

```
install → lint → test → build
```

- A failure blocks merging; not merging when tests fail is discipline, not preference.
- Cache dependencies for speed (use the lockfile hash as the cache key).
- This skill ships with its own validation that can be added to the pipeline: `python scripts/validate_skill.py .` (this repo's CI already demonstrates it).

## Release

- **No rollback plan, no release.** Before releasing, answer first: "If something goes wrong, how do we go back to the previous version? How long does it take?"
- Go through templates/release-checklist.md item by item: version number, CHANGELOG, migration order (compatibility first, drop later), gradual rollout plan, rollback commands, on-call notification.
- Order of database migrations versus code releases: add columns/tables first (old code stays compatible) → ship the new code → drop old columns in a separate batch. **It is forbidden** to both drop a column and ship new code that depends on it in the same release.
- Watch for 15-30 minutes after release: error rate, latency, core health probes; if anything is abnormal, follow incident.md.
- Version discipline: semantic versioning (breaking changes bump major, features bump minor, fixes bump patch), with tags kept in sync with the CHANGELOG.

## Observability (anything that goes live must be visible)

- Logs: structured (JSON preferred), carrying request/trace ids, written to files or a log service instead of only printed to the console.
- Metrics: cover at least QPS, error rate, P95 latency, and resource usage (CPU/memory/disk).
- Alerts: set thresholds for error rate and latency; **alerts must have someone responding to them** — alerts nobody reads are worse than having none (the crying-wolf effect).
- Health probes: health check endpoints distinguish liveness (the process is alive) from readiness (dependencies are ready).

## Backups and secret rotation

- **Backups**: having a backup policy is not enough — **it only counts as a backup once a restore has been rehearsed**. Periodically perform a real restore from the backup in an isolated environment, and record how long it took and the pitfalls.
- **Secret rotation**: rotate immediately on personnel changes, suspected leaks, and the end of an outsourcing engagement; write the rotation steps into the deployment docs (who has permission to change what, and what needs to be restarted/re-released afterwards) — do not wait for an incident to work it out on the spot.

## Checklist

- [ ] New environment variables have been added to .env.example
- [ ] Secrets exist only in the environment/secret service, not in code or images
- [ ] The build passes locally, the image starts, and the health check passes
- [ ] The CI pipeline is all green and failures block merging
- [ ] The release checklist has been fully gone through, with rollback commands rehearsed (or written out explicitly)
- [ ] Migration and release order confirmed, with no compatibility-window issues
- [ ] Metrics normal during the post-release observation period
- [ ] Deployment docs updated (docs-delivery.md)

## Common mistakes

- The code runs on the developer's machine but not on another one — configuration is scattered all over instead of going into environment variables.
- `.env` was packaged into the image (secrets are distributed with the image).
- Secrets in CI are written in plaintext into the yml instead of the platform's secrets.
- A release without a rollback plan: when something goes wrong, everyone scrambles on the spot.
- "Occasional timeouts" with no alert in place; three months later you find out the disk had been full all along.
