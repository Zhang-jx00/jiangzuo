# Booklet: API Design (HTTP/RPC)

> **When to read**: when designing a new API, modifying an existing API, or when frontend and backend integration turns up mismatched fields.
> **Prerequisite**: system layering has been decided (design.md).
> **Output**: the API contract written to disk (templates/api-contract.md), with frontend and backend both doing their work against the contract.
> **CRITICAL: read the entire booklet before starting work; execute the steps in order, do not skip steps.**

## Principles

An API is a **contract** between frontend and backend. The contract precedes construction: write the contract first (paths, methods, request, response, errors), so both sides develop in parallel and integration has a basis to check against. Changing an existing API is treated as a breaking change and goes through the breaking-change check in code-review.md.

## REST Design Conventions

| Item | Convention | Example |
|---|---|---|
| Resources use plural nouns | No verbs | `GET /orders` ✔, `GET /getOrders` ✘ |
| Actions go in the HTTP method | GET reads / POST creates / PUT/PATCH updates / DELETE deletes | `DELETE /orders/123` |
| Non-CRUD actions use sub-resources or action suffixes | Semantic clarity first | `POST /orders/123/cancel` |
| Hierarchy ≤2 levels | If too deep, use query parameters instead | `/users/5/orders` ✔ |
| Version goes in the path or header | Decide it from the first version | `/api/v1/orders` |
| Naming style unified across the project | Pick one of camelCase or snake_case | Check the project's existing APIs and follow them |
| Times always ISO 8601 with timezone | No mixing in timestamp strings | `2026-10-05T12:30:00+08:00` |
| Money uses smallest-unit integers or string decimals | No floating point | `price_cents: 9900` |

## Response Structure (one unified format for the whole project)

```json
// 成功
{ "code": 0, "message": "ok", "data": { ... } }
// 失败
{ "code": 40010, "message": "优惠券已过期", "data": null }
```

- HTTP status codes express transport-layer semantics (404 resource not found, 401 not logged in, 403 no permission, 422 invalid parameters, 500 server error); the business code `code` expresses business semantics. Do not mix the two.
- Register error codes in segments (e.g., 40xxx for user-related, 50xxx for system-related); build an error code table to prevent duplicates.
- **Forbidden**: returning 200 for all responses and stuffing errors into the body; returning exception stack traces directly to the frontend.

## Pagination / Filtering / Sorting

- Pagination: `?page=1&size=20` or `?cursor=xxx&limit=20` (use cursors for large data volumes); the response carries the total count or the next-page cursor, and **size has an upper limit** (e.g., ≤100) to prevent full-database pulls.
- Filtering: fixed whitelist parameters (`?status=paid`); do not build queries by concatenating arbitrary fields.
- Sorting: whitelist fields (`?sort=created_at&order=desc`).

## Authentication and Permissions

- The authentication method (JWT / Session / API Key) follows the project's existing practice; if there is none, ask the user.
- Every API is explicitly labeled: **public / requires login / requires specific permission**. Start the permission model with RBAC (user-role-permission).
- Write APIs must verify "does this resource belong to the current user?" (horizontal privilege escalation check); verification is done on the server side — hiding things on the frontend does not count.
- See security.md for details.

## Idempotency and Rate Limiting

- POST APIs involving money, inventory, or order creation support idempotency keys (the `Idempotency-Key` header) so that retries do not produce duplicate orders.
- Consider rate limiting (per user/IP) for public APIs and write APIs; at minimum, reserve a place for it in the design.

## Special API Patterns

- **File upload**: small files are uploaded directly via multipart; large files use "presigned URL direct upload to object storage" (the server only issues credentials and does not relay traffic). Must restrict type (whitelist) and size; the filename stored in the database is regenerated on the server side — do not trust the client's original name.
- **File download**: streaming output or short-lived signed URLs; it is forbidden to read an entire large file into memory.
- **Long tasks** (export, batch processing): do not let an HTTP request hang for minutes. Use `202 Accepted + task id` with `GET /jobs/{id}` polling for status (pending/running/done/failed + progress), or a webhook callback; task results have an expiry time.
- **Push (WebSocket/SSE)**: only push event notifications; business logic still goes through HTTP APIs. Agree on a catch-up mechanism for after disconnection and reconnection (incrementally fetch using the last received message id).

## Integration Alignment Checklist (one copy each for frontend and backend, field level)

- [ ] Every field: name, type, nullable or not, example value
- [ ] Error responses: trigger condition and message text for each error code
- [ ] Pagination/sorting/filtering parameter names are exactly identical
- [ ] Format conventions for times, money amounts, and IDs (IDs as strings or numbers — IDs exceeding 2^53 use strings)
- [ ] The contract is written to disk under `docs/jiangzuo/contracts/` and updated in sync whenever the API changes

## Success / Failure Examples

**Good**: for a new API, write the contract first and have the user and the frontend confirm it → both sides develop against mocks based on the contract → during integration, record differences back into the contract.
**Bad**: "the backend finishes writing, and the frontend guesses at the response fields" — every field rename blows things up again.

## Common mistakes

- An API's fields changed without notifying callers or updating the documentation — a breaking change.
- List APIs with no pagination limit, pulling the entire table in one request.
- Boolean fields with three values (true/false/null) and no agreed meaning for them.
- Business error codes assigned ad hoc, causing duplicate conflicts.
- The contract goes stale right after being written and the code becomes the single source of truth — the contract must be changed together with the code.
