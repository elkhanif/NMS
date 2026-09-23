# Network Monitoring System (Mini NMS)

A real network management system, not a CRUD app: device inventory + discovery,
multi-method monitoring (ICMP / TCP / SNMPv2c / HTTP), historical time-series metrics,
an alert engine with lifecycle, an event log, network topology visualization, and a
NOC-style dashboard.

See `plan.md`-equivalent design notes below; the authoritative design record is the
approved plan this was built from (architecture, schema, worker design, API, frontend
routes, security, and delivery order).

## Architecture

```
                     ┌────────────┐        ┌──────────────────┐
   browser  ───────▶ │  frontend  │──────▶ │        api        │◀───┐
                     │  (Next.js) │  proxy │      (FastAPI)     │    │
                     └────────────┘        └──────────────────┘    │
                                                     │              │ reads/writes
                                                     ▼              │
                                            ┌──────────────────┐    │
                                            │     postgres      │◀──┘
                                            │  (+ TimescaleDB)   │
                                            └──────────────────┘
                                                     ▲
                                                     │ metrics, alerts, events,
                                                     │ device_checks, credentials
                                            ┌──────────────────┐
                                            │ monitoring-worker  │──▶ network devices
                                            │  (ICMP/TCP/HTTP/    │   (ICMP/TCP/HTTP/SNMP)
                                            │   SNMP pollers)     │
                                            └──────────────────┘
```

- **api** never talks to network devices — it only reads/writes Postgres and serves
  the frontend.
- **monitoring-worker** is the only component that opens sockets to devices. It runs
  independently of the API and frontend, so monitoring keeps working even if either of
  those is down.
- **frontend** never sees JWTs directly — a Next.js route-handler proxy holds them in
  httpOnly cookies and forwards authenticated requests server-side.

## Quick start

```bash
cp .env.example .env
# generate real secrets:
python -c "import secrets; print(secrets.token_urlsafe(48))"      # -> JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # -> CREDENTIAL_ENCRYPTION_KEY
# edit .env and paste both in, plus a real INITIAL_ADMIN_PASSWORD

docker compose up --build
```

- API: http://localhost:8000/docs (OpenAPI/Swagger)
- Frontend: http://localhost:3000
- Log in with `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` from `.env` (seeded on
  first boot only, see `backend/app/services/seed.py`).

### Trying it without touching your real network

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev up --build
```

This adds `mock-snmp` (an `snmpsim`-based SNMPv2c agent serving fixture data from
`mock-devices/snmp-data/public.snmprec` — a fake router with 2 interfaces, CPU/memory/
disk stats) and `mock-targets` (fake open TCP ports + an HTTP health endpoint) to the
compose network. `Device.ip_address` only accepts a literal IP, not a hostname, so
look up each container's actual address on the compose network first --
`docker compose exec monitoring-worker getent hosts mock-snmp` (and `mock-targets`)
-- then register a device with that IP to exercise every check type end-to-end
without touching a production network.

## Repository layout

```
common/nms_common/   shared SQLAlchemy models, config, crypto -- installed editable
                     into both backend and worker so they never drift apart
backend/app/         FastAPI API: auth/RBAC, devices, discovery, alerts, alert-rules,
                     events, topology, dashboard. Alembic migrations in backend/alembic.
worker/worker/       monitoring worker: scheduler, ICMP/TCP/HTTP/SNMP pollers,
                     alert engine, discovery execution, heartbeat
frontend/            Next.js 14 App Router + TypeScript + Tailwind dashboard
mock-devices/        snmpsim fixture + fake TCP/HTTP targets for dev/test
docker-compose.yml   postgres(timescaledb), redis, api, monitoring-worker, frontend
docker-compose.dev.yml  adds mock-snmp / mock-targets under the `dev` profile
```

## Monitoring model

- Every device can have one or more `device_checks` (ICMP / TCP / HTTP(S) / SNMP),
  each with its own poll interval, timeout, and retry count — critical infra can poll
  every 30s while a low-priority IoT device polls every 5 minutes, independently.
- The worker reconciles its running poll tasks against `device_checks` every 15s; each
  (device, check) then runs its own loop at its own interval. A bad/unreachable device
  can only ever fail its own loop — never the scheduler or another device's polling.
- SNMP credentials (SNMPv2c community strings) are Fernet-encrypted at rest
  (`CREDENTIAL_ENCRYPTION_KEY`) and only ever decrypted inside the worker process; the
  API accepts them write-only and never echoes them back.
- Alert rules (`alert_rules` table, editable via `/settings/alert-rules` or the API)
  drive an alert engine with simple hysteresis (N consecutive breaches to open, N
  consecutive OK polls to auto-resolve) so a single noisy ping doesn't flap alerts.
  Defaults seeded on first boot match the spec: unreachable → CRITICAL, packet loss
  >10%/>30% → WARNING/CRITICAL, CPU >80%/>95% → WARNING/CRITICAL, memory >85% →
  WARNING, interface down → WARNING (severity is per-rule, editable).
- Device discovery is admin-triggered (CIDR + optional credentials + rate limit),
  capped and rate-limited (`DISCOVERY_MAX_HOSTS`, `DISCOVERY_RATE_PPS`) so it can never
  flood the network, and executed by the worker (never the API) — results land in a
  review queue that an admin explicitly imports into the device inventory.

## SNMPv3

Only SNMPv2c is implemented, per spec. The credential model
(`nms_common.enums.CredentialType.SNMPV3`) and the worker's `build auth data` seam in
`worker/worker/pollers/snmp.py` already leave room for it — adding it means branching
on `credential_type` there to build `UsmUserData` instead of `CommunityData`, nothing
else in the pipeline changes.

## Running tests

Tests need a reachable Postgres (plain `postgres:16` is enough — the tests use
`Base.metadata.create_all`, not the Timescale-specific migration):

```bash
docker compose up -d postgres
cd backend && pip install -r requirements-dev.txt && pytest
cd worker  && pip install -r requirements-dev.txt && pytest
```

Or inside the compose network: `docker compose run --rm api pytest` /
`docker compose run --rm monitoring-worker pytest` (install the `-dev` requirements in
the image, or `pip install -r requirements-dev.txt` first, if you want this to be the
default rather than a one-off).

Coverage: JWT auth + refresh, RBAC on device/user mutation, credential encrypt/decrypt
round-trip and non-exposure, alert acknowledge→resolve lifecycle and idempotency,
discovery CIDR-size validation and rate-limit cooldown, ICMP/TCP/HTTP pollers against
local fixtures, and the alert engine's hysteresis (breach/resolve counting) for both
metric-threshold and device-unreachable rules, plus device/interface up-down event
emission.

## Known limitations / what to verify before trusting this against a real network

- **This was built and reviewed without a local Docker or Python runtime available** —
  the code is internally consistent and the design was validated carefully, but
  `docker compose up` (full-stack smoke test), `alembic upgrade head` against a real
  Postgres, and the SNMP poller's exact `pysnmp` async API calls have not been
  execution-tested. `worker/worker/pollers/snmp.py` has a comment flagging it as the
  first place to check if SNMP polling errors on startup — everything else only
  depends on its plain-dict return shape. Similarly, `docker-compose.dev.yml`'s
  `mock-snmp` command (`snmpsim-command-responder`) is the current `snmpsim-lextudio`
  CLI name as of this writing — if the built image errors on that command, run
  `docker compose run --rm mock-snmp snmpsim-command-responder --help` (or `pip show
  -f snmpsim-lextudio` inside the image) to find the installed version's actual entry
  point and fix the `command:` in `docker-compose.dev.yml`.
- The frontend (`frontend/`) *was* built and `npm run build` (Next's production build,
  which type-checks the whole app) passes cleanly in this environment -- Node.js was
  available here even though Docker/Python were not.
- `npm audit` flags a long list of advisories against the Next.js 14 line in general;
  the specific one that matters most for this app's design (the March 2025 middleware
  authorization-bypass CVE, GHSA-f82v-jwr5-mffw -- directly relevant since
  `frontend/middleware.ts` is the auth gate) is fixed as of the pinned `^14.2.25`
  range. A full Next 15/16 upgrade would resolve the rest but is a breaking change
  this pass didn't take; consider it before any real deployment (`cd frontend && npm
  audit` to see current status).
- No websocket push yet — the dashboard/tables poll every 15-30s via TanStack Query.
- No reverse proxy/TLS termination in compose — add Caddy/nginx in front for anything
  beyond local/dev use.
