<img width="1280" height="590" alt="ScrapeGoat_Home" src="https://github.com/user-attachments/assets/0adb0430-9d38-4cdb-9ff5-0851e83838cb" />

# 🐐 ScrapeGoat

> **Web data extraction terminal. Three engines. Full session control. Zero framework overhead.**

ScrapeGoat is a full-stack web scraper with a tech-noir terminal UI. The frontend is a single self-contained HTML file. The backend is a pure Python server implementing six scraping classes — from fast TLS-fingerprinted HTTP requests to full Playwright Chromium browser automation — with built-in session management, proxy rotation, and domain blocking.

No framework. No build step. One command to run.

![Version](https://img.shields.io/badge/version-2.1-33ffff?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10+-5D81FF?style=flat-square)
![React](https://img.shields.io/badge/BS4-4.12.0-884dff?style=flat-square)
![Playwright](https://img.shields.io/badge/playwright-1.40.0-F0Fd02?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-F0F2F5?style=flat-square)

---

## Engines

| Engine | Class | Best For |
|---|---|---|
| **Fetcher** | `Fetcher` / `FetcherSession` | Static pages — fast HTTP with browser TLS fingerprint |
| **Stealth** | `StealthyFetcher` / `StealthySession` | Bot-protected pages — header rotation, timing jitter, IP spoofing |
| **Dynamic** | `DynamicFetcher` / `DynamicSession` | JS-rendered SPAs — full headless Chromium via Playwright |

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Run

```bash
# Clone or unzip the project
cd scrapegoat/

# macOS / Linux
bash start.sh

# Windows
start.bat
```

Open **[http://localhost:7331](http://localhost:7331)** in your browser.

That's it. `start.sh` installs all dependencies, installs the Playwright Chromium binary, and starts the server in one step.

### Manual Start

```bash
pip install -r requirements.txt
playwright install chromium
python3 server.py
```

---

## Features

### Fetching

- **TLS fingerprint impersonation** — 5 browser profiles (Chrome/Win, Chrome/Mac, Firefox, Safari, Edge) with exact Sec-CH-UA, Sec-Fetch-\*, Accept headers
- **Dynamic loading** — Playwright Chromium with stealth JS injection (removes `navigator.webdriver`, spoofs plugins, platform, permissions)
- **Anti-bot stealth** — per-request UA rotation, randomised header insertion order, timing jitter (0–400ms), spoofed X-Forwarded-For / X-Real-IP headers

### Sessions

- **Persistent cookies** — HTTP sessions use `http.cookiejar.CookieJar`; Playwright sessions save/restore `context.cookies()` across requests
- **Named sessions** — create a session ID in the UI; all requests with that ID share the same cookie state
- **Session inspection** — sidebar shows active sessions; click any to reuse, or clear individually or all at once

### Proxies

- **Proxy rotation** — `ProxyRotator` with cyclic and random strategies
- **Per-request override** — bypass the rotator for a single request
- **Live management** — add/remove proxies from the UI without restarting the server
- **All fetcher types** — proxy support on Fetcher, StealthyFetcher, and DynamicFetcher

### Domain Blocking

- **HTTP fetchers** — domain check runs before any request leaves the process
- **Playwright** — blocked at the network level via `page.route()` abort
- **Subdomain matching** — blocking `example.com` also blocks all subdomains

### Extraction

- **Tag targeting** — `<p>`, `<h1>`, `<h2>`, `<div>`, `<a>`, `.class`, `#id`, `<td>`, `<tr>`
- **Custom selectors** — `By.CLASS_NAME`, `By.CSS_SELECTOR`, `By.ID`, `By.LINK_TEXT`, `By.NAME`, `By.PARTIAL_LINK_TEXT`, `By.TAG_NAME`
- **Smart deduplication** — whitespace normalisation + set deduplication before returning
- **Script/style stripping** — `<script>` and `<style>` removed before extraction

### Export

| Format | Description |
|---|---|
| CSV | Header + one quoted value per row |
| JSON | Pretty-printed array |
| XLSX | TSV — opens natively in Excel |
| SQL | `CREATE TABLE` + `INSERT INTO` statements |

---

## Usage

1. Enter a **target URL** in the sidebar
2. Select **engine** — Fetcher, Stealth, or Dynamic
3. Choose a **browser profile** (Fetcher and Stealth only)
4. Check **tags** to extract
5. Optionally set a **custom selector** with a `By.*` method
6. Optionally set a **Session ID** for persistent cookies
7. Add **proxies** and choose rotation strategy if needed
8. Add **blocked domains** to suppress tracking or ad calls
9. Hit **EXECUTE** — watch the terminal stream the scrape log
10. Switch to **RAW DATA** tab to browse results
11. Select export format and click **DOWNLOAD**

---

## Project Structure

```
scrapegoat/
├── scrapegoat.html      ← Full frontend (HTML + CSS + JS, no build step)
├── server.py            ← Backend engine (stdlib + bs4 + playwright)
├── requirements.txt     ← Python dependencies
├── start.sh             ← macOS / Linux launcher
├── start.bat            ← Windows launcher
├── README.md            ← This file
├── deployment-guide.md  ← File placement, deployment procedures, API reference
└── tech-stack.md        ← Architecture, class map, technology decisions
```

> `scrapegoat.html` and `server.py` must live in the same directory.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serves `scrapegoat.html` |
| GET | `/api/health` | Health check |
| GET | `/api/profiles` | Lists browser fingerprint profiles |
| GET | `/api/sessions` | Lists active session IDs |
| POST | `/api/scrape` | Executes a scrape |
| POST | `/api/proxies` | Updates the proxy rotator pool |
| POST | `/api/sessions/clear` | Clears one or all sessions |

Full schemas in [`deployment-guide.md`](./deployment-guide.md).

---

## Configuration

All settings are constants in `server.py`. No `.env` file required.

| Setting | Default | Edit |
|---|---|---|
| Port | `7331` | `PORT = 7331` |
| Frontend path | `./scrapegoat.html` | `FRONTEND_PATH` constant |
| HTTP request timeout | `20s` | `Fetcher.__init__` default arg |
| Playwright timeout | `30s` | `DynamicFetcher.__init__` default arg |
| Stealth jitter | `400ms` max | `StealthyFetcher.__init__` default arg |
| Headless mode | `True` | `DynamicFetcher(headless=False)` |

---

## Limitations

- No HTTP/3 — Python `urllib` uses HTTP/1.1. Integrate `curl-cffi` for full HTTP/3 + TLS fingerprinting
- XPATH selectors not supported — use `By.CSS_SELECTOR` instead
- In-memory sessions only — state is lost on server restart
- Single process — Playwright scrapes block one thread each

---

## Roadmap

- [ ] `curl-cffi` for HTTP/2 + HTTP/3 TLS fingerprinting
- [ ] Persistent session storage (SQLite)
- [ ] Pagination and recursive crawl
- [ ] Scheduled jobs
- [ ] Captcha solver integration

---

## License

MIT — use it, fork it, scrape responsibly.

Authors

    David Spies
