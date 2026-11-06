# Booklet: Requirements Clarification and Task Breakdown

> **When to read**: whenever the user raises any new requirement, idea, or wish for a change; when the requirement is described colloquially, incompletely, or admits multiple interpretations; before breaking down tasks at L2/L3.
> **Prerequisite**: a basic understanding of the project (if unsure, read onboarding.md first).
> **Output**: a requirements brief in `docs/jiangzuo/briefs/` + a task plan in `docs/jiangzuo/plans/`.
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip any step.**

## Principles

The user's spoken description is the **starting point, not the endpoint**. "Build a search" may hide ten different things behind it. Your job is to clarify the vague idea into a verifiable contract before starting work. Better to ask three extra questions before kicking off than to redo three days of work.

## Actionable Steps

### Step 1: Ask follow-up questions to clarify (if there are ≥2 reasonable readings, you MUST ask)

Check the user's description against the five dimensions below; whichever is missing, ask about it (at most 3 questions per round, offering options with a recommendation):

| Dimension | What to clarify | Example question |
|---|---|---|
| Goals and users | Who it is for, what problem it solves | "Is this list mainly for operations staff or for end users?" |
| Core flow | What the main path looks like | "Does the user pick products first and then fill in the address, or fill everything in on one screen?" |
| Inputs and outputs | What goes in, what comes out | "Should search just match the title, or search the content too?" |
| Boundaries and non-goals | What is explicitly out of scope | "Does the first version need to support mobile?" |
| Constraints | Time, technical, and compliance limits | "Must we use the existing component library, or can we bring in a new one?" |

### Step 2: Restate in plain language and confirm (mandatory for L2/L3)

> What I understand you want is: ____
> What is out of scope this time: ____
> The standard for judging it done: ____
> Is that right? Please point out any discrepancies.

### Step 3: Write acceptance criteria (a three-part set, each item individually verifiable)

Write **results observable from the user's perspective** first (e.g., "after submitting, a success message is seen"); purely technical metrics (response time, QPS) go in a separate non-functional section.

1. **Functional criteria**: write them in EARS syntax, one behavior per item —
   - "When the user enters a keyword and clicks search, the system shall display results matching the title or the content, sorted by relevance in descending order."
   - "When results exceed 20 items, the system shall paginate, 20 items per page."
2. **Boundary and exception criteria**: "When the keyword is empty, the system shall show everything instead of raising an error." "When the search service times out (>2s), the system shall show 'Please try again later' instead of a blank screen."
3. **Verification method**: for each criterion, how to verify it — one command, one operation, one test. An acceptance criterion with no way to verify it is filler; delete it and rewrite.

### Step 4: Break down tasks

- Each task = **which files to touch + what to do + how to verify**, sized so it can be completed within half a day.
- Mark dependency order (which comes first), and flag what can run in parallel.
- Database changes and interface contracts are scheduled before the frontend/caller tasks that depend on them.
- Use templates/task-plan.md to persist the plan to `docs/jiangzuo/plans/YYYY-MM-DD-<名称>.md`, as checkboxes, ticking them off as you go.

### Mid-stream requirement changes (task half done, user changes their mind)

1. **Stop** — do not silently continue on the new idea, and do not leave the old half-finished work abandoned in a heap.
2. Update the requirements brief: what is added, what is discarded, and the impact on already-completed work (reuse or roll back).
3. Restate the new scope in plain language and confirm it again; update the task plan (tick off voided items, add new tasks).
4. Explain to the user "of the completed X, which parts are kept and which are voided"; resume work only after confirmation.

### Step 5: Scope confirmation

Show the task list to the user for review ("Here is what I plan to do: 5 steps in total, steps 1 and 2 first"); enter implementation only after confirmation.

## Checklist

- [ ] The user's original requirement wording has been recorded in the brief (to prevent disputes afterwards)
- [ ] All five dimensions have been asked about or confirmed
- [ ] The user has confirmed the plain-language restatement
- [ ] Every acceptance criterion is individually verifiable and has a verification method
- [ ] Tasks are broken down to half-day granularity, each with a verification command/operation
- [ ] Non-goals are written out explicitly (what will NOT be done this time)
- [ ] The brief and the plan have been persisted to disk

## Example

**User says**: "Build me a search box."

**Bad response**: immediately starting to write `<input>` + calling the API.

**Good response**:
> Confirm three things before starting:
> 1. Search scope: search product titles only (recommended; the existing `/api/items` endpoint already supports the `?q=` parameter)? Or titles plus details?
> 2. Interaction: auto-search after a 300ms typing pause (recommended, better experience)? Or search only on Enter?
> 3. Empty results: show "No matching products found" + a clear button (recommended)?
> I'll go with the recommended options first; the done criteria are: typing "手机" (phone) returns phone-category products, empty results show a hint, and clearing restores the list. Correct?

## Common mistakes

- Starting to code straight from the spoken requirement, and only after finishing discovering the user wanted something else.
- Writing acceptance criteria as "works correctly, good experience" — unverifiable, which equals not writing them.
- Breaking tasks down into "finish the frontend" and "finish the backend" — granularity too coarse to verify one by one.
- Starting work after asking only half the questions, then circling back mid-task for the other half, leaving the context a mess.
- Treating "what the user didn't say" as "what the user doesn't want" — for boundaries you are unsure about, list them and ask.

## Closing red lines (thought it through ≠ the user has confirmed)

- Go back to the Checklist above and tick every item; if even one cannot be ticked, do not enter implementation.
- Ask your follow-ups all in one batch with recommended options, and **stop and wait for the answers as soon as you have asked** — do not keep writing while asking.
- Acceptance criteria must be independently executable by someone else (command/operation + expected result); writing "works correctly" means you did not write them.
- Write out non-goals (what will not be done this time) explicitly, to stop the scope from quietly growing.
- If requirements change mid-stream: stop first, assess the impact, update the brief and the plan, then decide what to continue and what to discard.
