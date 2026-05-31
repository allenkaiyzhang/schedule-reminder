# schedule-reminder

`schedule-reminder` is a standalone Telegram reminder bot. It owns only bot-local
reminder functionality: Telegram commands, SQLite persistence, a scheduler,
health checks, logs, tests, and venv + systemd deployment.

This project does not manage other services. It does not SSH into other hosts.
It does not read other projects' logs. Future ops-core or multi-project control
planes should be implemented in a separate repository.

## Architecture

```text
FastAPI app.main:app
  /health
  lifespan
    Telegram polling
    APScheduler due-reminder scan
SQLite reminder store
Local rotating log file + journalctl
```

The root `main.py` is only a compatibility entrypoint that imports
`app.main:app`.

## Commands

- `/start`: intro and command list
- `/help`: usage examples
- `/remind 2026-06-01 09:30 Take medicine`
- `/remind 2026-06-01 09:30 Asia/Shanghai Take medicine`
- `/remind in 10m Take a break`
- `/remind in 2h Check report`
- `/list`: list active and paused reminders for the current Telegram user
- `/delete <id>`: soft-delete your own reminder
- `/pause <id>`: pause your own reminder
- `/resume <id>`: resume your own reminder
- `/status`: bot-local status only
- `/logs [lines]`: bot-local logs only, clamped to a safe maximum

## Configuration

`.env` is for secrets and private identifiers only:

```env
TELEGRAM_BOT_TOKEN=
ALLOWED_USER_IDS=
DEFAULT_CHAT_ID=
ADMIN_BEARER_TOKEN=
```

`registry.yaml` is the non-sensitive registry for service defaults:

- service host, port, health path
- data, log, and SQLite paths
- Telegram parse mode and command timeout
- scheduler timezone and behavior
- deployment path and systemd service name

Do not put host, port, service name, paths, scheduler defaults, or log settings
in `.env` unless they are genuinely sensitive.

If `ALLOWED_USER_IDS` is empty, Telegram commands fail closed. `/health` remains
available on localhost.

For tests and diagnostics:

```bash
ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true
```

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
cp .env.example .env
```

For local health-only mode:

```bash
ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true \
  uvicorn app.main:app --host 127.0.0.1 --port 8030
```

Health check:

```bash
curl -fsS http://127.0.0.1:8030/health
```

## Tests

```bash
ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true python -m compileall .
ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true pytest -q
```

Tests cover:

- `/health` without Telegram network calls
- SQLite reminder CRUD
- user isolation
- absolute and relative time parsing

## Deployment

The deployment target is:

```text
/opt/schedule-reminder
```

Create the server environment:

```bash
cd /opt/schedule-reminder
cp .env.example .env
chmod 600 .env
```

Edit `.env` with real secret values. Edit `registry.yaml` for non-sensitive
runtime defaults.

Manual deployment:

```bash
cd /opt/schedule-reminder
chmod +x scripts/deploy.sh scripts/smoke_test.sh scripts/tail_logs.sh
scripts/deploy.sh
scripts/smoke_test.sh
```

`scripts/deploy.sh` creates or repairs `.venv`, installs dependencies, runs
compile/tests unless `SKIP_TESTS=1`, installs the systemd unit, restarts the
service, checks `/health`, prints status, and exits. It never runs uvicorn in the
foreground.

## systemd

The unit is `systemd/schedule-reminder.service`.

Key command:

```bash
/opt/schedule-reminder/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8030
```

Service management:

```bash
sudo systemctl status schedule-reminder --no-pager --full
sudo systemctl restart schedule-reminder
sudo journalctl -u schedule-reminder -n 100 --no-pager
```

## GitHub Actions

Manual deployment uses `.github/workflows/deploy.yml` and these secrets:

```text
VPS_HOST
VPS_USER
VPS_SSH_KEY
VPS_PORT
```

The workflow SSHes to the target, ensures `/opt/schedule-reminder` exists,
fetches `origin/main`, hard resets the checkout to avoid local drift, then runs:

```bash
scripts/deploy.sh
scripts/smoke_test.sh
```

## Logs

```bash
scripts/tail_logs.sh
sudo journalctl -u schedule-reminder -n 100 --no-pager
tail -n 120 logs/schedule-reminder.log
```

The `/logs [lines]` Telegram command reads only this bot's local log file.

## Troubleshooting

`.env missing`: create it from `.env.example` and set real secrets.

`commands rejected`: set `ALLOWED_USER_IDS` to a comma-separated list of allowed
Telegram user IDs.

`bot does not start`: check `TELEGRAM_BOT_TOKEN`, `ENABLE_BOT`, and journal logs.

`health check failed`: run `curl -fsS http://127.0.0.1:8030/health` on the VPS
and inspect `sudo journalctl -u schedule-reminder -n 100 --no-pager`.

`SQLite write failure`: verify the `deploy` user can write to `data/` and
`logs/`.

`tests accidentally call Telegram`: run with
`ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true`.

`deployment checkout drift`: GitHub Actions uses `git reset --hard origin/main`
and `git clean -fd` on `/opt/schedule-reminder`.
