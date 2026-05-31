# ops-core + tg_schedule_bot

## schedule-reminder VPS deployment

This repository can also run as a single `schedule-reminder` service on a VPS.
The deploy target is `/opt/schedule-reminder`, using Python 3.11+, venv,
systemd, and a local health endpoint.

### Service entrypoint

The VPS service entrypoint is:

```bash
uvicorn main:app --host 127.0.0.1 --port 8030
```

`main:app` is the root FastAPI control app. `GET /health` returns:

```json
{"status":"ok","service":"schedule-reminder"}
```

The existing Telegram bot and APScheduler logic are preserved in `main.py`,
`scheduler.py`, and `workers/`. They start from the FastAPI lifespan only when
`ENABLE_SCHEDULER=true`. Importing `main:app` in CI does not start polling,
APScheduler, Telegram calls, email, webhooks, or other external API calls.

### Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a health-only local run that does not start Telegram polling, set:

```bash
ENABLE_SCHEDULER=false
uvicorn main:app --host 127.0.0.1 --port 8030
curl -fsS http://127.0.0.1:8030/health
```

To run the original Telegram bot directly:

```bash
python main.py
```

### Tests

```bash
python -m compileall .
pytest -q
```

The smoke test expects the service to be running:

```bash
scripts/smoke_test.sh
```

### VPS deployment

The expected server checkout path is:

```bash
/opt/schedule-reminder
```

Create the server environment file:

```bash
cd /opt/schedule-reminder
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set real values for `TELEGRAM_BOT_TOKEN`, user IDs, and any
optional AI/notification settings. Do not commit real secrets.

Manual deploy on the VPS:

```bash
cd /opt/schedule-reminder
chmod +x scripts/deploy.sh scripts/smoke_test.sh scripts/tail_logs.sh
scripts/deploy.sh
scripts/smoke_test.sh
```

`scripts/deploy.sh` installs dependencies into `.venv`, installs the systemd
unit, restarts `schedule-reminder`, runs a health check, prints service status,
and exits. It never runs uvicorn or Python as a foreground long-running process.

### GitHub Actions deployment

Add these GitHub repository secrets:

```text
VPS_HOST
VPS_USER
VPS_SSH_KEY
VPS_PORT
```

Run **Deploy to VPS** manually from GitHub Actions. The workflow SSHes in as
the configured deploy user, runs `git pull --ff-only`, then executes:

```bash
scripts/deploy.sh
scripts/smoke_test.sh
```

The workflow intentionally does not use `sudo -iu deploy`, `sudo -u deploy`, or
`su - deploy`; it assumes SSH already logs in as `deploy`.

### systemd management and logs

```bash
sudo systemctl status schedule-reminder --no-pager --full
sudo systemctl restart schedule-reminder
sudo systemctl stop schedule-reminder
sudo journalctl -u schedule-reminder -n 100 --no-pager
scripts/tail_logs.sh
```

### Troubleshooting

`.env missing`: create `/opt/schedule-reminder/.env` from `.env.example`.

`sudo password required`: allow the `deploy` user to run the required
`systemctl`, `cp` to `/etc/systemd/system`, and `journalctl` commands, or run
deployment from a user with those privileges.

`git pull permission denied`: verify repository deploy keys, GitHub access, and
ownership of `/opt/schedule-reminder`.

`service failed`: inspect `sudo systemctl --no-pager --full status
schedule-reminder` and `sudo journalctl -u schedule-reminder -n 100 --no-pager`.

`health check failed`: verify the service listens on `127.0.0.1:8030`, then run
`curl -fsS http://127.0.0.1:8030/health`.

`scheduler not started`: check `ENABLE_SCHEDULER=true`, `TELEGRAM_BOT_TOKEN`,
and journal logs for startup errors. With `ENABLE_SCHEDULER=false`, only the
FastAPI health/control service starts.

本项目已升级为“多入口 Adapter + ops-core API + 运维 service layer”的结构。

新的边界是：

```text
Telegram / Lark / Web / CLI / Agent
        ↓
    Adapter
        ↓
    ops-core HTTP API
        ↓
    service layer
        ↓
SSH / SQLite / Notification / Audit
```

Telegram Bot 不再直接执行 SSH，不再读取 `projects.yaml`，不再操作 SQLite。它只接收 Telegram 消息，调用 ops-core API，并把结果返回给用户。

## 目录

```text
ops-core/
├── main.py
├── config.py
├── projects.yaml
├── api/
│   ├── routes_projects.py
│   ├── routes_notifications.py
│   └── routes_commands.py
├── core/
│   ├── project_registry.py
│   ├── command_router.py
│   ├── auth_service.py
│   ├── status_service.py
│   ├── logs_service.py
│   ├── notification_service.py
│   └── audit_service.py
├── adapters/
│   ├── ssh_adapter.py
│   ├── sqlite_adapter.py
│   ├── notification_archive_adapter.py
│   └── audit_log_adapter.py
├── data/
├── logs/
├── requirements.txt
└── redeploy.sh

tg_schedule_bot/
├── main.py
├── handlers/
│   └── telegram_handlers.py
├── adapters/
│   └── ops_api_client.py
├── requirements.txt
└── redeploy.sh
```

## ops-core 职责

ops-core 统一负责：

- `projects.yaml` 项目白名单
- 固定 SSH 脚本执行
- status 查询
- logs 查询
- notification pull
- notification id dedup
- Telegram notification send_message
- audit log
- API Token 校验
- Telegram 用户权限校验
- SQLite 状态存储

安全边界：

- 不支持任意 shell
- 不使用 `shell=True`
- 用户不能传 SSH 命令
- 只执行 `projects.yaml` 中声明的 `scripts.status`、`scripts.logs`、`scripts.notifications`

## ops-core 配置

根目录 `.env.example` 只保留迁移提示。新部署请使用两个子项目各自的配置样例。

复制配置：

```bash
cd ops-core
cp .env.example .env
```

示例：

```env
OPS_API_TOKEN=change-me
OPS_API_HOST=0.0.0.0
OPS_API_PORT=8080
ALLOWED_USER_IDS=123456789

SSH_KEY_PATH=/opt/ops-core/keys/control_key
SSH_TIMEOUT_SECONDS=10
DEFAULT_LOG_LINES=80
PROJECTS_CONFIG_PATH=/opt/ops-core/projects.yaml
DATABASE_PATH=/opt/ops-core/data/ops_core.db
LOG_DIR=/opt/ops-core/logs

TELEGRAM_BOT_TOKEN=your-telegram-token
TELEGRAM_NOTIFY_CHAT_ID=
NOTIFICATION_PULL_LINES=50
```

`ALLOWED_USER_IDS` 为空时，ops-core 默认拒绝所有用户。

## projects.yaml

```yaml
projects:
  api-report-agent:
    host: 8.153.80.200
    port: 22
    user: deploy
    service: api-report-agent
    scripts:
      status: /opt/api-report-agent/scripts/status.sh
      logs: /opt/api-report-agent/scripts/logs.sh
      notifications: /opt/api-report-agent/scripts/notifications_tail.sh
```

后续可按项目增加更细权限：

```yaml
allowed_user_ids:
  - 123456789
allowed_actions:
  - status
  - logs
  - pull_notifications
```

## API 调用

所有请求必须带：

```text
Authorization: Bearer <OPS_API_TOKEN>
X-Channel: telegram
X-User-Id: 123456789
```

Telegram 手动拉取通知时还会带：

```text
X-Chat-Id: <telegram_chat_id>
```

列项目：

```bash
curl -H "Authorization: Bearer $OPS_API_TOKEN" \
  -H "X-Channel: telegram" \
  -H "X-User-Id: 123456789" \
  http://127.0.0.1:8080/api/projects
```

查状态：

```bash
curl -H "Authorization: Bearer $OPS_API_TOKEN" \
  -H "X-Channel: telegram" \
  -H "X-User-Id: 123456789" \
  http://127.0.0.1:8080/api/projects/api-report-agent/status
```

查日志：

```bash
curl -H "Authorization: Bearer $OPS_API_TOKEN" \
  -H "X-Channel: telegram" \
  -H "X-User-Id: 123456789" \
  "http://127.0.0.1:8080/api/projects/api-report-agent/logs?lines=50"
```

拉取通知：

```bash
curl -X POST \
  -H "Authorization: Bearer $OPS_API_TOKEN" \
  -H "X-Channel: telegram" \
  -H "X-User-Id: 123456789" \
  -H "X-Chat-Id: 123456789" \
  http://127.0.0.1:8080/api/projects/api-report-agent/pull-notifications
```

失败统一返回：

```json
{
  "ok": false,
  "project": "api-report-agent",
  "action": "status",
  "error": "ssh_timeout",
  "message": "远程执行超时"
}
```

## tg_schedule_bot

Telegram Adapter 只依赖 ops-core：

```bash
cd tg_schedule_bot
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=
OPS_CORE_BASE_URL=http://127.0.0.1:8080
OPS_API_TOKEN=
OPS_API_TIMEOUT_SECONDS=15
```

支持命令：

```text
/projects
/status <project>
/logs <project> [lines]
/pull_notifications <project>
```

调用链：

```text
Telegram handler
    ↓
tg_schedule_bot/adapters/ops_api_client.py
    ↓
HTTP API
    ↓
ops-core
```

## 新增 Adapter

未来新增 Lark、Web UI、CLI、AI Agent 时，只需要实现新的 Adapter：

1. 接收对应入口的用户请求。
2. 带上 `Authorization`、`X-Channel`、`X-User-Id`。
3. 调用 ops-core HTTP API。
4. 展示 API 返回。

不需要修改 `ops-core/core` service layer。

## SSH 与远程脚本

在 ops-core 部署机生成 key：

```bash
sudo mkdir -p /opt/ops-core/keys
sudo ssh-keygen -t ed25519 -f /opt/ops-core/keys/control_key -C "ops-core" -N ""
sudo chmod 700 /opt/ops-core/keys
sudo chmod 600 /opt/ops-core/keys/control_key
```

目标主机创建低权限用户并写入公钥：

```bash
sudo useradd --system --create-home --shell /bin/bash deploy
sudo mkdir -p /home/deploy/.ssh
sudo tee -a /home/deploy/.ssh/authorized_keys
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
```

远程脚本示例：

```bash
#!/usr/bin/env bash
set -euo pipefail
systemctl is-active api-report-agent || true
systemctl --no-pager --full status api-report-agent | tail -n 40
```

日志脚本示例：

```bash
#!/usr/bin/env bash
set -euo pipefail
LINES="${1:-80}"
case "$LINES" in ''|*[!0-9]*) LINES=80 ;; esac
if [ "$LINES" -gt 300 ]; then LINES=300; fi
journalctl -u api-report-agent -n "$LINES" --no-pager
```

通知脚本输出 JSONL，每行一条：

```json
{"id":"evt-001","level":"info","title":"Job done","time":"2026-05-10T10:00:00Z","message":"Report generated"}
```

## systemd 部署

新增两个 service：

- `systemd/ops_core.service`
- `systemd/tg_schedule_bot.service`

`tg_schedule_bot.service` 依赖 `ops_core.service`：

```ini
After=network-online.target ops_core.service
Requires=ops_core.service
```

安装示例：

```bash
sudo cp systemd/ops_core.service /etc/systemd/system/ops_core.service
sudo cp systemd/tg_schedule_bot.service /etc/systemd/system/tg_schedule_bot.service
sudo systemctl daemon-reload
sudo systemctl enable ops_core tg_schedule_bot
sudo systemctl start ops_core
sudo systemctl start tg_schedule_bot
```

查看日志：

```bash
sudo journalctl -u ops_core -f
sudo journalctl -u tg_schedule_bot -f
```

## redeploy

两个子项目都有独立 `redeploy.sh`：

- `ops-core/redeploy.sh`
- `tg_schedule_bot/redeploy.sh`

根目录 `redeploy.sh` 是一个编排脚本，会按顺序调用 `/opt/ops-core/redeploy.sh` 和 `/opt/tg_schedule_bot/redeploy.sh`。也可以通过环境变量覆盖路径：

```bash
OPS_CORE_DIR=/opt/ops-core TG_BOT_DIR=/opt/tg_schedule_bot ./redeploy.sh
```

流程一致：

1. `git pull`
2. 自动创建 `.venv`
3. `pip install -r requirements.txt`
4. 检查必要配置
5. `systemctl daemon-reload`
6. restart service
7. 写入 `deploy.log`

## audit log

ops-core 统一写：

```text
/opt/ops-core/logs/audit.log
```

字段：

```text
timestamp channel user_id action project success/failure duration_ms message
```

## 验收

- Telegram Bot 不再直接 SSH
- Telegram Bot 不再读取 `projects.yaml`
- Telegram Bot 不再操作 SQLite
- `/status api-report-agent` 走 ops-core API
- `/logs api-report-agent 50` 走 ops-core API
- `/pull_notifications api-report-agent` 走 ops-core API
- notification id 通过 ops-core SQLite 去重
- audit log 由 ops-core 写入
- 未来新增 Lark/Web/CLI/Agent 只需要新增 Adapter
