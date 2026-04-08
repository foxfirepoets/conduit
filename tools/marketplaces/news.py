from __future__ import annotations

from urllib.parse import urlparse

from .base import MarketplaceAdapter, TargetDefinition


class NewsAdapter(MarketplaceAdapter):
    slug = "news"
    display_name = "News (Generic)"
    schema_version = "news.v1"
    target_definitions = (
        TargetDefinition(
            key="article",
            label="News article",
            description="Generic news article page with body text, author, and metadata.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["title", "article_url"],
                "properties": {
                    "title": {"type": "string"},
                    "article_url": {"type": "string"},
                    "author": {"type": "string"},
                    "published_at": {"type": "string"},
                    "body": {"type": "string"},
                    "tags": {"type": "array"},
                    "source_domain": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="homepage",
            label="News homepage / section listing",
            description="News site homepage or section page listing article links.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["articles"],
                "properties": {
                    "articles": {"type": "array"},
                    "source_domain": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="rss-feed",
            label="RSS / Atom feed",
            description="RSS 2.0 or Atom feed page with item listings.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["feed_url", "items"],
                "properties": {
                    "feed_url": {"type": "string"},
                    "items": {"type": "array"},
                    "feed_title": {"type": "string"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("News adapter only accepts http/https URLs")
        return cleaned

    def login_url(self) -> str:
        return ""

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input[type='email'],input[type='text'],input[name='username'],input[name='email']",
            "password": "input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        if target_type == "homepage":
            return 3
        return super().scroll_iterations(target_type)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "article": {
                "primary": [
                    "article",
                    "main article",
                    "[itemprop='articleBody']",
                    ".article-body",
                    ".post-content",
                    ".entry-content",
                    ".story-body",
                ],
                "fallback": [
                    "main",
                    ".content",
                    "#content",
                    ".post",
                ],
            },
            "homepage": {
                "primary": [
                    "article",
                    ".article-list article",
                    ".story-list li",
                    "main .card",
                    "[data-testid='article-card']",
                ],
                "fallback": [
                    ".card",
                    ".teaser",
                    ".headline",
                    "h2 a",
                    "h3 a",
                ],
            },
            "rss-feed": {
                "primary": [
                    "item",
                    "entry",
                    "channel item",
                ],
                "fallback": [
                    "rss channel",
                    "feed",
                    "channel",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "article": """
() => {
  const pickText = (...selectors) => {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && (el.innerText || el.textContent || el.content || el.getAttribute('content'))) {
        return (el.innerText || el.textContent || el.content || el.getAttribute('content') || "").trim();
      }
    }
    return "";
  };
  const pickAttr = (attr, ...selectors) => {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.getAttribute(attr)) return el.getAttribute(attr).trim();
    }
    return "";
  };
  const title = pickText("h1", "h1.headline", "h1.article-title")
    || document.title
    || pickAttr("content", "meta[property='og:title']", "meta[name='title']");
  const author = pickText(
    "[rel='author']", "a[rel='author']", ".byline a", ".byline", ".author",
    "[data-testid='byline']", "[class*='author']", "[itemprop='author']"
  ) || pickAttr("content", "meta[name='author']", "meta[property='article:author']");
  const published_at = pickAttr("datetime", "time[datetime]", "time[pubdate]")
    || pickAttr("content", "meta[property='article:published_time']", "meta[name='pubdate']", "meta[name='date']")
    || pickText("time", ".date", ".published", "[class*='publish']");
  const bodyEl = document.querySelector("article")
    || document.querySelector("[itemprop='articleBody']")
    || document.querySelector("main");
  const body = bodyEl ? (bodyEl.innerText || bodyEl.textContent || "").trim().replace(/\\s{3,}/g, "\\n\\n").slice(0, 5000) : "";
  const keywordsMeta = document.querySelector("meta[name='keywords']");
  const tagsFromMeta = keywordsMeta
    ? (keywordsMeta.getAttribute("content") || "").split(",").map((t) => t.trim()).filter(Boolean)
    : [];
  const tagsFromLinks = tagsFromMeta.length === 0
    ? Array.from(document.querySelectorAll(".tags a, [rel='tag'], [class*='tag'] a, [class*='topic'] a"))
        .map((el) => (el.innerText || el.textContent || "").trim())
        .filter(Boolean)
        .slice(0, 20)
    : [];
  const tags = tagsFromMeta.length > 0 ? tagsFromMeta : tagsFromLinks;
  const source_domain = window.location.hostname;
  const canonicalEl = document.querySelector("link[rel='canonical']");
  const article_url = (canonicalEl && canonicalEl.href) ? canonicalEl.href : window.location.href;
  return { title, article_url, author, published_at, body, tags, source_domain };
}
""",
            "homepage": """
() => {
  const source_domain = window.location.hostname;
  const cardSelectors = [
    "article",
    ".article-list article",
    ".story-list li",
    "main .card",
    "[data-testid='article-card']",
    ".card",
    ".teaser",
  ];
  let cards = [];
  for (const sel of cardSelectors) {
    const found = Array.from(document.querySelectorAll(sel));
    if (found.length > 0) { cards = found; break; }
  }
  cards = cards.slice(0, 30);
  const articles = cards.map((card) => {
    const headingEl = card.querySelector("h2, h3, h4, h1");
    const title = headingEl ? (headingEl.innerText || headingEl.textContent || "").trim() : "";
    const linkEl = card.querySelector("a[href]");
    let article_url = linkEl ? (linkEl.href || "") : "";
    const timeEl = card.querySelector("time[datetime]");
    const published_at = timeEl
      ? (timeEl.getAttribute("datetime") || timeEl.innerText.trim())
      : ((card.querySelector(".date, .published, [class*='date'], [class*='time']") || {}).innerText || "").trim();
    const authorEl = card.querySelector("[rel='author'], .byline, .author, [class*='author']");
    const author = authorEl ? (authorEl.innerText || authorEl.textContent || "").trim() : "";
    const excerptEl = card.querySelector("p");
    const excerpt = excerptEl ? (excerptEl.innerText || excerptEl.textContent || "").trim().slice(0, 200) : "";
    return { title, article_url, published_at, author, excerpt };
  }).filter((a) => a.title || a.article_url);
  return { articles, source_domain };
}
""",
            "rss-feed": """
() => {
  const feed_url = window.location.href;
  // Check if we have actual XML DOM (Firefox-style) or browser-rendered pre/prettified view
  const hasXmlDom = !!document.querySelector("rss, feed, channel, item, entry");

  if (hasXmlDom) {
    const channelEl = document.querySelector("channel");
    const feedEl = document.querySelector("feed");
    const feedTitleEl = channelEl
      ? channelEl.querySelector(":scope > title")
      : (feedEl ? feedEl.querySelector(":scope > title") : null);
    const feed_title = feedTitleEl ? (feedTitleEl.textContent || "").trim() : "";
    const isAtom = !!feedEl && !channelEl;
    const itemEls = isAtom
      ? Array.from(document.querySelectorAll("entry")).slice(0, 30)
      : Array.from(document.querySelectorAll("item")).slice(0, 30);
    const items = itemEls.map((item) => {
      const titleEl = item.querySelector("title");
      const title = titleEl ? (titleEl.textContent || "").trim() : "";
      let url = "";
      if (isAtom) {
        const linkEl = item.querySelector("link[href]") || item.querySelector("link");
        url = linkEl ? (linkEl.getAttribute("href") || linkEl.textContent || "").trim() : "";
      } else {
        const linkEl = item.querySelector("link");
        url = linkEl ? (linkEl.textContent || linkEl.getAttribute("href") || "").trim() : "";
      }
      const pubDateEl = isAtom ? item.querySelector("updated, published") : item.querySelector("pubDate");
      const published_at = pubDateEl ? (pubDateEl.textContent || "").trim() : "";
      const descEl = isAtom ? item.querySelector("summary, content") : item.querySelector("description");
      const description = descEl
        ? (descEl.textContent || "").replace(/<[^>]*>/g, "").trim().slice(0, 300)
        : "";
      return { title, url, published_at, description };
    }).filter((i) => i.title || i.url);
    return { feed_url, feed_title, items };
  }

  // Chromium renders XML as styled HTML — parse the raw text from <pre> or body
  const rawText = (document.querySelector("pre") || document.body || {}).textContent || "";
  const feed_title = (rawText.match(/<title[^>]*>([^<]*)<\\/title>/) || [])[1] || document.title || "";
  // Extract items via regex from raw XML text
  const itemMatches = [...rawText.matchAll(/<item[^>]*>([\\s\\S]*?)<\\/item>/gi)];
  const entryMatches = itemMatches.length === 0
    ? [...rawText.matchAll(/<entry[^>]*>([\\s\\S]*?)<\\/entry>/gi)]
    : [];
  const allMatches = itemMatches.length > 0 ? itemMatches : entryMatches;
  const items = allMatches.slice(0, 30).map((m) => {
    const chunk = m[1];
    const title = ((chunk.match(/<title[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/title>/i) || [])[1] || "").trim();
    const urlMatch = chunk.match(/<link[^>]*>([^<]*)<\\/link>/)
      || chunk.match(/<link[^>]+href=["']([^"']+)["']/i);
    const url = (urlMatch ? urlMatch[1] : "").trim();
    const pubDate = ((chunk.match(/<pubDate[^>]*>(.*?)<\\/pubDate>/i)
      || chunk.match(/<updated[^>]*>(.*?)<\\/updated>/i) || [])[1] || "").trim();
    const desc = ((chunk.match(/<description[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/description>/is)
      || chunk.match(/<summary[^>]*>(.*?)<\\/summary>/is) || [])[1] || "")
      .replace(/<[^>]*>/g, "").trim().slice(0, 300);
    return { title, url, published_at: pubDate, description: desc };
  }).filter((i) => i.title || i.url);
  return { feed_url, feed_title, items };
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

        if target_type == "article":
            body = self._as_string(structured.get("body"))
            if len(body) > 5000:
                body = body[:5000]
            parsed_url = urlparse(target_url)
            source_domain = (
                self._as_string(structured.get("source_domain")) or parsed_url.netloc
            )
            payload = {
                "title": self._as_string(structured.get("title"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "article_url": self._as_string(structured.get("article_url")) or target_url,
                "author": self._as_string(structured.get("author")),
                "published_at": self._as_string(structured.get("published_at")),
                "body": body,
                "tags": self._as_string_list(structured.get("tags")),
                "source_domain": source_domain,
            }
            return self.validate_payload(target_type, payload)

        if target_type == "homepage":
            parsed_url = urlparse(target_url)
            source_domain = (
                self._as_string(structured.get("source_domain")) or parsed_url.netloc
            )
            articles: list[dict[str, object]] = []
            for raw in structured.get("articles", []) if isinstance(structured.get("articles"), list) else []:
                if not isinstance(raw, dict):
                    continue
                title = self._as_string(raw.get("title"))
                article_url = self._as_string(raw.get("article_url"))
                if not title and not article_url:
                    continue
                articles.append(
                    {
                        "title": title,
                        "article_url": article_url,
                        "published_at": self._as_string(raw.get("published_at")),
                        "author": self._as_string(raw.get("author")),
                        "excerpt": self._as_string(raw.get("excerpt")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "articles": articles,
                    "source_domain": source_domain,
                },
            )

        # rss-feed
        raw_items = structured.get("items", [])
        items: list[dict[str, object]] = []
        for raw in raw_items if isinstance(raw_items, list) else []:
            if not isinstance(raw, dict):
                continue
            title = self._as_string(raw.get("title"))
            url = self._as_string(raw.get("url"))
            if not title and not url:
                continue
            description = self._as_string(raw.get("description"))
            if len(description) > 300:
                description = description[:300]
            items.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": self._as_string(raw.get("published_at")),
                    "description": description,
                }
            )
        return self.validate_payload(
            target_type,
            {
                "feed_url": self._as_string(structured.get("feed_url")) or target_url,
                "items": items,
                "feed_title": self._as_string(structured.get("feed_title")),
            },
        )
