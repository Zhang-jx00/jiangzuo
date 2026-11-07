# Booklet: Frontend Pages and Interactions

> **When to read**: When writing any frontend page, component, or interaction logic, or doing frontend-backend integration.
> **Prerequisite**: Requirements confirmed; visual direction settled (if unsure, read ui-design.md first to confirm preferences).
> **Output**: Runnable pages/components with all four states complete and integration passed.
> **CRITICAL: read the entire booklet before starting; execute the steps in order, do not skip steps.**

## Principles

**Reuse first**: If the project already has a component library, request wrapper, state management, or utility functions, use them; first find the closest existing implementation in the project and write yours following it. Your code should look like this project's code.

## Executable steps

1. **Find a reference**: Find the most similar existing page/component in the project (copy a list page from a list page, a form from a form) and see how it organizes files, names things, and calls APIs. Only create something new following the project scaffold conventions when no reference exists.
2. **Component decomposition**:
   - One component, one responsibility; consider splitting once it exceeds ~300 lines or a third level of indentation appears.
   - Split signals: recurring UI blocks, state+view tangled and hard to read, logic that needs separate testing.
   - props are the component's contract: spell out required/optional/defaults; do not pass a pile of boolean switches to piece behavior together.
3. **State management**:
   - Keep **server state** (lists, details) separate from **client state** (modal toggles, form drafts); for server state, prefer the project's existing request/cache layer (e.g., TanStack Query, Pinia store, RTK) — do not hand-copy it into useState.
   - Put state in the smallest common parent that needs it; do not scatter it globally.
4. **Request layer**: Go through the project's unified request wrapper (interceptors, error handling, and token injection all live there); do not write raw fetch/axios for new APIs.
5. **All four states complete**: every data view must have—
   - **Loading state**: skeleton screen or loading, not a blank screen
   - **Empty state**: guidance copy when there is no data ("No orders yet, place one?")
   - **Error state**: a retry entry point when a request fails, not throwing the exception in the user's face
   - **No-permission state**: hide or prompt according to the project's permission rules
6. **Forms**: validation rules consistent between frontend and backend; error messages right next to the field; disable the button during submission to prevent duplicate submits.
7. **Integration**:
   - Contract first (api-design.md): mock against the contract first, then switch to real APIs.
   - During integration, open the network panel and verify: request URL/params/headers, response structure, status codes, timing.
   - Where things do not match, fix the code **and write back to the contract**; the frontend is forbidden from quietly adapting to wrong fields.
8. **Verification**: Actually exercise every acceptance criterion in the browser, including edge cases (empty list, overly long text, offline, slow network). No new errors or warnings in the console.

## Performance and Accessibility Awareness (do these in passing while coding)

- First-screen vigilance: route-level code splitting (lazy-load large pages), image lazy loading, on-demand imports for icon and similar libraries; do not bundle entire libraries.
- Accessibility baseline: form controls have associated labels, meaningful images have alt text, body text contrast ≥4.5:1, interactive elements reachable by keyboard.

## Checklist

- [ ] Used the project's existing component library/wrappers; did not reinvent the wheel
- [ ] File naming and directory placement match project conventions
- [ ] All four states (loading/empty/error/no-permission) are handled
- [ ] Form validation and duplicate-submit prevention done
- [ ] Integration verified requests and responses; contract written back
- [ ] Actually clicked through every acceptance criterion + edge cases in the browser
- [ ] No new errors in the console

## Success / Failure Examples

**Good**: The new list page reuses the existing `DataTable` component and the `useListQuery` wrapper, done in 30 lines, with the four states consistent with the rest of the site.
**Bad**: Pulled in a second UI library "because it looked nice", hand-wrote the list logic all over again, blank screen while loading, and the page crashes outright when an API errors.

## Common mistakes

- Testing only the happy path: the page crashes or falls apart when the API returns 500, the list is empty, or text is overly long.
- Copy, colors, and magic numbers hardcoded in components instead of going into constants/config.
- State hoisted to global causing full-page re-renders on refresh, or local state that should be global not being global.
- When integration reveals field mismatches, the frontend papers over them layer by layer with `res.data?.item?.name ?? ''` — the root cause is in the contract; fix it in the contract.
- Performance traps: large lists not virtualized, list items using index as key, creating new objects in render and passing them to memo components.
