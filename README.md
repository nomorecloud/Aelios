# Aelios

Aelios is a lightweight AI companion gateway with a built-in web panel.

It gives you:

- a local dashboard for configuration
- memory management backed by SQLite
- tool calling (web fetch, file reading, image analysis, MCP bridge)
- reminder scheduling
- optional Feishu channel support

The goal is simple: clone it, start it, open the panel, fill in your API + persona settings, and use it.

## Project structure

- `saki-gateway/` — Python gateway backend
- `saki-phone/web/` — web dashboard served by the gateway

## Features

- Dashboard-protected admin panel (default password: `admin123`)
- Persona settings
- Chat / action / search / TTS / image API settings
- Feishu WebSocket channel support
- SQLite memory store with FTS search
- Session rotation and scheduler
- Built-in reminder APIs

## Quick start

### 1. Install dependencies

```bash
cd saki-gateway
python3 -m pip install -e .
python3 -m pip install lark-oapi
```

### 2. Start the gateway

```bash
PYTHONPATH=src python3 -m saki_gateway
```

Default address:

- `http://127.0.0.1:3457`

If deployed on a server, the default config listens on:

- `0.0.0.0:3457`

### 3. Open the panel

Open:

- `http://127.0.0.1:3457`

Default panel password:

- `admin123`

Then go to **Settings** and fill in:

- Persona
- Chat API
- Action API
- Search API
- Feishu channel (optional)

## Configuration

Main config file:

- `saki-gateway/data/config.json`

This repository ships with a **sanitized template config** at:

- `saki-gateway/data/config.example.json`

On first boot, the gateway will automatically create `saki-gateway/data/config.json` from that template if it does not already exist.

### Environment variable overrides

You can also override config with env vars:

- `SAKI_HOST`
- `SAKI_PORT`
- `SAKI_CONFIG_PATH`
- `SAKI_CHAT_BASE_URL` / `SAKI_CHAT_API_KEY` / `SAKI_CHAT_MODEL`
- `SAKI_ACTION_BASE_URL` / `SAKI_ACTION_API_KEY` / `SAKI_ACTION_MODEL`
- `SAKI_SEARCH_BASE_URL` / `SAKI_SEARCH_API_KEY` / `SAKI_SEARCH_MODEL`
- `SAKI_FEISHU_ENABLED`
- `SAKI_FEISHU_APP_ID`
- `SAKI_FEISHU_APP_SECRET`
- `SAKI_DASHBOARD_PASSWORD`

## Feishu

To enable Feishu, configure these fields in the panel or `config.json`:

- `channels.feishu_enabled`
- `channels.feishu_app_id`
- `channels.feishu_app_secret`

The gateway supports Feishu long connection (WebSocket) message receive and reply flow.

## API overview

- `GET /health`
- `GET /api/config`
- `POST /api/config`
- `GET /api/tools`
- `POST /api/tools/execute`
- `GET /api/memories`
- `POST /api/memories`
- `PUT /api/memories/{id}`
- `DELETE /api/memories/{id}`
- `GET /api/memories/search?q=...`
- `GET /api/context`
- `GET /api/reminders`
- `POST /api/reminders`
- `DELETE /api/reminders/{id}`
- `POST /api/chat/respond`
- `POST /api/chat/complete`

## Security notes

- This repo does **not** include real API keys or channel secrets.
- Runtime databases and logs are ignored by `.gitignore`.
- The default dashboard password is only for first boot convenience — change it immediately.
- If exposed publicly, put the service behind HTTPS / a reverse proxy.

## Local data

The following are local runtime files and are intentionally not committed:

- `saki-gateway/data/*.db`
- `saki-gateway/data/*.db-shm`
- `saki-gateway/data/*.db-wal`
- `saki-gateway/data/raw/`

## License

Add your preferred license before public distribution if needed.
