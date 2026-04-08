"""
DEPRECATED — UpworkAdapter is no longer registered in MarketplaceService.

Upwork requires login for nearly all useful data and uses heavy anti-scrape
measures. Retained for historical reference only. Use one of the supported
adapters instead: amazon, github, google_search, hackernews, linkedin, news,
reddit.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class UpworkAdapter(MarketplaceAdapter):
    slug = "upwork"
    display_name = "Upwork"
    schema_version = "upwork.v1"
    target_definitions = (
        TargetDefinition(
            key="job-search",
            label="Job search results",
            description="Search and filter pages listing jobs on Upwork.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["query", "jobs"],
                "properties": {
                    "query": {"type": "string"},
                    "jobs": {"type": "array"},
                    "next_cursor": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="job-detail",
            label="Job detail",
            description="Single job post pages with scope, budget, and client metadata.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["title", "description", "job_url"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "job_url": {"type": "string"},
                    "budget": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="freelancer-profile",
            label="Freelancer profile",
            description="Public or logged-in freelancer profile pages.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["name", "profile_url"],
                "properties": {
                    "name": {"type": "string"},
                    "profile_url": {"type": "string"},
                    "hourly_rate": {"type": "string"},
                    "skills": {"type": "array"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        if "upwork.com" not in cleaned:
            raise ValueError("Upwork adapter requires an upwork.com URL")
        return cleaned

    def login_url(self) -> str:
        return "https://www.upwork.com/ab/account-security/login"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input#login_username,input[name='login[username]'],input[type='email'],input[name='email']",
            "password": "input#login_password,input[name='login[password]'],input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        if target_type == "job-search":
            return 4
        return super().scroll_iterations(target_type)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "job-search": {
                "primary": [
                    "[data-test='job-tile-list'] article",
                    "section[data-test='job-tile']",
                ],
                "fallback": [
                    "article.job-tile",
                    "section.air3-card-section",
                ],
            },
            "job-detail": {
                "primary": [
                    "h1",
                    "[data-test='job-description-text']",
                ],
                "fallback": [
                    "section.up-card-section",
                    "[data-qa='job-description']",
                ],
            },
            "freelancer-profile": {
                "primary": [
                    "h1[data-qa='freelancer-name']",
                    "[data-qa='freelancer-overview']",
                ],
                "fallback": [
                    "main h1",
                    ".air3-card-section",
                ],
            },
        }
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "job-search": """
() => {
  const cards = Array.from(document.querySelectorAll(
    "[data-test='job-tile-list'] article, section[data-test='job-tile'], article.job-tile, section.air3-card-section"
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
  return {
    query: new URL(window.location.href).searchParams.get("q") || "",
    jobs: cards.map((card) => ({
      title: textOf(card, ["h2", "h3", "a[data-test='job-tile-title-link']", "a[href*='/jobs/']"]),
      job_url: hrefOf(card, ["a[data-test='job-tile-title-link']", "a[href*='/jobs/']"]),
      description: textOf(card, ["[data-test='job-description-text']", "[data-test='UpCLineClamp JobDescription']", "p", "div"]),
      budget: textOf(card, ["[data-test='is-fixed-price']", "[data-test='job-type']", "strong", "small"]),
    })).filter((job) => job.title || job.job_url)
  };
}
""",
            "job-detail": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  return {
    title: pickText("h1", "[data-test='job-title']", "[data-qa='job-title']"),
    description: pickText("[data-test='job-description-text']", "[data-qa='job-description']", "main"),
    job_url: window.location.href,
    budget: pickText("[data-test='is-fixed-price']", "[data-test='job-type']", "small", "strong")
  };
}
""",
            "freelancer-profile": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  return {
    name: pickText("h1[data-qa='freelancer-name']", "main h1", "h1"),
    profile_url: window.location.href,
    hourly_rate: pickText("[data-qa='freelancer-hourly-rate']", "[data-test='freelancer-hourly-rate']", "strong"),
    skills: Array.from(document.querySelectorAll("[data-qa='skill'], [data-test='skill-chip'], a[href*='/skills/']"))
      .map((el) => (el.innerText || "").trim())
      .filter(Boolean)
      .slice(0, 25)
  };
}
""",
        }
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
        if target_type == "job-search":
            parsed_url = urlparse(target_url)
            query = self._as_string(structured.get("query")) or parse_qs(parsed_url.query).get("q", [""])[0]
            jobs: list[dict[str, str]] = []
            for raw_job in structured.get("jobs", []):
                if not isinstance(raw_job, dict):
                    continue
                title = self._as_string(raw_job.get("title"))
                job_url = self._as_string(raw_job.get("job_url"))
                if not title and not job_url:
                    continue
                jobs.append(
                    {
                        "title": title,
                        "job_url": job_url,
                        "description": self._as_string(raw_job.get("description")),
                        "budget": self._as_string(raw_job.get("budget")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "jobs": jobs,
                    "next_cursor": self._as_string(structured.get("next_cursor")),
                },
            )

        if target_type == "job-detail":
            payload = {
                "title": self._as_string(structured.get("title"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "description": self._as_string(structured.get("description"))
                or self._as_string(main_content.get("text")),
                "job_url": self._as_string(structured.get("job_url")) or target_url,
                "budget": self._as_string(structured.get("budget")),
            }
            return self.validate_payload(target_type, payload)

        payload = {
            "name": self._as_string(structured.get("name"))
            or self._as_string(main_content.get("title"))
            or self._as_string(navigation.get("title")),
            "profile_url": self._as_string(structured.get("profile_url")) or target_url,
            "hourly_rate": self._as_string(structured.get("hourly_rate")),
            "skills": self._as_string_list(structured.get("skills")),
        }
        return self.validate_payload(target_type, payload)
