from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class LinkedInAdapter(MarketplaceAdapter):
    slug = "linkedin"
    display_name = "LinkedIn"
    schema_version = "linkedin.v1"
    target_definitions = (
        TargetDefinition(
            key="people-search",
            label="People search results",
            description="LinkedIn people search result pages listing member profiles.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["query", "people"],
                "properties": {
                    "query": {"type": "string"},
                    "people": {"type": "array"},
                    "next_cursor": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="person-profile",
            label="Person profile",
            description="Individual LinkedIn member profile pages.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["name", "profile_url"],
                "properties": {
                    "name": {"type": "string"},
                    "profile_url": {"type": "string"},
                    "headline": {"type": "string"},
                    "current_company": {"type": "string"},
                    "location": {"type": "string"},
                    "connections": {"type": "string"},
                    "skills": {"type": "array"},
                    "experience": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="company-profile",
            label="Company profile",
            description="LinkedIn company pages with overview, headcount, and about sections.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["name", "company_url"],
                "properties": {
                    "name": {"type": "string"},
                    "company_url": {"type": "string"},
                    "tagline": {"type": "string"},
                    "employee_count": {"type": "string"},
                    "industry": {"type": "string"},
                    "website": {"type": "string"},
                    "about": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="job-search",
            label="Job search results",
            description="LinkedIn job search result pages listing open positions.",
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
            description="Single LinkedIn job posting page with full description and metadata.",
            login_required=True,
            output_schema={
                "type": "object",
                "required": ["title", "company", "job_url"],
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "job_url": {"type": "string"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                    "posted_at": {"type": "string"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("LinkedIn adapter only accepts http/https URLs")
        if "linkedin.com" not in parsed.netloc:
            raise ValueError("LinkedIn adapter requires a linkedin.com URL")
        return cleaned

    def login_url(self) -> str:
        return "https://www.linkedin.com/login"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input#username,input[name='session_key'],input[type='email'],input[name='email']",
            "password": "input#password,input[name='session_password'],input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        if target_type in ("people-search", "job-search"):
            return 5
        return super().scroll_iterations(target_type)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "people-search": {
                "primary": [
                    "ul.reusable-search__entity-result-list li",
                    ".entity-result",
                ],
                "fallback": [
                    ".search-results-container li",
                    "[data-chameleon-result-urn]",
                ],
            },
            "person-profile": {
                "primary": [
                    "h1.text-heading-xlarge",
                    ".pv-text-details__left-panel",
                    ".pvs-list__outer-container",
                ],
                "fallback": [
                    "main h1",
                    ".ph5.pb5",
                    ".pv-profile-section",
                ],
            },
            "company-profile": {
                "primary": [
                    "h1.org-top-card-summary__title",
                    ".org-top-card-summary-info-list",
                    ".org-about-company-module",
                ],
                "fallback": [
                    "main h1",
                    ".org-grid__core-rail",
                    ".org-about-module__description",
                ],
            },
            "job-search": {
                "primary": [
                    ".jobs-search-results__list li",
                    ".job-card-container",
                ],
                "fallback": [
                    ".scaffold-layout__list li",
                    "[data-occludable-job-id]",
                ],
            },
            "job-detail": {
                "primary": [
                    "h1.job-details-jobs-unified-top-card__job-title",
                    ".jobs-description",
                ],
                "fallback": [
                    ".job-view-layout h1",
                    ".jobs-description-content",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "people-search": """
() => {
  const cards = Array.from(document.querySelectorAll(
    "ul.reusable-search__entity-result-list li, .entity-result, .search-results-container li[data-chameleon-result-urn]"
  )).filter((el) => el.querySelector("a[href*='/in/']")).slice(0, 10);
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
    query: new URL(window.location.href).searchParams.get("keywords") || new URL(window.location.href).searchParams.get("q") || "",
    people: cards.map((card) => {
      const profileUrl = hrefOf(card, ["a[href*='/in/']"]);
      return {
        name: textOf(card, [
          ".entity-result__title-text a span[aria-hidden='true']",
          "a[href*='/in/'] span[aria-hidden='true']",
          ".entity-result__title-text",
          "span.actor-name"
        ]),
        profile_url: profileUrl ? profileUrl.split("?")[0] : "",
        headline: textOf(card, [
          ".entity-result__primary-subtitle",
          ".entity-result__summary",
          "div.t-14.t-black.t-normal"
        ]),
        current_company: textOf(card, [
          ".entity-result__secondary-subtitle",
          "div.t-14.t-black--light.t-normal"
        ]),
        location: textOf(card, [
          ".entity-result__tertiary-subtitle",
          "div.t-12.t-black--light.t-normal"
        ])
      };
    }).filter((p) => p.name || p.profile_url)
  };
}
""",
            "person-profile": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const skills = Array.from(document.querySelectorAll(
    ".pvs-list__outer-container .pvs-entity__path-node, [data-field='skill_card_skill_topic'] span[aria-hidden='true'], .pv-skill-category-entity__name span"
  )).map((el) => (el.innerText || "").trim()).filter(Boolean).slice(0, 20);
  const experience = Array.from(document.querySelectorAll(
    "#experience ~ div .pvs-list > li, #experience-section .pv-entity__summary-info, section[data-section='experience'] li"
  )).map((el) => (el.innerText || "").trim().split("\n").filter(Boolean).slice(0, 3).join(" | ")).filter(Boolean).slice(0, 5);
  return {
    name: pickText(
      "h1.text-heading-xlarge",
      ".pv-text-details__left-panel h1",
      "main h1",
      "h1"
    ),
    profile_url: window.location.href.split("?")[0],
    headline: pickText(
      ".text-body-medium.break-words",
      ".pv-text-details__left-panel .text-body-medium",
      "div.text-body-medium"
    ),
    current_company: pickText(
      "button[aria-label*='Current company'] div span:not(.visually-hidden)",
      ".pv-text-details__right-panel-item-text",
      ".inline-show-more-text--is-collapsed"
    ),
    location: pickText(
      ".text-body-small.inline.t-black--light.break-words",
      ".pv-text-details__left-panel span.text-body-small",
      "span.text-body-small"
    ),
    connections: pickText(
      ".pvs-header__subtitle span",
      "span.t-bold ~ span",
      ".pv-text-details__left-panel .t-black--light"
    ),
    skills: skills,
    experience: experience
  };
}
""",
            "company-profile": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const pickHref = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.href) return el.href;
    }
    return "";
  };
  return {
    name: pickText(
      "h1.org-top-card-summary__title",
      "h1.ember-view",
      "main h1",
      "h1"
    ),
    company_url: window.location.href.split("?")[0],
    tagline: pickText(
      ".org-top-card-summary__tagline",
      "p.org-top-card-summary__tagline",
      ".org-grid__core-rail p.t-16"
    ),
    employee_count: pickText(
      ".org-top-card-summary-info-list__info-item:nth-child(2)",
      "a[href*='employees'] span",
      ".t-normal.link-without-visited-state"
    ),
    industry: pickText(
      ".org-top-card-summary-info-list__info-item:first-child",
      "dd.org-top-card-summary-info-list__info-item",
      ".org-top-card-summary-info-list li:first-child"
    ),
    website: pickHref(
      "a[data-field='website_link']",
      ".org-about-module__member-info a[href*='http']",
      "a[href*='http']:not([href*='linkedin.com'])"
    ),
    about: (document.querySelector(".org-about-module__description, .about-us-organization-description, [data-test-id='about-us__description']") || {}).innerText || ""
  };
}
""",
            "job-search": """
() => {
  const cards = Array.from(document.querySelectorAll(
    ".jobs-search-results__list li, .job-card-container, .scaffold-layout__list li[data-occludable-job-id]"
  )).filter((el) => el.querySelector("a[href*='/jobs/']")).slice(0, 20);
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
    query: new URL(window.location.href).searchParams.get("keywords") || new URL(window.location.href).searchParams.get("q") || "",
    jobs: cards.map((card) => {
      const jobUrl = hrefOf(card, ["a[href*='/jobs/view/']", "a.job-card-list__title", "a[href*='/jobs/']"]);
      return {
        title: textOf(card, [
          "a.job-card-list__title strong",
          "a.job-card-list__title",
          "h3.base-search-card__title",
          "h3",
          "a[href*='/jobs/']"
        ]),
        company: textOf(card, [
          ".job-card-container__primary-description",
          "h4.base-search-card__subtitle",
          "a[href*='/company/']",
          ".job-card-container__company-name"
        ]),
        job_url: jobUrl ? jobUrl.split("?")[0] : "",
        location: textOf(card, [
          ".job-card-container__metadata-item",
          "span.job-search-card__location",
          ".base-search-card__metadata span"
        ]),
        posted_at: textOf(card, [
          "time",
          ".job-search-card__listdate",
          ".base-search-card__metadata time"
        ])
      };
    }).filter((j) => j.title || j.job_url)
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
  const descEl = document.querySelector(".jobs-description__content, .jobs-description, #job-details, .show-more-less-html__markup");
  const fullDesc = descEl ? descEl.innerText.trim() : "";
  return {
    title: pickText(
      "h1.job-details-jobs-unified-top-card__job-title",
      "h1.jobs-unified-top-card__job-title",
      "h1.topcard__title",
      "main h1",
      "h1"
    ),
    company: pickText(
      ".job-details-jobs-unified-top-card__company-name a",
      ".job-details-jobs-unified-top-card__company-name",
      ".jobs-unified-top-card__company-name a",
      "a.topcard__org-name-link",
      ".topcard__org-name-link"
    ),
    job_url: window.location.href.split("?")[0],
    location: pickText(
      ".job-details-jobs-unified-top-card__bullet",
      ".jobs-unified-top-card__bullet",
      "span.topcard__flavor--bullet"
    ),
    description: fullDesc.slice(0, 1000),
    posted_at: pickText(
      "span.jobs-unified-top-card__posted-date",
      ".job-details-jobs-unified-top-card__posted-date",
      "time",
      "span.topcard__flavor--metadata"
    )
  };
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

        if target_type == "people-search":
            parsed_url = urlparse(target_url)
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("keywords", [""])[0]
                or parse_qs(parsed_url.query).get("q", [""])[0]
            )
            people: list[dict[str, object]] = []
            for raw in structured.get("people", []):
                if not isinstance(raw, dict):
                    continue
                name = self._as_string(raw.get("name"))
                profile_url = self._as_string(raw.get("profile_url"))
                if not name and not profile_url:
                    continue
                people.append(
                    {
                        "name": name,
                        "profile_url": profile_url,
                        "headline": self._as_string(raw.get("headline")),
                        "current_company": self._as_string(raw.get("current_company")),
                        "location": self._as_string(raw.get("location")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "people": people,
                    "next_cursor": self._as_string(structured.get("next_cursor")),
                },
            )

        if target_type == "person-profile":
            payload = {
                "name": self._as_string(structured.get("name"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "profile_url": self._as_string(structured.get("profile_url")) or target_url,
                "headline": self._as_string(structured.get("headline")),
                "current_company": self._as_string(structured.get("current_company")),
                "location": self._as_string(structured.get("location")),
                "connections": self._as_string(structured.get("connections")),
                "skills": self._as_string_list(structured.get("skills")),
                "experience": self._as_string_list(structured.get("experience")),
            }
            return self.validate_payload(target_type, payload)

        if target_type == "company-profile":
            payload = {
                "name": self._as_string(structured.get("name"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "company_url": self._as_string(structured.get("company_url")) or target_url,
                "tagline": self._as_string(structured.get("tagline")),
                "employee_count": self._as_string(structured.get("employee_count")),
                "industry": self._as_string(structured.get("industry")),
                "website": self._as_string(structured.get("website")),
                "about": self._as_string(structured.get("about"))
                or self._as_string(main_content.get("text")),
            }
            return self.validate_payload(target_type, payload)

        if target_type == "job-search":
            parsed_url = urlparse(target_url)
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("keywords", [""])[0]
                or parse_qs(parsed_url.query).get("q", [""])[0]
            )
            jobs: list[dict[str, object]] = []
            for raw in structured.get("jobs", []):
                if not isinstance(raw, dict):
                    continue
                title = self._as_string(raw.get("title"))
                job_url = self._as_string(raw.get("job_url"))
                if not title and not job_url:
                    continue
                jobs.append(
                    {
                        "title": title,
                        "company": self._as_string(raw.get("company")),
                        "job_url": job_url,
                        "location": self._as_string(raw.get("location")),
                        "posted_at": self._as_string(raw.get("posted_at")),
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

        # job-detail
        payload = {
            "title": self._as_string(structured.get("title"))
            or self._as_string(main_content.get("title"))
            or self._as_string(navigation.get("title")),
            "company": self._as_string(structured.get("company"))
            or self._as_string(main_content.get("site_name")),
            "job_url": self._as_string(structured.get("job_url")) or target_url,
            "location": self._as_string(structured.get("location")),
            "description": self._as_string(structured.get("description"))
            or self._as_string(main_content.get("text")),
            "posted_at": self._as_string(structured.get("posted_at")),
        }
        return self.validate_payload(target_type, payload)
