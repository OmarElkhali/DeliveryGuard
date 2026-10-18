# Local operations and pilot deployment

## Configuration and trust boundary

The default is company mode (`DG_DEMO=false`): API startup refuses an absent/short
key. `.env.example` contains no secret. The standalone `.env.demo` opts into public,
synthetic-only access and a public demonstration DB password. Never switch an
existing demo volume into a company pilot. Create a new project/volumes and load
only the company's approved data. PostgreSQL is not published by Compose.

Serve a real pilot behind an administrator-managed HTTPS reverse proxy and restrict
network access. Configure proxy body limits, rate limits and timeouts consistently
with the app's limits; preserve Streamlit WebSocket forwarding. Native servers
should bind to loopback. Avoid public Swagger “Try it” with a production key on a
shared machine. The UI needs users to enter a key in each Streamlit session in
company mode; it does **not** automatically reuse the server's API key as an
unauthenticated proxy. No key is sent to an external service.

The current shared key gives all business permissions. Treat access to Docker,
the filesystem, joblib artifacts, database and trusted local CLI as administrator
access. joblib is not safe for untrusted artifacts. Never replace model files with
downloaded or user-provided ones. Store volumes with restrictive OS permissions and
encrypt disks/backups according to company policy. No personal information belongs
in category or identifier fields. Logs deliberately omit row contents and secrets.

## Health and jobs

```sh
docker compose --env-file .env.demo ps
docker compose --env-file .env.demo logs --tail 100 api worker
docker compose --env-file .env.demo exec api deliveryguard worker --once
```

For company mode, omit `--env-file .env.demo` and add the same `-p
deliveryguard-company` on **every** command. `/health/ready` checks DB/migration;
it does not require a model or assert that a worker is currently running. A run
remaining queued means the worker is stopped/unavailable. After a crash, restarted
workers mark running jobs failed; explicitly create a new run. Training errors are
persisted with safe codes; no raw business data are logged.

## Backup and restoration

Stop writers for a consistent DB/files pair. The following POSIX commands are for
the demo; adapt the Compose project and env file for company mode. Protect backup
files, which contain all private sources and models.

```sh
mkdir -p backups
docker compose --env-file .env.demo stop ui api worker
docker compose --env-file .env.demo exec -T db sh -c 'pg_dump -U deliveryguard -d deliveryguard -Fc > /tmp/deliveryguard.dump'
docker compose --env-file .env.demo cp db:/tmp/deliveryguard.dump backups/deliveryguard.dump
docker compose --env-file .env.demo run --rm --no-deps -T api python -c "import tarfile; t=tarfile.open('/app/data/backup.tar.gz','w:gz'); t.add('/app/data/imports',arcname='imports'); t.add('/app/data/models',arcname='models'); t.close()"
docker compose --env-file .env.demo cp api:/app/data/backup.tar.gz backups/files.tar.gz
docker compose --env-file .env.demo start api worker ui
```

Back up after at least one import and one successful training so both directories
exist. `app_data` is a named volume shared by the stopped API and one-off backup
container, so `compose cp api:...` reads the same file. Copy the env secrets into a
separate restricted backup system; never into Git. Remove the temporary archive
after copying to avoid wasting private-volume space.

Restore to an **empty, isolated Compose project** with matching dependency pins:

1. Start only `db`; copy the dump with `docker compose ... cp backups/deliveryguard.dump db:/tmp/restore.dump`.
2. Restore with `docker compose ... exec -T db pg_restore -U deliveryguard -d deliveryguard --clean --if-exists /tmp/restore.dump`.
3. Copy `files.tar.gz` into the new private volume with a one-off trusted container,
   then extract it into `/app/data` as the app user. Only extract your own trusted
   archive; review members first. Keep the `imports/` and `models/` paths unchanged.
4. Start migration/API/worker/UI. Confirm readiness, import receipts, model list,
   active version and a saved known prediction before reconnecting integrations.
5. Keep the original backup intact until restoration has been independently verified.

The following isolated **synthetic demo** restoration was executed locally. The
original project remains on 8000/8501; the restored instance uses 8004/8504. Do not
reuse a non-empty restoration project or point this at company volumes.

```sh
export DG_API_PORT=8004 DG_UI_PORT=8504
docker compose -p deliveryguard-restore --env-file .env.demo up -d --wait db
docker compose -p deliveryguard-restore --env-file .env.demo cp backups/deliveryguard.dump db:/tmp/restore.dump
docker compose -p deliveryguard-restore --env-file .env.demo exec -T db pg_restore -U deliveryguard -d deliveryguard --clean --if-exists /tmp/restore.dump
docker compose -p deliveryguard-restore --env-file .env.demo create api
docker compose -p deliveryguard-restore --env-file .env.demo cp backups/files.tar.gz api:/app/data/restore.tar.gz
docker compose -p deliveryguard-restore --env-file .env.demo run --rm --no-deps -T api python -c "import tarfile; t=tarfile.open('/app/data/restore.tar.gz'); t.extractall('/app/data',filter='data'); t.close()"
docker compose -p deliveryguard-restore --env-file .env.demo up -d --wait
# Compare counts, active version and a saved known prediction via API on 8004.
docker compose -p deliveryguard-restore --env-file .env.demo down
unset DG_API_PORT DG_UI_PORT
```

PowerShell equivalents for the two environment assignments are
`$env:DG_API_PORT='8004'; $env:DG_UI_PORT='8504'`; remove them afterward with
`Remove-Item Env:DG_API_PORT,Env:DG_UI_PORT`. The fixture uses no real business data.

For native Python: stop API/worker, `pg_dump -Fc`, archive `DG_DATA_DIR`, restore
with `pg_restore` and the same data directory contents. A DB-only backup is
insufficient. Dangling files from an interrupted import are possible (files are
written before DB commit); retain for investigation and remove only after checking
that no import/run references them. Do not remove named volumes as routine cleanup.

## Rotation and upgrades

Rotate the API key by stopping API/UI, replacing `DG_API_KEY` in the environment,
recreating services and updating all clients. Old keys stop working immediately;
there is no overlap window or individual revocation. Database password rotation
also requires changing the actual PostgreSQL role password through an authenticated
administrator session: changing `POSTGRES_PASSWORD` alone does not update an
existing volume. Then update the URL/env and recreate clients. Never paste secrets
into tickets/logs. Back up before migrations; retain dependency pins with artifacts.

No deletion API, retention scheduler, TLS certificate automation, SSO, per-user
authorization, external observability, HA or disaster-recovery SLA is provided.
Set retention and deletion procedures before importing company data. Exercise
restore on an isolated instance; written instructions alone do not establish RPO/RTO.
