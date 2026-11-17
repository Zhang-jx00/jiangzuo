# Booklet: Production Incident Response (L4)

> **When to read**: a surge of errors in production services, features going unavailable, data anomalies, a flood of user complaints — any moment when "production is on fire".
> **Prerequisite**: you can access the production environment, or you can reach someone who can operate it.
> **Output**: the restored service + a postmortem report (templates/postmortem.md) + action items.
> **CRITICAL: read the entire booklet before you start; execute the steps in order, do not skip steps.**

## Core mindset

**Stop the bleeding first, investigate the cause after.** The only goal during an incident is to restore the service as fast as possible; the root cause investigation comes after the bleeding is stopped. "Fixing while trying" in the production environment is forbidden — every blind change is a new risk.

## Actionable steps

### Step 1: Confirm the impact scope (within 2 minutes)

- Who is affected (all users / some users / internal)? How severe is it (unavailable / degraded / wrong data)? Is it still happening?
- When did it start? (Align the timeline with releases, configuration changes, and dependency changes)
- Tell users/the team the current status in one sentence: "We are handling it; we will confirm the scope of impact at X:Y, and sync progress before Z." — Silence is the worst thing in an incident.

### Step 2: Stop the bleeding (pick the fastest and most stable option by priority)

| Priority | Means | Applies when |
|---|---|---|
| 1 | **Roll back** to the last known-good version | The failure closely follows a release — the default first choice |
| 2 | Feature flag / degradation | When the feature is designed with a switch: turn off the broken feature to preserve the main body of the service |
| 3 | Hotfix the configuration | The configuration is wrong (e.g. a wrong environment variable, a wrong rate-limit threshold) |
| 4 | Forward hotfix | Rollback is not feasible (including data migrations) and the fix is extremely small |

- Every bleeding-stopping action **leaves a trail**: time, operator, command/version, result.
- Destructive database operations (data corrections, rolling back data) must be confirmed by the user/the owner; back up first, then act.
- When the bleeding-stopping actions conflict with each other (a rollback would lose legitimate data that was just produced), stop and get a decision from the owner; do not pick one on your own.

### Step 3: Recovery verification

- Actually walk the core paths end to end (login, place order, payment…… defined by the business), and watch the monitoring metrics fall back to normal.
- Reporting "recovered" to users/the team must come with evidence (a screenshot of the metrics / a liveness probe result), not with "it should be fine now".

### Step 4: Root cause investigation (after the service is restored)

Switch to the four stages of debugging.md. Focus on filling in the questions that are specific to an incident:
- Why did the tests not catch it? Why was there no alert / why did nobody see the alert?
- Timeline: anomaly starts → detected → bleeding stopped → recovered, with the timestamp of every node.

### Step 5: Postmortem (templates/postmortem.md)

- The postmortem targets the incident, not the person: write "what the system was missing", not "who made the mistake" — otherwise nobody will dare to report the next outage.
- Every action item has an owner and a deadline: add the missing tests, add monitoring alerts, add switches, change the process.
- Action items must land in the task plan (docs/jiangzuo/plans/); writing them in the postmortem and stopping there is not enough.

## Discipline during the incident

- Only do operations related to stopping the bleeding; do not do "drive-by optimizations".
- All production operations leave a trail (command, time, result) so they can be replayed afterwards.
- Escalate operations you are unsure about to a human for a decision; do not push ahead anyway.
- Communication cadence: while it is being handled, sync progress every 15-30 minutes, even if the content is "still diagnosing".

## Common mistakes

- Debugging big logic on the spot in the production environment, the more you fix it the worse it explodes (roll back when you should roll back).
- Declaring it over as soon as the bleeding is stopped — without investigating the root cause, the same landmine explodes again in three days.
- Forgetting during the rollback that the database migration is incompatible with the old version, so the service cannot start.
- Turning the postmortem into a blame session, after which problems get "solved" by concealment.
- No monitoring or alerting at all, so users become the first people to discover the incident.
