# ScrapeGoat — Tech Stack Reference

> Version 2.1 · March 2026

Complete reference for every technology, library, pattern, and architectural decision in the ScrapeGoat stack.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Frontend](#2-frontend)
3. [Backend](#3-backend)
4. [Scraping Engine Classes](#4-scraping-engine-classes)
5. [Browser Fingerprint Profiles](#5-browser-fingerprint-profiles)
6. [Session Architecture](#6-session-architecture)
7. [Proxy Rotation System](#7-proxy-rotation-system)
8. [Domain Blocking](#8-domain-blocking)
9. [Extraction Pipeline](#9-extraction-pipeline)
10. [HTTP Server](#10-http-server)
11. [Async Model](#11-async-model)
12. [Dependency Map](#12-dependency-map)
13. [Design Decisions](#13-design-decisions)

---

## 1. Architecture Overview

ScrapeGoat is a two-tier application:

```
┌─────────────────────────────────────────────────────────────┐
│  BROWSER  (any modern browser)                              │
│                                                             │
│  scrapegoat.html                                            │
│  ├── HTML5 layout                                           │
│  ├── CSS3 (custom props, grid, animations)                  │
│  └── Vanilla JS ES2020                                      │
│       ├── Engine/session/proxy/block config                 │
│       ├── fetch() → POST /api/scrape                        │
│       ├── Terminal log renderer                             │
│       └── Client-side export (Blob + download)             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP JSON  localhost:7331
┌────────────────────▼────────────────────────────────────────┐
│  PYTHON BACKEND  (server.py)                                │
│                                                             │
│  ThreadedHTTPServer (stdlib socketserver)                   │
│  └── ScrapeGoatHandler                                      │
│       ├── GET  /              → serves scrapegoat.html      │
│       ├── GET  /api/*         → JSON responses              │
│       └── POST /api/scrape   → run_scrape()                 │
│                                                             │
│  Scraping engine                                            │
│  ├── Fetcher / FetcherSession                               │
│  │    └── urllib.request + CookieJar + TLS profiles         │
│  ├── StealthyFetcher / StealthySession                      │
│  │    └── Fetcher + header rotation + jitter + IP spoof     │
│  ├── DynamicFetcher / DynamicSession                        │
│  │    └── Playwright async_api → Chromium                   │
│  ├── ProxyRotator                                           │
│  └── extract() → BeautifulSoup + lxml                      │
└─────────────────────────────────────────────────────────────┘
```

**Communication:** The frontend calls the backend over `localhost` via standard `fetch()`. All scrape operations — HTTP requests, browser automation, HTML parsing — happen server-side. The frontend never touches target websites directly.

---

## 2. Frontend

### Core Technologies

| Technology | Version | Role |
|---|---|---|
| HTML5 | Living Standard | Document structure, semantic markup |
| CSS3 | Living Standard | Layout, theming, animations |
| JavaScript | ES2020 | Application logic, API calls, export |

### CSS Architecture

All styles are in a single `<style>` block within `scrapegoat.html`. No preprocessor, no utility framework (Tailwind is not used — all classes are handwritten).

**Design system — CSS custom properties:**

```css
:root {
  --black:      #080a0f;   /* page background */
  --dark:       #0d1117;   /* sidebar background */
  --panel:      #111820;   /* card / input backgrounds */
  --panel2:     #141c26;   /* secondary panels */
  --border:     #1e2d3d;   /* all borders */
  --slate:      #2a3f5a;   /* mid-tone elements */
  --slate-light:#3d5a80;   /* hover states */
  --green:      #39d353;   /* primary accent — all interactive states */
  --green-dim:  #1a6b28;   /* dimmed green — borders, decorative */
  --green-glow: rgba(57,211,83,0.18); /* glow backgrounds */
  --white:      #e8eaf0;   /* body text */
  --gray:       #8899aa;   /* secondary text */
  --gray-dim:   #445566;   /* labels, placeholders */
  --accent:     #00ffa3;   /* progress bar highlight */
  --red:        #ff2d55;   /* errors, danger actions */
  --amber:      #ffb800;   /* warnings */
}
```

**Layout:** CSS Grid — two-column `300px 1fr` split between sidebar and main panel. Sidebar scrolls independently. Main panel is a flex column stacking hero, controls, tabs, terminal, and export bar.

**Visual effects (all CSS/SVG, no JavaScript):**

| Effect | Technique |
|---|---|
| CRT scanlines | `repeating-linear-gradient` fixed overlay, `z-index: 9999` |
| Film grain noise | Inline SVG `feTurbulence` filter tiled at 200% with `noiseShift` keyframe animation |
| Logo glitch | `::after` pseudo-element with `clip-path` polygon + opacity keyframes |
| Title RGB split | `::before` (red channel) + `::after` (green channel) with `translateX` + `skewX` |
| Grid background | Dual `linear-gradient` background-image on `.main-panel` |
| Status pulse | `@keyframes pulse` on `.status-dot` box-shadow |
| Button fill | `::before` sliding pseudo-element, `transform: translateX(-102% → 0)` |
| Floating goat | `@keyframes floatGoat` translateY on empty state SVG |

### Typography

| Font | Source | Usage |
|---|---|---|
| `Syncopate` (700) | Google Fonts | Hero title, logo, button labels, section titles — high-impact display |
| `Share Tech Mono` | Google Fonts | Terminal output, all code, labels, status — monospace data feel |
| `Barlow Condensed` (300/400/600/700) | Google Fonts | Body text, sidebar labels — legible condensed sans |

### JavaScript

Single inline `<script>` block. No module system, no bundler. Structured as named functions with a small amount of module-level state:

```javascript
// Module-level state
let scrapedData   = [];   // extracted items from last scrape
let currentFormat = 'CSV';
let currentTab    = 'terminal';
let proxyList     = [];   // proxies currently in the rotator
let blockedDomains= [];   // domains blocked in the current session
```

**Key functions:**

| Function | Description |
|---|---|
| `checkBackend()` | Polls `GET /api/health` every 4s; updates status dot |
| `runScrape()` | Collects all sidebar config, POSTs to `/api/scrape`, animates progress, replays server logs |
| `replayLogs(logs)` | Takes the `logs[]` array from the API response and streams entries into the terminal view |
| `renderResults(data)` | Populates the RAW DATA card grid (up to 80 cards) |
| `downloadData()` | Serialises `scrapedData` to chosen format and triggers `<a>` download via `Blob + createObjectURL` |
| `pushProxiesToBackend()` | POSTs current `proxyList` to `/api/proxies` |
| `addBlock() / removeBlock()` | Manages `blockedDomains[]`; rendered as badge pills |
| `refreshSessions()` | GETs `/api/sessions` and renders session pills in sidebar |

---

## 3. Backend

### Runtime

| Technology | Version | Role |
|---|---|---|
| Python | 3.10+ | Runtime (3.12+ recommended) |
| `asyncio` | stdlib | Async orchestration for Playwright |
| `http.server` | stdlib | HTTP request handling |
| `socketserver.ThreadingMixIn` | stdlib | Concurrent request handling |
| `http.cookiejar` | stdlib | Cookie persistence for HTTP sessions |
| `urllib.request` | stdlib | HTTP/HTTPS requests |
| `ssl` | stdlib | TLS configuration (cert verification disabled for scraping) |
| `threading` | stdlib | Thread-safe session and proxy state |

### External Packages

| Package | Version | Role |
|---|---|---|
| `beautifulsoup4` | ≥4.12 | HTML parsing and element extraction |
| `lxml` | ≥4.9 | Fast HTML parser backend for BeautifulSoup |
| `playwright` | ≥1.40 | Headless Chromium browser automation |

**Total external runtime dependencies: 3**

---

## 4. Scraping Engine Classes

### Inheritance Hierarchy

```
_BaseSession
├── Fetcher
│   ├── FetcherSession          (persistent cookies)
│   └── StealthyFetcher
│       └── StealthySession     (stealth + persistent cookies)
│
DynamicFetcher                  (independent — Playwright, not urllib)
└── DynamicSession              (Playwright + persistent cookies)
```

### `_BaseSession`

Abstract base providing shared infrastructure to all HTTP-based fetchers.

| Attribute / Method | Type | Description |
|---|---|---|
| `cookie_jar` | `http.cookiejar.CookieJar` | Shared cookie store across requests |
| `_extra_headers` | `dict` | Custom headers merged into every request |
| `_blocked_domains` | `set[str]` | Normalised domain blocklist |
| `proxy_rotator` | `ProxyRotator \| None` | Attached rotator (set by orchestrator) |
| `set_header(key, val)` | method | Add/override a persistent header |
| `block_domain(domain)` | method | Strips `*.` prefix, lowercases, adds to set |
| `_is_blocked(url)` | method | Checks hostname and all parent domains against blocklist |
| `_get_proxy(override)` | method | Returns override proxy, or next from rotator, or None |
| `_build_opener(proxy)` | method | Builds `urllib.request.OpenerDirector` with cookie + proxy + permissive TLS handlers |

### `Fetcher`

Fast HTTP fetcher with browser fingerprint impersonation.

```python
Fetcher(profile="chrome_win", timeout=20)
```

The `_build_headers()` method performs a deep copy of the selected profile dict, injects a `Referer` header derived from the target URL's origin, and merges `_extra_headers` and any per-call extra headers. The `get()` method builds a `urllib.request.Request`, opens it with the cookie-aware opener, reads the response body, detects charset from `Content-Type`, and returns a structured result dict including `ok`, `html`, `status`, `elapsed_ms`, `url`, `profile`, and `engine`.

### `FetcherSession`

Subclass of `Fetcher` with no additional code — the inherited `cookie_jar` on `_BaseSession` persists automatically across calls because the same `CookieJar` instance is reused on every `_build_opener()` call.

### `StealthyFetcher`

Extends `Fetcher` with anti-bot evasion layer.

```python
StealthyFetcher(rotate_profiles=True, jitter_ms=400)
```

**Evasion techniques:**

| Technique | Implementation |
|---|---|
| Profile rotation | Randomly selects a new profile from `BROWSER_PROFILES` on each `_build_headers()` call |
| Accept-Language rotation | Randomly selects from 4 realistic language strings |
| Header order randomisation | `random.shuffle()` on the header item list before returning — exploits Python dict insertion-order preservation |
| Fake IP injection | Generates a random `X.X.X.X` and sets both `X-Forwarded-For` and `X-Real-IP` |
| Timing jitter | `time.sleep(random.uniform(0, jitter_ms/1000))` before each request |

### `StealthySession`

Subclass of `StealthyFetcher` — same as `FetcherSession`, inherits cookie persistence automatically.

### `DynamicFetcher`

Full headless Chromium automation via Playwright. Independent class (does not inherit `_BaseSession`).

```python
DynamicFetcher(headless=True, timeout=30, blocked_domains=None)
```

**Stealth JS injected via `add_init_script()`** before any page scripts run:

```javascript
// Injected stealth payload removes all standard automation signals:
navigator.webdriver       → undefined
navigator.plugins         → [1, 2, 3, 4, 5]  (non-empty)
navigator.languages       → ['en-US', 'en']
navigator.platform        → 'Win32'
window.chrome             → { runtime: {} }
navigator.permissions.query  → spoofed (returns Notification.permission for 'notifications')
```

**Domain blocking** in Playwright is implemented at the network layer using `page.route("**/*", handler)`. The handler calls `route.abort()` for any request whose hostname matches the blocklist — the request never leaves the browser process.

**Session persistence** is handled by storing the full `context.cookies()` list after each successful scrape and passing it back via `ctx.add_cookies()` on the next call.

**Browser launch arguments:**

```python
"--no-sandbox"
"--disable-blink-features=AutomationControlled"
"--disable-dev-shm-usage"
"--disable-infobars"
```

### `DynamicSession`

Subclass of `DynamicFetcher`. Cookie list (`self._cookies`) is an instance attribute that persists between calls.

---

## 5. Browser Fingerprint Profiles

Five profiles defined in `BROWSER_PROFILES` dict. Each is a complete HTTP header set matching a real browser's network signature.

| Profile Key | Browser | Platform | Notable Headers |
|---|---|---|---|
| `chrome_win` | Chrome 122 | Windows 10 | Full `Sec-CH-UA` suite, `Sec-Fetch-*` |
| `chrome_mac` | Chrome 122 | macOS 10.15.7 | `Sec-CH-UA-Platform: "macOS"` |
| `firefox_win` | Firefox 123 | Windows 10 | No `Sec-CH-UA` (Firefox doesn't send it) |
| `safari_mac` | Safari 17.3.1 | macOS 14.3.1 | `AppleWebKit/605.1.15`, no Sec-CH-UA |
| `edge_win` | Edge 122 | Windows 10 | `Edg/122.0.0.0` in UA, Edge-specific `Sec-CH-UA` |

All profiles include the correct ordered set of headers that real browsers send. Order matters — some bot detectors fingerprint the header sequence, not just presence/absence.

---

## 6. Session Architecture

### HTTP Sessions (`FetcherSession`, `StealthySession`)

```
Request 1 → _build_opener(proxy) → HTTPCookieProcessor(self.cookie_jar)
                                  → Set-Cookie response headers → stored in cookie_jar
Request 2 → _build_opener(proxy) → same cookie_jar → Cookie header sent automatically
```

The `http.cookiejar.CookieJar` follows RFC 2965 and Netscape cookie spec. The `HTTPCookieProcessor` handler intercepts both outgoing requests (to inject `Cookie` header) and incoming responses (to store `Set-Cookie` headers).

### Playwright Sessions (`DynamicSession`)

```
Request 1 → new_context() → add_cookies([])    (empty on first call)
          ← context.cookies() → stored in self._cookies

Request 2 → new_context() → add_cookies(self._cookies)  (restored)
          ← context.cookies() → stored in self._cookies  (updated)
```

A new browser context is created per request (not a persistent browser instance). This trades startup overhead for clean isolation. Session state is carried via the `_cookies` list on the `DynamicSession` instance.

### In-Memory Session Store

```python
_SESSIONS: dict[str, _BaseSession | DynamicFetcher] = {}
_SESSIONS_LOCK = threading.Lock()
```

Sessions are keyed by the `session_id` string from the API request. The `_get_or_create_session()` function lazily instantiates the correct class based on the `engine` parameter. All access is protected by `_SESSIONS_LOCK` for thread safety.

---

## 7. Proxy Rotation System

### `ProxyRotator`

```python
ProxyRotator(proxies: list[str], strategy: str = "cyclic")
```

| Strategy | Behaviour |
|---|---|
| `cyclic` | Round-robin — increments `_index` modulo list length on each call |
| `random` | `random.choice(self.proxies)` on each call |

Thread safety: `_index` increments are protected by `self._lock` (a `threading.Lock`). `add()` and `remove()` also acquire the lock.

**Proxy format:** Standard URL format — `http://host:port` or `http://username:password@host:port`. The proxy is passed to `urllib.request.ProxyHandler` for HTTP fetchers, or to Playwright's `browser.launch(proxy={"server": proxy_str})` for the dynamic engine.

**Proxy priority:** per-request override → `proxy_rotator.next()` → no proxy.

### Global vs Session Proxies

The global `_PROXY_ROTATOR` (set via `POST /api/proxies`) is attached to sessions at creation time and to stateless fetchers at scrape time. A session can also be given its own rotator by assigning `session.proxy_rotator = ProxyRotator(...)` directly in code.

---

## 8. Domain Blocking

### HTTP Fetchers

`_BaseSession._is_blocked(url)` runs before any `urllib.request` call:

```python
host = urllib.parse.urlparse(url).hostname
for blocked in self._blocked_domains:
    if host == blocked or host.endswith("." + blocked):
        return True
```

Blocked requests return immediately with `{"ok": False, "error": "Domain blocked: ..."}` — no network activity.

### Playwright

`DynamicFetcher` registers a route handler on `page.route("**/*", handler)` that calls `route.abort()` for any matching request hostname. This intercepts all resource types (XHR, fetch, images, scripts, iframes) — not just the main document.

---

## 9. Extraction Pipeline

### `extract(html, tags, selector_method, selector_expr)`

```
Raw HTML string
    │
    ▼
BeautifulSoup(html, "lxml")
    │
    ├── Decompose <script>, <style>, <noscript>  (noise removal)
    │
    ├── For each tag in tags[]:
    │    ├── "class" → find_all(attrs={"class": True})
    │    ├── "id"    → find_all(attrs={"id": True})
    │    └── other   → find_all(tag)
    │    └── el.get_text(" ", strip=True) → append to results[]
    │
    ├── If selector_expr:
    │    ├── By.ID          → "#expr"
    │    ├── By.CLASS_NAME  → ".expr"
    │    ├── By.TAG_NAME    → "expr"
    │    └── others         → "expr" (used as CSS selector directly)
    │    └── soup.select(css) → el.get_text() → append to results[]
    │
    └── Deduplication pass:
         re.sub(r"\s+", " ", item).strip()
         → seen = set() → yield only unseen items
         → return clean list[str]
```

**Parser choice:** `lxml` is used as the BeautifulSoup parser backend (not `html.parser`). `lxml` is significantly faster on large pages and handles malformed HTML better.

---

## 10. HTTP Server

### `ThreadedHTTPServer`

```python
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
```

`ThreadingMixIn` spawns a new thread per request, allowing concurrent scrape operations. `daemon_threads = True` ensures threads do not block process exit. `allow_reuse_address = True` prevents `Address already in use` errors on rapid restarts.

### Request Routing

```
GET  /                    → _serve_frontend()  (reads scrapegoat.html from disk)
GET  /api/health          → {"status": "ok", "version": "2.0"}
GET  /api/profiles        → {"profiles": [...]}
GET  /api/sessions        → {"sessions": [...]}
POST /api/scrape          → asyncio.run(run_scrape(payload))
POST /api/proxies         → update _PROXY_ROTATOR
POST /api/sessions/clear  → clear _SESSIONS
OPTIONS *                 → CORS preflight (200 OK)
```

### CORS

All responses include:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

This allows the frontend to call the API even when opened via `file://` during development.

### Access Log Suppression

`log_message()` is overridden to a no-op. Server-side scrape progress is captured in the `logs[]` array of the API response and replayed in the frontend terminal — this is more useful than raw HTTP access logs.

---

## 11. Async Model

`DynamicFetcher.async_get()` is a native coroutine using `playwright.async_api`. It must run inside an async event loop.

`DynamicFetcher.get()` (sync wrapper) uses `asyncio.run()` to create a new event loop and run the coroutine to completion:

```python
def get(self, url, **kwargs):
    return asyncio.run(self.async_get(url, **kwargs))
```

`Fetcher.async_get()` and `StealthyFetcher.async_get()` use `loop.run_in_executor(None, ...)` to run the blocking `urllib` call in a thread pool without blocking the event loop:

```python
async def async_get(self, url, proxy=None, extra_headers=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: self.get(url, proxy, extra_headers))
```

The HTTP server handler calls `asyncio.run(run_scrape(payload))` directly — each request gets its own event loop. This is correct for the threaded server model (each request runs in its own thread).

---

## 12. Dependency Map

### Runtime Dependencies

```
server.py
├── beautifulsoup4          pip install
│   └── lxml                pip install (parser backend)
└── playwright              pip install
    └── chromium            playwright install chromium (binary, ~150MB)

scrapegoat.html
├── Google Fonts CDN        fonts.googleapis.com (optional — falls back to system fonts)
└── (no other external deps)
```

### Standard Library Usage

| Module | Used For |
|---|---|
| `asyncio` | Playwright coroutine execution, executor for blocking HTTP |
| `copy` | Deep copy of browser profile header dicts |
| `http.cookiejar` | `CookieJar` for HTTP session cookie storage |
| `http.server` | `BaseHTTPRequestHandler`, `HTTPServer` |
| `json` | Request/response serialisation |
| `os` | `os.environ` (optional port override) |
| `pathlib` | `Path(__file__).parent` for frontend file resolution |
| `random` | Profile rotation, IP generation, header shuffle, jitter |
| `re` | Whitespace normalisation in extraction pipeline |
| `socketserver` | `ThreadingMixIn` for concurrent request handling |
| `ssl` | Permissive SSL context for scraping (cert verify disabled) |
| `threading` | `Lock` for session store and proxy rotator thread safety |
| `time` | `time.sleep()` for stealth jitter, `time.time()` for elapsed timing |
| `traceback` | Error formatting in exception handlers |
| `urllib.error` | `HTTPError` catching |
| `urllib.parse` | URL parsing for domain extraction, blocked check, proxy building |
| `urllib.request` | `Request`, `OpenerDirector`, `HTTPCookieProcessor`, `ProxyHandler` |

---

## 13. Design Decisions

### Why no FastAPI / Flask / uvicorn?

The stdlib `http.server` + `socketserver.ThreadingMixIn` handles ScrapeGoat's use case with zero external dependencies. FastAPI would add uvicorn, starlette, pydantic, and anyio to the dependency tree. For a tool with 7 endpoints and no request validation schema requirements, that overhead is not justified.

### Why a single HTML file for the frontend?

Single-file deployment is a first-class feature, not a constraint. It means: copy one file, open in a browser, done. No `npm install`, no bundler config, no `node_modules` directory. The tradeoff is that CSS and JS are not separately cacheable, which is irrelevant for a localhost dev tool.

### Why Python stdlib HTTP instead of `httpx` or `requests`?

`requests` is a runtime dependency that requires a pip install. `urllib.request` is always present. For the Fetcher classes, `urllib` provides everything needed: connection pooling (via `http.client` underneath), cookie processing, proxy support, and custom headers. `requests` would be a convenience wrapper around the same underlying mechanics.

### Why `lxml` over `html.parser`?

`lxml` parses large, malformed pages 3–10× faster than Python's built-in `html.parser`. It also handles real-world HTML quirks (unclosed tags, mixed encodings, nested table structures) more robustly. The only downside is a pip install, but `lxml` is already a dependency of many projects so it is likely already present.

### Why no XPATH support?

`querySelectorAll` (used in the browser-side DOMParser in the legacy all-origins mode) does not support XPATH. In the backend, BeautifulSoup's `lxml` backend does support XPATH via `soup.find_all()` with the `find` method, but exposing it through the same `selector_expr` field would require different parsing logic and user-visible complexity. It is on the roadmap but deferred to avoid ambiguity in the current selector UX.

### Why `asyncio.run()` per request rather than a persistent loop?

The threaded HTTP server model means each request runs in its own thread. A persistent event loop would need to be shared across threads, requiring thread-safe access coordination. `asyncio.run()` creates and destroys a fresh event loop per request — this is slightly slower (milliseconds) but is simpler, safer, and correct. For ScrapeGoat's workload (human-initiated scrapes, not high-frequency automation), this tradeoff is appropriate.

### Why in-memory session storage?

Simplicity and zero dependencies. Persistent storage (SQLite, Redis) would require either an additional package or significant stdlib boilerplate. Sessions are expected to be short-lived scraping contexts, not long-term state. The roadmap item for SQLite persistence will address use cases that require durability across restarts.
