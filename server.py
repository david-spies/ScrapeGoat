"""
ScrapeGoat Backend — scraping engine server
Implements: Fetcher, StealthyFetcher, DynamicFetcher, sessions,
            proxy rotation, domain blocking, async support.
Serves the frontend HTML and exposes /api/scrape.

Run:  python3 server.py
"""

import asyncio
import copy
import http.cookiejar
import http.server
import json
import mimetypes
import os
import random
import re
import socketserver
import ssl
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

# ─── TLS / BROWSER FINGERPRINT PROFILES ──────────────────────────────────────
# Each profile mimics a real browser's TLS + HTTP header fingerprint.
# These are used by Fetcher (HTTP) and StealthyFetcher (enhanced stealth).

BROWSER_PROFILES = {
    "chrome_win": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-CH-UA": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
    },
    "chrome_mac": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-CH-UA": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    "firefox_win": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    },
    "safari_mac": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Connection": "keep-alive",
    },
    "edge_win": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-CH-UA": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    },
}

# Stealth profiles add extra anti-bot evasion headers
STEALTH_EXTRA_HEADERS = {
    "DNT": "1",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "X-Forwarded-For": None,  # filled dynamically
    "X-Real-IP": None,        # filled dynamically
}

# ─── PROXY ROTATOR ────────────────────────────────────────────────────────────

class ProxyRotator:
    """
    Cyclic or random proxy rotation across all fetcher types.
    Proxy format: 'http://user:pass@host:port' or 'http://host:port'
    """

    STRATEGIES = ("cyclic", "random")

    def __init__(self, proxies: list[str], strategy: str = "cyclic"):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"strategy must be one of {self.STRATEGIES}")
        self.proxies = proxies
        self.strategy = strategy
        self._index = 0
        self._lock = threading.Lock()

    def next(self) -> str | None:
        if not self.proxies:
            return None
        with self._lock:
            if self.strategy == "cyclic":
                proxy = self.proxies[self._index % len(self.proxies)]
                self._index += 1
            else:
                proxy = random.choice(self.proxies)
        return proxy

    def add(self, proxy: str):
        with self._lock:
            self.proxies.append(proxy)

    def remove(self, proxy: str):
        with self._lock:
            self.proxies = [p for p in self.proxies if p != proxy]

    def __len__(self):
        return len(self.proxies)


# ─── BASE SESSION ─────────────────────────────────────────────────────────────

class _BaseSession:
    """Shared state: cookies, headers, blocked domains."""

    def __init__(self):
        self.cookie_jar = http.cookiejar.CookieJar()
        self._extra_headers: dict = {}
        self._blocked_domains: set[str] = set()
        self.proxy_rotator: ProxyRotator | None = None

    def set_header(self, key: str, value: str):
        self._extra_headers[key] = value

    def block_domain(self, domain: str):
        """Block domain and all subdomains."""
        self._blocked_domains.add(domain.lstrip("*.").lower())

    def unblock_domain(self, domain: str):
        self._blocked_domains.discard(domain.lstrip("*.").lower())

    def _is_blocked(self, url: str) -> bool:
        try:
            host = urllib.parse.urlparse(url).hostname or ""
        except Exception:
            return False
        for blocked in self._blocked_domains:
            if host == blocked or host.endswith("." + blocked):
                return True
        return False

    def _get_proxy(self, override: str | None = None) -> str | None:
        if override:
            return override
        if self.proxy_rotator:
            return self.proxy_rotator.next()
        return None

    def _build_opener(self, proxy: str | None = None) -> urllib.request.OpenerDirector:
        handlers = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
        if proxy:
            ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            handlers.append(ph)
        # Permissive SSL for scraping
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
        return urllib.request.build_opener(*handlers)


# ─── FETCHER ──────────────────────────────────────────────────────────────────

class Fetcher(_BaseSession):
    """
    Fast HTTP fetcher that impersonates a browser's headers and TLS fingerprint.
    Supports proxy, session cookies, domain blocking, and async.
    """

    def __init__(self, profile: str = "chrome_win", timeout: int = 20):
        super().__init__()
        self.profile = profile
        self.timeout = timeout

    def _build_headers(self, url: str, extra: dict | None = None) -> dict:
        headers = copy.deepcopy(BROWSER_PROFILES.get(self.profile, BROWSER_PROFILES["chrome_win"]))
        # Set Referer to the origin
        parsed = urllib.parse.urlparse(url)
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
        headers.update(self._extra_headers)
        if extra:
            headers.update(extra)
        return headers

    def get(self, url: str, proxy: str | None = None,
            extra_headers: dict | None = None) -> dict:
        if self._is_blocked(url):
            return {"ok": False, "error": f"Domain blocked: {urllib.parse.urlparse(url).hostname}"}

        proxy = self._get_proxy(proxy)
        opener = self._build_opener(proxy)
        headers = self._build_headers(url, extra_headers)

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            t0 = time.time()
            with opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                encoding = resp.headers.get_content_charset("utf-8")
                try:
                    html = raw.decode(encoding, errors="replace")
                except Exception:
                    html = raw.decode("utf-8", errors="replace")
                elapsed = int((time.time() - t0) * 1000)
                return {
                    "ok": True,
                    "html": html,
                    "status": resp.status,
                    "elapsed_ms": elapsed,
                    "url": resp.url,
                    "profile": self.profile,
                    "engine": "Fetcher",
                }
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}: {e.reason}", "status": e.code}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def async_get(self, url: str, proxy: str | None = None,
                        extra_headers: dict | None = None) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.get(url, proxy, extra_headers))


# ─── FETCHER SESSION ──────────────────────────────────────────────────────────

class FetcherSession(Fetcher):
    """
    Fetcher with persistent cookie + state management across requests.
    Cookie jar is preserved between calls.
    """
    # Inherits everything from Fetcher; cookie_jar persists across calls
    # because the same opener factory reuses self.cookie_jar
    pass


# ─── STEALTHY FETCHER ─────────────────────────────────────────────────────────

class StealthyFetcher(Fetcher):
    """
    Enhanced anti-bot evasion:
    - Randomises header order (harder to fingerprint)
    - Adds realistic timing jitter
    - Rotates UA between requests
    - Injects spoofed IP headers (for proxied setups)
    - Varies Accept-Language per request
    """

    _LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.8",
        "en-US,en;q=0.8,es;q=0.5",
        "en-US,en;q=0.9,fr;q=0.3",
    ]

    _PROFILES_LIST = list(BROWSER_PROFILES.keys())

    def __init__(self, rotate_profiles: bool = True, jitter_ms: int = 400, **kwargs):
        super().__init__(**kwargs)
        self.rotate_profiles = rotate_profiles
        self.jitter_ms = jitter_ms

    def _build_headers(self, url: str, extra: dict | None = None) -> dict:
        # Rotate browser profile for fingerprint diversity
        if self.rotate_profiles:
            self.profile = random.choice(self._PROFILES_LIST)

        headers = super()._build_headers(url, extra)

        # Randomise Accept-Language
        headers["Accept-Language"] = random.choice(self._LANGUAGES)

        # Spoof IP headers (simulates being behind a proxy/CDN)
        fake_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
        headers["X-Forwarded-For"] = fake_ip
        headers["X-Real-IP"] = fake_ip

        # Shuffle header order (Python dicts preserve insertion order → randomise)
        items = list(headers.items())
        random.shuffle(items)
        return dict(items)

    def get(self, url: str, proxy: str | None = None,
            extra_headers: dict | None = None) -> dict:
        # Timing jitter to evade rate-limit fingerprinting
        if self.jitter_ms > 0:
            time.sleep(random.uniform(0, self.jitter_ms / 1000))
        result = super().get(url, proxy, extra_headers)
        if result.get("ok"):
            result["engine"] = "StealthyFetcher"
        return result


class StealthySession(StealthyFetcher):
    """StealthyFetcher with persistent cookie session."""
    pass


# ─── DYNAMIC FETCHER (Playwright) ─────────────────────────────────────────────

class DynamicFetcher:
    """
    Full browser automation via Playwright Chromium.
    Supports JS rendering, stealth scripts, domain blocking, proxy, async.
    """

    # Playwright stealth JS — injected before page load to mask automation signals
    _STEALTH_SCRIPT = """
    () => {
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Spoof plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Spoof languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Spoof platform
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32',
        });

        // Chrome runtime object
        window.chrome = { runtime: {} };

        // Permissions spoof
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    }
    """

    def __init__(self, headless: bool = True, timeout: int = 30,
                 blocked_domains: list[str] | None = None):
        self.headless = headless
        self.timeout = timeout * 1000  # Playwright uses ms
        self._blocked_domains: set[str] = set(d.lstrip("*.").lower() for d in (blocked_domains or []))
        self.proxy_rotator: ProxyRotator | None = None
        self._cookies: list[dict] = []

    def block_domain(self, domain: str):
        self._blocked_domains.add(domain.lstrip("*.").lower())

    def _is_blocked(self, url: str) -> bool:
        try:
            host = urllib.parse.urlparse(url).hostname or ""
        except Exception:
            return False
        for blocked in self._blocked_domains:
            if host == blocked or host.endswith("." + blocked):
                return True
        return False

    def _get_proxy(self, override: str | None = None) -> str | None:
        if override:
            return override
        if self.proxy_rotator:
            return self.proxy_rotator.next()
        return None

    async def async_get(self, url: str, proxy: str | None = None,
                        wait_for: str = "networkidle",
                        extra_headers: dict | None = None) -> dict:
        if self._is_blocked(url):
            return {"ok": False, "error": f"Domain blocked: {urllib.parse.urlparse(url).hostname}"}

        proxy_str = self._get_proxy(proxy)
        proxy_cfg = None
        if proxy_str:
            proxy_cfg = {"server": proxy_str}

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"ok": False, "error": "Playwright not installed. Run: playwright install chromium"}

        try:
            t0 = time.time()
            async with async_playwright() as pw:
                launch_args = {
                    "headless": self.headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-infobars",
                    ],
                }
                if proxy_cfg:
                    launch_args["proxy"] = proxy_cfg

                browser = await pw.chromium.launch(**launch_args)
                ctx = await browser.new_context(
                    user_agent=random.choice(list(BROWSER_PROFILES.values()))["User-Agent"],
                    viewport={"width": 1280 + random.randint(-100, 100),
                              "height": 800 + random.randint(-50, 50)},
                    locale="en-US",
                    timezone_id="America/New_York",
                    extra_http_headers=extra_headers or {},
                )

                # Restore session cookies
                if self._cookies:
                    await ctx.add_cookies(self._cookies)

                page = await ctx.new_page()

                # Block specified domains at the network level
                if self._blocked_domains:
                    async def _route_handler(route):
                        req_url = route.request.url
                        try:
                            req_host = urllib.parse.urlparse(req_url).hostname or ""
                        except Exception:
                            req_host = ""
                        for bd in self._blocked_domains:
                            if req_host == bd or req_host.endswith("." + bd):
                                await route.abort()
                                return
                        await route.continue_()
                    await page.route("**/*", _route_handler)

                # Inject stealth JS before page scripts run
                await page.add_init_script(self._STEALTH_SCRIPT)

                await page.goto(url, wait_until=wait_for, timeout=self.timeout)
                html = await page.content()
                final_url = page.url

                # Persist cookies for session
                self._cookies = await ctx.cookies()

                await browser.close()

            elapsed = int((time.time() - t0) * 1000)
            return {
                "ok": True,
                "html": html,
                "status": 200,
                "elapsed_ms": elapsed,
                "url": final_url,
                "profile": "playwright_chromium",
                "engine": "DynamicFetcher",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get(self, url: str, **kwargs) -> dict:
        """Sync wrapper around async_get."""
        return asyncio.run(self.async_get(url, **kwargs))


class DynamicSession(DynamicFetcher):
    """DynamicFetcher with persistent cookie session across calls."""
    pass


# ─── EXTRACTOR ────────────────────────────────────────────────────────────────

def extract(html: str, tags: list[str], selector_method: str,
            selector_expr: str, blocked_domains: list[str] | None = None) -> list[str]:
    """
    Parse HTML and extract text nodes by tag list and/or CSS selector.
    Returns deduplicated, cleaned text items.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove script/style noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    results = []

    for tag in tags:
        if tag in ("class", "id"):
            elements = soup.find_all(attrs={tag: True})
        else:
            elements = soup.find_all(tag)
        for el in elements:
            text = el.get_text(" ", strip=True)
            if text:
                results.append(text)

    # Custom selector
    if selector_expr:
        css = selector_expr
        method = selector_method.upper()
        if "ID" in method:
            css = f"#{selector_expr.lstrip('#')}"
        elif "CLASS_NAME" in method:
            css = f".{selector_expr.lstrip('.')}"
        elif "TAG_NAME" in method:
            css = selector_expr
        # CSS_SELECTOR, NAME → use as-is
        try:
            for el in soup.select(css):
                text = el.get_text(" ", strip=True)
                if text:
                    results.append(text)
        except Exception:
            pass

    # Dedupe + clean
    seen = set()
    clean = []
    for item in results:
        norm = re.sub(r"\s+", " ", item).strip()
        if norm and norm not in seen:
            seen.add(norm)
            clean.append(norm)

    return clean


# ─── SCRAPE ORCHESTRATOR ──────────────────────────────────────────────────────

# In-memory sessions keyed by session_id
_SESSIONS: dict[str, _BaseSession | DynamicFetcher] = {}
_SESSIONS_LOCK = threading.Lock()

# Shared proxy rotator (populated from /api/proxies)
_PROXY_ROTATOR: ProxyRotator | None = None

def _get_or_create_session(session_id: str | None, engine: str,
                           profile: str) -> _BaseSession | DynamicFetcher | None:
    if not session_id:
        return None
    with _SESSIONS_LOCK:
        if session_id not in _SESSIONS:
            if engine == "dynamic":
                _SESSIONS[session_id] = DynamicSession()
            elif engine == "stealth":
                _SESSIONS[session_id] = StealthySession(profile=profile)
            else:
                _SESSIONS[session_id] = FetcherSession(profile=profile)
            if _PROXY_ROTATOR:
                _SESSIONS[session_id].proxy_rotator = _PROXY_ROTATOR
        return _SESSIONS[session_id]


async def run_scrape(payload: dict) -> dict:
    """Main async scrape handler called by the HTTP server."""
    url           = payload.get("url", "").strip()
    engine        = payload.get("engine", "fetcher")        # fetcher|stealth|dynamic
    profile       = payload.get("profile", "chrome_win")
    tags          = payload.get("tags", ["p"])
    sel_method    = payload.get("selector_method", "")
    sel_expr      = payload.get("selector_expr", "")
    proxy_override = payload.get("proxy", None)
    session_id    = payload.get("session_id", None)
    blocked       = payload.get("blocked_domains", [])

    if not url:
        return {"ok": False, "error": "No URL provided"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    logs = []
    def log(msg, level="info"):
        logs.append({"msg": msg, "level": level, "ts": int(time.time() * 1000)})

    log(f"Target: {url}")
    log(f"Engine: {engine}  |  Profile: {profile}")
    log(f"Tags: {tags}  |  Selector: {sel_method} {sel_expr}")
    if blocked:
        log(f"Blocked domains: {blocked}", "warn")

    # ── Pick fetcher ──────────────────────────────────────────────────────────
    session = _get_or_create_session(session_id, engine, profile)

    if engine == "dynamic":
        fetcher = session if session else DynamicFetcher()
        for d in blocked:
            fetcher.block_domain(d)
        if _PROXY_ROTATOR:
            fetcher.proxy_rotator = _PROXY_ROTATOR
        log("Launching headless Chromium browser...")
        fetch_result = await fetcher.async_get(url, proxy=proxy_override)

    elif engine == "stealth":
        fetcher = session if session else StealthyFetcher(profile=profile)
        for d in blocked:
            fetcher.block_domain(d)
        if _PROXY_ROTATOR:
            fetcher.proxy_rotator = _PROXY_ROTATOR
        log("StealthyFetcher — rotating fingerprint + jitter active")
        fetch_result = await fetcher.async_get(url, proxy=proxy_override)

    else:  # fetcher (default)
        fetcher = session if session else Fetcher(profile=profile)
        for d in blocked:
            fetcher.block_domain(d)
        if _PROXY_ROTATOR:
            fetcher.proxy_rotator = _PROXY_ROTATOR
        log(f"Fetcher — impersonating {profile}")
        fetch_result = await fetcher.async_get(url, proxy=proxy_override)

    if not fetch_result.get("ok"):
        log(f"Fetch failed: {fetch_result.get('error')}", "error")
        return {"ok": False, "error": fetch_result["error"], "logs": logs}

    log(f"HTTP {fetch_result.get('status', '?')}  {fetch_result.get('elapsed_ms', '?')}ms  [{fetch_result.get('engine')}]", "success")
    log("Parsing DOM and extracting elements...")

    html = fetch_result["html"]
    items = extract(html, tags, sel_method, sel_expr, blocked)

    log(f"Extracted {len(items)} unique items", "success")

    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "elapsed_ms": fetch_result.get("elapsed_ms"),
        "engine": fetch_result.get("engine"),
        "url": fetch_result.get("url"),
        "status": fetch_result.get("status"),
        "session_id": session_id,
        "logs": logs,
    }


# ─── HTTP SERVER ──────────────────────────────────────────────────────────────
# Pure stdlib HTTP server — no FastAPI/uvicorn needed.

FRONTEND_PATH = Path(__file__).parent / "scrapegoat.html"
PORT = 7331


class ScrapeGoatHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress access logs; our terminal shows scrape logs instead
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html", "/scrapegoat.html"):
            self._serve_frontend()
        elif path == "/api/health":
            self._json({"status": "ok", "version": "2.0"})
        elif path == "/api/sessions":
            with _SESSIONS_LOCK:
                self._json({"sessions": list(_SESSIONS.keys())})
        elif path == "/api/profiles":
            self._json({"profiles": list(BROWSER_PROFILES.keys())})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        try:
            payload = json.loads(body)
        except Exception:
            self._json({"ok": False, "error": "Invalid JSON"}, 400)
            return

        if path == "/api/scrape":
            result = asyncio.run(run_scrape(payload))
            self._json(result)

        elif path == "/api/proxies":
            global _PROXY_ROTATOR
            proxies = payload.get("proxies", [])
            strategy = payload.get("strategy", "cyclic")
            _PROXY_ROTATOR = ProxyRotator(proxies, strategy) if proxies else None
            self._json({"ok": True, "count": len(proxies), "strategy": strategy})

        elif path == "/api/sessions/clear":
            sid = payload.get("session_id")
            with _SESSIONS_LOCK:
                if sid:
                    _SESSIONS.pop(sid, None)
                    self._json({"ok": True, "cleared": sid})
                else:
                    _SESSIONS.clear()
                    self._json({"ok": True, "cleared": "all"})

        else:
            self.send_response(404)
            self.end_headers()

    def _serve_frontend(self):
        if FRONTEND_PATH.exists():
            html = FRONTEND_PATH.read_bytes()
        else:
            html = b"<h1>scrapegoat.html not found alongside server.py</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self._cors()
        self.end_headers()
        self.wfile.write(html)

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), ScrapeGoatHandler)
    print(f"\n  🐐  ScrapeGoat backend running")
    print(f"  ➜  http://localhost:{PORT}\n")
    print(f"  Engines available: Fetcher, StealthyFetcher, DynamicFetcher (Playwright)")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
