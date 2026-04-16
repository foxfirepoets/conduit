"""
cato/tools/browser.py — Browser automation using Patchright (stealth Playwright fork).

Actions: navigate, snapshot, click, type, fill, screenshot, pdf, search,
         eval, extract_main, output_to_file, accessibility_snapshot,
         network_requests, scroll, wait, wait_for, key_press, hover,
         select_option, handle_dialog, navigate_back, console_messages
Search engine: DuckDuckGo only (Google/Brave block bots).
Browser: Chromium only with persistent profile at ~/.cato/browser_profile/.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..platform import get_data_dir

logger = logging.getLogger(__name__)

_CATO_DIR = get_data_dir()


@dataclass
class FingerprintProfile:
    """Randomized browser fingerprint for one session."""
    viewport_w: int = 1920
    viewport_h: int = 1080
    user_agent: str = ""
    locale: str = "en-US"
    timezone: str = "America/New_York"
    color_depth: int = 24
    device_scale_factor: float = 1.0


@dataclass
class ProxyConfig:
    """Proxy configuration for browser sessions."""
    host: str = ""
    port: int = 8080
    username: str = ""
    password: str = ""
    protocol: str = "http"  # "http" or "socks5"

    @property
    def server_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ProxyConfig":
        return cls(
            host=payload.get("host", ""),
            port=int(payload.get("port", 8080)),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            protocol=payload.get("protocol", "http"),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "has_auth": bool(self.username or self.password),
        }


_PROFILE_DIR = _CATO_DIR / "browser_profile"
_SCREENSHOT_DIR = _CATO_DIR / "workspace" / "screenshots"
_PDF_DIR = _CATO_DIR / "workspace" / "pdfs"
_SESSION_DIR = _CATO_DIR / "sessions"


def _html_to_markdown(html: str) -> str:
    """Lightweight HTML to Markdown: headings, lists, code, links. No heavy dependency."""
    import re
    s = html
    # Strip script/style
    s = re.sub(r"<script[^>]*>.*?</script>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<style[^>]*>.*?</style>", "", s, flags=re.DOTALL | re.IGNORECASE)
    # Headings
    for i in range(6, 0, -1):
        s = re.sub(rf"<h{i}[^>]*>(.*?)</h{i}>", r"\n" + "#" * i + r" \1\n", s, flags=re.DOTALL | re.IGNORECASE)
    # Code blocks
    s = re.sub(r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", s, flags=re.DOTALL | re.IGNORECASE)
    # Links
    s = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r"[\2](\1)", s, flags=re.DOTALL | re.IGNORECASE)
    # Lists
    s = re.sub(r"<li[^>]*>", "\n- ", s, re.IGNORECASE)
    s = re.sub(r"</?(ul|ol)[^>]*>", "\n", s, re.IGNORECASE)
    s = re.sub(r"</li>", "", s, re.IGNORECASE)
    # Paragraphs and line breaks
    s = re.sub(r"</p>", "\n\n", s, re.IGNORECASE)
    s = re.sub(r"<br\s*/?>", "\n", s, re.IGNORECASE)
    s = re.sub(r"<p[^>]*>", "\n", s, re.IGNORECASE)
    # Strip remaining tags
    s = re.sub(r"<[^>]+>", "", s)
    # Decode common entities
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"\n{3,}", "\n\n", s).strip()


class BrowserTool:
    """Browser automation using Patchright (stealth Playwright fork).

    Provides:
    - navigate(url): Go to URL, return page title + visible text
    - snapshot():    Return current page title + text + interactive elements
    - click(selector): Click element by CSS selector or text
    - type(selector, text): Type text into input
    - screenshot():  Take screenshot, save to workspace, return path
    - pdf(filename): Save page as PDF
    - search(query): DuckDuckGo search, return top 5 results

    Uses persistent browser profile at ~/.cato/browser_profile/
    Chromium only (no Firefox, no WebKit)
    """

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        profile_dir: Path | None = None,
        screenshot_dir: Path | None = None,
        pdf_dir: Path | None = None,
        session_dir: Path | None = None,
        proxy_config: ProxyConfig | dict[str, Any] | None = None,
        headless: bool = True,
    ) -> None:
        self._browser = None
        self._page = None
        self._playwright = None
        self._network_log: list[dict] = []
        self._console_messages: list[dict] = []
        self._cdp_session = None
        self._fingerprint: FingerprintProfile = FingerprintProfile()  # will be replaced in _ensure_browser
        self._noise_seed: int = random.randint(1, 99999)
        self._stealth_js: str = ""  # built in _ensure_browser; injected post-navigate
        self._proxy_config: Optional[ProxyConfig] = None
        self._explicit_proxy_config: Optional[ProxyConfig] = self._coerce_proxy_config(proxy_config)
        self._proxy_list: list[ProxyConfig] = []
        self._proxy_index: int = 0
        self._data_dir = data_dir or _CATO_DIR
        self._profile_dir = profile_dir or (self._data_dir / "browser_profile")
        self._screenshot_dir = screenshot_dir or (self._data_dir / "workspace" / "screenshots")
        self._pdf_dir = pdf_dir or (self._data_dir / "workspace" / "pdfs")
        self._session_dir = session_dir or (self._data_dir / "sessions")
        self._headless = headless
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        self._session_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _coerce_proxy_config(
        proxy_config: ProxyConfig | dict[str, Any] | None,
    ) -> Optional["ProxyConfig"]:
        if proxy_config is None:
            return None
        if isinstance(proxy_config, ProxyConfig):
            return proxy_config
        return ProxyConfig.from_mapping(proxy_config)

    @staticmethod
    def _load_proxy_config() -> Optional["ProxyConfig"]:
        """Load proxy config from env vars. Returns None if not configured."""
        import os
        host = os.environ.get("CONDUIT_PROXY_HOST", "")
        if not host:
            return None
        port_str = os.environ.get("CONDUIT_PROXY_PORT", "8080")
        try:
            port = int(port_str)
        except ValueError:
            port = 8080
        return ProxyConfig(
            host=host,
            port=port,
            username=os.environ.get("CONDUIT_PROXY_USER", ""),
            password=os.environ.get("CONDUIT_PROXY_PASS", ""),
            protocol=os.environ.get("CONDUIT_PROXY_PROTOCOL", "http"),
        )

    @staticmethod
    def _generate_fingerprint_profile() -> "FingerprintProfile":
        """Generate a randomized but realistic browser fingerprint for this session."""
        viewports = [
            (1920, 1080), (1440, 900), (1366, 768),
            (1536, 864), (2560, 1440), (1280, 800),
        ]
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]
        timezones = [
            "America/New_York", "America/Chicago", "America/Los_Angeles",
            "America/Denver", "Europe/London", "Europe/Berlin", "Europe/Paris",
            "America/Toronto", "America/Vancouver",
        ]
        locales = ["en-US", "en-GB", "en-CA", "en-AU"]
        vp = random.choice(viewports)
        return FingerprintProfile(
            viewport_w=vp[0],
            viewport_h=vp[1],
            user_agent=random.choice(user_agents),
            locale=random.choice(locales),
            timezone=random.choice(timezones),
            color_depth=random.choice([24, 30]),
            device_scale_factor=random.choice([1.0, 1.25, 1.5, 2.0]),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute(self, args: dict[str, Any]) -> str:
        """Dispatch from agent_loop tool registry (receives raw args dict)."""
        action = args.pop("action", "") if isinstance(args, dict) else ""
        result = await self._dispatch(action, args)
        return json.dumps(result)

    async def _dispatch(self, action: str, kwargs: dict) -> dict:
        """Ensure browser is running, then dispatch to sub-action."""
        await self._ensure_browser()

        actions = {
            "navigate":               self._navigate,
            "snapshot":               self._snapshot,
            "click":                  self._click,
            "type":                   self._type,
            "fill":                   self._type,           # alias — same page.fill() semantics
            "screenshot":             self._screenshot,
            "pdf":                    self._pdf,
            "search":                 self._search,
            "eval":                   self._eval,
            "extract_main":           lambda **kw: self._extract_main(max_chars=kw.get("max_chars", 5000), fmt=kw.get("fmt", "text")),
            "js_delta":               lambda **kw: self._js_delta(),
            "output_to_file":         self._output_to_file,
            "accessibility_snapshot": self._accessibility_snapshot,
            "network_requests":       self._get_network_requests,
            "scroll":                 self._scroll,
            "wait":                   self._wait,
            "wait_for":               self._wait_for,
            "key_press":              self._key_press,
            "hover":                  self._hover,
            "select_option":          self._select_option,
            "handle_dialog":          self._handle_dialog,
            "navigate_back":          self._navigate_back,
            "console_messages":       self._get_console_messages,
            "detect_captcha":         self._detect_captcha,
            "solve_captcha":          self._auto_solve_captcha,
            "solve_captcha_vision":   self._solve_captcha_vision,
            "rotate_proxy":           self._rotate_proxy,
            "save_cookies":           self._save_cookies,
            "load_cookies":           self._load_cookies,
            "check_session":          self._check_session,
            "login":                  self._login,
        }

        if action not in actions:
            return {"error": f"Unknown browser action: {action!r}. Valid: {list(actions)}"}

        try:
            return await actions[action](**kwargs)
        except Exception as exc:
            logger.error("Browser action %s failed: %s", action, exc)
            return {"error": str(exc), "action": action}

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        """Launch Patchright browser if not already running."""
        if self._browser is not None:
            try:
                # self._browser is a BrowserContext (from launch_persistent_context),
                # not a Browser — BrowserContext has no is_connected() method.
                # Use len(pages) > 0 as the liveness check instead.
                if len(self._browser.pages) > 0:
                    return
            except Exception:
                pass

        from patchright.async_api import async_playwright

        # Generate per-session fingerprint profile BEFORE launch so values
        # can be passed to both the context constructor and the init script.
        self._fingerprint = self._generate_fingerprint_profile()

        # Load proxy configuration
        self._proxy_config = self._explicit_proxy_config or self._load_proxy_config()

        self._playwright = await async_playwright().start()

        # Build proxy dict — only include credentials when present
        if self._proxy_config:
            proxy_dict = {"server": self._proxy_config.server_url}
            if self._proxy_config.username:
                proxy_dict["username"] = self._proxy_config.username
            if self._proxy_config.password:
                proxy_dict["password"] = self._proxy_config.password
        else:
            proxy_dict = None

        launch_kwargs = {
            "user_data_dir": str(self._profile_dir),
            "headless": self._headless,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-infobars",
                f"--window-size={self._fingerprint.viewport_w},{self._fingerprint.viewport_h}",
                "--ignore-certificate-errors",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=NetworkServiceSandbox",
                "--no-zygote",
            ],
            "ignore_default_args": ["--enable-automation"],
            "user_agent": self._fingerprint.user_agent,
        }
        if proxy_dict:
            launch_kwargs["proxy"] = proxy_dict

        self._browser = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)

        if self._proxy_config:
            logger.info(
                "Proxy enabled: %s://%s:%d",
                self._proxy_config.protocol,
                self._proxy_config.host,
                self._proxy_config.port,
            )

        self._page = await self._browser.new_page()
        await self._page.set_viewport_size({
            "width": self._fingerprint.viewport_w,
            "height": self._fingerprint.viewport_h,
        })

        # Build stealth JS. We inject it via page.evaluate() after each navigation
        # (stored as self._stealth_js). We cannot use add_init_script() — on this
        # Windows Server + Patchright combination, ANY call to add_init_script()
        # (context-level or page-level) corrupts Chromium's internal DNS resolver,
        # causing ERR_NAME_NOT_RESOLVED on ALL subsequent navigations. The CDP
        # Page.addScriptToEvaluateOnNewDocument approach was tried but silently
        # fails (script never executes). Post-navigation evaluate() is reliable.
        self._stealth_js = f"""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
            // Normalize plugins (empty in headless, detectable)
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{
                    const arr = [
                        {{name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'}},
                        {{name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'}},
                        {{name: 'Native Client', filename: 'internal-nacl-plugin'}},
                    ];
                    arr.refresh = () => {{}};
                    return arr;
                }}
            }});
            // Normalize languages
            Object.defineProperty(navigator, 'languages', {{get: () => ['en-US', 'en']}});
            // Normalize chrome object (missing in headless)
            if (!window.chrome) {{
                window.chrome = {{runtime: {{}}, loadTimes: () => {{}}, csi: () => {{}}, app: {{}}}};
            }}
            // Normalize permissions
            const origQuery = window.navigator.permissions && window.navigator.permissions.query;
            if (origQuery) {{
                window.navigator.permissions.query = (params) =>
                    (params.name === 'notifications')
                        ? Promise.resolve({{state: Notification.permission}})
                        : origQuery(params);
            }}
            // Screen dimensions matching viewport
            Object.defineProperty(screen, 'width', {{get: () => {self._fingerprint.viewport_w}}});
            Object.defineProperty(screen, 'height', {{get: () => {self._fingerprint.viewport_h}}});
            Object.defineProperty(screen, 'colorDepth', {{get: () => {self._fingerprint.color_depth}}});
            Object.defineProperty(screen, 'pixelDepth', {{get: () => {self._fingerprint.color_depth}}});
            // Canvas fingerprint noise — per-session seed: {self._noise_seed}
            (function() {{
                const seed = {self._noise_seed};
                function mulberry32(a) {{
                    return function() {{
                        a |= 0; a = a + 0x6D2B79F5 | 0;
                        var t = Math.imul(a ^ a >>> 15, 1 | a);
                        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
                        return ((t ^ t >>> 14) >>> 0) / 4294967296;
                    }}
                }}
                const rand = mulberry32(seed);
                const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
                    const ctx = this.getContext('2d');
                    if (ctx) {{
                        const imgData = ctx.getImageData(0, 0, Math.min(this.width, 10), Math.min(this.height, 10));
                        for (let i = 0; i < imgData.data.length; i += 4) {{
                            imgData.data[i] = Math.min(255, imgData.data[i] + Math.floor((rand() - 0.5) * 2));
                        }}
                        ctx.putImageData(imgData, 0, 0);
                    }}
                    return origToDataURL.apply(this, arguments);
                }};
                // WebGL renderer/vendor noise
                const getParamOrig = WebGLRenderingContext.prototype.getParameter;
                const gpuVendors = ['Intel Inc.', 'NVIDIA Corporation', 'AMD', 'Google Inc. (Intel)'];
                const gpuRenderers = ['Intel Iris OpenGL Engine', 'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)', 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11)'];
                const vendor = gpuVendors[seed % gpuVendors.length];
                const renderer = gpuRenderers[seed % gpuRenderers.length];
                WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return vendor;   // UNMASKED_VENDOR_WEBGL
                    if (parameter === 37446) return renderer; // UNMASKED_RENDERER_WEBGL
                    return getParamOrig.apply(this, arguments);
                }};
                // Also patch WebGL2
                if (typeof WebGL2RenderingContext !== 'undefined') {{
                    const getParam2Orig = WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                        if (parameter === 37445) return vendor;
                        if (parameter === 37446) return renderer;
                        return getParam2Orig.apply(this, arguments);
                    }};
                }}
                // AudioBuffer noise
                if (typeof AudioBuffer !== 'undefined') {{
                    const origGetChannelData = AudioBuffer.prototype.getChannelData;
                    AudioBuffer.prototype.getChannelData = function(channel) {{
                        const data = origGetChannelData.call(this, channel);
                        const noiseMag = 0.0001;
                        for (let i = 0; i < Math.min(data.length, 100); i++) {{
                            data[i] += (rand() - 0.5) * noiseMag;
                        }}
                        return data;
                    }};
                }}
            }})();
        """
        # Register a load event handler to re-inject stealth JS after every page
        # navigation (including raw page.goto() calls from test fixtures).
        # We cannot use add_init_script() — on this Windows Server + Patchright
        # combination it corrupts Chromium's DNS resolver. Post-load evaluate is
        # reliable and sufficient for the stealth properties we override.
        async def _inject_stealth_on_load():
            if self._stealth_js:
                try:
                    await self._page.evaluate(self._stealth_js)
                except Exception:
                    pass
        self._page.on("load", lambda: asyncio.ensure_future(_inject_stealth_on_load()))
        # Register network listeners for network_requests action
        self._page.on("request", lambda req: self._network_log.append({
            "type": "request", "url": req.url, "method": req.method
        }))
        self._page.on("response", lambda res: self._network_log.append({
            "type": "response", "url": res.url, "status": res.status
        }))
        # Register console listener via CDP — Patchright's stealth patches break
        # the Playwright-level page.on("console") event, so we subscribe directly
        # to Runtime.consoleAPICalled via a CDP session.
        self._cdp_session = await self._page.context.new_cdp_session(self._page)
        await self._cdp_session.send("Runtime.enable")
        self._cdp_session.on(
            "Runtime.consoleAPICalled",
            lambda params: self._console_messages.append({
                "type": params.get("type", "log"),
                "text": " ".join(
                    a.get("value", a.get("description", ""))
                    for a in params.get("args", [])
                ),
            }),
        )
        logger.debug(
            "Fingerprint profile: viewport=%dx%d ua=%s locale=%s tz=%s",
            self._fingerprint.viewport_w, self._fingerprint.viewport_h,
            self._fingerprint.user_agent[:50], self._fingerprint.locale,
            self._fingerprint.timezone,
        )
        logger.debug("Patchright browser launched with profile %s", self._profile_dir)

    async def close(self) -> None:
        """Gracefully close the browser and Playwright instance."""
        if self._cdp_session:
            try:
                await self._cdp_session.detach()
            except Exception:
                pass
            self._cdp_session = None
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
            self._page = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    async def _navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        """Navigate to URL and return title + visible text (first 3000 chars)."""
        # Validate URL scheme (no file://, no internal IPs)
        import ipaddress
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return {"error": f"Blocked URL scheme: {parsed.scheme}. Only http/https allowed."}
        # Block RFC-1918 and link-local
        try:
            host = parsed.hostname
            addr = ipaddress.ip_address(host) if host else None
            if addr and (addr.is_private or addr.is_link_local or addr.is_loopback):
                return {"error": f"Blocked internal IP: {host}"}
        except ValueError:
            pass  # hostname, not IP — allow

        await self._page.goto(url, wait_until=wait_until, timeout=30000)

        # Auto-detect CAPTCHA after navigation
        try:
            captcha = await self._detect_captcha()
            if captcha["detected"]:
                logger.info("CAPTCHA detected on %s (type: %s) — attempting auto-solve", url, captcha["type"])
                await self._auto_solve_captcha()
        except Exception:
            pass  # Never let captcha detection crash navigation

        title = await self._page.title()
        text = await self._page.evaluate("document.body.innerText")
        return {
            "title": title,
            "url": self._page.url,
            "text": text[:3000],
        }

    async def _snapshot(self) -> dict:
        """Return current page state: title, URL, visible text, interactive elements."""
        title = await self._page.title()
        text = await self._page.evaluate("document.body.innerText")

        elements = await self._page.evaluate("""
            () => {
                const els = [];
                document.querySelectorAll('a, button, input, select, textarea').forEach(el => {
                    els.push({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || el.value || el.placeholder || '').substring(0, 100),
                        href: el.href || null,
                        id: el.id || null,
                        type: el.type || null
                    });
                });
                return els.slice(0, 50);
            }
        """)

        return {
            "title": title,
            "url": self._page.url,
            "text": text[:2000],
            "elements": elements,
        }

    async def _human_move_to(self, x: float, y: float) -> None:
        """Move mouse smoothly to (x, y) via a bezier-curve-approximated path."""
        import random
        # Current position is unknown — start from center of viewport
        vp = self._page.viewport_size or {"width": 1280, "height": 720}
        start_x, start_y = vp["width"] / 2, vp["height"] / 2
        steps = random.randint(5, 8)
        # Control points for quadratic bezier approximation
        cp_x = start_x + (x - start_x) * 0.5 + random.uniform(-80, 80)
        cp_y = start_y + (y - start_y) * 0.5 + random.uniform(-80, 80)
        total_ms = random.uniform(300, 800)
        step_ms = total_ms / steps
        for i in range(1, steps + 1):
            t = i / steps
            bx = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * cp_x + t ** 2 * x
            by = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * cp_y + t ** 2 * y
            await self._page.mouse.move(bx, by)
            await asyncio.sleep(step_ms / 1000.0)

    async def _random_delay(self) -> None:
        """Random human think-time pause 0.5-1.5s."""
        import random
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _click(self, selector: str) -> dict:
        """Click element by CSS selector with human-like mouse movement."""
        try:
            # Get element bounding box for bezier path target
            element = self._page.locator(selector).first
            box = await element.bounding_box()
            if box:
                target_x = box["x"] + box["width"] / 2
                target_y = box["y"] + box["height"] / 2
                await self._human_move_to(target_x, target_y)
            await self._page.click(selector, timeout=10000)
            return {"success": True, "selector": selector, "url": self._page.url}
        except Exception as exc:
            return {"success": False, "selector": selector, "error": str(exc)}

    async def _type(self, selector: str, text: str, fast: bool = False) -> dict:
        """Type text into an input element. fast=False uses human-like per-char delay."""
        import random
        try:
            if fast:
                await self._page.fill(selector, text, timeout=10000)
            else:
                await self._page.click(selector, timeout=10000)  # focus first
                await self._page.fill(selector, "", timeout=5000)  # clear
                delay_ms = random.randint(50, 150)
                await self._page.type(selector, text, delay=delay_ms)
            return {"success": True, "selector": selector, "typed": text}
        except Exception as exc:
            return {"success": False, "selector": selector, "error": str(exc)}

    async def _screenshot(self, filename: str = None) -> dict:
        """Take a full-page screenshot and save to workspace."""
        import time
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        # Strip path components to prevent directory traversal
        filename = Path(filename).name
        if not filename.endswith(".png"):
            filename += ".png"

        out_path = self._screenshot_dir / filename
        # Verify path stays within screenshots dir after resolution
        try:
            out_path.resolve().relative_to(self._screenshot_dir.resolve())
        except ValueError:
            return {"error": f"Invalid filename: {filename!r}"}
        await self._page.screenshot(path=str(out_path), full_page=True)
        return {"success": True, "path": str(out_path), "url": self._page.url}

    async def _pdf(self, filename: str = None) -> dict:
        """Save the current page as a PDF."""
        import time
        if not filename:
            filename = f"page_{int(time.time())}.pdf"
        # Strip path components to prevent directory traversal
        filename = Path(filename).name
        if not filename.endswith(".pdf"):
            filename += ".pdf"

        out_path = self._pdf_dir / filename
        # Verify path stays within pdfs dir after resolution
        try:
            out_path.resolve().relative_to(self._pdf_dir.resolve())
        except ValueError:
            return {"error": f"Invalid filename: {filename!r}"}
        await self._page.pdf(path=str(out_path))
        return {"success": True, "path": str(out_path), "url": self._page.url}

    async def _eval(self, js_code: str) -> dict:
        """Execute arbitrary JavaScript in page context. Returns result + SHA-256 code hash."""
        import hashlib
        code_hash = hashlib.sha256(js_code.encode()).hexdigest()[:16]
        try:
            result = await self._page.evaluate(js_code)
            return {
                "success": True,
                "result": result,
                "code_hash": code_hash,
                "url": self._page.url,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "code_hash": code_hash}

    async def _extract_main(self, max_chars: int = 5000, fmt: str = "text") -> dict:
        """Readability-style main content extraction. Removes nav/header/footer noise.

        Operates on a deep clone of <body> so the live DOM is never mutated.
        fmt: "text" (default) or "md" for markdown-preserving output.
        """
        raw = await self._page.evaluate("""
            () => {
                const clone = document.body.cloneNode(true);
                const noise = ['nav','header','footer','aside','[role="banner"]',
                              '[role="navigation"]','[role="complementary"]',
                              '.nav','.header','.footer','.sidebar','.menu',
                              '#nav','#header','#footer','#sidebar'];
                noise.forEach(sel => {
                    clone.querySelectorAll(sel).forEach(el => el.remove());
                });
                const candidates = clone.querySelectorAll('article,main,[role="main"],p,div');
                let best = null, bestScore = 0;
                candidates.forEach(el => {
                    const text = el.innerText || '';
                    const score = text.length - (el.querySelectorAll('a').length * 20);
                    if (score > bestScore) { bestScore = score; best = el; }
                });
                const el = best || clone;
                return { text: el.innerText.trim(), html: el.innerHTML };
            }
        """)
        if isinstance(raw, dict):
            text = raw.get("text", "")
            if fmt == "md" and raw.get("html"):
                text = _html_to_markdown(raw["html"])
        else:
            text = str(raw) if raw is not None else ""
        truncated = len(text) > max_chars
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        # HTTP status for current page from network log (last response for this URL)
        http_status = None
        for entry in reversed(getattr(self, "_network_log", [])):
            if entry.get("type") == "response" and entry.get("url") == self._page.url:
                http_status = entry.get("status")
                break
        links_found = 0
        try:
            links_found = await self._page.evaluate(
                "() => document.querySelectorAll('a[href]').length"
            )
        except Exception:
            pass
        return {
            "text": text[:max_chars],
            "char_count": len(text),
            "url": self._page.url,
            "title": await self._page.title(),
            "truncated": truncated,
            "content_hash": content_hash,
            "fetched_at": time.time(),
            "http_status": http_status,
            "links_found": links_found,
        }

    async def _js_delta(self) -> dict:
        """
        Capture the JS delta: diff between static HTML (pre-JS) and rendered DOM (post-JS).

        This measures how much content is only accessible after JavaScript execution.
        AI crawlers that don't execute JS will miss content that only exists in the
        rendered DOM. A high js_dependency_ratio means the site is invisible to
        non-browser AI crawlers.

        Returns:
            {
                "static_text": str,          # text from raw HTML (no JS)
                "rendered_text": str,         # text from rendered DOM (post-JS)
                "static_char_count": int,
                "rendered_char_count": int,
                "js_only_char_count": int,    # chars present only after JS
                "js_dependency_ratio": float, # 0.0 = all static, 1.0 = all JS-dependent
                "static_hash": str,           # SHA-256 of static text
                "rendered_hash": str,         # SHA-256 of rendered text
                "url": str,
                "title": str,
            }
        """
        url = self._page.url
        title = await self._page.title()

        # Capture rendered DOM text (post-JS, what the user sees)
        rendered_text = await self._page.evaluate(
            "() => document.body ? document.body.innerText.trim() : ''"
        )

        # Capture static HTML content (pre-JS equivalent: what non-JS crawlers see)
        # We get the raw HTML and extract text without script-generated content
        static_text = await self._page.evaluate("""
            () => {
                // Parse the raw outerHTML to get a fresh DOM without script effects
                const parser = new DOMParser();
                const doc = parser.parseFromString(document.documentElement.outerHTML, 'text/html');
                // Remove all script tags and their generated content markers
                doc.querySelectorAll('script, noscript, style, template').forEach(el => el.remove());
                // Remove elements that are typically JS-rendered (data-react, data-vue, etc.)
                doc.querySelectorAll('[data-reactroot], [data-server-rendered], [id="__next"], [id="__nuxt"], [id="app"]').forEach(el => {
                    // Keep the element but strip it to just its noscript/static content
                    const noscript = el.querySelector('noscript');
                    if (noscript) {
                        el.innerHTML = noscript.innerHTML;
                    }
                });
                return doc.body ? doc.body.innerText.trim() : '';
            }
        """)

        static_count = len(static_text)
        rendered_count = len(rendered_text)
        js_only_count = max(0, rendered_count - static_count)

        # Ratio: 0.0 = fully static, 1.0 = fully JS-dependent
        if rendered_count > 0:
            js_dependency_ratio = round(js_only_count / rendered_count, 4)
        else:
            js_dependency_ratio = 0.0

        static_hash = hashlib.sha256(static_text.encode()).hexdigest()
        rendered_hash = hashlib.sha256(rendered_text.encode()).hexdigest()

        return {
            "static_text": static_text[:5000],
            "rendered_text": rendered_text[:5000],
            "static_char_count": static_count,
            "rendered_char_count": rendered_count,
            "js_only_char_count": js_only_count,
            "js_dependency_ratio": js_dependency_ratio,
            "static_hash": static_hash,
            "rendered_hash": rendered_hash,
            "url": url,
            "title": title,
        }

    async def _output_to_file(self, filename: str, content: str, fmt: str = "md") -> dict:
        """Write content to workspace file. Sanitizes filename to prevent path traversal."""
        from pathlib import Path as _Path
        out_dir = _Path.home() / ".cato" / "workspace" / ".conduit"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _Path(filename).name  # strip any path traversal
        # Guard against empty or dot-only names (e.g. filename='' or filename='.')
        if not safe_name or safe_name in (".", ".."):
            safe_name = "output"
        if not safe_name.endswith(f".{fmt}"):
            safe_name = f"{safe_name}.{fmt}"
        out_path = out_dir / safe_name
        content_bytes = content.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        out_path.write_bytes(content_bytes)
        return {
            "success": True,
            "path": str(out_path),
            "bytes": len(content_bytes),
            "content_hash": content_hash,
        }

    async def _accessibility_snapshot(self) -> dict:
        """Return accessibility tree for the current page.

        Tries multiple Patchright/Playwright APIs in order:
        1. page.aria_snapshot() — Playwright ≥1.45 / Patchright current
        2. page.accessibility.snapshot() — Playwright 1.35-1.44 (deprecated)
        3. Manual DOM extraction — fallback for any version
        """
        snapshot = None
        try:
            snapshot = await self._page.aria_snapshot()
        except (AttributeError, Exception):
            pass
        if snapshot is None:
            try:
                acc = getattr(self._page, "accessibility", None)
                if acc is not None:
                    snapshot = await acc.snapshot()
            except Exception:
                pass
        if snapshot is None:
            # Manual fallback: build a structured accessibility description from the DOM
            try:
                items = await self._page.evaluate("""
                    () => {
                        const items = [];
                        const els = document.querySelectorAll(
                            'h1,h2,h3,h4,h5,h6,button,a,input,select,textarea,[role],[aria-label]'
                        );
                        els.forEach(el => {
                            const role = el.getAttribute('role') || el.tagName.toLowerCase();
                            const label = el.getAttribute('aria-label') || el.innerText || el.value || '';
                            if (label.trim()) items.push({role, label: label.trim().substring(0, 100)});
                        });
                        return items.slice(0, 100);
                    }
                """)
                snapshot = {"method": "dom_fallback", "nodes": items}
            except Exception as exc:
                snapshot = {"method": "unavailable", "error": str(exc)}
        elif isinstance(snapshot, str):
            # Wrap plain string (from aria_snapshot) in a dict for consistent return type
            snapshot = {"method": "aria_snapshot", "text": snapshot}
        return {
            "tree": snapshot,
            "url": self._page.url,
            "title": await self._page.title(),
        }

    async def _get_cookies(self) -> list:
        """Return current context cookies (for session persistence)."""
        await self._ensure_browser()
        if self._browser is None:
            return []
        try:
            return await self._browser.cookies()
        except Exception:
            return []

    async def _get_network_requests(self) -> dict:
        """Return and clear the accumulated network request/response log."""
        reqs = list(self._network_log)
        self._network_log.clear()
        return {"requests": reqs, "count": len(reqs)}

    async def _search(self, query: str) -> dict:
        """DuckDuckGo search — returns top 5 results."""
        search_url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"
        await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

        # Detect bot-block pages (418, Captcha, redirect to static-pages, etc.)
        current_url = self._page.url
        if "418" in current_url or "static-pages" in current_url or "blocked" in current_url.lower():
            return {"query": query, "results": [], "error": f"bot_detected: {current_url}"}
        page_text = await self._page.evaluate("document.body && document.body.innerText || ''")
        if any(phrase in page_text[:500].lower() for phrase in ("please enable javascript", "enable cookies", "access denied")):
            return {"query": query, "results": [], "error": "bot_detected: page requires JS/cookies gate"}

        results = await self._page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('[data-testid="result"]').forEach(r => {
                    const titleEl = r.querySelector('h2 a');
                    const snippetEl = r.querySelector('[data-result="snippet"]');
                    if (titleEl) {
                        results.push({
                            title: titleEl.innerText,
                            url: titleEl.href,
                            snippet: snippetEl ? snippetEl.innerText : ''
                        });
                    }
                });
                return results.slice(0, 5);
            }
        """)

        if not results:
            return {"query": query, "results": [], "error": "no_results: DDG returned 0 results (bot detection or DOM change)"}
        return {"query": query, "results": results}

    # ------------------------------------------------------------------
    # Action implementations (Wave 1 additions: scroll, fill-alias, wait,
    # wait_for, key_press, hover, select_option, handle_dialog,
    # navigate_back, console_messages)
    # ------------------------------------------------------------------

    async def _scroll(self, direction: str = "down", amount: int = 300, selector: str = None) -> dict:
        """Scroll the page or scroll a specific element into view."""
        if selector:
            await self._page.locator(selector).scroll_into_view_if_needed()
            return {"success": True, "action": "scroll_into_view", "selector": selector}
        delta_x = {"left": -amount, "right": amount}.get(direction, 0)
        delta_y = {"up": -amount, "down": amount}.get(direction, 0)
        await self._page.mouse.wheel(delta_x, delta_y)
        return {"success": True, "direction": direction, "amount": amount, "url": self._page.url}

    async def _wait(self, seconds: float = 1.0) -> dict:
        """Wait a fixed number of seconds (capped at 30s)."""
        capped = min(float(seconds), 30.0)
        await asyncio.sleep(capped)
        return {"success": True, "waited_seconds": capped}

    async def _wait_for(
        self,
        condition: str = "selector",
        value: str = "",
        timeout_ms: int = 10000,
    ) -> dict:
        """Wait for a condition: selector | text | network_idle | url."""
        import json as _json
        try:
            if condition == "selector":
                await self._page.wait_for_selector(value, timeout=timeout_ms)
            elif condition == "text":
                await self._page.wait_for_function(
                    f"document.body.innerText.includes({_json.dumps(value)})",
                    timeout=timeout_ms,
                )
            elif condition == "network_idle":
                await self._page.wait_for_load_state("networkidle", timeout=timeout_ms)
            elif condition == "url":
                await self._page.wait_for_url(value, timeout=timeout_ms)
            return {"success": True, "condition": condition, "value": value}
        except Exception as exc:
            return {"success": False, "condition": condition, "value": value, "error": str(exc)}

    async def _key_press(self, key: str = "Enter") -> dict:
        """Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape')."""
        await self._page.keyboard.press(key)
        return {"success": True, "key": key, "url": self._page.url}

    async def _hover(self, selector: str) -> dict:
        """Move the mouse pointer over an element with human-like path."""
        try:
            element = self._page.locator(selector).first
            box = await element.bounding_box()
            if box:
                target_x = box["x"] + box["width"] / 2
                target_y = box["y"] + box["height"] / 2
                await self._human_move_to(target_x, target_y)
            await self._page.hover(selector, timeout=10000)
            return {"success": True, "selector": selector}
        except Exception as exc:
            return {"success": False, "selector": selector, "error": str(exc)}

    async def _select_option(
        self,
        selector: str,
        value: str = "",
        label: str = "",
        index: int = None,
    ) -> dict:
        """Select an option in a <select> element by value, visible label, or 0-based index."""
        try:
            if index is not None:
                await self._page.select_option(selector, index=index)
            elif label:
                await self._page.select_option(selector, label=label)
            else:
                await self._page.select_option(selector, value=value)
            return {"success": True, "selector": selector, "value": value or label}
        except Exception as exc:
            return {"success": False, "selector": selector, "error": str(exc)}

    async def _handle_dialog(self, action: str = "accept", text: str = "") -> dict:
        """Register an accept or dismiss handler for the next browser dialog (alert/confirm/prompt)."""
        result: dict = {"handled": False}

        async def on_dialog(dialog):
            if action == "accept":
                await dialog.accept(text) if text else await dialog.accept()
            else:
                await dialog.dismiss()
            result["handled"] = True
            result["message"] = dialog.message
            result["type"] = dialog.type

        self._page.once("dialog", on_dialog)
        return {"success": True, "registered_action": action}

    async def _navigate_back(self) -> dict:
        """Navigate to the previous page in browser history."""
        await self._page.go_back(timeout=15000)
        return {"success": True, "url": self._page.url, "title": await self._page.title()}

    async def _get_console_messages(self) -> dict:
        """Return all buffered console messages and clear the internal buffer."""
        msgs = list(self._console_messages)
        self._console_messages.clear()
        return {"messages": msgs, "count": len(msgs)}

    async def _rotate_proxy(self) -> dict:
        """Rotate to next proxy in the list (if proxy list is configured)."""
        import os
        import json as _json
        # Load proxy list from env (JSON array of proxy objects)
        proxy_list_json = os.environ.get("CONDUIT_PROXY_LIST", "")
        if proxy_list_json:
            try:
                raw_list = _json.loads(proxy_list_json)
                self._proxy_list = [
                    ProxyConfig(
                        host=p.get("host", ""),
                        port=int(p.get("port", 8080)),
                        username=p.get("username", ""),
                        password=p.get("password", ""),
                        protocol=p.get("protocol", "http"),
                    )
                    for p in raw_list if p.get("host")
                ]
            except Exception as exc:
                return {"success": False, "error": f"Failed to parse CONDUIT_PROXY_LIST: {exc}"}

        if not self._proxy_list:
            return {
                "success": False,
                "error": "No proxy list configured (set CONDUIT_PROXY_LIST env var as JSON array)",
            }

        self._proxy_index = (self._proxy_index + 1) % len(self._proxy_list)
        self._proxy_config = self._proxy_list[self._proxy_index]
        # Note: proxy only takes effect on next browser launch — cannot hot-swap
        return {
            "success": True,
            "proxy_index": self._proxy_index,
            "proxy_host": self._proxy_config.host,
            "proxy_port": self._proxy_config.port,
            "note": "Proxy will apply on next browser restart",
        }

    # ------------------------------------------------------------------
    # CAPTCHA detection and auto-solve
    # ------------------------------------------------------------------

    async def _detect_captcha(self) -> dict:
        """Scan current page for CAPTCHA signals. Returns {detected, type}."""
        url = self._page.url.lower()
        url_signals = any(kw in url for kw in ("captcha", "challenge", "verify", "robot", "human-check"))

        dom_result = await self._page.evaluate("""
            () => {
                const signals = {
                    recaptcha: !!(
                        document.querySelector('.g-recaptcha') ||
                        document.querySelector('iframe[src*="recaptcha"]') ||
                        document.querySelector('[data-sitekey]')
                    ),
                    hcaptcha: !!(
                        document.querySelector('.h-captcha') ||
                        document.querySelector('iframe[src*="hcaptcha"]')
                    ),
                    cloudflare: !!(
                        document.querySelector('#cf-challenge-running') ||
                        document.querySelector('.cf-browser-verification') ||
                        document.querySelector('iframe[src*="challenges.cloudflare.com"]')
                    ),
                    sitekey: (() => {
                        const el = document.querySelector('[data-sitekey]');
                        return el ? el.getAttribute('data-sitekey') : null;
                    })(),
                };
                return signals;
            }
        """)

        detected = url_signals or any([
            dom_result.get("recaptcha"),
            dom_result.get("hcaptcha"),
            dom_result.get("cloudflare"),
        ])

        captcha_type = None
        if dom_result.get("cloudflare"):
            captcha_type = "cloudflare"
        elif dom_result.get("hcaptcha"):
            captcha_type = "hcaptcha"
        elif dom_result.get("recaptcha"):
            captcha_type = "recaptcha"
        elif url_signals:
            captcha_type = "unknown"

        return {
            "detected": detected,
            "type": captcha_type,
            "sitekey": dom_result.get("sitekey"),
            "url": self._page.url,
        }

    async def _auto_solve_captcha(self) -> dict:
        """Detect and attempt to solve any CAPTCHA on the current page."""
        detection = await self._detect_captcha()
        if not detection["detected"]:
            return {"solved": False, "captcha_type": None, "error": "No CAPTCHA detected"}

        captcha_type = detection["type"]
        site_key = detection.get("sitekey", "")
        page_url = self._page.url

        # Try to get API key from env
        import os
        api_key = os.environ.get("CAPSOLVER_API_KEY", "")
        if not api_key:
            logger.info("No CAPSOLVER_API_KEY — attempting vision fallback")
            vision_result = await self._solve_captcha_vision()
            if vision_result.get("solved"):
                return {"solved": True, "captcha_type": captcha_type, "method": "vision"}
            return {
                "solved": False,
                "captcha_type": captcha_type,
                "error": f"No CapSolver key. Vision fallback: {vision_result.get('error', 'failed')}",
            }

        # Import here to avoid circular issues — captcha_solver is in same package
        import sys as _sys
        captcha_mod = _sys.modules.get("cato.tools.captcha_solver")
        if captcha_mod is None:
            from pathlib import Path as _Path
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "cato.tools.captcha_solver",
                str(_Path(__file__).parent / "captcha_solver.py"),
            )
            captcha_mod = _ilu.module_from_spec(_spec)
            _sys.modules["cato.tools.captcha_solver"] = captcha_mod
            _spec.loader.exec_module(captcha_mod)

        solver = captcha_mod.CapSolverClient(api_key=api_key)
        token = ""
        try:
            if captcha_type == "recaptcha":
                token = await solver.solve_recaptcha_v2(site_key, page_url)
            elif captcha_type == "hcaptcha":
                token = await solver.solve_hcaptcha(site_key, page_url)
            elif captcha_type == "cloudflare":
                token = await solver.solve_cloudflare_turnstile(site_key, page_url)
        except Exception as exc:
            return {"solved": False, "captcha_type": captcha_type, "error": str(exc)}

        if not token:
            # CapSolver failed — try vision fallback for image challenges
            logger.info("CapSolver returned no token — attempting vision fallback")
            vision_result = await self._solve_captcha_vision()
            if vision_result.get("solved"):
                return {"solved": True, "captcha_type": captcha_type, "method": "vision"}
            return {
                "solved": False,
                "captcha_type": captcha_type,
                "error": f"CapSolver: empty token. Vision: {vision_result.get('error', 'failed')}",
            }

        # Inject token into page
        try:
            await self._page.evaluate(f"""
                (() => {{
                    const el = document.getElementById('g-recaptcha-response') ||
                               document.querySelector('textarea[name="g-recaptcha-response"]');
                    if (el) el.value = '{token}';
                    if (window.___grecaptcha_cfg) {{
                        const id = Object.keys(window.___grecaptcha_cfg.clients || {{}})[0];
                        if (id !== undefined) window.grecaptcha && window.grecaptcha.execute(id);
                    }}
                }})()
            """)
        except Exception as exc:
            logger.warning("Token injection failed: %s", exc)

        return {"solved": True, "captcha_type": captcha_type, "token_injected": True}

    async def _solve_captcha_vision(self) -> dict:
        """
        Attempt to solve an image/text CAPTCHA using Claude vision API.
        Only works for image challenge CAPTCHAs (not token-based reCAPTCHA/hCaptcha).
        Requires ANTHROPIC_API_KEY environment variable.
        """
        import os, base64
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {
                "solved": False,
                "method": "vision",
                "error": "No ANTHROPIC_API_KEY configured for vision solve",
            }

        # Screenshot the full page to find the CAPTCHA
        import time as _time
        screenshot_path = self._screenshot_dir / f"captcha_vision_{int(_time.time())}.png"
        try:
            await self._page.screenshot(path=str(screenshot_path), full_page=False)
        except Exception as exc:
            return {"solved": False, "method": "vision", "error": f"Screenshot failed: {exc}"}

        # Base64 encode screenshot
        try:
            img_bytes = screenshot_path.read_bytes()
            img_b64 = base64.b64encode(img_bytes).decode()
        except Exception as exc:
            return {"solved": False, "method": "vision", "error": f"Image read failed: {exc}"}

        # Ask Claude to solve the CAPTCHA
        try:
            import urllib.request as _req
            import json as _json
            payload = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 64,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is a CAPTCHA image. What text, characters, or objects does it show? "
                                "Reply with ONLY the answer to the CAPTCHA — no explanation, no punctuation, "
                                "just the answer text. If you see a checkbox or unsolvable CAPTCHA, reply: UNSOLVABLE"
                            ),
                        },
                    ],
                }],
            }
            req_data = _json.dumps(payload).encode()
            request = _req.Request(
                "https://api.anthropic.com/v1/messages",
                data=req_data,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                method="POST",
            )
            with _req.urlopen(request, timeout=30) as resp:
                response_data = _json.loads(resp.read().decode())
            captcha_answer = response_data.get("content", [{}])[0].get("text", "").strip()
        except Exception as exc:
            return {"solved": False, "method": "vision", "error": f"Claude API call failed: {exc}"}

        if not captcha_answer or captcha_answer.upper() == "UNSOLVABLE":
            return {"solved": False, "method": "vision", "error": "CAPTCHA marked unsolvable by vision model"}

        # Try to type the answer into a CAPTCHA input
        typed = False
        for selector in ["input[name*='captcha']", "input[id*='captcha']", "#captcha", ".captcha-input", "input[type='text']"]:
            try:
                await self._page.fill(selector, captcha_answer, timeout=2000)
                typed = True
                break
            except Exception:
                continue

        return {
            "solved": typed,
            "method": "vision",
            "captcha_answer": captcha_answer if typed else None,
            "error": None if typed else "Could not find CAPTCHA input field to type answer",
        }

    # ------------------------------------------------------------------
    # Wave 8: Cookie & Auth session management
    # ------------------------------------------------------------------

    async def _save_cookies(self, label: str = "default") -> dict:
        """Serialize current browser context cookies to a JSON file in the session vault."""
        import json as _json
        safe_label = Path(label).name or "default"
        try:
            cookies = await self._browser.cookies()
            session_file = self._session_dir / f"{safe_label}.json"
            session_file.write_text(_json.dumps(cookies, indent=2), encoding="utf-8")
            return {
                "success": True,
                "label": safe_label,
                "count": len(cookies),
                "path": str(session_file),
            }
        except Exception as exc:
            return {"success": False, "label": label, "error": str(exc)}

    async def _load_cookies(self, label: str = "default") -> dict:
        """Load cookies from the session vault and install into current browser context."""
        import json as _json
        safe_label = Path(label).name or "default"
        session_file = self._session_dir / f"{safe_label}.json"
        if not session_file.exists():
            return {
                "success": False,
                "label": safe_label,
                "error": f"No saved session found for label: {safe_label!r}",
            }
        try:
            cookies = _json.loads(session_file.read_text(encoding="utf-8"))
            await self._browser.add_cookies(cookies)
            return {"success": True, "label": safe_label, "count": len(cookies)}
        except Exception as exc:
            return {"success": False, "label": safe_label, "error": str(exc)}

    async def _check_session(self, url: str = "") -> dict:
        """
        Check if the current page (or given URL after navigation) is an auth wall.
        Returns {authenticated: bool, redirect_url: str|None}.
        """
        current_url = self._page.url.lower()
        auth_signals = ("login", "signin", "sign-in", "auth", "account/login",
                        "session/new", "users/sign_in", "authenticate", "sso")
        is_auth_wall = any(signal in current_url for signal in auth_signals)
        return {
            "authenticated": not is_auth_wall,
            "redirect_url": self._page.url if is_auth_wall else None,
            "current_url": self._page.url,
        }

    async def _login(
        self,
        url: str,
        username_selector: str = "input[type='email'],input[type='text'],input[name='username'],input[name='email']",
        password_selector: str = "input[type='password']",
        credential_key: str = "",
    ) -> dict:
        """
        Automated login using credentials from environment variables.
        credential_key maps to env vars: {KEY}_USERNAME and {KEY}_PASSWORD.
        The credential_key reference (NOT values) is logged to audit chain.
        """
        import os
        if not credential_key:
            return {"success": False, "error": "credential_key is required"}

        env_key = credential_key.upper().replace("-", "_").replace(".", "_")
        username = os.environ.get(f"{env_key}_USERNAME", "")
        password = os.environ.get(f"{env_key}_PASSWORD", "")

        if not username or not password:
            return {
                "success": False,
                "error": (
                    f"Credentials not found. Set {env_key}_USERNAME and "
                    f"{env_key}_PASSWORD environment variables."
                ),
                "credential_key": credential_key,
            }

        try:
            # Navigate to login URL
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Fill username — try each selector in the comma-separated list
            username_filled = False
            for sel in username_selector.split(","):
                sel = sel.strip()
                try:
                    await self._page.fill(sel, username, timeout=3000)
                    username_filled = True
                    break
                except Exception:
                    continue

            if not username_filled:
                return {
                    "success": False,
                    "error": f"Could not find username field: {username_selector}",
                    "credential_key": credential_key,
                }

            # Fill password
            await self._page.fill(password_selector, password, timeout=10000)

            # Submit — press Enter or click submit button
            submitted = False
            for submit_sel in [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Sign in')",
                "button:has-text('Log in')",
                "button:has-text('Login')",
            ]:
                try:
                    await self._page.click(submit_sel, timeout=3000)
                    submitted = True
                    break
                except Exception:
                    continue

            if not submitted:
                await self._page.keyboard.press("Enter")

            # Wait for navigation
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

            final_url = self._page.url
            # Check if still on login page (login failed)
            session_check = await self._check_session()
            success = session_check["authenticated"]

            return {
                "success": success,
                "final_url": final_url,
                "credential_key": credential_key,  # reference only, not values
                "error": None if success else "Login may have failed — still on auth page",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "credential_key": credential_key}
