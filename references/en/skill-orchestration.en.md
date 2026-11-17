# Booklet: Skill Orchestration (Other Skills in the Orchestration Environment)

> **When to read**: a situation from the skill orchestration table in SKILL.md appears; the user asks for deliverables beyond code (presentations, charts, formal documents, illustrations); real browser verification is needed; you want to use another skill.
> **Prerequisite**: the task goal and the deliverable are clear.
> **Output**: a multi-skill collaboration result that has been authorized by the user and verified, recorded in the delivery report.
> **CRITICAL: read the entire booklet before starting; execute the steps in order, do not skip steps.**

## Positioning and the three principles

Act as the foreman directing craftsmen of every trade: **you are the chief engineer, the other skills are subcontractors**. However good a subcontractor's craft is, you must brief them when handing out the job and you must accept the delivery.

1. **Propose only when appropriate**: propose only when the task truly needs it; do not orchestrate just to show off. When the task can be completed with your own methods and the quality is not worse, do not disturb the user.
2. **Invoke only with approval**: by default every job needs the user's nod; except in scenarios where the user has granted a "standing authorization".
3. **Always verify the output**: a subcontractor's output, exactly like a subagent's output, is "a half-finished piece pending acceptance", not a result.

## The six steps of the coordination protocol (expanded)

### 1. Inventory — know which craftsmen are on site

- The list of available skills is whatever the **current environment actually provides** (the skills listed in the session context); do not assume that something "should be installed".
- Do not guess a skill's capabilities from its name: if you are unsure what a skill does and what its inputs and outputs are, first read its description (the description in its `SKILL.md` or its documentation), then decide whether to propose it.
- Treat "what gear the environment has" as part of the reconnaissance; at the start of an L3 project, jot it into the project profile as the line "可协同技能：……".

### 2. Propose — give the user a choice

Script template (propose the 1-2 most relevant ones at a time; do not bombard):

> This task needs to produce ____. The environment has a ____ skill; I suggest using it to do ____, because ____.
> If not, my fallback plan is ____ (quality/efficiency difference: ____).
> Shall I invoke it? (You can also reply "use it directly next time for this kind of task")

When the user **explicitly names a type of deliverable** ("make it a PPT", "draw an architecture diagram"), that equals authorization for that deliverable; at that point, ask one more question only if the environment has **multiple candidate skills of the same kind** and a choice must be made; otherwise pick the best match directly and explain it.

### 3. Obtain approval — authorization comes in two levels

| Level | Meaning | How it is recorded |
|---|---|---|
| One-off authorization | Covers only this one invocation in the current task | Written into the task plan / delivery report |
| Standing authorization | The user says "use it directly next time for this kind of task / do not ask every time" | Appended to the project's `docs/jiangzuo/learnings.md`: `授权：<情境> → 直接调用 <技能/技能类型>`, and the user is reminded that this record is now in effect |

- **Only the user can grant the scope of authorization.** It is forbidden to "infer default authorization" on your own, and forbidden to extend a standing authorization into unauthorized scenarios (being authorized for "chart skills" does not mean being authorized for "image generation").
- Read the authorization records in learnings once at the start of the task; that is the equivalent of quickly restoring the authorization state.

### 4. Invoke — the handover sheet must be complete

Treat the subcontractor like a newly arrived outsourcing team: explain everything in one go, do not make the other side guess:

- **Goal**: which acceptance criterion of the task this job ultimately serves
- **Context**: relevant file paths, project constraints, style requirements, conclusions already reached
- **Expected output**: format, on-disk path, naming
- **Acceptance criteria**: what counts as passing (checkable items)
- **Off-limits**: what must not be touched; restrictions such as you must not access the network / must not change configuration

### 5. Verify — the delivery must be accepted

- [ ] The artifact really exists and can be opened (file generated ≠ content correct)
- [ ] The content matches the requirement: all items present, no placeholders and no lorem ipsum
- [ ] The data is accurate: spot-check the key numbers against the real data source (precise charts especially require this)
- [ ] The style is consistent: no conflict with the project's existing artifacts / brand
- [ ] No overstepping: nothing in the off-limits zone of the handover sheet was changed

If it fails → send it back for rework with a **specific list of problems**, or switch to the fallback plan. Write the verification evidence (what you ran, what you looked at) into the delivery report.

### 6. Receipt — the four states and the circuit breaker (the only legal reply format for subagents / subcontractors)

When dispatching, you must require the other side to reply with **only** one of the four states, and to attach evidence; free-form text such as "done" is not accepted.
One command pins the work order into a file (diff + the user's original wording + acceptance criteria + verification commands + receipt template),
`python scripts/review_packet.py --root . --out ../review.md --brief "…" --acceptance-file accept.md`
— it only reads and never executes; the verification commands are listed for the human to run.

| State | Meaning | What to do after receiving it |
|---|---|---|
| `DONE` | It is finished; every acceptance criterion has evidence of having been run | Re-run it yourself or look at the artifact before judging (the other side saying "I ran it" is not the same as it having been run); only a pass enters review |
| `CONCERNS` | It is finished but it knows where something is wrong | Hand it back to the user/upstream for a decision, do not absorb it yourself; turn the concerns into answerable questions |
| `NEEDS_CONTEXT` | Information is missing, it can only guess | Stop; list what is missing; **do not pass reasonable guesses off as requirements** |
| `BLOCKED` | There is work it cannot do (permissions / environment / upstream undecided) | Stop; report the blocking point + a workaround suggestion; do not silently downgrade the delivery |

Circuit breaker (hard-coded, not left to on-the-spot judgment):

- The **cap on repair rounds for the same issue is 2**; you must not start a 3rd round on your own — go back upstream with the symptoms, the items already ruled out, and a suggestion for the next step.
  This is the same thing as the "hand back to the user after 3 full rounds" rule in the self-doubt loop of `code-review.md` — two entry points to one rule, consistent in wording.
- Stop the moment it is triggered: the fixes make it worse (the number of regressions rises), files in the off-limits zone must be touched, network access / configuration changes are needed,
  or the other side cannot produce evidence that can be re-run.
- **The work order file is the memory**: append the result of every round to the 「修复轮次」 (repair rounds) table in the work order. After the context has been compressed, **read that file first**
  before taking over, and do not recite from memory — this repository has measured an evidence-collection bias of "treating 'said not done' as the verdict on 'done or not'" (sampling too early leads to a false judgment that a subagent fabricated the work).

## Fallback strategy (always propose with a Plan B)

| Situation | Action |
|---|---|
| There is no matching skill in the environment | Go straight to the fallback plan, do not interrupt the user; note in the delivery report that "installing skill X would improve Y" |
| The user disagrees | Use the fallback, do not keep selling it |
| The invocation fails / the output is unsatisfactory | Send it back once; if it is still unsatisfactory, switch to the fallback — do not grind on it |
| You are unsure whether to propose it at all | Do not propose, finish it with the methods at hand — better to orchestrate less than to stall the task |

## Success / failure examples

**Good collaboration**:
> User: "The feature is done; help me explain it to the team."
> → Inventory: the environment has a presentation skill. → Propose (using the script template, including the "Markdown outline" fallback). → User: "Sure." → Handover sheet: goal — explain the architecture and the demo flow within 15 pages; context — attach the architecture diagram and the interface contract paths; acceptance — it opens, no placeholders, screenshots come from real pages. → Output verification finds that the data on page 8 does not match the actual API response → send it back with specific problems → the revised version passes verification → the delivery report notes "the presentation was produced by the pptx skill and revised through one round of verification".

**Failed collaboration**:
> User: "Make me a chart."
> → Invoked the image-generation skill directly and produced a pretty but purely decorative graphic whose data was made up on the fly.
> Lesson: first distinguish whether the deliverable is an "illustrative diagram" or a "precise data chart" — the former may be produced by image generation, the latter must be produced by a charting skill or drawn in code; choosing the wrong type means rework and a loss of trust.

## Common mistakes

- Invoking without approval — even if you are one hundred percent certain that the user would agree.
- Guessing a skill's capabilities from its name, handing over an empty handover sheet and letting the other side improvise.
- Playing the absentee landlord after the invocation — delivering the subcontractor's output directly as a verified result.
- Bombarding the user with a pile of skills in a single proposal.
- Blocking the task when the other side's skill is unavailable — always carry a fallback in the proposal.
- Treating one-off authorization as permanent authorization, or extending authorization of type A to type B.
- Letting a subagent report "done" in free-form text — there is no legal reply outside the four states; if no evidence is received, treat it as `CONCERNS`.
- Still trying it on your own in the 3rd round on the same issue: the circuit-breaker line is 2 rounds; beyond that you must hand it back upstream, not gamble one more time.
