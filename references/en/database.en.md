# Booklet: Database Design and Changes

> **When to read**: when designing table schemas, changing fields, writing migrations, correcting data, or investigating slow queries.
> **Prerequisite**: the business model has been thought through (design.md).
> **Output**: reversible migration scripts, a verified table schema, updated models/docs.
> **CRITICAL: read the entire booklet before taking action; execute the steps in order, do not skip steps.**

## Principles

Database changes are **the operations most likely to cause irreversible loss**. Three iron rules: **every change goes through a migration script; every migration can be rolled back; destructive operations must be confirmed by the user**. Hand-editing the database directly to get things done is forbidden.

## Table design

- Naming is consistent with the project's current conventions (plural/singular, snake_case); the same meaning uses the same name across the whole database (`user_id` is called this in every table).
- Every table must have: a primary key, creation time `created_at`, update time `updated_at` (tables with soft deletion add `deleted_at`, provided soft deletion has been confirmed as intended).
- Constraints are built for real in the database: unique constraints (to prevent duplicates), foreign keys or reference integrity guaranteed at the application layer, NOT NULL constraints set according to the business truth — "nullable everywhere" is a sign the design was not thought through.
- Indexes: build them for known query paths (columns involved in WHERE / JOIN / ORDER BY); unique indexes paired with business constraints; **do not build indexes for queries that do not exist**.
- Amounts use integers in the smallest unit or DECIMAL, never FLOAT/DOUBLE.
- All times are stored in UTC and converted to the user's time zone in the presentation layer; time fields uniformly use the `_at` suffix with consistent meaning.
- Status fields use a finite set of enumerated values; write the value domain into comments/documentation.

## Change process (followed for every table change)

1. **Confirm the current state**: `\d table` / `SHOW CREATE TABLE` / read the model definitions; see the current state clearly before acting.
2. **Write the migration script**: use the migration tool the project already has (Alembic / Flyway / Prisma Migrate / Django migrations); if the project has none, establish a conventional directory `migrations/NNN_<描述>.sql` with incrementing numbers.
3. **Every migration comes with a rollback**: a down script or compensating SQL. For changes where a rollback cannot be written (e.g. dropping a column), the rollback plan is "restore from backup", and this must be stated explicitly in the plan.
4. **Assess the impact**: for large tables, consider table locking and duration when adding columns/indexes (PostgreSQL adds indexes with `CONCURRENTLY`; MySQL large-table changes use online DDL or pt-osc); write the row-count estimate into the delivery notes.
5. **Destructive change list — must be confirmed with the user first**:
   - DROP TABLE / DROP COLUMN / TRUNCATE
   - UPDATE / DELETE without WHERE, or whose conditions may match all rows
   - Tightening constraints (NOT NULL, unique) may make existing data fail
   - Changing field type/length may truncate
6. **Verify**: the migration runs successfully on the local database → the rollback runs successfully → the migration runs successfully again; affected queries are actually executed to confirm; all related tests green.
7. **Synchronize**: update the ORM models/entity classes and the table schema documentation; commit the migration scripts together with the code.

## Data correction

- For a correction script, first run `SELECT` to check the rows that will be affected, then change it to an UPDATE and execute — know how many rows will be affected before writing the UPDATE.
- Wrap in a transaction and trial-run in a test/canary environment first.
- Keep one copy of verification data before and after the correction (export the affected rows).

## Query health

- Give new queries on large tables a quick `EXPLAIN` look: whether an index is used and how many rows are scanned.
- Use cursors for deep pagination (`WHERE id > ?` or keyset); `OFFSET 100000`-style queries get slower the deeper you page.
- Run large UPDATE/DELETE operations in batches (a few thousand rows per batch + an interval between batches) to prevent a long transaction from locking the table and dragging down production.
- Heavy report/export queries: limit the time range, run them on a read replica or as background jobs, and do not block the main business.

## Checklist

- [ ] Changes went through migration scripts, with correct numbering/order
- [ ] Rollback scripts have been written and verified
- [ ] Destructive operations have been confirmed by the user (with chat logs or documents as evidence)
- [ ] Large-table impact has been assessed
- [ ] ORM models match the actual table schema
- [ ] Key queries have been checked with EXPLAIN
- [ ] Table schema documentation has been updated

## Common mistakes

- The table schema was hand-edited locally and the migration was forgotten; other people cannot start the project after pulling the code.
- The migration wrote the up but not the down; when something breaks, the only option is downtime and manual repair.
- Indexes were forgotten for foreign keys / high-frequency WHERE fields; full table scans after going live.
- Soft deletion removed only the main table's rows, leaving orphan data in related child tables.
- An unverified UPDATE was run directly on the production database, and the affected row count exceeded expectations.
