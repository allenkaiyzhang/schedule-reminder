# Telegram Schedule Bot + Project Control Center

这是一个 Python 3.11+ Telegram Bot 项目，包含两类能力：

- 日程提醒助手：添加、查看、修改、完成、取消日程，并按时间自动提醒。
- 项目状态查询控制台：通过 Telegram 查询白名单项目的远程状态和日志。

项目控制台只支持固定白名单脚本：

- `/projects`
- `/status <project>`
- `/logs <project> [lines]`

它不会执行任意 shell 命令，也不包含 deploy、restart、delete、rollback 或 AI 自动执行命令能力。

## 目录结构

```text
.
├── main.py
├── config.py
├── auth.py
├── audit.py
├── projects.yaml
├── db.py
├── handlers.py
├── parser.py
├── reminder.py
├── scheduler.py
├── adapters/
│   ├── __init__.py
│   └── ssh_adapter.py
├── handlers/
│   └── project_handlers.py
├── ai/
├── workers/
├── logs/
│   └── audit.log
├── requirements.txt
├── .env.example
└── systemd/
    └── tg-schedule-bot.service
```

说明：当前项目已有根级 `handlers.py` 用于日程功能，因此项目控制台 handler 放在 `handlers/project_handlers.py`，并由 `main.py` 兼容性加载。

## 安装依赖

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 可使用：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## .env 配置

最小配置示例：

```env
TELEGRAM_BOT_TOKEN=
DEFAULT_TIMEZONE=Asia/Singapore
DATABASE_PATH=./data/schedule.db
CHECK_INTERVAL_SECONDS=30
DEFAULT_REMIND_BEFORE_MINUTES=30,10,0
ALLOWED_USER_IDS=123456789

AI_PROVIDER=disabled
AI_API_KEY=
AI_BASE_URL=
AI_MODEL=
AI_TIMEOUT_SECONDS=20

MORNING_SUMMARY_HOUR=8
EVENING_SUMMARY_HOUR=22
LOG_DIR=./logs
SQLITE_BUSY_TIMEOUT_MS=5000

SSH_KEY_PATH=/opt/tg-control-center/keys/control_key
SSH_TIMEOUT_SECONDS=10
DEFAULT_LOG_LINES=80
PROJECTS_CONFIG_PATH=./projects.yaml
```

关键配置：

| 配置项 | 说明 |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token，通过 `@BotFather` 创建 |
| `ALLOWED_USER_IDS` | 允许使用 Bot 的 Telegram user_id，逗号分隔 |
| `SSH_KEY_PATH` | Bot 连接远程主机使用的 SSH 私钥路径 |
| `SSH_TIMEOUT_SECONDS` | SSH 执行超时时间，默认 10 秒 |
| `DEFAULT_LOG_LINES` | `/logs` 默认返回行数，默认 80 |
| `PROJECTS_CONFIG_PATH` | 项目配置文件路径，默认 `./projects.yaml` |

安全默认值：

- `ALLOWED_USER_IDS` 为空时，Bot 默认拒绝所有用户。
- 不要提交 `.env`。
- 不要在日志、README、截图中暴露 Bot Token 或 SSH 私钥内容。

## 配置 projects.yaml

`projects.yaml` 只允许声明固定项目和固定脚本路径。用户在 Telegram 里只能传项目名和 `/logs` 行数，不能传任意命令。

示例：

```yaml
projects:
  api-report-agent:
    host: 1.2.3.4
    port: 22
    user: deploy
    service: api-report-agent
    scripts:
      status: /opt/api-report-agent/scripts/status.sh
      logs: /opt/api-report-agent/scripts/logs.sh
```

字段说明：

- `host`：远程主机 IP 或域名
- `port`：SSH 端口
- `user`：远程执行用户，建议使用低权限 `deploy`
- `service`：项目服务名，供脚本使用
- `scripts.status`：状态查询脚本路径
- `scripts.logs`：日志查询脚本路径

## 项目控制台命令

列出可用项目：

```text
/projects
```

返回示例：

```text
可用项目：
- api-report-agent
```

查询状态：

```text
/status api-report-agent
```

Bot 执行的远程命令等价于：

```bash
ssh -i "$SSH_KEY_PATH" -p 22 deploy@1.2.3.4 /opt/api-report-agent/scripts/status.sh
```

查询日志：

```text
/logs api-report-agent
/logs api-report-agent 50
```

Bot 执行的远程命令等价于：

```bash
ssh -i "$SSH_KEY_PATH" -p 22 deploy@1.2.3.4 /opt/api-report-agent/scripts/logs.sh 50
```

`lines` 规则：

- 可选，默认使用 `DEFAULT_LOG_LINES`
- 必须是整数
- 最小 1
- 最大 300

输出规则：

- 远程执行超时：返回 `远程执行超时`
- 远程脚本非 0：返回 `远程脚本执行失败`，并附带 stderr 最后 1000 字符
- 输出为空：返回 `命令执行完成，但没有输出`
- Telegram 单条消息过长时，只返回最后 3500 字符

## 安全设计

项目控制台遵守以下限制：

- 只允许 `ALLOWED_USER_IDS` 中的用户使用。
- `ALLOWED_USER_IDS` 为空时拒绝所有用户。
- 不支持任意 shell 命令执行。
- 不支持 deploy、restart、delete、rollback。
- 不允许用户输入脚本路径。
- 只能执行 `projects.yaml` 中配置好的 `status` 和 `logs` 脚本。
- SSH 使用 `subprocess.run([...], shell=False)`。
- 用户输入不会拼接成 shell 字符串。
- SSH 执行有超时限制，避免卡死 Bot。
- 每次项目控制台操作写入 `logs/audit.log`。

audit log 字段：

```text
time    telegram_user_id    command    project    success/failure    duration_ms    message
```

不会记录：

- Bot Token
- SSH 私钥内容
- `.env` 完整内容

## 生成 SSH Key

在 Bot 部署机上生成专用 key：

```bash
sudo mkdir -p /opt/tg-control-center/keys
sudo ssh-keygen -t ed25519 -f /opt/tg-control-center/keys/control_key -C "tg-control-center" -N ""
sudo chmod 700 /opt/tg-control-center/keys
sudo chmod 600 /opt/tg-control-center/keys/control_key
```

如果 Bot 使用 `schedulebot` 用户运行：

```bash
sudo chown -R schedulebot:schedulebot /opt/tg-control-center/keys
```

把公钥内容复制出来：

```bash
sudo cat /opt/tg-control-center/keys/control_key.pub
```

## 配置目标主机 deploy 用户

在远程目标主机上创建低权限用户：

```bash
sudo useradd --system --create-home --shell /bin/bash deploy
sudo mkdir -p /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
```

把 Bot 部署机的 `control_key.pub` 内容追加到远程主机：

```bash
sudo tee -a /home/deploy/.ssh/authorized_keys
```

粘贴公钥后按 `Ctrl+D` 结束输入，然后设置权限：

```bash
sudo chmod 600 /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
```

在 Bot 部署机测试 SSH：

```bash
ssh -i /opt/tg-control-center/keys/control_key -p 22 deploy@1.2.3.4 whoami
```

预期输出：

```text
deploy
```

## 创建远程脚本

以 `api-report-agent` 为例，在目标主机上创建脚本目录：

```bash
sudo mkdir -p /opt/api-report-agent/scripts
sudo chown -R deploy:deploy /opt/api-report-agent/scripts
```

创建 `status.sh`：

```bash
sudo -u deploy nano /opt/api-report-agent/scripts/status.sh
```

示例内容：

```bash
#!/usr/bin/env bash
set -euo pipefail

systemctl is-active api-report-agent || true
systemctl --no-pager --full status api-report-agent | tail -n 40
```

创建 `logs.sh`：

```bash
sudo -u deploy nano /opt/api-report-agent/scripts/logs.sh
```

示例内容：

```bash
#!/usr/bin/env bash
set -euo pipefail

LINES="${1:-80}"
case "$LINES" in
  ''|*[!0-9]*) LINES=80 ;;
esac

if [ "$LINES" -gt 300 ]; then
  LINES=300
fi

journalctl -u api-report-agent -n "$LINES" --no-pager
```

设置可执行权限：

```bash
sudo chmod +x /opt/api-report-agent/scripts/status.sh
sudo chmod +x /opt/api-report-agent/scripts/logs.sh
sudo chown deploy:deploy /opt/api-report-agent/scripts/status.sh /opt/api-report-agent/scripts/logs.sh
```

在 Bot 部署机测试：

```bash
ssh -i /opt/tg-control-center/keys/control_key -p 22 deploy@1.2.3.4 /opt/api-report-agent/scripts/status.sh
ssh -i /opt/tg-control-center/keys/control_key -p 22 deploy@1.2.3.4 /opt/api-report-agent/scripts/logs.sh 50
```

## 本地运行

```bash
python main.py
```

Bot 使用 Telegram long polling，不需要公网 webhook。

## systemd 部署

下面以 Ubuntu/Debian 为例：

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip openssh-client
```

创建运行用户：

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin schedulebot
```

部署代码：

```bash
sudo mkdir -p /opt/tg-schedule-bot
sudo chown -R schedulebot:schedulebot /opt/tg-schedule-bot
sudo rsync -av --exclude ".env" --exclude ".venv" --exclude "data" --exclude "__pycache__" ./ /opt/tg-schedule-bot/
sudo chown -R schedulebot:schedulebot /opt/tg-schedule-bot
```

安装依赖：

```bash
cd /opt/tg-schedule-bot
sudo -u schedulebot python3.11 -m venv .venv
sudo -u schedulebot .venv/bin/pip install -r requirements.txt
```

配置 `.env`：

```bash
cd /opt/tg-schedule-bot
sudo -u schedulebot cp .env.example .env
sudo -u schedulebot nano .env
```

确认这些路径和用户匹配：

```env
DATABASE_PATH=/opt/tg-schedule-bot/data/schedule.db
LOG_DIR=/opt/tg-schedule-bot/logs
PROJECTS_CONFIG_PATH=/opt/tg-schedule-bot/projects.yaml
SSH_KEY_PATH=/opt/tg-control-center/keys/control_key
ALLOWED_USER_IDS=123456789
```

创建数据和日志目录：

```bash
sudo -u schedulebot mkdir -p /opt/tg-schedule-bot/data /opt/tg-schedule-bot/logs
```

先手动试运行：

```bash
cd /opt/tg-schedule-bot
sudo -u schedulebot .venv/bin/python main.py
```

确认 Telegram 命令可用后按 `Ctrl+C` 停止，再安装 systemd service：

```bash
sudo cp /opt/tg-schedule-bot/systemd/tg-schedule-bot.service /etc/systemd/system/tg-schedule-bot.service
sudo nano /etc/systemd/system/tg-schedule-bot.service
```

重点检查：

```ini
User=schedulebot
Group=schedulebot
WorkingDirectory=/opt/tg-schedule-bot
EnvironmentFile=/opt/tg-schedule-bot/.env
ExecStart=/opt/tg-schedule-bot/.venv/bin/python /opt/tg-schedule-bot/main.py
ReadWritePaths=/opt/tg-schedule-bot/data
```

如果 `LOG_DIR` 在 `/opt/tg-schedule-bot/logs`，建议把 service 中的 `ReadWritePaths` 改成：

```ini
ReadWritePaths=/opt/tg-schedule-bot/data /opt/tg-schedule-bot/logs
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-schedule-bot
sudo systemctl start tg-schedule-bot
sudo systemctl status tg-schedule-bot
```

查看日志：

```bash
sudo journalctl -u tg-schedule-bot -f
```

重启：

```bash
sudo systemctl restart tg-schedule-bot
```

## 测试项目控制台

在 Telegram 中依次测试：

```text
/projects
/status api-report-agent
/logs api-report-agent
/logs api-report-agent 50
```

验收点：

- `/projects` 能列出 `projects.yaml` 中的项目
- `/status api-report-agent` 能返回远程状态脚本输出
- `/logs api-report-agent 50` 能返回远程日志
- 非白名单用户会被拒绝
- `/logs api-report-agent abc` 会被拒绝
- `/logs api-report-agent 999` 最多只查询 300 行
- 远程命令超时后 Bot 返回 `远程执行超时`
- `logs/audit.log` 有操作记录

## 日程命令

```text
/start
/help
/add YYYY-MM-DD HH:MM title
/list
/today
/tomorrow
/edit ID title 新标题
/edit ID time YYYY-MM-DD HH:MM
/edit ID desc 新备注
/remind ID 60m,30m,10m
/snooze 10m
/repeat ID daily|weekly|monthly
/done ID
/delete ID
```

示例：

```text
/add 2026-05-10 18:30 Team meeting
/list
/done 1
```

## 后续扩展方向

- 为项目控制台增加只读健康检查聚合页
- 为不同项目配置不同 Telegram 用户白名单
- 增加 Docker 部署方式
- 在保持“只读白名单脚本”的前提下扩展更多查询命令
