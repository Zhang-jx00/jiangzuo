# Booklet: Backend APIs and Business Logic

> **When to read**: When implementing any backend API, business logic, scheduled task, or message handling.
> **Prerequisite**: The API contract is settled (api-design.md); the data model is settled (database.md).
> **Output**: APIs that can be called through successfully, with parameter validation, error paths, and logging all complete.
> **CRITICAL: read the entire booklet before you start; execute the steps in order, do not skip steps.**

## Principles

**Layer ownership**: The routing layer only does protocol conversion (receiving parameters, returning responses); business rules go in the service layer; data access goes in the data layer. Writing business logic into route functions = untestable = technical debt. Follow the layering the project already has; in a small project without layering, at least separate "routes" from "business functions".

## Executable steps

1. **Find a reference**: Read an existing API of the same kind in the project (same resource type, same read/write pattern) and write following its structure: how exceptions are thrown, how responses are wrapped, how dependencies are injected.
2. **Parameter validation (at the entry, whitelist mindset)**:
   - Validate: type, requiredness, length, range, format, legal enum values.
   - **Whitelist**: accept only known fields; ignore or reject extra fields; do not pass the request body straight through to the model (prevents mass-assignment vulnerabilities).
   - Use the project's existing validation mechanism (Pydantic, Zod, Joi, DTO); if there is none, write a centralized validation function instead of scattering checks through business code.
3. **Business logic**:
   - One function, one intent; split once it exceeds one screen or reaches a third level of nesting.
   - Name business rules in domain language (`can_user_withdraw()`); do not write anonymous boolean expressions.
   - Cross-module calls go through interfaces/services; do not directly touch other modules' tables.
4. **Error handling**:
   - Business errors throw business exceptions (with error codes), which the unified exception handler converts into the error response of api-design.md.
   - **Forbidden**: `except: pass` swallowing exceptions; catching and only logging without handling or rethrowing; returning stack traces to the client.
   - Failures of external calls (third-party APIs, DB) must have a clear failure path: retry (with backoff) or fail fast; a timeout must be set.
5. **Transactions and concurrency**:
   - Wrap multiple write operations (placing an order and deducting stock, transferring money) in one transaction; on failure, roll everything back.
   - Use optimistic locking (version numbers) or row locks for concurrent-conflict scenarios; first think through "what happens when two people submit at the same time".
   - Idempotency: replaying the same request produces no duplicate side effects (paired with the idempotency key in api-design.md).
   - Async tasks and scheduled tasks: must be idempotent + concurrency-protected (prevent duplicate execution) + failure retries with an upper limit and dead-letter records; they must not be silently dropped.
   - The external-call trio: explicit timeout, bounded retries with backoff and a cap, and a degradation plan for failures — calling third parties bare is the source of incidents.
6. **Logging**:
   - Key paths have logs: input summary (desensitized), result, elapsed time, trace/user id.
   - Levels used correctly: ERROR means a human must handle it, WARN means it can recover automatically, INFO is business events, DEBUG is troubleshooting detail.
   - **Never print**: passwords, tokens, full ID card numbers/phone numbers, secret keys.
7. **Performance awareness (do it in passing while coding; optimization is deferred to refactor-performance.md)**: no SQL/HTTP inside loops; paginate list APIs; stream large files and large result sets, do not read them whole into memory.
8. **Verification**:
   - Actually call it through with curl / .http files / project tests: **normal requests + every class of error request (missing parameters, wrong format, no permission, resource not found)**.
   - Verify the log output matches expectations and contains no sensitive information.

## API completion checklist

- [ ] Parameter validation complete (including the whitelist)
- [ ] All error paths implemented and actually tested (not only the success case)
- [ ] Transaction and concurrency safety thought through (what happens when multiple people operate at the same time)
- [ ] Idempotency (anything involving creation/payment)
- [ ] Logs carry context and no sensitive values
- [ ] Permission checks on the server side (security.md)
- [ ] Returned fields match the contract; no internal fields leaked (such as password hashes, or table fields beyond internal ids)
- [ ] curl/tests actually pass, with output pasted into the delivery report

## Success / failure examples

**Good**: `POST /orders` entry validates whitelist fields → service layer `create_order` locks stock, creates the order, and writes the ledger in one transaction → insufficient stock throws `BusinessError(40020, "库存不足")` → the unified exception handler returns the standard error structure → logs record order_id, user_id, and elapsed time.
**Bad**: 80 lines inside a route function: hand-written SQL string concatenation, one try wrapping everything with `except Exception: return {"ok": False}`, no transaction between the stock check and the deduction (two people buying the last item at the same time both succeed).

## Common mistakes

- A blanket `except Exception` that catches everything and returns vague errors — neither callers nor the people debugging can survive.
- Validation done only on the frontend; requests that bypass the page and hit the API directly all get through.
- Letting amounts participate in arithmetic as float.
- Returning the entire ORM object, serializing password_hash and internal_flag out along with it.
- Scheduled tasks without idempotency and concurrency protection: repeated execution, repeated shipments.
