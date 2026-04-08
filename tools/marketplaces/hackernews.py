from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class HackerNewsAdapter(MarketplaceAdapter):
    slug = "hackernews"
    display_name = "Hacker News"
    schema_version = "hackernews.v1"
    target_definitions = (
        TargetDefinition(
            key="frontpage",
            label="Front page",
            description="Hacker News front page or /newest, /ask, /show listing pages.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["stories"],
                "properties": {
                    "stories": {"type": "array"},
                    "page_type": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="story-detail",
            label="Story detail",
            description="Hacker News story page with full comment thread.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["title", "story_url"],
                "properties": {
                    "title": {"type": "string"},
                    "story_url": {"type": "string"},
                    "hn_url": {"type": "string"},
                    "author": {"type": "string"},
                    "score": {"type": "integer"},
                    "num_comments": {"type": "integer"},
                    "posted_at": {"type": "string"},
                    "top_comments": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="ask-hn",
            label="Ask HN listing",
            description="Ask HN listing page with question posts.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["posts"],
                "properties": {
                    "posts": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="user-profile",
            label="User profile",
            description="Hacker News user profile page with karma and about section.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["username", "profile_url"],
                "properties": {
                    "username": {"type": "string"},
                    "profile_url": {"type": "string"},
                    "karma": {"type": "integer"},
                    "created_at": {"type": "string"},
                    "about": {"type": "string"},
                    "submitted_count": {"type": "string"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Hacker News adapter only accepts http/https URLs")
        if not (parsed.netloc == "news.ycombinator.com" or parsed.netloc.endswith(".ycombinator.com")):
            raise ValueError("Hacker News adapter requires a news.ycombinator.com URL")
        return cleaned

    def login_url(self) -> str:
        return "https://news.ycombinator.com/login"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input[name='acct'],input[type='text'],input[name='username']",
            "password": "input[name='pw'],input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        return 0

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "frontpage": {
                "primary": [
                    "tr.athing",
                    ".itemlist tr.athing",
                ],
                "fallback": [
                    "table.itemlist tr",
                    ".storylink",
                ],
            },
            "story-detail": {
                "primary": [
                    ".fatitem",
                    ".comment-tree .comtr",
                ],
                "fallback": [
                    "table.fatitem",
                    "tr.comtr",
                ],
            },
            "ask-hn": {
                "primary": [
                    "tr.athing",
                    ".itemlist tr.athing",
                ],
                "fallback": [
                    "table.itemlist tr",
                    ".storylink",
                ],
            },
            "user-profile": {
                "primary": [
                    "table.fatitem",
                    "form",
                ],
                "fallback": [
                    "table",
                    "td[valign='top']",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "frontpage": """
() => {
  const rows = Array.from(document.querySelectorAll("tr.athing")).slice(0, 30);
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  let page_type = "frontpage";
  if (window.location.pathname.includes('/newest')) page_type = "newest";
  else if (window.location.pathname.includes('/ask')) page_type = "ask";
  else if (window.location.pathname.includes('/show')) page_type = "show";
  const stories = rows.map((row) => {
    const id = row.id || "";
    const titleEl = row.querySelector("a.titlelink, .titleline > a, a[href*='item?id=']");
    const title = titleEl ? titleEl.innerText.trim() : "";
    const story_url = titleEl ? (titleEl.href || "") : "";
    const subRow = row.nextElementSibling;
    let score = "", author = "", num_comments = "", posted_at = "";
    if (subRow) {
      const scoreEl = subRow.querySelector("#score_" + id + ", span.score");
      score = scoreEl ? scoreEl.innerText.trim() : "";
      const authorEl = subRow.querySelector("a.hnuser");
      author = authorEl ? authorEl.innerText.trim() : "";
      const ageEl = subRow.querySelector("span.age");
      posted_at = ageEl ? (ageEl.getAttribute("title") || ageEl.innerText.trim()) : "";
      const commentLinks = Array.from(subRow.querySelectorAll("a[href*='item?id=']"));
      for (const link of commentLinks) {
        const txt = (link.innerText || "").trim();
        if (txt.includes("comment") || /^\\d+$/.test(txt)) {
          num_comments = txt;
          break;
        }
      }
    }
    return { id, title, story_url, score, author, num_comments, posted_at };
  }).filter((s) => s.title || s.story_url);
  return { stories, page_type };
}
""",
            "story-detail": """
() => {
  const fatitem = document.querySelector("table.fatitem, .fatitem");
  const pickText = (...selectors) => {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && (el.innerText || el.textContent)) return (el.innerText || el.textContent).trim();
    }
    return "";
  };
  const titleEl = fatitem ? fatitem.querySelector("a.titlelink, .titleline > a, a[href*='item?id=']") : document.querySelector("a.titlelink, .titleline > a");
  const title = titleEl ? titleEl.innerText.trim() : pickText("title");
  const story_url = titleEl ? (titleEl.href || window.location.href) : window.location.href;
  const hn_url = window.location.href;
  const scoreEl = document.querySelector("span.score, #score");
  const scoreRaw = scoreEl ? scoreEl.innerText.trim() : "";
  const authorEl = document.querySelector("a.hnuser");
  const author = authorEl ? authorEl.innerText.trim() : "";
  const ageEl = document.querySelector("span.age");
  const posted_at = ageEl ? (ageEl.getAttribute("title") || ageEl.innerText.trim()) : "";
  const commentLinks = Array.from(document.querySelectorAll("a[href*='item?id=']"));
  let num_comments_raw = "";
  for (const link of commentLinks) {
    const txt = (link.innerText || "").trim();
    if (txt.includes("comment")) { num_comments_raw = txt; break; }
  }
  const commentRows = Array.from(document.querySelectorAll("tr.comtr")).slice(0, 15);
  const top_comments = commentRows.map((row) => {
    const commentAuthorEl = row.querySelector("a.hnuser");
    const commentAuthor = commentAuthorEl ? commentAuthorEl.innerText.trim() : "";
    const commentBodyEl = row.querySelector(".commtext, .comment");
    const commentBody = commentBodyEl ? (commentBodyEl.innerText || commentBodyEl.textContent || "").trim().slice(0, 400) : "";
    const indEl = row.querySelector("td.ind img, td.ind");
    let indent_level = 0;
    if (indEl) {
      const imgEl = indEl.tagName === 'TD' ? indEl.querySelector("img") : indEl;
      if (imgEl) {
        const w = parseInt(imgEl.getAttribute("width") || imgEl.style.width || "0", 10);
        indent_level = Math.round(w / 40);
      }
    }
    const commentAgeEl = row.querySelector("span.age");
    const commentPostedAt = commentAgeEl ? (commentAgeEl.getAttribute("title") || commentAgeEl.innerText.trim()) : "";
    return { author: commentAuthor, body: commentBody, indent_level, posted_at: commentPostedAt };
  }).filter((c) => c.author || c.body);
  return { title, story_url, hn_url, author, score: scoreRaw, num_comments: num_comments_raw, posted_at, top_comments };
}
""",
            "ask-hn": """
() => {
  const rows = Array.from(document.querySelectorAll("tr.athing")).slice(0, 30);
  const posts = rows.map((row) => {
    const id = row.id || "";
    const titleEl = row.querySelector("a.titlelink, .titleline > a, a[href*='item?id=']");
    const title = titleEl ? titleEl.innerText.trim() : "";
    const story_url = titleEl ? (titleEl.href || "") : "";
    const subRow = row.nextElementSibling;
    let score = "", author = "", num_comments = "", posted_at = "";
    if (subRow) {
      const scoreEl = subRow.querySelector("#score_" + id + ", span.score");
      score = scoreEl ? scoreEl.innerText.trim() : "";
      const authorEl = subRow.querySelector("a.hnuser");
      author = authorEl ? authorEl.innerText.trim() : "";
      const ageEl = subRow.querySelector("span.age");
      posted_at = ageEl ? (ageEl.getAttribute("title") || ageEl.innerText.trim()) : "";
      const commentLinks = Array.from(subRow.querySelectorAll("a[href*='item?id=']"));
      for (const link of commentLinks) {
        const txt = (link.innerText || "").trim();
        if (txt.includes("comment") || /^\\d+$/.test(txt)) { num_comments = txt; break; }
      }
    }
    return { id, title, story_url, score, author, num_comments, posted_at };
  }).filter((p) => p.title || p.story_url);
  return { posts };
}
""",
            "user-profile": """
() => {
  const rows = Array.from(document.querySelectorAll("tr"));
  const labelOf = (label) => {
    for (const row of rows) {
      const cells = row.querySelectorAll("td");
      if (cells.length >= 2) {
        const labelText = (cells[0].innerText || cells[0].textContent || "").trim().toLowerCase().replace(":", "");
        if (labelText === label.toLowerCase()) {
          return (cells[1].innerText || cells[1].textContent || "").trim();
        }
      }
    }
    return "";
  };
  const username = labelOf("user") || new URL(window.location.href).searchParams.get("id") || "";
  const karmaRaw = labelOf("karma");
  const created_at = labelOf("created");
  const about = labelOf("about");
  const submittedLinkEl = document.querySelector("a[href*='submitted?id=']");
  const submitted_count = submittedLinkEl ? submittedLinkEl.innerText.trim() : "";
  return { username, profile_url: window.location.href, karma: karmaRaw, created_at, about, submitted_count };
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

        def _int(value: object) -> int:
            try:
                raw = str(value or "").replace(",", "").strip()
                # extract first run of digits
                digits = ""
                for ch in raw:
                    if ch.isdigit():
                        digits += ch
                    elif digits:
                        break
                return int(digits) if digits else 0
            except (ValueError, TypeError):
                return 0

        if target_type in ("frontpage", "ask-hn"):
            stories_key = "stories" if target_type == "frontpage" else "posts"
            raw_list = structured.get(stories_key, [])
            items: list[dict[str, object]] = []
            for raw in raw_list if isinstance(raw_list, list) else []:
                if not isinstance(raw, dict):
                    continue
                title = self._as_string(raw.get("title"))
                story_url = self._as_string(raw.get("story_url"))
                if not title and not story_url:
                    continue
                items.append(
                    {
                        "id": self._as_string(raw.get("id")),
                        "title": title,
                        "story_url": story_url,
                        "score": _int(raw.get("score")),
                        "author": self._as_string(raw.get("author")),
                        "num_comments": _int(raw.get("num_comments")),
                        "posted_at": self._as_string(raw.get("posted_at")),
                    }
                )
            if target_type == "frontpage":
                parsed_url = urlparse(target_url)
                path = parsed_url.path.rstrip("/")
                if path.endswith("/newest"):
                    page_type = "newest"
                elif path.endswith("/ask"):
                    page_type = "ask"
                elif path.endswith("/show"):
                    page_type = "show"
                else:
                    page_type = "frontpage"
                page_type = self._as_string(structured.get("page_type")) or page_type
                return self.validate_payload(
                    target_type,
                    {"stories": items, "page_type": page_type},
                )
            return self.validate_payload(target_type, {"posts": items})

        if target_type == "story-detail":
            comments_raw = structured.get("top_comments", [])
            top_comments: list[dict[str, object]] = []
            for c in comments_raw if isinstance(comments_raw, list) else []:
                if not isinstance(c, dict):
                    continue
                top_comments.append(
                    {
                        "author": self._as_string(c.get("author")),
                        "body": self._as_string(c.get("body")),
                        "indent_level": _int(c.get("indent_level")),
                        "posted_at": self._as_string(c.get("posted_at")),
                    }
                )
            payload = {
                "title": self._as_string(structured.get("title"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "story_url": self._as_string(structured.get("story_url")),
                "hn_url": self._as_string(structured.get("hn_url")) or target_url,
                "author": self._as_string(structured.get("author")),
                "score": _int(structured.get("score")),
                "num_comments": _int(structured.get("num_comments")),
                "posted_at": self._as_string(structured.get("posted_at")),
                "top_comments": top_comments,
            }
            return self.validate_payload(target_type, payload)

        # user-profile
        parsed_url = urlparse(target_url)
        url_username = parse_qs(parsed_url.query).get("id", [""])[0]
        payload = {
            "username": self._as_string(structured.get("username")) or url_username,
            "profile_url": self._as_string(structured.get("profile_url")) or target_url,
            "karma": _int(structured.get("karma")),
            "created_at": self._as_string(structured.get("created_at")),
            "about": self._as_string(structured.get("about")),
            "submitted_count": self._as_string(structured.get("submitted_count")),
        }
        return self.validate_payload(target_type, payload)
