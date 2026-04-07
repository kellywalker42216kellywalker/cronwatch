# cronwatch

A lightweight CLI tool to monitor, log, and alert on cron job failures with Slack and email integration.

---

## Installation

```bash
pip install cronwatch
```

Or install from source:

```bash
git clone https://github.com/yourname/cronwatch.git && cd cronwatch && pip install .
```

---

## Usage

Wrap any cron command with `cronwatch` to automatically log output and receive alerts on failure:

```bash
cronwatch --name "daily-backup" --notify slack,email -- /usr/bin/backup.sh
```

Configure your notification settings in `~/.cronwatch.yml`:

```yaml
slack:
  webhook_url: "https://hooks.slack.com/services/your/webhook/url"

email:
  smtp_host: "smtp.example.com"
  from: "alerts@example.com"
  to: "you@example.com"
```

Run with a timeout and log output to file:

```bash
cronwatch --name "etl-job" --timeout 300 --log /var/log/cronwatch/ -- python etl.py
```

View recent job history:

```bash
cronwatch history --last 10
```

---

## Options

| Flag | Description |
|------|-------------|
| `--name` | Identifier for the job |
| `--notify` | Notification channels (`slack`, `email`) |
| `--timeout` | Kill job after N seconds |
| `--log` | Directory to store logs |
| `--retries` | Retry count before alerting |

---

## License

MIT © 2024 [Your Name](https://github.com/yourname)