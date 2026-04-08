from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class RedditAdapter(MarketplaceAdapter):
    slug = "reddit"
    display_name = "Reddit"
    schema_version = "reddit.v1"
    target_definitions = (
        TargetDefinition(
            key="subreddit-feed",
            label="Subreddit feed",
            description="Reddit subreddit listing pages with posts sorted by hot, new, top, etc.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["subreddit", "posts"],
                "properties": {
                    "subreddit": {"type": "string"},
                    "posts": {"type": "array"},
                    "sort": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="post-detail",
            label="Post detail",
            description="Reddit post page with full body, metadata, and top comments.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["title", "post_url"],
                "properties": {
                    "title": {"type": "string"},
                    "post_url": {"type": "string"},
                    "subreddit": {"type": "string"},
                    "author": {"type": "string"},
                    "score": {"type": "integer"},
                    "upvote_ratio": {"type": "string"},
                    "num_comments": {"type": "integer"},
                    "created_at": {"type": "string"},
                    "body": {"type": "string"},
                    "top_comments": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="user-profile",
            label="User profile",
            description="Reddit user profile page with karma and bio.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["username", "profile_url"],
                "properties": {
                    "username": {"type": "string"},
                    "profile_url": {"type": "string"},
                    "karma_post": {"type": "string"},
                    "karma_comment": {"type": "string"},
                    "created_at": {"type": "string"},
                    "bio": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="search-results",
            label="Search results",
            description="Reddit search result pages listing matching posts.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["query", "posts"],
                "properties": {
                    "query": {"type": "string"},
                    "posts": {"type": "array"},
                    "result_count_text": {"type": "string"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Reddit adapter only accepts http/https URLs")
        if "reddit.com" not in parsed.netloc:
            raise ValueError("Reddit adapter requires a reddit.com URL")
        # Use Reddit's public JSON API — reliable, no JS rendering required, no bot blocking.
        # Append .json to subreddit, search, and post paths if not already present.
        if parsed.netloc in ("www.reddit.com", "reddit.com", "old.reddit.com"):
            path = parsed.path.rstrip("/")
            if not path.endswith(".json"):
                cleaned = f"https://www.reddit.com{path}.json"
                if parsed.query:
                    cleaned += "?" + parsed.query
        return cleaned

    def login_url(self) -> str:
        return "https://www.reddit.com/login"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input[name='username'],input[id='loginUsername'],input[type='text']",
            "password": "input[name='password'],input[id='loginPassword'],input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        if target_type == "subreddit-feed":
            return 5
        if target_type == "search-results":
            return 3
        return super().scroll_iterations(target_type)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "subreddit-feed": {
                "primary": [
                    "[data-testid='post-container']",
                    "article",
                    "div[data-fullname]",
                ],
                "fallback": [
                    "shreddit-post",
                    ".Post",
                    "[data-click-id='body']",
                ],
            },
            "post-detail": {
                "primary": [
                    "[data-test-id='post-content']",
                    "div[data-adclicklocation='title']",
                    "._3sf33-9rVAO_v4y0pIW_CH",
                ],
                "fallback": [
                    "shreddit-post",
                    "[slot='title']",
                    ".Post",
                ],
            },
            "user-profile": {
                "primary": [
                    "[id='profile--id-card--highlight-container']",
                    "h1",
                    "[data-testid='profile_user_card']",
                ],
                "fallback": [
                    ".ProfileCard",
                    "[data-testid='profile-card']",
                    "main h1",
                ],
            },
            "search-results": {
                "primary": [
                    "[data-testid='search-results'] [data-testid='post-container']",
                    ".search-result-link",
                ],
                "fallback": [
                    "[data-testid='post-container']",
                    "article",
                    "shreddit-post",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        # All scripts parse Reddit's public JSON API response rendered in <pre> by the browser.
        # normalize_url() appends .json to the URL so the browser loads JSON, not the SPA.
        scripts = {
            "subreddit-feed": """
() => {
  // Reddit JSON API: browser renders the JSON in a <pre> tag
  const preEl = document.querySelector("pre");
  const rawText = preEl ? preEl.textContent : document.body.textContent;
  let data;
  try { data = JSON.parse(rawText); } catch(e) { return { subreddit: "", posts: [], sort: "hot", _error: String(e) }; }
  const listing = Array.isArray(data) ? data[0] : data;
  const children = (listing && listing.data && listing.data.children) ? listing.data.children : [];
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  const subreddit = (pathParts[1] || "").replace(/\\.json$/, "");
  const urlParams = new URL(window.location.href).searchParams;
  const sort = urlParams.get('sort') || "hot";
  const posts = children.slice(0, 25).map((child) => {
    const p = child.data || {};
    return {
      id: p.id || "",
      title: p.title || "",
      post_url: p.url || ("https://www.reddit.com" + (p.permalink || "")),
      subreddit: "r/" + (p.subreddit || subreddit),
      author: p.author || "",
      score: String(p.score || 0),
      num_comments: String(p.num_comments || 0),
      created_at: p.created_utc ? new Date(p.created_utc * 1000).toISOString() : "",
      flair: p.link_flair_text || ""
    };
  }).filter((p) => p.title || p.post_url);
  return { subreddit, posts, sort };

  // old.reddit.com: posts are div.thing with class "link"
  const oldRedditPosts = Array.from(document.querySelectorAll('div.thing.link')).slice(0, 25);
  if (oldRedditPosts.length > 0) {
    const posts = oldRedditPosts.map((thing) => {
      const titleEl = thing.querySelector('a.title');
      const title = titleEl ? titleEl.innerText.trim() : "";
      const postUrl = thing.getAttribute('data-url') || (titleEl ? titleEl.href : "");
      const score = thing.getAttribute('data-score') || textOf(thing, ['.score.unvoted', '.score.likes', '.score']);
      const author = thing.getAttribute('data-author') || textOf(thing, ['.author']);
      const subReddit = thing.getAttribute('data-subreddit-prefixed') || ("r/" + subreddit);
      const commentsEl = thing.querySelector('a.comments');
      const numComments = commentsEl ? commentsEl.innerText.trim() : "";
      const timeEl = thing.querySelector('time[datetime]');
      const createdAt = timeEl ? timeEl.getAttribute('datetime') : thing.getAttribute('data-timestamp') || "";
      const flair = textOf(thing, ['.linkflairlabel', '.flair']);
      return { title, post_url: postUrl, subreddit: subReddit, author, score, num_comments: numComments, created_at: createdAt, flair };
    }).filter((p) => p.title || p.post_url);
    return { subreddit, posts, sort };
  }

  // new Reddit SPA / shreddit fallback
  const hrefOf = (root, selectors) => {
    for (const selector of selectors) {
      const el = root.querySelector(selector);
      if (el && el.href) return el.href;
      if (el && el.getAttribute && el.getAttribute('permalink')) return 'https://www.reddit.com' + el.getAttribute('permalink');
    }
    return "";
  };
  const containers = Array.from(document.querySelectorAll(
    "[data-testid='post-container'], article, shreddit-post, div[data-fullname]"
  )).slice(0, 25);
  const posts = containers.map((card) => {
    const isShreddit = card.tagName && card.tagName.toLowerCase() === 'shreddit-post';
    const title = isShreddit
      ? (card.getAttribute('post-title') || textOf(card, ["h3", "h2", "[slot='title'] a"]))
      : textOf(card, ["h3", "h2", "a[data-click-id='body']", "[data-testid='post-title']"]);
    const postUrl = isShreddit
      ? (card.getAttribute('permalink') ? 'https://www.reddit.com' + card.getAttribute('permalink') : hrefOf(card, ["a[data-click-id='body']"]))
      : hrefOf(card, ["a[data-click-id='body']", "a[href*='/comments/']"]);
    const sub = isShreddit ? (card.getAttribute('subreddit-prefixed-name') || subreddit) : subreddit;
    const author = isShreddit ? (card.getAttribute('author') || "") : textOf(card, ["a[href*='/user/']"]);
    const score = isShreddit ? (card.getAttribute('score') || "") : textOf(card, ["[data-testid='vote-score']"]);
    const numComments = textOf(card, ["a[data-click-id='comments']", "[data-testid='comment-count']"]);
    const timeEl = card.querySelector("time[datetime]");
    const createdAt = timeEl ? timeEl.getAttribute("datetime") : "";
    return { title, post_url: postUrl, subreddit: sub, author, score, num_comments: numComments, created_at: createdAt || "", flair: "" };
  }).filter((p) => p.title || p.post_url);
  return { subreddit, posts, sort };
}
""",
            "post-detail": """
() => {
  const preEl = document.querySelector("pre");
  const rawText = preEl ? preEl.textContent : document.body.textContent;
  let data;
  try { data = JSON.parse(rawText); } catch(e) { return { title: "", post_url: window.location.href, subreddit: "", _error: String(e) }; }
  // Post detail returns [listing, comments]
  const postListing = Array.isArray(data) ? data[0] : data;
  const commentListing = Array.isArray(data) ? data[1] : null;
  const postChild = postListing && postListing.data && postListing.data.children && postListing.data.children[0];
  const p = postChild ? (postChild.data || {}) : {};
  const title = p.title || "";
  const subreddit = "r/" + (p.subreddit || "");
  const author = p.author || "";
  const score = String(p.score || 0);
  const upvote_ratio = p.upvote_ratio ? String(Math.round(p.upvote_ratio * 100)) + "%" : "";
  const num_comments = String(p.num_comments || 0);
  const created_at = p.created_utc ? new Date(p.created_utc * 1000).toISOString() : "";
  const body = (p.selftext || "").slice(0, 2000);
  const post_url = p.url || window.location.href.replace(".json", "");
  const top_comments = [];
  if (commentListing && commentListing.data && commentListing.data.children) {
    for (const child of commentListing.data.children.slice(0, 10)) {
      if (!child.data || child.kind === "more") continue;
      const c = child.data;
      top_comments.push({ author: c.author || "", body: (c.body || "").slice(0, 300), score: String(c.score || 0) });
    }
  }
  return { title, post_url, subreddit, author, score, upvote_ratio, num_comments, created_at, body, top_comments };
}
""",
            "user-profile": """
() => {
  const preEl = document.querySelector("pre");
  const rawText = preEl ? preEl.textContent : document.body.textContent;
  let data;
  try { data = JSON.parse(rawText); } catch(e) { return { username: "", profile_url: window.location.href, _error: String(e) }; }
  const u = (data && data.data) ? data.data : {};
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  const uIdx = Math.max(pathParts.indexOf('user'), pathParts.indexOf('u'));
  const username = u.name || (uIdx >= 0 ? pathParts[uIdx + 1] || "" : "");
  const karma_post = String(u.link_karma || 0);
  const karma_comment = String(u.comment_karma || 0);
  const created_at = u.created_utc ? new Date(u.created_utc * 1000).toISOString() : "";
  const bio = u.subreddit ? (u.subreddit.public_description || "") : "";
  return { username, profile_url: window.location.href.replace(".json", ""), karma_post, karma_comment, created_at, bio };
}
""",
            "search-results": """
() => {
  const preEl = document.querySelector("pre");
  const rawText = preEl ? preEl.textContent : document.body.textContent;
  const urlParams = new URL(window.location.href).searchParams;
  const query = urlParams.get('q') || urlParams.get('query') || "";
  let data;
  try { data = JSON.parse(rawText); } catch(e) { return { query, posts: [], result_count_text: "", _error: String(e) }; }
  const listing = Array.isArray(data) ? data[0] : data;
  const children = (listing && listing.data && listing.data.children) ? listing.data.children : [];
  const posts = children.slice(0, 25).map((child) => {
    const p = child.data || {};
    return {
      id: p.id || "",
      title: p.title || "",
      post_url: p.url || ("https://www.reddit.com" + (p.permalink || "")),
      subreddit: "r/" + (p.subreddit || ""),
      author: p.author || "",
      score: String(p.score || 0),
      num_comments: String(p.num_comments || 0)
    };
  }).filter((p) => p.title || p.post_url);
  return { query, posts, result_count_text: String(children.length) + " results" };
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
                if raw.lower().endswith("k"):
                    return int(float(raw[:-1]) * 1000)
                return int(float(raw)) if raw else 0
            except (ValueError, TypeError):
                return 0

        if target_type == "subreddit-feed":
            parsed_url = urlparse(target_url)
            path_parts = [p for p in parsed_url.path.split("/") if p]
            r_idx = path_parts.index("r") if "r" in path_parts else -1
            subreddit = path_parts[r_idx + 1] if r_idx >= 0 and r_idx + 1 < len(path_parts) else ""
            subreddit = subreddit.removesuffix(".json")
            subreddit = self._as_string(structured.get("subreddit")) or subreddit
            sort = self._as_string(structured.get("sort")) or parse_qs(parsed_url.query).get("sort", ["hot"])[0]
            posts: list[dict[str, object]] = []
            for raw in structured.get("posts", []):
                if not isinstance(raw, dict):
                    continue
                title = self._as_string(raw.get("title"))
                post_url = self._as_string(raw.get("post_url"))
                if not title and not post_url:
                    continue
                posts.append(
                    {
                        "title": title,
                        "post_url": post_url,
                        "subreddit": self._as_string(raw.get("subreddit")) or subreddit,
                        "author": self._as_string(raw.get("author")),
                        "score": _int(raw.get("score")),
                        "num_comments": _int(raw.get("num_comments")),
                        "created_at": self._as_string(raw.get("created_at")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "subreddit": subreddit,
                    "posts": posts,
                    "sort": sort,
                },
            )

        if target_type == "post-detail":
            parsed_url = urlparse(target_url)
            path_parts = [p for p in parsed_url.path.split("/") if p]
            r_idx = path_parts.index("r") if "r" in path_parts else -1
            subreddit = path_parts[r_idx + 1] if r_idx >= 0 and r_idx + 1 < len(path_parts) else ""
            comments_raw = structured.get("top_comments", [])
            top_comments: list[dict[str, object]] = []
            for c in comments_raw if isinstance(comments_raw, list) else []:
                if not isinstance(c, dict):
                    continue
                top_comments.append(
                    {
                        "author": self._as_string(c.get("author")),
                        "body": self._as_string(c.get("body")),
                        "score": _int(c.get("score")),
                    }
                )
            payload = {
                "title": self._as_string(structured.get("title"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "post_url": self._as_string(structured.get("post_url")) or target_url,
                "subreddit": self._as_string(structured.get("subreddit")) or subreddit,
                "author": self._as_string(structured.get("author")),
                "score": _int(structured.get("score")),
                "upvote_ratio": self._as_string(structured.get("upvote_ratio")),
                "num_comments": _int(structured.get("num_comments")),
                "created_at": self._as_string(structured.get("created_at")),
                "body": self._as_string(structured.get("body")),
                "top_comments": top_comments,
            }
            return self.validate_payload(target_type, payload)

        if target_type == "user-profile":
            parsed_url = urlparse(target_url)
            path_parts = [p for p in parsed_url.path.split("/") if p]
            u_idx = -1
            for marker in ("user", "u"):
                if marker in path_parts:
                    u_idx = path_parts.index(marker)
                    break
            url_username = path_parts[u_idx + 1] if u_idx >= 0 and u_idx + 1 < len(path_parts) else ""
            payload = {
                "username": self._as_string(structured.get("username")) or url_username,
                "profile_url": self._as_string(structured.get("profile_url")) or target_url,
                "karma_post": self._as_string(structured.get("karma_post")),
                "karma_comment": self._as_string(structured.get("karma_comment")),
                "created_at": self._as_string(structured.get("created_at")),
                "bio": self._as_string(structured.get("bio")),
            }
            return self.validate_payload(target_type, payload)

        # search-results
        parsed_url = urlparse(target_url)
        query = self._as_string(structured.get("query")) or parse_qs(parsed_url.query).get("q", [""])[0]
        posts_raw: list[dict[str, object]] = []
        for raw in structured.get("posts", []):
            if not isinstance(raw, dict):
                continue
            title = self._as_string(raw.get("title"))
            post_url = self._as_string(raw.get("post_url"))
            if not title and not post_url:
                continue
            posts_raw.append(
                {
                    "title": title,
                    "post_url": post_url,
                    "subreddit": self._as_string(raw.get("subreddit")),
                    "author": self._as_string(raw.get("author")),
                    "score": _int(raw.get("score")),
                    "num_comments": _int(raw.get("num_comments")),
                }
            )
        return self.validate_payload(
            target_type,
            {
                "query": query,
                "posts": posts_raw,
                "result_count_text": self._as_string(structured.get("result_count_text")),
            },
        )
