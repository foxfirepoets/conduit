from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class GitHubAdapter(MarketplaceAdapter):
    slug = "github"
    display_name = "GitHub"
    schema_version = "github.v1"
    target_definitions = (
        TargetDefinition(
            key="repo-search",
            label="Repository search results",
            description="GitHub repository search result pages.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["query", "repos"],
                "properties": {
                    "query": {"type": "string"},
                    "repos": {"type": "array"},
                    "result_count_text": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="repo-detail",
            label="Repository detail",
            description="GitHub repository main page with stars, forks, topics, and README preview.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["owner", "repo_name", "repo_url"],
                "properties": {
                    "owner": {"type": "string"},
                    "repo_name": {"type": "string"},
                    "repo_url": {"type": "string"},
                    "description": {"type": "string"},
                    "stars": {"type": "integer"},
                    "forks": {"type": "integer"},
                    "language": {"type": "string"},
                    "topics": {"type": "array"},
                    "readme_preview": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="issues-list",
            label="Issues list",
            description="GitHub repository issues list page.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["repo_url", "issues"],
                "properties": {
                    "repo_url": {"type": "string"},
                    "issues": {"type": "array"},
                    "open_count": {"type": "string"},
                    "closed_count": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="issue-detail",
            label="Issue detail",
            description="Single GitHub issue page with body, labels, and comments.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["title", "issue_url"],
                "properties": {
                    "title": {"type": "string"},
                    "issue_url": {"type": "string"},
                    "number": {"type": "integer"},
                    "state": {"type": "string"},
                    "author": {"type": "string"},
                    "created_at": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array"},
                    "comment_count": {"type": "integer"},
                },
            },
        ),
        TargetDefinition(
            key="release-notes",
            label="Release notes",
            description="GitHub repository releases page listing release tags, names, and bodies.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["repo_url", "releases"],
                "properties": {
                    "repo_url": {"type": "string"},
                    "releases": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="user-profile",
            label="User/org profile",
            description="GitHub user or organization profile page.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["username", "profile_url"],
                "properties": {
                    "username": {"type": "string"},
                    "profile_url": {"type": "string"},
                    "name": {"type": "string"},
                    "bio": {"type": "string"},
                    "location": {"type": "string"},
                    "company": {"type": "string"},
                    "followers": {"type": "string"},
                    "following": {"type": "string"},
                    "public_repos": {"type": "string"},
                    "pinned_repos": {"type": "array"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("GitHub adapter only accepts http/https URLs")
        if "github.com" not in parsed.netloc:
            raise ValueError("GitHub adapter requires a github.com URL")
        return cleaned

    def login_url(self) -> str:
        return "https://github.com/login"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input#login_field,input[name='login'],input[type='text'],input[type='email']",
            "password": "input#password,input[name='password'],input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        scroll_map = {
            "repo-search": 3,
            "issues-list": 3,
            "release-notes": 2,
        }
        return scroll_map.get(target_type, 0)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "repo-search": {
                "primary": [
                    ".search-title",
                    "li.repo-list-item",
                    "[data-testid='results-list'] li",
                ],
                "fallback": [
                    "ul.repo-list li",
                    "[data-type='Repository']",
                    ".f4.text-normal",
                ],
            },
            "repo-detail": {
                "primary": [
                    "h1.d-flex",
                    "#readme",
                    ".BorderGrid-cell",
                ],
                "fallback": [
                    "[itemprop='name']",
                    "article.markdown-body",
                    ".repository-content",
                ],
            },
            "issues-list": {
                "primary": [
                    ".js-issue-row",
                    "[id^='issue_']",
                    "li[data-labels]",
                ],
                "fallback": [
                    "div[id^='issue_']",
                    ".issue-list-item",
                    "[data-hovercard-type='issue']",
                ],
            },
            "issue-detail": {
                "primary": [
                    ".js-issue-title",
                    ".comment-body",
                    ".labels",
                ],
                "fallback": [
                    "h1.gh-header-title",
                    ".js-comment-body",
                    ".sidebar-labels",
                ],
            },
            "release-notes": {
                "primary": [
                    ".release",
                    "[data-testid='release']",
                    "section.release",
                ],
                "fallback": [
                    "[class*='release-entry']",
                    "article[class*='release']",
                    ".release-header",
                ],
            },
            "user-profile": {
                "primary": [
                    "h1.vcard-names",
                    ".p-name",
                    ".js-pinned-items-reorder-list",
                ],
                "fallback": [
                    ".vcard-fullname",
                    "[itemprop='name']",
                    ".pinned-item-list-item",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "repo-search": """
() => {
  const queryParam = new URL(window.location.href).searchParams.get("q") || "";
  const countEl = document.querySelector("h3.f5, [data-testid='results-count'], .codesearch-results h3");
  const resultCountText = countEl ? countEl.innerText.trim() : "";
  // GitHub search results: try new UI (results-list li) then legacy (repo-list-item)
  let items = Array.from(document.querySelectorAll("[data-testid='results-list'] li")).slice(0, 20);
  if (items.length === 0) {
    items = Array.from(document.querySelectorAll(".search-title, li.repo-list-item, [data-type='Repository']")).slice(0, 20);
  }
  const textOf = (root, selectors) => {
    for (const selector of selectors) {
      const el = root.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const repos = items.map((item) => {
    // GitHub search UI: repo links appear as /owner/repo/stargazers, /owner/repo/forks, etc.
    // Extract owner/repo from any anchor whose path has >= 2 parts (take first non-feature href)
    let repoUrl = "";
    let repoName = "";
    const allLinks = Array.from(item.querySelectorAll("a[href]"));
    for (const a of allLinks) {
      try {
        const path = new URL(a.href).pathname.replace(/^\\//, "");
        const parts = path.split("/").filter(Boolean);
        if (parts.length >= 2 && !["features", "enterprise", "pricing", "about", "explore"].includes(parts[0])) {
          const owner = parts[0], repo = parts[1];
          repoName = owner + "/" + repo;
          repoUrl = "https://github.com/" + owner + "/" + repo;
          break;
        }
      } catch (e) {}
    }
    const description = textOf(item, ["p.mb-1", ".mb-1", "p[class*='description']", "p"]);
    const starsEl = item.querySelector("a[href*='/stargazers']");
    const starsText = starsEl ? (starsEl.innerText || "").trim() : "";
    let stars = 0;
    try { stars = parseInt(starsText.replace(/,/g, "").replace(/[^0-9k]/gi, ""), 10) || 0; } catch (e) {}
    // Handle "61.2k" style star counts
    if (starsText.toLowerCase().endsWith("k")) {
      try { stars = Math.round(parseFloat(starsText) * 1000); } catch (e) {}
    }
    const language = textOf(item, ["[itemprop='programmingLanguage'] span", "span[class*='language']", "[data-hovercard-type='language']"]);
    const topics = Array.from(item.querySelectorAll("a.topic-tag, a[data-octo-dimensions*='topic']"))
      .map((el) => el.innerText.trim()).filter(Boolean);
    return { repo_name: repoName, repo_url: repoUrl, description, stars, language, topics };
  }).filter((r) => r.repo_name || r.repo_url);
  return { query: queryParam, repos, result_count_text: resultCountText };
}
""",
            "repo-detail": """
() => {
  const path = window.location.pathname.replace(/^\\//, "");
  const pathParts = path.split("/");
  const owner = pathParts[0] || "";
  const repoName = pathParts[1] || "";
  const descEl = document.querySelector("meta[name='description']");
  const description = descEl ? descEl.getAttribute("content") || "" : "";
  const starsEl = document.querySelector("#repo-stars-counter, [id$='-stargazers-count'], a[href$='/stargazers'] strong");
  const starsText = starsEl ? (starsEl.getAttribute("aria-label") || starsEl.innerText || "").trim() : "";
  let stars = 0;
  try { stars = parseInt(starsText.replace(/,/g, "").replace(/[^0-9]/g, ""), 10) || 0; } catch (e) {}
  const forksEl = document.querySelector("#repo-network-counter, [id$='-forks-count'], a[href$='/forks'] strong, a[href$='/network/members'] strong");
  const forksText = forksEl ? (forksEl.getAttribute("aria-label") || forksEl.innerText || "").trim() : "";
  let forks = 0;
  try { forks = parseInt(forksText.replace(/,/g, "").replace(/[^0-9]/g, ""), 10) || 0; } catch (e) {}
  const langEl = document.querySelector(".d-inline-flex span:first-child, [itemprop='programmingLanguage'] span");
  const language = langEl ? langEl.innerText.trim() : "";
  const topics = Array.from(document.querySelectorAll("a.topic-tag"))
    .map((el) => el.innerText.trim()).filter(Boolean);
  const readmeEl = document.querySelector("#readme article, #readme .markdown-body, #readme");
  const readmeText = readmeEl ? readmeEl.innerText.trim().slice(0, 500) : "";
  return {
    owner,
    repo_name: owner + "/" + repoName,
    repo_url: window.location.href,
    description,
    stars,
    forks,
    language,
    topics,
    readme_preview: readmeText
  };
}
""",
            "issues-list": """
() => {
  const repoUrl = window.location.href.split("/issues")[0];
  const openTabEl = document.querySelector("a[href$='/issues'] span.Counter, [data-ga-click*='Open'] .Counter, #js-issues-toolbar a[href*='state=open'] .Counter");
  const closedTabEl = document.querySelector("a[href*='state=closed'] .Counter, [data-ga-click*='Closed'] .Counter");
  const openCount = openTabEl ? openTabEl.innerText.trim() : "";
  const closedCount = closedTabEl ? closedTabEl.innerText.trim() : "";
  const rows = Array.from(document.querySelectorAll(
    ".js-issue-row, [id^='issue_'], li[data-labels], div[id^='issue_']"
  )).slice(0, 30);
  const issues = rows.map((row) => {
    const titleLinkEl = row.querySelector("a[data-hovercard-type='issue'], a[id*='issue'][href*='/issues/'], .js-navigation-open[href*='/issues/']");
    const title = titleLinkEl ? titleLinkEl.innerText.trim() : "";
    const issueUrl = titleLinkEl ? titleLinkEl.href : "";
    let number = 0;
    try {
      const match = (issueUrl || row.id || "").match(/\\/issues\\/(\\d+)|issue_(\\d+)/);
      if (match) number = parseInt(match[1] || match[2], 10);
    } catch (e) {}
    const stateEl = row.querySelector("[aria-label*='Open'], [aria-label*='Closed'], .octicon-issue-opened, .octicon-issue-closed");
    const stateLabel = stateEl ? stateEl.getAttribute("aria-label") || "" : "";
    const state = stateLabel.toLowerCase().includes("closed") ? "closed" : "open";
    const authorEl = row.querySelector("a[data-hovercard-type='user']");
    const author = authorEl ? authorEl.innerText.trim() : "";
    const timeEl = row.querySelector("relative-time[datetime], time[datetime]");
    const createdAt = timeEl ? timeEl.getAttribute("datetime") || "" : "";
    const labels = Array.from(row.querySelectorAll("a.IssueLabel, [data-name], .label"))
      .map((el) => el.innerText.trim()).filter(Boolean);
    return { number, title, issue_url: issueUrl, state, author, created_at: createdAt, labels };
  }).filter((i) => i.title || i.issue_url);
  return { repo_url: repoUrl, issues, open_count: openCount, closed_count: closedCount };
}
""",
            "issue-detail": """
() => {
  const issueUrl = window.location.href;
  const titleEl = document.querySelector(".js-issue-title, h1.gh-header-title .js-issue-title, h1[class*='title']");
  const title = titleEl ? titleEl.innerText.trim() : (document.querySelector("h1") || {innerText: ""}).innerText.trim();
  let number = 0;
  try {
    const match = issueUrl.match(/\\/issues\\/(\\d+)/);
    if (match) number = parseInt(match[1], 10);
    if (!number) {
      const numEl = document.querySelector("h1 .f1, .gh-header-number");
      if (numEl) number = parseInt((numEl.innerText || "").replace(/[^0-9]/g, ""), 10) || 0;
    }
  } catch (e) {}
  const stateEl = document.querySelector(".State, [data-component='text'][class*='State'], span[class*='IssueLabel--state']");
  const state = stateEl ? stateEl.innerText.trim().toLowerCase() : "open";
  const authorEl = document.querySelector(".author.Link--primary, a.author[data-hovercard-type='user'], .timeline-comment-header a[data-hovercard-type='user']");
  const author = authorEl ? authorEl.innerText.trim() : "";
  const timeEl = document.querySelector("relative-time[datetime], time[datetime]");
  const createdAt = timeEl ? timeEl.getAttribute("datetime") || "" : "";
  const bodyEl = document.querySelector(".comment-body, .js-comment-body, .markdown-body");
  const body = bodyEl ? bodyEl.innerText.trim().slice(0, 2000) : "";
  const labels = Array.from(document.querySelectorAll("a.IssueLabel, .js-issue-labels a, .sidebar-labels a.IssueLabel"))
    .map((el) => el.innerText.trim()).filter(Boolean);
  const commentCountEl = document.querySelector(".js-discussions-count, [aria-label*='comment']");
  let commentCount = 0;
  try {
    const countText = commentCountEl ? (commentCountEl.innerText || commentCountEl.getAttribute("aria-label") || "") : "";
    commentCount = parseInt(countText.replace(/[^0-9]/g, ""), 10) || 0;
  } catch (e) {}
  return { title, issue_url: issueUrl, number, state, author, created_at: createdAt, body, labels, comment_count: commentCount };
}
""",
            "release-notes": """
() => {
  const repoUrl = window.location.href.split("/releases")[0];
  const releaseEls = Array.from(document.querySelectorAll(
    ".release, [data-testid='release'], section.release, [class*='release-entry']"
  )).slice(0, 10);
  const releases = releaseEls.map((rel) => {
    const tagEl = rel.querySelector("a[href*='/releases/tag/']");
    const tag = tagEl ? tagEl.innerText.trim() : "";
    const nameEl = rel.querySelector("h2.f1, h2, .release-title");
    const name = nameEl ? nameEl.innerText.trim() : tag;
    const timeEl = rel.querySelector("relative-time[datetime], time[datetime]");
    const publishedAt = timeEl ? timeEl.getAttribute("datetime") || "" : "";
    const bodyEl = rel.querySelector(".markdown-body, .release-body, [data-testid='release-body']");
    const bodyPreview = bodyEl ? bodyEl.innerText.trim().slice(0, 500) : "";
    const preEl = rel.querySelector(".Label--preRelease, [data-testid='prerelease-label'], span[class*='pre']");
    const isPrelease = preEl ? preEl.innerText.toLowerCase().includes("pre") : false;
    return { tag, name, published_at: publishedAt, body_preview: bodyPreview, is_prerelease: isPrelease };
  }).filter((r) => r.tag || r.name);
  return { repo_url: repoUrl, releases };
}
""",
            "user-profile": """
() => {
  const profileUrl = window.location.href;
  const pathParts = window.location.pathname.replace(/^\\//, "").split("/");
  const username = pathParts[0] || "";
  const nameEl = document.querySelector("h1 .p-name, .vcard-fullname, h1.vcard-names, [itemprop='name']");
  const name = nameEl ? nameEl.innerText.trim() : "";
  const bioEl = document.querySelector(".p-note, [data-bio-text], .user-profile-bio");
  const bio = bioEl ? bioEl.innerText.trim() : "";
  const locationEl = document.querySelector("li[itemprop='homeLocation'] span, .p-label, [aria-label*='Home location']");
  const location = locationEl ? locationEl.innerText.trim() : "";
  const companyEl = document.querySelector("li[itemprop='worksFor'] span, span[itemprop='worksFor'], .p-org");
  const company = companyEl ? companyEl.innerText.trim() : "";
  const followersEl = document.querySelector("a[href*='followers'] span.text-bold, a[href$='?tab=followers'] span");
  const followers = followersEl ? followersEl.innerText.trim() : "";
  const followingEl = document.querySelector("a[href*='following'] span.text-bold, a[href$='?tab=following'] span");
  const following = followingEl ? followingEl.innerText.trim() : "";
  const repoCountEl = document.querySelector("[data-tab-item='repositories'] span.Counter, a[href*='tab=repositories'] span.Counter");
  const publicRepos = repoCountEl ? repoCountEl.innerText.trim() : "";
  const pinnedRepos = Array.from(document.querySelectorAll(
    ".js-pinned-items-reorder-list .pinned-item-list-item a[href*='/'], .pinned-item-list-item span.repo"
  )).map((el) => el.innerText.trim()).filter(Boolean).slice(0, 6);
  return { username, profile_url: profileUrl, name, bio, location, company, followers, following, public_repos: publicRepos, pinned_repos: pinnedRepos };
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

        if target_type == "repo-search":
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("q", [""])[0]
            )
            repos: list[dict[str, object]] = []
            for raw in structured.get("repos", []):
                if not isinstance(raw, dict):
                    continue
                repos.append(
                    {
                        "repo_name": self._as_string(raw.get("repo_name")),
                        "repo_url": self._as_string(raw.get("repo_url")),
                        "description": self._as_string(raw.get("description")),
                        "stars": self._parse_count(raw.get("stars")),
                        "language": self._as_string(raw.get("language")),
                        "topics": self._as_string_list(raw.get("topics")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "repos": repos,
                    "result_count_text": self._as_string(structured.get("result_count_text")),
                },
            )

        if target_type == "repo-detail":
            path = parsed_url.path.lstrip("/")
            path_parts = path.split("/")
            owner = self._as_string(structured.get("owner")) or (path_parts[0] if len(path_parts) >= 1 else "")
            raw_repo_name = self._as_string(structured.get("repo_name"))
            if not raw_repo_name and len(path_parts) >= 2:
                raw_repo_name = path_parts[0] + "/" + path_parts[1]
            payload: dict[str, object] = {
                "owner": owner,
                "repo_name": raw_repo_name,
                "repo_url": self._as_string(structured.get("repo_url")) or target_url,
                "description": self._as_string(structured.get("description"))
                    or self._as_string(main_content.get("text", "")),
                "stars": self._parse_count(structured.get("stars")),
                "forks": self._parse_count(structured.get("forks")),
                "language": self._as_string(structured.get("language")),
                "topics": self._as_string_list(structured.get("topics")),
                "readme_preview": self._as_string(structured.get("readme_preview")),
            }
            return self.validate_payload(target_type, payload)

        if target_type == "issues-list":
            issues: list[dict[str, object]] = []
            for raw in structured.get("issues", []):
                if not isinstance(raw, dict):
                    continue
                issues.append(
                    {
                        "number": self._parse_count(raw.get("number")),
                        "title": self._as_string(raw.get("title")),
                        "issue_url": self._as_string(raw.get("issue_url")),
                        "state": self._as_string(raw.get("state")),
                        "author": self._as_string(raw.get("author")),
                        "created_at": self._as_string(raw.get("created_at")),
                        "labels": self._as_string_list(raw.get("labels")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "repo_url": self._as_string(structured.get("repo_url")) or target_url,
                    "issues": issues,
                    "open_count": self._as_string(structured.get("open_count")),
                    "closed_count": self._as_string(structured.get("closed_count")),
                },
            )

        if target_type == "issue-detail":
            payload = {
                "title": self._as_string(structured.get("title"))
                    or self._as_string(main_content.get("title"))
                    or self._as_string(navigation.get("title")),
                "issue_url": self._as_string(structured.get("issue_url")) or target_url,
                "number": self._parse_count(structured.get("number")),
                "state": self._as_string(structured.get("state")),
                "author": self._as_string(structured.get("author")),
                "created_at": self._as_string(structured.get("created_at")),
                "body": self._as_string(structured.get("body")),
                "labels": self._as_string_list(structured.get("labels")),
                "comment_count": self._parse_count(structured.get("comment_count")),
            }
            return self.validate_payload(target_type, payload)

        if target_type == "release-notes":
            releases: list[dict[str, object]] = []
            for raw in structured.get("releases", []):
                if not isinstance(raw, dict):
                    continue
                is_prerelease = raw.get("is_prerelease")
                if not isinstance(is_prerelease, bool):
                    is_prerelease = str(is_prerelease or "").lower() in ("true", "1", "yes")
                releases.append(
                    {
                        "tag": self._as_string(raw.get("tag")),
                        "name": self._as_string(raw.get("name")),
                        "published_at": self._as_string(raw.get("published_at")),
                        "body_preview": self._as_string(raw.get("body_preview")),
                        "is_prerelease": is_prerelease,
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "repo_url": self._as_string(structured.get("repo_url")) or target_url,
                    "releases": releases,
                },
            )

        # user-profile
        payload = {
            "username": self._as_string(structured.get("username"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
            "profile_url": self._as_string(structured.get("profile_url")) or target_url,
            "name": self._as_string(structured.get("name")),
            "bio": self._as_string(structured.get("bio")),
            "location": self._as_string(structured.get("location")),
            "company": self._as_string(structured.get("company")),
            "followers": self._as_string(structured.get("followers")),
            "following": self._as_string(structured.get("following")),
            "public_repos": self._as_string(structured.get("public_repos")),
            "pinned_repos": self._as_string_list(structured.get("pinned_repos")),
        }
        return self.validate_payload(target_type, payload)

    @staticmethod
    def _parse_count(value: object) -> int:
        raw = value if isinstance(value, (int, float)) else str(value or "")
        if isinstance(raw, (int, float)):
            try:
                return int(raw)
            except (ValueError, TypeError):
                return 0
        cleaned = str(raw).replace(",", "").strip()
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
