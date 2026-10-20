# Security

Development-stage controls for a potential defence-sector pilot. **Not** certified, accredited or approved for
classified or restricted data.

## Access control
Roles are enforced in the API by a single dependency (`require(permission)` in `backend/app/security.py`); the UI only
hides controls for convenience.

| Permission | admin | officer | technician | analyst |
|---|---|---|---|---|
| read fleet, predictions, plans | ✓ | ✓ | ✓ | ✓ |
| audit log / audit-type exports | ✓ | ✓ | | ✓ |
| data ingestion | ✓ | ✓ | | |
| inventory changes | ✓ | ✓ | | |
| propose plans, technician availability | ✓ | ✓ | | |
| approve / reject (recommendations, plans, work orders) | ✓ | ✓ | | |
| run TrustTwin scenarios / simulations | ✓ | ✓ | | ✓ |
| work-order progress (start / complete) | ✓ | ✓ | ✓ | |
| thresholds, users, roles | ✓ | | | |

Decisions require a reason for rejections and requests; administrators cannot change their own role.

## Authentication
Local demo: bcrypt password hashes, HS256 JWT (8 h), sliding-window login rate limit (10 attempts / 5 min per client +
username, per process). Tokens live in `sessionStorage` (cleared when the tab closes).
**Organisation SSO (implemented):** set `AUTH_MODE=oidc` plus `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` and
`OIDC_ROLE_MAP` (`idp-group=role,...`). The API then accepts only IdP-signed bearer tokens (RS256/ES256, verified
against the IdP's JWKS with issuer, audience and expiry checks), maps the token's groups to the most privileged matching
role, provisions the user just-in-time, re-applies the role on every request (the IdP is the source of truth), returns
403 for accounts with no mapped group, and disables local password login (404). The browser side works behind any
OIDC-capable reverse proxy (e.g. oauth2-proxy with `--pass-authorization-header`): the SPA always asks `/api/auth/me`
on load, so a proxy-injected identity signs the user in without the local login form. Tested with locally generated
keys: valid token, wrong audience, expired token, foreign signer, unmapped group.

## Application controls
* Secrets only via environment; `.env` is git-ignored; production mode refuses to start without `JWT_SECRET_KEY`.
* CORS restricted to configured origins; no credentials mode.
* Pydantic validation on every request body; consistent error schema; unhandled errors logged server-side, generic to client.
* SQLAlchemy ORM / bound parameters only — no string-built SQL.
* Uploads: extension allow-list, 5 MB cap, parsed in memory, never written to disk; sample download path-traversal guarded.
* CSV exports neutralise spreadsheet formula injection.
* nginx: CSP (`default-src 'self'`), `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, `server_tokens off`.
* Containers run as a non-root user; PostgreSQL is not published to the host.
* Bundle scan (`npm run check:secrets`) fails the build check if any server secret name or value appears in the SPA.

## Audit
Every state-changing action writes an `AuditEvent`. Events are chained (`hash = sha256(prev_hash + event)`), and
`GET /api/audit/verify` detects edits or deletions of individual events (tested). This is **tamper-evident, not
tamper-proof**: someone with database-owner rights could rewrite the entire chain. A pilot should ship the chain head to
write-once storage or a separate log system.

## Data protection
* No real defence data, no real personnel names; aircraft and part identifiers are fictional.
* The optional LLM explainer sends structured synthetic results to Google's Gemini API — it must stay disabled for any
  restricted data and in disconnected deployments (default: disabled).
* Hosted Neon is for non-sensitive demonstrations only; restricted deployments use the local PostgreSQL profile.

## Dependency management
Python dependencies pinned in `backend/requirements.txt`; frontend locked by `package-lock.json`.
Checked 2026-10-21: `pip-audit` on backend and training requirements — no known vulnerabilities; `npm audit` —
0 vulnerabilities (Vitest upgraded to 5.x after advisories in 4.x test tooling). Third-party licences: `THIRD_PARTY_NOTICES.md`.

## Known gaps before any pilot
Accredited security review and penetration test; an OIDC proxy configured for the organisation's IdP; TLS termination and certificate management; shared
rate-limit store if horizontally scaled; database-level append-only enforcement for audit; secrets manager; SBOM and
image signing; centralised log shipping; backup encryption.
