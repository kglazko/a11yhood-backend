# Security Best Practices

Practical defaults for keeping a11yhood secure across backend, frontend, and tests.

## Core Principles
- Least privilege by default; fail closed on auth or validation errors.
- Trust nothing from the client. Re-derive user identity and role server-side per request.
- Minimize data: store only what is required and avoid logging secrets or PII.
- Make secure paths easy: reuse shared helpers/services for auth, database access, and APIService instead of bespoke flows.
- Ship observability: log security-relevant events (auth, role changes, ownership changes, bans) with minimal data.

## Authentication & Session Handling
- GitHub OAuth and dev tokens must be validated server-side; never rely on client-asserted roles or IDs.
- Reject expired or missing tokens with 401; do not downscope to guest implicitly.
- Prefer short-lived tokens; refresh via trusted backend endpoints only.
- Store secrets and tokens in environment variables (not in git). Use `.env.local` for local dev and keep it out of the repo.
- Do not expose Supabase keys or OAuth secrets to the frontend.

## Authorization & RBAC
- Enforce role checks on the server for every mutating endpoint (product submission/edit, management requests, bans, role changes, scraper runs, collection edits, ratings, discussions).
- Re-check ownership on each request (product managers, collection owners, discussion owners) to prevent IDOR.
- Keep authorization logic centralized (services/routers) and avoid per-handler ad hoc checks.
- Default to deny on missing role, missing ownership, or missing product/collection membership.
- Keep a matrix for admin vs. moderator vs. user; do not assume UI gating is sufficient.

## Input Validation & Output Safety
- Validate and normalize all inputs at the edge (pydantic schemas backend; Zod/types frontend). Use allowlists and length limits.
- Reject or sanitize HTML/JS in user-generated content (reviews, discussions). Encode output in UI; never render raw HTML.
- Validate URLs (scheme allowlist https/http, length, no `javascript:`). Avoid SSRF by restricting outbound fetches in scrapers.
- Enforce file/type/size limits for any uploads (avatars, images) and store via trusted storage.

## Data Protection
- Use HTTPS in all environments that handle real data. For dev, treat data as non-sensitive but still keep secrets private.
- Avoid logging access tokens, passwords, or personal data. Redact sensitive fields in logs and analytics.
- Apply least-privilege DB roles; avoid direct Supabase client calls when `database_adapter.py` or services exist.

## Rate Limiting & Abuse Controls
- Rate limit auth endpoints, product submission, management requests, discussions/replies, and scraping triggers.
- Add per-IP and per-account throttles to reduce brute force and spam.
- Consider CAPTCHA or proof-of-work only after accessibility review.

## Transport, CORS, and CSRF
- Use strict CORS allowlists; avoid wildcard origins for authenticated routes.
- Prefer same-site cookies where applicable; if using bearer tokens, scope them to HTTPS and avoid storage in localStorage when possible.
- CSRF: for cookie-backed auth, require CSRF tokens and SameSite=Lax/Strict. For bearer token APIs, reject missing `Authorization: Bearer` headers.

## Dependency & Build Hygiene
- Pin dependencies; run `npm audit`/`npm outdated` for frontend and `uv pip check`/`uv pip install --upgrade` for backend.
- Remove unused dependencies to shrink attack surface.
- Keep build tooling updated (Vite, Vitest, FastAPI, Pydantic) and monitor security advisories.

## Logging & Monitoring
- Log auth failures, role changes, manager changes, bans/unbans, and scraper runs with request IDs and timestamps.
- Do not log full request bodies for auth or user-generated content.
- Add alerts for repeated failures or unusual spikes in management requests, submissions, or scraping.

## Secrets Management
- Never commit secrets. Use env vars and secret stores (GitHub Actions secrets, local `.env` ignored by git).
- Rotate secrets regularly; document rotation procedures.

## Deployment & Infrastructure
- Run backend behind a reverse proxy that adds TLS, rate limits, and secure headers (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy).
- Ensure database access is restricted to application roles and networks; avoid public DB endpoints.
- Back up data securely and test restores; encrypt backups at rest.

## Feature-Specific Notes
- Product management and ownership: always verify manager/admin status server-side before edits or URL additions.
- Collections: enforce ownership for add/remove/edit; ensure private collections return 403 to non-owners.
- Discussions/Reviews: strip scripts, limit length, and rate limit posting; include spam controls.
- Scrapers: validate target URLs, restrict to allowed domains (GitHub, Ravelry, Thingiverse), and avoid arbitrary outbound fetches.
- Activity logging: ensure activity entries do not leak private data (e.g., private collections, emails).