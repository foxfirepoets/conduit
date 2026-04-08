from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class GoogleSearchAdapter(MarketplaceAdapter):
    slug = "google_search"
    display_name = "Google Search"
    schema_version = "google_search.v1"
    target_definitions = (
        TargetDefinition(
            key="web-search",
            label="Web search results",
            description="Google web search result pages listing organic results.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["query", "results"],
                "properties": {
                    "query": {"type": "string"},
                    "results": {"type": "array"},
                    "total_results_text": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="news-search",
            label="News search results",
            description="Google News search result pages listing news articles.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["query", "articles"],
                "properties": {
                    "query": {"type": "string"},
                    "articles": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="image-search",
            label="Image search metadata",
            description="Google Image search result pages — metadata only (title, source URL, image URL, alt text). No image downloading.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["query", "images"],
                "properties": {
                    "query": {"type": "string"},
                    "images": {"type": "array"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        import re as _re
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Google Search adapter only accepts http/https URLs")
        if not _re.search(r"(?:^|\.)google\.[a-z]{2,}$", parsed.netloc):
            raise ValueError("Google Search adapter requires a google.* URL")
        return cleaned

    def login_url(self) -> str:
        return "https://accounts.google.com/signin"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input[type='email'],input[name='identifier'],input[id='identifierId']",
            "password": "input[type='password'],input[name='password'],input[name='Passwd']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        return 3

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "web-search": {
                "primary": [
                    "#search .g",
                    "div[data-sokoban-container]",
                    ".tF2Cxc",
                ],
                "fallback": [
                    "#rso .g",
                    "div[jscontroller][data-hveid]",
                    ".LC20lb",
                ],
            },
            "news-search": {
                "primary": [
                    "[data-n-tid]",
                    ".SoaBEf",
                    "g-card",
                ],
                "fallback": [
                    ".WlydOe",
                    "[data-news-doc-id]",
                    "article",
                ],
            },
            "image-search": {
                "primary": [
                    "#islrg .isv-r",
                    "[data-id]",
                    ".rg_i",
                ],
                "fallback": [
                    "#islrg [role='listitem']",
                    ".isv-r",
                    "img[data-src]",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "web-search": """
() => {
  const queryParam = new URL(window.location.href).searchParams.get("q") || "";
  const totalEl = document.querySelector("#result-stats, #resultStats");
  const totalText = totalEl ? totalEl.innerText.trim() : "";
  const cards = Array.from(document.querySelectorAll(
    "#search .g, div[data-sokoban-container], .tF2Cxc, #rso .g"
  )).filter((el) => !el.querySelector("[data-text-ad]") && !el.closest("[data-text-ad]"))
    .slice(0, 20);
  const textOf = (root, selectors) => {
    for (const selector of selectors) {
      const el = root.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const results = cards.map((card) => {
    const titleEl = card.querySelector("h3");
    const title = titleEl ? titleEl.innerText.trim() : "";
    const citeEl = card.querySelector("cite");
    const displayedUrl = citeEl ? citeEl.innerText.trim() : "";
    const linkEl = card.querySelector("a[href]");
    let url = linkEl ? linkEl.href : "";
    try {
      const parsed = new URL(url);
      if (parsed.pathname === "/url") {
        url = parsed.searchParams.get("q") || url;
      }
    } catch (e) {}
    const snippet = textOf(card, ["div[data-sncf]", ".VwiC3b", ".lEBKkf", ".s3v9rd"]);
    return { title, url, snippet, displayed_url: displayedUrl };
  }).filter((r) => r.title || r.url);
  return { query: queryParam, results, total_results_text: totalText };
}
""",
            "news-search": """
() => {
  const queryParam = new URL(window.location.href).searchParams.get("q") || "";
  const cards = Array.from(document.querySelectorAll(
    "[data-n-tid], .SoaBEf, g-card, .WlydOe, [data-news-doc-id], article"
  )).slice(0, 20);
  const textOf = (root, selectors) => {
    for (const selector of selectors) {
      const el = root.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const hrefOf = (root, selectors) => {
    for (const selector of selectors) {
      const el = root.querySelector(selector);
      if (el && el.href) return el.href;
    }
    return "";
  };
  const articles = cards.map((card) => {
    const title = textOf(card, ["h3", "h4", "a[class*='title']", "a"]);
    let url = hrefOf(card, ["a[href]"]);
    try {
      const parsed = new URL(url);
      if (parsed.pathname === "/url") {
        url = parsed.searchParams.get("q") || url;
      }
      if (url.startsWith("/")) {
        url = window.location.origin + url;
      }
    } catch (e) {}
    const source = textOf(card, [".NUnG9d span", ".CEMjEf", "[data-source]", "cite"]);
    const timeEl = card.querySelector("time[datetime]");
    const publishedAt = timeEl ? timeEl.getAttribute("datetime") || timeEl.innerText.trim() : "";
    const snippet = textOf(card, [".GI74Re", ".Rai5ob", "p", "[data-content]"]);
    return { title, url, source, published_at: publishedAt, snippet };
  }).filter((a) => a.title || a.url);
  return { query: queryParam, articles };
}
""",
            "image-search": """
() => {
  const queryParam = new URL(window.location.href).searchParams.get("q") || "";
  const items = Array.from(document.querySelectorAll(
    "#islrg .isv-r, [data-id], .rg_i, #islrg [role='listitem']"
  )).slice(0, 30);
  const images = items.map((item) => {
    const imgEl = item.querySelector("img");
    const linkEl = item.querySelector("a[href]");
    const title = (item.getAttribute("aria-label") || (imgEl ? imgEl.getAttribute("alt") || "" : "")).trim();
    const altText = imgEl ? (imgEl.getAttribute("alt") || "").trim() : "";
    let sourceUrl = linkEl ? linkEl.href : "";
    try {
      const parsed = new URL(sourceUrl);
      if (parsed.pathname === "/imgres" || parsed.pathname === "/url") {
        sourceUrl = parsed.searchParams.get("imgurl") || parsed.searchParams.get("q") || sourceUrl;
      }
    } catch (e) {}
    const imageUrl = imgEl ? (imgEl.getAttribute("data-src") || imgEl.src || "") : "";
    return { title, source_url: sourceUrl, image_url: imageUrl, alt_text: altText };
  }).filter((img) => img.source_url || img.image_url);
  return { query: queryParam, images };
}
""",
        }
        if target_type not in scripts:
            raise ValueError(f"{self.slug}: no extraction script for target type: {target_type!r}")
        return scripts[target_type]

    def transform_extraction(
        self,
        target_type: str,
        target_url: str,
        structured_payload: dict[str, object] | None,
        main_content: dict[str, object],
        navigation: dict[str, object],
    ) -> dict[str, object]:
        structured = structured_payload if isinstance(structured_payload, dict) else {}
        parsed_url = urlparse(target_url)

        if target_type == "web-search":
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("q", [""])[0]
            )
            results: list[dict[str, str]] = []
            for raw in structured.get("results", []):
                if not isinstance(raw, dict):
                    continue
                title = self._as_string(raw.get("title"))
                url = self._as_string(raw.get("url"))
                if not title and not url:
                    continue
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": self._as_string(raw.get("snippet")),
                        "displayed_url": self._as_string(raw.get("displayed_url")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "results": results,
                    "total_results_text": self._as_string(structured.get("total_results_text")),
                },
            )

        if target_type == "news-search":
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("q", [""])[0]
            )
            articles: list[dict[str, str]] = []
            for raw in structured.get("articles", []):
                if not isinstance(raw, dict):
                    continue
                articles.append(
                    {
                        "title": self._as_string(raw.get("title")),
                        "url": self._as_string(raw.get("url")),
                        "source": self._as_string(raw.get("source")),
                        "published_at": self._as_string(raw.get("published_at")),
                        "snippet": self._as_string(raw.get("snippet")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "articles": articles,
                },
            )

        # image-search
        query = (
            self._as_string(structured.get("query"))
            or parse_qs(parsed_url.query).get("q", [""])[0]
        )
        images: list[dict[str, str]] = []
        for raw in structured.get("images", []):
            if not isinstance(raw, dict):
                continue
            source_url = self._as_string(raw.get("source_url"))
            image_url = self._as_string(raw.get("image_url"))
            if not source_url and not image_url:
                continue
            images.append(
                {
                    "title": self._as_string(raw.get("title")),
                    "source_url": source_url,
                    "image_url": image_url,
                    "alt_text": self._as_string(raw.get("alt_text")),
                }
            )
        return self.validate_payload(
            target_type,
            {
                "query": query,
                "images": images,
            },
        )
