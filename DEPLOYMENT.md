# Deployment guide

How to run the Human–AI Cooperative Word Game on a server for the study.
Secret values (API key, database password, Prolific code) are **not** in this
repository; I will send them to you separately.

## 1. What runs

- One **Streamlit** web app (Python), started with `streamlit run app.py`.
  It is a single process that serves all participants; each browser tab is
  a session kept in the server's memory.
- A **PostgreSQL** database stores all study data (the existing, managed
  Supabase instance).
- The app calls the **OpenAI API** for the AI teammate.
- Participants arrive from **Prolific** through the study link.
  A session takes about 45–60 minutes; several participants may play at the
  same time.

## 2. Requirements

| Item | Requirement |
|---|---|
| Python | 3.12 |
| Python packages | `pip install -r requirements.txt` (pinned versions, incl. `streamlit==1.50.0`) |
| Outbound network | HTTPS to `api.openai.com`; TCP to the PostgreSQL host and port |
| Database | The existing Supabase PostgreSQL database (`DATABASE_URL`, which I will send you); nothing to set up (section 5) |
| Web server | A reverse proxy with HTTPS **and WebSocket support** (section 6) |

## 3. Install

```bash
git clone https://github.com/Shima1994/human-ai-game.git
cd human-ai-game
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. Configuration

Put all settings in one environment file on the server, for example
`/etc/human-ai-game.env`, one `NAME=value` per line. The service in section 6
loads this file when it starts. Please make it readable only by the service
user, as it contains the secrets.

| Setting | Required | Purpose | Example / value |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | Key for the OpenAI API | sent separately |
| `DATABASE_URL` | yes | PostgreSQL connection URI | `postgresql://USER:PASSWORD@HOST:PORT/DBNAME` |
| `PROLIFIC_COMPLETION_CODE` | yes (main study) | Completion code of the Prolific study, shown at the end and used for the "Return to Prolific" link | sent separately |
| `DEPLOYMENT_VERSION` | recommended | Stored with every session; identifies this server | `colaps-2026-10` |
| `CODE_COMMIT` | recommended | Exact code version, stored with every session | output of `git rev-parse HEAD` |

Example `/etc/human-ai-game.env`:

```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
PROLIFIC_COMPLETION_CODE=XXXXXXXX
DEPLOYMENT_VERSION=colaps-2026-10
CODE_COMMIT=<output of git rev-parse HEAD>
```

`.streamlit/config.toml` is part of the repository and should be kept as it
is: it enables static files (self-hosted fonts), hides error details from
participants, fixes the light theme and handles one click at a time per
participant.

## 5. Database

The study keeps using the existing database (the `DATABASE_URL` I send). No
new database and no manual setup are needed: all tables already exist, and
the app recreates any that are missing when it starts.

## 6. Run the app

From the project folder:

```bash
streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true
```

If the app is served under a sub-path (e.g. `https://example.org/human-ai-game/`),
add `--server.baseUrlPath human-ai-game`.

If it helps, here is an example service file for systemd:

```ini
[Unit]
Description=Human-AI word game (Streamlit)
After=network-online.target

[Service]
WorkingDirectory=/opt/human-ai-game
EnvironmentFile=/etc/human-ai-game.env
ExecStart=/opt/human-ai-game/venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Reverse proxy

Streamlit keeps a **WebSocket** open for each participant (`/_stcore/stream`).
The proxy must pass WebSocket upgrades, keep idle connections open for at
least the length of a session, and pass the query string unchanged (it
carries the Prolific IDs). Example for nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:8501;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 10800;
    proxy_send_timeout 10800;
    proxy_buffering off;
}
```

## 7. Operation

- **The app is meant to run as a single instance.** Sessions live in the
  server's memory, so several instances behind a load balancer would lose
  participants' progress.
- **A restart ends every running session**, so updates are best done when
  nobody is in the study. If I push a change, I will let you know; updating
  is then `git pull` and a restart.
- If something goes wrong, the log usually says why: "OPENAI_API_KEY is not
  configured" or "DATABASE_URL is not configured" means a missing setting in
  the environment file.

## 8. Check after deploying

1. `curl https://<host>/<path>/_stcore/health` returns `ok`.
2. The app address opens the consent page with the university logos and the
   correct fonts (static files are served).

After that, please let me know and send me the address; I will play a full
test session myself.

## Contact

Shima Ghasempour, shima.ghasempour-ardestani@stud.uni-due.de
