# tg_schedule_bot

Telegram 私人 AI 日程与远程项目通知助手。

核心原则：

- 日程提醒由本地调度系统负责，AI 只做解析和分析。
- 远程项目控制只允许执行 `projects.yaml` 中声明的固定脚本。
- 不允许用户传入自由 shell 命令。
- Telegram 手动控制命令必须通过白名单。

## 功能

日程命令：

```text
/start
/help
/add YYYY-MM-DD HH:MM 标题
/list
/today
/tomorrow
/edit ID title|time|desc 新内容
/snooze 10m
/repeat ID daily|weekly|monthly
/remind ID 60m,30m,10m
/done ID
/delete ID
```

远程项目控制：

```text
/projects
/status <project>
/logs <project> [lines]
/pull_notifications <project>
```

通知拉取：

- 定时通过 SSH 执行 `scripts.notifications`
- 读取远程 JSONL 通知归档
- 根据 notification `id` 去重
- Telegram 发送成功后才写入 `pushed_notifications`
- Telegram 失败时下一轮重试

## 项目结构

```text
.
├── main.py
├── config.py
├── db.py
├── handlers.py
├── notification_puller.py
├── parser.py
├── reminder.py
├── scheduler.py
├── adapters/
│   └── ssh_adapter.py
├── ai/
├── handlers/
│   ├── notification_handlers.py
│   └── project_handlers.py
├── workers/
├── projects.yaml
├── redeploy.sh
├── requirements.txt
└── systemd/
    └── tg_schedule_bot.service
```

## .env

```env
TELEGRAM_BOT_TOKEN=
DEFAULT_TIMEZONE=Asia/Singapore
DATABASE_PATH=./data/schedule.db
CHECK_INTERVAL_SECONDS=30
DEFAULT_REMIND_BEFORE_MINUTES=30,10,0
ALLOWED_USER_IDS=

AI_PROVIDER=disabled
AI_API_KEY=
AI_BASE_URL=
AI_MODEL=
AI_TIMEOUT_SECONDS=20

MORNING_SUMMARY_HOUR=8
EVENING_SUMMARY_HOUR=22
LOG_DIR=./logs
SQLITE_BUSY_TIMEOUT_MS=5000

SSH_KEY_PATH=/opt/tg_schedule_bot/keys/control_key
SSH_TIMEOUT_SECONDS=10
DEFAULT_LOG_LINES=80
PROJECTS_CONFIG_PATH=./projects.yaml

NOTIFICATION_PULL_ENABLED=true
NOTIFICATION_PULL_INTERVAL_SECONDS=120
NOTIFICATION_PULL_PROJECTS=api-report-agent
NOTIFICATION_PULL_LINES=50
TELEGRAM_NOTIFY_CHAT_ID=
```

`ALLOWED_USER_IDS` 不为空时，只有白名单用户可以执行手动控制命令。

`TELEGRAM_NOTIFY_CHAT_ID` 用于定时通知推送；手动 `/pull_notifications` 在未配置该值时会推送到当前聊天。

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

用户只能传项目名和有限参数，不能传远程命令。

## 远程通知 JSONL

`notifications_tail.sh` 应输出 JSONL，每行一条通知，例如：

```json
{"id":"2026-05-10T12:30:00+08:00-report-ok","level":"info","title":"日报生成完成","time":"2026-05-10T12:30:00+08:00","body":"xxxx","attachments":["/path/to/file"]}
```

Telegram 推送格式：

```text
[api-report-agent] INFO
标题：日报生成完成
时间：2026-05-10T12:30:00+08:00

正文：
xxxx

附件：
- /path/to/file
```

消息长度限制为 3500 字符，超过会截断。

## 数据库

新增通知去重表：

```sql
CREATE TABLE IF NOT EXISTS pushed_notifications (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    level TEXT,
    title TEXT,
    time TEXT,
    pushed_at TEXT NOT NULL
);
```

## 本地运行

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

## systemd

只允许使用：

```text
tg_schedule_bot.service
```

安装：

```bash
sudo cp /opt/tg_schedule_bot/systemd/tg_schedule_bot.service /etc/systemd/system/tg_schedule_bot.service
sudo systemctl daemon-reload
sudo systemctl enable tg_schedule_bot
sudo systemctl start tg_schedule_bot
sudo systemctl --no-pager --full status tg_schedule_bot
```

如果存在旧服务 `tg-schedule-bot.service`，请删除，避免 Telegram polling 多实例冲突：

```bash
sudo systemctl stop tg-schedule-bot
sudo systemctl disable tg-schedule-bot
sudo rm -f /etc/systemd/system/tg-schedule-bot.service
sudo systemctl daemon-reload
```

## 如何 redeploy

脚本路径：

```text
/opt/tg_schedule_bot/redeploy.sh
```

首次设置执行权限：

```bash
chmod +x redeploy.sh
```

执行：

```bash
sudo ./redeploy.sh
```

`redeploy.sh` 会自动完成：

- `git pull`
- 检查并创建 `.venv`
- 使用 `/opt/tg_schedule_bot/.venv/bin/python -m pip` 安装 `requirements.txt`
- 检查 `.env`、`projects.yaml`、`keys/control_key`
- `systemctl daemon-reload`
- 重启 `tg_schedule_bot`
- 输出 `systemctl --no-pager --full status tg_schedule_bot`
- 追加写入 `/opt/tg_schedule_bot/deploy.log`

脚本可重复执行，不依赖手工 `activate` venv。

## 验收

- `/pull_notifications api-report-agent` 可手动拉取
- 定时任务可自动拉取
- 同一 notification `id` 不重复推送
- Telegram 失败时下一轮重试
- `projects.yaml` 未配置 `notifications` 时给出明确错误
- 不影响 `/status`、`/logs`
- 不影响原有日程提醒
- `redeploy.sh` 可重复执行并追加 `deploy.log`
- 缺少 `.env`、`projects.yaml`、`keys/control_key` 时 redeploy 失败退出
- 只保留一个 Telegram polling 服务：`tg_schedule_bot`
