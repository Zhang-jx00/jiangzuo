# Booklet: Security Checklist

> **When to read**: features involving login/registration/permissions/payment/file upload/external input/third-party calls; pre-launch self-checks; whenever the user mentions "security".
> **Prerequisite**: None.
> **Output**: code that passes the security checks; a list of issues found.
> **CRITICAL: read the entire booklet before you start; execute the steps in order, do not skip steps.**

## Core mindset

Security is not a patch applied before launch; it is a hook at every stage: think through the permission model at the **design stage**, handle input and output at the **coding stage**, run through the checklist at the **review stage**. Default assumptions: all external input is malicious, and every user will try to access other people's data.

## Injection

- **SQL injection**: always use parameterized queries/ORM; string-concatenated SQL is forbidden. When concatenating table names/column names/sort fields, use whitelist mapping, because parameterization cannot cover them.
- **Command injection**: avoid assembling shell commands; when you must execute one, use the argument-array form (which does not go through shell interpretation).
- **Path traversal**: filter `..` and absolute paths from filename/path parameters; the landing path must stay within the designated directory.

## Authentication and sessions

- Store passwords as hashes using bcrypt/argon2; **never store plaintext, never store MD5/SHA1**.
- Failed logins have attempt limits/CAPTCHA (to prevent credential stuffing); sessions have expiration times; logout must truly invalidate.
- JWT: verify the signature and expiry; re-verify the password for sensitive operations (password change, payment); tokens never go in the URL.
- The policy for invalidating old sessions/tokens after a password change must be explicit.

## Privilege escalation (the category most often missed)

For every endpoint that requires login, answer two questions before writing code:
- **Horizontal escalation**: can user A swap the id in the URL/request for B's resource? → the query must carry an ownership condition (`WHERE id=? AND user_id=?`), validated server-side.
- **Vertical escalation**: can an ordinary user call admin endpoints? → roles/permissions are validated server-side; hiding menus in the frontend does not count.
- Make object-level permission checks a unified dependency/middleware; do not rely on each endpoint remembering on its own.

## XSS and CSRF

- Escape user content when outputting it to the page, or use the framework's default safe rendering; inserting user input directly via `innerHTML` is forbidden.
- For rich text use a whitelist-based sanitizing library (bleach, DOMPurify and the like).
- Configure the CSP header according to the project's current state; at minimum, forbid inline scripts and execution of untrusted sources.
- Endpoints that change data need CSRF protection: SameSite Cookie / CSRF token (SPA + Bearer token may be exempt, but confirm).
- Configure CORS by domain whitelist; endpoints beyond public read-only **do not use `*`**; credentialed requests must explicitly list the origins.

## Sensitive data and secrets

- Secrets and connection strings go only into environment variables/secret management services; **never into code, never into git in full**.
- Run preflight.py's secret scan before every commit; if an already-committed secret is found: **revoke and rotate it immediately** (changing the code does not delete history; treat the leak as having happened).
- Log redaction: passwords, tokens, phone numbers, ID numbers, bank card numbers never appear in full.
- Responses must not leak internal fields: hashes, internal flags, other users' fields.
- **Audit logs**: sensitive operations (password change, permission change, payment, data deletion, bulk data export) are recorded separately — who, when, on what, with what result — stored apart from ordinary business logs, and business code must not be able to tamper with them.
- File upload: type whitelist + size limit + renamed storage + never placed in executable directories + never trust user-supplied filenames.

## Dependencies and supply chain

- Before introducing a new dependency, glance at: maintenance activity, weekly downloads, known vulnerabilities (`npm audit` / `pip-audit` / `cargo audit`).
- Commit the lockfile; upgrade periodically; do not introduce a large dependency "just for one small function".

## Checklist (go through item by item whenever the change involves external input/permissions)

- [ ] All SQL parameterized
- [ ] Every resource endpoint has passed the horizontal-escalation question
- [ ] Admin endpoints have passed the vertical-escalation question
- [ ] Password hashing algorithm compliant
- [ ] User content output is escaped/sanitized
- [ ] Uploads have type/size/storage-path restrictions
- [ ] Logs and responses contain no sensitive values
- [ ] No newly added hardcoded secrets (preflight.py passes)
- [ ] New dependencies audited
- [ ] Error messages do not leak stacks/SQL/paths externally

## Common mistakes

- "The admin backend is on a subdomain, no one will find it" — do the permission checks anyway.
- Escaping only at the rendering layer, while the JSON returned by the API is inserted straight into the DOM by the SPA.
- Storing tokens in localStorage and never expiring them.
- Fixing a leak merely by "changing the secret in the code" — the old secret must be revoked.
- Upload endpoints trusting the `Content-Type` header — it is filled in arbitrarily by the client.
