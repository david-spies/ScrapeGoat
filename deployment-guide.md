# ScrapeGoat — Deployment Guide

> Version 2.1 · March 2026

---

## Table of Contents

1. [Project File Structure](#1-project-file-structure)
2. [File Descriptions](#2-file-descriptions)
3. [Pre-Deployment Checklist](#3-pre-deployment-checklist)
4. [Local Development — Single Machine](#4-local-development--single-machine)
5. [Production Deployment](#5-production-deployment)
6. [Environment Configuration](#6-environment-configuration)
7. [API Endpoint Reference](#7-api-endpoint-reference)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Project File Structure

All files live flat in a single project directory. There are no subdirectories required for the application to run.

```
scrapegoat/
│
├── scrapegoat.html        ← Frontend UI (single-file app)
├── server.py              ← Backend engine (Python stdlib + BS4 + Playwright)
├── requirements.txt       ← Python package dependencies
│
├── start.sh               ← One-command launcher (macOS / Linux)
├── start.bat              ← One-command launcher (Windows)
│
├── README.md              ← Project overview and quick start
├── deployment-guide.md    ← This file
└── tech-stack.md          ← Technology and architecture reference
```

### Strict Placement Rules

| File | Must be in same directory as `server.py`? | Notes |
|---|---|---|
| `scrapegoat.html` | **Yes** | Server reads it by path relative to itself |
| `server.py` | Root of project dir | Entry point |
| `requirements.txt` | Root of project dir | Used by `start.sh` / `start.bat` |
| `start.sh` / `start.bat` | Root of project dir | Must be run from project root |
| Markdown docs | Root of project dir | Documentation only, not loaded at runtime |

`server.py` resolves the frontend path as:

```python
FRONTEND_PATH = Path(__file__).parent / "scrapegoat.html"
```

If `scrapegoat.html` is moved to a subdirectory, update this line accordingly.

---

## 2. File Descriptions

### `scrapegoat.html`
The complete frontend application. Contains HTML structure, all CSS (custom properties, grid layout, glitch animations, scanlines), and all JavaScript (engine selection, session management, proxy configuration, domain blocking, terminal log renderer, export logic). No build step, no bundler, no npm packages. Served directly by `server.py` at `GET /`.

### `server.py`
The Python backend. Implements six scraping classes from scratch using only Python's standard library, `beautifulsoup4`, and `playwright`:

- `Fetcher` / `FetcherSession` — HTTP with TLS fingerprint spoofing
- `StealthyFetcher` / `StealthySession` — Anti-bot evasion layer
- `DynamicFetcher` / `DynamicSession` — Headless Playwright Chromium
- `ProxyRotator` — Cyclic and random proxy rotation
- `extract()` — HTML parsing and element extraction
- `ScrapeGoatHandler` — Threaded stdlib HTTP server on port `7331`

### `requirements.txt`
Declares two runtime packages (`beautifulsoup4`, `lxml`, `playwright`). All other dependencies are Python standard library. Install with:

```bash
pip install -r requirements.txt
playwright install chromium
```

### `start.sh` / `start.bat`
Shell wrappers that run the full setup sequence: check Python, install deps, install Playwright Chromium browser binary, check port availability, then launch `server.py`. Use these for first-run and routine restarts.

---

## 3. Pre-Deployment Checklist

Run through this before any deployment.

### Software Requirements

| Requirement | Minimum Version | Check Command |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | 22+ | `pip --version` |
| Git (optional) | Any | `git --version` |
| Chromium (via Playwright) | auto-installed | `playwright install chromium` |

Python 3.10 is required for the `X | Y` union type syntax used in `server.py`. Python 3.12+ is recommended.

### Network Requirements

| Direction | What | Required For |
|---|---|---|
| Outbound port 443 | Target websites | All scraping |
| Outbound port 443 | Playwright Chromium download | First-time `playwright install` |
| Inbound port 7331 | Browser to backend | All usage |

Port `7331` can be changed by editing `PORT = 7331` in `server.py`.

### Python Packages

```bash
# Verify all packages resolve before deployment
pip install -r requirements.txt --dry-run
```

---

## 4. Local Development — Single Machine

### Option A — One-Command Start (Recommended)

```bash
# macOS / Linux
cd scrapegoat/
bash start.sh

# Windows
cd scrapegoat\
start.bat
```

Open `http://localhost:7331` in your browser. The frontend is served directly by the backend — no separate dev server needed.

### Option B — Manual Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Playwright's Chromium browser binary (one-time)
playwright install chromium

# 3. Start the backend
python3 server.py
```

Expected output:

```
  🐐  ScrapeGoat backend running
  ➜  http://localhost:7331

  Engines available: Fetcher, StealthyFetcher, DynamicFetcher (Playwright)
  Press Ctrl+C to stop
```

### Option C — Keep Running After Terminal Close

```bash
# Using nohup
nohup python3 server.py > scrapegoat.log 2>&1 &
echo $! > scrapegoat.pid        # save PID for later

# Stop it
kill $(cat scrapegoat.pid)

# View logs
tail -f scrapegoat.log
```

### Option D — systemd Service (Linux)

Create `/etc/systemd/system/scrapegoat.service`:

```ini
[Unit]
Description=ScrapeGoat Scraping Backend
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/scrapegoat
ExecStart=/usr/bin/python3 /path/to/scrapegoat/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable scrapegoat
sudo systemctl start scrapegoat
sudo systemctl status scrapegoat
```

View logs:

```bash
journalctl -u scrapegoat -f
```

### Development Workflow

Editing `server.py` requires a server restart. There is no hot-reload. Editing `scrapegoat.html` takes effect on the next browser refresh with no restart needed, since the file is read from disk on every `GET /` request.

---

## 5. Production Deployment

ScrapeGoat's backend is a standard HTTP server on port `7331`. For production, put it behind a reverse proxy (nginx or Caddy) that handles TLS, compression, and access control.

### 5.1 nginx Reverse Proxy

#### Install nginx

```bash
sudo apt update && sudo apt install -y nginx
```

#### Create server block

```bash
sudo nano /etc/nginx/sites-available/scrapegoat
```

Paste:

```nginx
server {
    listen 80;
    server_name scrapegoat.yourdomain.com;

    # Redirect HTTP → HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name scrapegoat.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/scrapegoat.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/scrapegoat.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header Referrer-Policy no-referrer;

    location / {
        proxy_pass         http://127.0.0.1:7331;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;    # allow time for Playwright scrapes
        proxy_send_timeout 120s;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/scrapegoat /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### Add HTTPS with Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d scrapegoat.yourdomain.com
```

### 5.2 Caddy (Automatic HTTPS, Zero Config TLS)

```bash
sudo apt install -y caddy
```

`/etc/caddy/Caddyfile`:

```caddyfile
scrapegoat.yourdomain.com {
    reverse_proxy localhost:7331
}
```

```bash
sudo systemctl reload caddy
```

Caddy provisions and renews TLS automatically via Let's Encrypt.

### 5.3 Docker

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY scrapegoat.html .
COPY server.py .

EXPOSE 7331

CMD ["python3", "server.py"]
```

Build and run:

```bash
docker build -t scrapegoat:2.1 .
docker run -d \
  --name scrapegoat \
  -p 7331:7331 \
  --restart unless-stopped \
  scrapegoat:2.1
```

View logs:

```bash
docker logs -f scrapegoat
```

Stop / update:

```bash
docker stop scrapegoat && docker rm scrapegoat
docker build -t scrapegoat:2.1 . && docker run -d ...
```

### 5.4 Access Control

The backend has no built-in authentication. For internal tools, restrict access at the network/proxy layer:

**nginx basic auth:**

```bash
sudo apt install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd scrapegoat_user
```

Add to nginx `location /` block:

```nginx
auth_basic           "ScrapeGoat";
auth_basic_user_file /etc/nginx/.htpasswd;
```

**IP allowlist** (restrict to office/VPN CIDR):

```nginx
allow 203.0.113.0/24;
deny  all;
```

---

## 6. Environment Configuration

All configuration is inline in `server.py`. No `.env` file is required. Key settings:

| Setting | Location in `server.py` | Default | Notes |
|---|---|---|---|
| `PORT` | Module level constant | `7331` | Change to any free port |
| `FRONTEND_PATH` | Module level constant | `Path(__file__).parent / "scrapegoat.html"` | Adjust if moving HTML file |
| Fetcher `timeout` | `Fetcher.__init__` default arg | `20` seconds | Increase for slow targets |
| DynamicFetcher `timeout` | `DynamicFetcher.__init__` default arg | `30` seconds (×1000 → ms) | Playwright timeout |
| Stealth jitter | `StealthyFetcher.__init__` default arg | `400` ms max | Reduce for speed, increase for stealth |
| `headless` | `DynamicFetcher.__init__` default arg | `True` | Set `False` to watch the browser (debug only) |

To override the port without editing the file:

```bash
# Monkey-patch via environment variable (add to server.py if needed)
PORT = int(os.environ.get("SCRAPEGOAT_PORT", 7331))
```

---

## 7. API Endpoint Reference

The backend exposes a minimal REST API consumed by the frontend. All endpoints accept and return JSON.

### `GET /`
Serves `scrapegoat.html`. No parameters.

### `GET /api/health`
Returns `{"status": "ok", "version": "2.0"}`. Used by the frontend for the status indicator.

### `GET /api/profiles`
Returns the list of available browser fingerprint profiles.

```json
{ "profiles": ["chrome_win", "chrome_mac", "firefox_win", "safari_mac", "edge_win"] }
```

### `GET /api/sessions`
Returns all active session IDs currently held in memory.

```json
{ "sessions": ["sess-a1b2c3", "research-session"] }
```

### `POST /api/scrape`
The primary scrape endpoint.

**Request body:**

```json
{
  "url":             "https://news.ycombinator.com",
  "engine":          "fetcher",
  "profile":         "chrome_win",
  "tags":            ["p", "h1", "a"],
  "selector_method": "By.CSS_SELECTOR",
  "selector_expr":   ".titleline",
  "session_id":      "my-session",
  "proxy":           "http://proxy:8080",
  "blocked_domains": ["ads.example.com", "tracker.io"]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `url` | string | Yes | Target URL (http/https) |
| `engine` | string | No | `fetcher` \| `stealth` \| `dynamic`. Default: `fetcher` |
| `profile` | string | No | Browser profile key. Default: `chrome_win` |
| `tags` | array | No | HTML tags to extract (`p`, `h1`, `div`, `a`, `class`, `id`, `td`, `tr`) |
| `selector_method` | string | No | `By.*` selector method |
| `selector_expr` | string | No | Selector expression string |
| `session_id` | string | No | Session key. Omit for stateless request |
| `proxy` | string | No | Per-request proxy override |
| `blocked_domains` | array | No | Domains to block (includes subdomains) |

**Response:**

```json
{
  "ok":          true,
  "items":       ["Extracted text 1", "Extracted text 2"],
  "count":       142,
  "elapsed_ms":  834,
  "engine":      "Fetcher",
  "url":         "https://news.ycombinator.com",
  "status":      200,
  "session_id":  "my-session",
  "logs": [
    { "msg": "Target: https://...", "level": "info", "ts": 1709500000000 },
    { "msg": "HTTP 200  834ms  [Fetcher]", "level": "success", "ts": 1709500000834 }
  ]
}
```

### `POST /api/proxies`
Sets the global proxy rotator pool.

```json
{ "proxies": ["http://p1:8080", "http://user:pass@p2:8080"], "strategy": "cyclic" }
```

### `POST /api/sessions/clear`
Clears one or all sessions from memory.

```json
{ "session_id": "my-session" }   // clear one
{}                                // clear all
```

---

## 8. Troubleshooting

### `BACKEND OFFLINE` shown in the UI
The frontend cannot reach `http://localhost:7331`. Verify `server.py` is running (`ps aux | grep server.py`). Check that nothing else is using port 7331 (`lsof -i :7331`).

### `playwright install chromium` fails
Ensure outbound internet access is available. On restricted networks, download the Playwright browser archive on a machine with internet access and transfer it. See [Playwright offline docs](https://playwright.dev/python/docs/browsers#install-behind-a-firewall-or-a-proxy).

### Dynamic engine returns empty results
The page may require more time to load. In `server.py`, change the `DynamicFetcher` `wait_for` parameter from `"networkidle"` to `"domcontentloaded"` for faster but earlier capture, or increase the timeout.

### `ModuleNotFoundError: No module named 'bs4'`
Dependencies not installed. Run `pip install -r requirements.txt`.

### Python version errors (`X | Y` syntax)
Requires Python 3.10+. Run `python3 --version`. On systems with multiple Python versions, use `python3.12 server.py` explicitly.

### Port already in use
```bash
# Find what's using the port
lsof -i :7331
# Kill it
kill -9 $(lsof -ti :7331)
```

### Playwright `BrowserType.launch` error on Linux
Install system dependencies:
```bash
playwright install-deps chromium
# or manually:
sudo apt install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1
```

### Scrapes return no data on heavily guarded sites
Switch to the `stealth` or `dynamic` engine. For Cloudflare-protected sites, the `dynamic` engine with `networkidle` wait has the best bypass rate. Combining with a residential proxy further improves success.
