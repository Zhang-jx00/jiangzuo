# Booklet: UI / UX Design

> **When to read**: building a new interface, the user has requirements about "how good it looks / how usable it is", visual walkthroughs, or an existing interface is being criticized.
> **Prerequisite**: visual preferences have been confirmed (see Step 1).
> **Output**: interfaces with a unified style + a record of passing the walkthrough.
> **CRITICAL: read the entire booklet before starting; execute the steps in order, do not skip steps.**

## Step 1 is always: confirm visual preferences (HARD-GATE)

Ask three questions before starting, giving options with recommendations:

1. **Style baseline**: stay consistent with the project's existing pages (recommended, unless the user explicitly asks for a redesign)? Or is there a reference draft / competitor screenshot? (If there are reference images, look at them first)
2. **Primary device**: desktop-first or mobile-first? If both are needed, how are breakpoints handled?
3. **Expected tier**: good-enough is fine (internal tool), or polish is required (a product facing external users)?

Freestyling without asking = the mistake with the highest rework rate.

## Design system first

- **The project already has design tokens / theme config** (CSS variables, tailwind.config, theme files): follow them strictly; hardcoding color values and font sizes is forbidden.
- **When building from scratch**, define tokens before writing components:
  - Colors: 1 primary color, neutral scale, semantic colors (success/warning/danger/link) + three levels of text gray (primary/secondary/disabled)
  - A font-size ladder of 4-5 steps (e.g. 12/14/16/20/24), with matching line heights
  - Spacing on a 4px grid (4/8/12/16/24/32); **a 5th spacing value never appears on the same page**
  - 2-3 levels each for corner radius and shadows — that is enough
- **Dark mode** (when the project supports it): verify the same token set against both themes, checking contrast one by one — directly inverting colors in dark mode often produces gray text on a gray background.
- **Data display baseline**: numbers right-aligned + thousands separators, units written clearly (¥ / % / items), null values shown as "—" instead of 0 or blank.

## Layout and hierarchy

- Alignment is the baseline: every row of the same list and every field of the same form is strictly aligned.
- Hierarchy is expressed through **font size, font weight, color depth, and whitespace**, not by bolding everything.
- Information density: tool-type interfaces are compact, marketing-type interfaces leave whitespace; clarify the scenario first.
- Responsive: on narrow screens no horizontal scrolling, no overlapping, no truncation of key actions; tables have a fallback on mobile (card style or horizontal scrolling).

## Interaction baseline

- Clickable things must **look** clickable (hover gives feedback, cursor is correct); non-clickable things must not look like buttons.
- Operation feedback is immediate: a response within ≤100ms of a click (loading, button states); long-running operations show progress or skeleton screens.
- Dangerous operations (delete, payment, overwrite) get a second confirmation; the copy states the consequence ("3 files will be deleted, unrecoverable") instead of "Are you sure?".
- Forms: validation close to the field, specific errors ("Invalid phone number format; should be 11 digits"), required-field markers clear.
- Keyboard usable: sensible Tab order, visible focus, Enter submits the form.

## Anti-AI-flavor checklist (avoid looking fake at a glance)

- [ ] No overused purple-blue gradients + no stacked glassmorphism
- [ ] No emoji used as feature icons
- [ ] Unified icon style (same line style / same fill, consistent sizes)
- [ ] No screen-filling ALL-CAPS and no exclamation-mark bombardment
- [ ] Shadows / corner radii / strokes consistent site-wide, not invented by each component
- [ ] Restrained color palette: large areas in neutral colors, primary color as accent, semantic colors only express semantics

## Design walkthrough checklist (go through item by item before delivery)

- [ ] All four states of hover / active / focus / disabled have been designed
- [ ] Empty, loading, and error states have dedicated designs (not blank screens)
- [ ] Extreme data does not break the layout: extra-long titles, 0 items, 9999+, negative numbers, long foreign-language words
- [ ] Contrast meets the standard: body text against background ≥4.5:1 (large text ≥3:1)
- [ ] Spacing / font sizes / corner radii on the same page belong to the same token set
- [ ] Tested on mobile (or the target primary device)
- [ ] Screenshots of key interfaces confirmed with the user before entering batch implementation

## Success / failure examples

**Good**: ask preferences first → user provides competitor screenshots → extract their palette and density → implement with existing tokens → run through the walkthrough checklist → confirm with screenshots.
**Bad**: preferences not asked; AI-flavored purple gradient + emoji icons shipped directly; user: "I said this is for back-office staff, it should be plain."

## Common mistakes

- Only the happy path gets visuals; empty and error states are patched in at launch, and the style does not match.
- Three button corner radii and two primary colors within one page.
- The walkthrough only looks at Chrome maximized, without testing narrow screens or extreme data.
- "I think it looks pretty good" replaces user confirmation.
