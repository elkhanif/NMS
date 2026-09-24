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

Both SNMPv2c and SNMPv3 (USM: auth SHA/MD5/SHA224/256/384/512, priv DES/3DES/AES) are
supported. `worker/worker/pollers/snmp.py:build_auth_data()` branches on
`credential_type` to build a `CommunityData` or `UsmUserData` object; the scheduler and
discovery worker try an `SNMPV3` credential first, falling back to `SNMPV2C`. Store an
SNMPv3 credential via `POST /devices/{id}/credentials` with
`{"credential_type": "SNMPV3", "payload": {"username": ..., "auth_protocol": "SHA",
"auth_password": ..., "priv_protocol": "AES", "priv_password": ...}}` (omit
`priv_protocol`/`priv_password` for authNoPriv, and `auth_protocol`/`auth_password` too
for noAuthNoPriv).

Verified end-to-end (engine discovery + authPriv GET) against a real net-snmp `snmpd`
agent. The bundled `mock-snmp` dev fixture (`docker-compose.dev.yml`) is **not** a
reliable SNMPv3 test target: it runs the deprecated `pysnmp-lextudio`/`pysnmpcrypto`
fork, whose AES/auth-key implementation doesn't interoperate with the actively
maintained `pysnmp` package this app uses -- authPriv requests against it silently time
out with no wire-level indication of why. Test SNMPv3 against a real device or a
net-snmp `snmpd` instead.

## Live updates (WebSocket)

The dashboard, alerts, events, and incidents pages get pushed live updates instead of
waiting for their 20s poll: the worker publishes a small `{type, action, id,
device_id}` message to Redis (`nms:live` channel) whenever it opens/resolves an alert
or incident, or logs a device/interface/IP/MAC-change event; the API fans those out to
every connected browser over a WebSocket, and the frontend responds by invalidating
the relevant TanStack Query cache keys so the affected `useQuery` hooks refetch
immediately. The 20s poll stays in place as a fallback in case a message is ever
missed — this is a "refresh sooner" layer, not a replacement data path.

Because Next.js Route Handlers can't proxy a WebSocket upgrade, the browser connects
to the API directly (`NEXT_PUBLIC_API_WS_URL`, baked into the frontend build) instead
of through the usual `/api/backend` proxy. The JWT still never reaches the browser:
the client first calls the authenticated `POST /api/v1/ws/ticket` (through the normal
proxy) to get a single-use, 30-second ticket, then opens the socket with that ticket
as a query param. A production deployment's reverse proxy needs to forward the WS path
to the api container too, and `NEXT_PUBLIC_API_WS_URL` needs to point at its public
`wss://` URL.

## Running tests

Tests need a reachable Postgres and Redis (plain `postgres:16` is enough — the tests
use `Base.metadata.create_all`, not the Timescale-specific migration):

```bash
docker compose up -d postgres redis
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
- No reverse proxy/TLS termination in compose — add Caddy/nginx in front for anything
  beyond local/dev use. Once added, it must also forward the WebSocket path (see "Live
  updates" above) and `NEXT_PUBLIC_API_WS_URL` must be rebuilt to point at the public
  `wss://` URL — a raw `docker compose up --build` with the current `.env.example`
  default only works for local/dev where the browser can reach `API_PORT` directly.
