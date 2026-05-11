# Ingest

Capture actionable messages from anywhere — Discord, iOS share sheet, screenshots, or any HTTP client — into a LAN-hosted, AI-summarised todo list. No cloud. No API key. Runs on a Raspberry Pi.

![PWA screenshot](docs/screenshot.png)

## What it does

- Receives text or images via HTTP POST from any source on your LAN
- OCRs screenshots with Tesseract (no external service)
- Summarises with a local Ollama model (no API key required)
- Stores everything in SQLite
- Serves a mobile-first PWA: filter, group, drag to reorder, check off items
- Installable on iPhone/Android via "Add to Home Screen"

## Architecture

```
[iOS Shortcuts]  ──share sheet──▶ ┐
[Discord bot]    ──forward──────▶ │  POST /ingest
[Any LAN client] ──HTTP POST────▶ │  (ingest.lan)
                                  ▼
                           FastAPI (Docker)
                                  │
                    ┌─────────────┴──────────────┐
                    ▼                            ▼
               Ollama (local LLM)          SQLite DB
               summarise + tag             /db/ingest.db
                                            │
                                            ▼
                                      PWA (ingest.lan)
                                      filter / group / done
```

## Prerequisites

- Docker + Docker Compose
- [Traefik](https://traefik.io) reverse proxy with a `*.lan` TLS cert (or any reverse proxy — adjust labels)
- [Ollama](https://ollama.ai) running on your LAN with a model pulled: `ollama pull qwen2.5:3b`

## Quick start

```bash
git clone https://github.com/your-username/ingest
cd ingest
cp .env.example .env
# Edit .env — set OLLAMA_HOST at minimum
docker compose up -d api
```

Visit `https://ingest.lan` (or your configured hostname).

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OLLAMA_HOST` | Yes | — | Ollama base URL, e.g. `http://192.168.1.x:11434` |
| `OLLAMA_MODEL` | No | `qwen2.5:3b` | Any model pulled in Ollama |
| `DISCORD_TOKEN` | No | — | Discord bot token (only needed if using Discord) |
| `DISCORD_CHANNEL_ID` | No | — | Channel ID the bot watches |
| `INGEST_HOST` | No | `ingest.lan` | Traefik hostname |
| `TZ` | No | `UTC` | Container timezone |

## iOS Shortcuts

Since `.shortcut` files must be signed per-device, create them manually:

### "Ingest Text" shortcut

1. Open **Shortcuts** → tap **+**
2. Add action: **Receive** `Text` from **Share Sheet**
3. Add action: **Get Contents of URL**
   - URL: `https://ingest.lan/ingest`
   - Method: `POST`
   - Headers: `Content-Type: application/json`
   - Body (JSON):
     ```json
     {"source": "ios-text", "raw_text": "[Shortcut Input]"}
     ```
4. Name it **"Ingest Text"**
5. Enable in **Share Sheet** (shortcut settings → Show in Share Sheet)

### "Ingest Screenshot" shortcut

1. Open **Shortcuts** → tap **+**
2. Add action: **Receive** `Images` from **Share Sheet**
3. Add action: **Convert** `Shortcut Input` to `Base64`
4. Add action: **Get Contents of URL**
   - URL: `https://ingest.lan/ingest`
   - Method: `POST`
   - Headers: `Content-Type: application/json`
   - Body (JSON):
     ```json
     {"source": "ios-screenshot", "raw_text": "", "image_data": "[Base64 Encoded]"}
     ```
5. Name it **"Ingest Screenshot"**

**Note:** If using a self-signed `*.lan` cert, install your CA certificate on the device first:
- Serve it at `https://ingest.lan/ca` and visit that URL in Safari on the device
- Go to Settings → Profile Downloaded → Install, then Settings → General → About → Certificate Trust Settings → enable it

## Discord bot

1. Create a bot at [discord.com/developers](https://discord.com/developers/applications)
2. Enable **Message Content Intent** under Bot → Privileged Gateway Intents
3. Invite to your private server with `Send Messages` + `Add Reactions` permissions
4. Set `DISCORD_TOKEN` and `DISCORD_CHANNEL_ID` in `.env`
5. `docker compose up -d bot`

**Usage:** Forward any Discord message to the watched channel. The bot adds ✅ when ingested.

## HTTP API

Interactive docs available at `https://ingest.lan/docs` (Swagger UI) once running.

### Quick reference

```bash
# Ingest text
curl -X POST https://ingest.lan/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "cli", "raw_text": "Follow up with Jake about the invoice"}'

# List todo items
curl https://ingest.lan/api/items?done=0

# Mark done
curl -X PATCH https://ingest.lan/api/items/42 \
  -H "Content-Type: application/json" \
  -d '{"done": true}'

# Create group
curl -X POST https://ingest.lan/api/groups \
  -H "Content-Type: application/json" \
  -d '{"name": "Work"}'

# Assign item to group
curl -X PATCH https://ingest.lan/api/items/42 \
  -H "Content-Type: application/json" \
  -d '{"group_id": 1}'
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest text or image |
| `GET` | `/api/items` | List items (`?done=0/1&source=X&limit=50&offset=0`) |
| `PATCH` | `/api/items/{id}` | Update item (`done`, `group_id`, `ungroup`) |
| `GET` | `/api/sources` | List distinct sources |
| `GET` | `/api/groups` | List groups with nested items |
| `POST` | `/api/groups` | Create group |
| `PATCH` | `/api/groups/{id}` | Rename group |
| `DELETE` | `/api/groups/{id}` | Delete group (items become ungrouped) |
| `POST` | `/api/groups/{id}/reorder` | Reorder items (`{"item_ids": [3,1,2]}`) |
| `GET` | `/health` | Health check |

### Ingest payload

```json
{
  "source": "string",        // free-form label (discord, ios-text, cli, etc.)
  "raw_text": "string",      // text to ingest (optional if image_data set)
  "image_data": "string",    // base64-encoded image — OCR'd with Tesseract (optional)
  "image_url": "string",     // URL hint (logged only, not fetched) (optional)
  "metadata": {}             // arbitrary extra data (optional)
}
```

## Use from other services

Any service on your LAN can capture context with a one-liner:

```bash
# Shell
curl -s -X POST https://ingest.lan/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "my-service", "raw_text": "Thing to follow up on"}'
```

```js
// Node.js / browser
await fetch('https://ingest.lan/ingest', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ source: 'publisher', raw_text: text }),
})
```

```python
# Python
import httpx
httpx.post('https://ingest.lan/ingest', json={'source': 'script', 'raw_text': text})
```

## Roadmap

- [ ] Signal integration (signal-cli linked device)
- [ ] Voice memo → Whisper transcription
- [ ] macOS share sheet shortcut
- [ ] Email ingestion (forwarding alias)
- [ ] Browser bookmarklet

## Stack

- **API**: FastAPI + uvicorn
- **Database**: SQLite via aiosqlite
- **OCR**: Tesseract (pytesseract)
- **Summarisation**: Ollama (local, configurable model)
- **Frontend**: Vanilla JS PWA — no framework, no build step
- **Infra**: Docker, Traefik

## Licence

MIT
