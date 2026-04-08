"""
DEPRECATED — FiverrAdapter is no longer registered in MarketplaceService.

Fiverr's anti-scrape protections (Cloudflare, heavy JS rendering, login walls)
make reliable extraction impractical. Retained for historical reference only.
Use one of the supported adapters instead: amazon, github, google_search,
hackernews, linkedin, news, reddit.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class FiverrAdapter(MarketplaceAdapter):
    slug = "fiverr"
    display_name = "Fiverr"
    schema_version = "fiverr.v1"
    target_definitions = (
        TargetDefinition(
            key="gig-search",
            label="Gig search results",
            description="Search result pages listing Fiverr gigs.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["query", "gigs"],
                "properties": {
                    "query": {"type": "string"},
                    "gigs": {"type": "array"},
                    "pagination_token": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="gig-detail",
            label="Gig detail",
            description="Single Fiverr gig pages with package and seller metadata.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["title", "gig_url"],
                "properties": {
                    "title": {"type": "string"},
                    "gig_url": {"type": "string"},
                    "packages": {"type": "array"},
                    "seller_username": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="seller-profile",
            label="Seller profile",
            description="Fiverr seller profile pages with service history and ratings.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["username", "profile_url"],
                "properties": {
                    "username": {"type": "string"},
                    "profile_url": {"type": "string"},
                    "rating": {"type": "number"},
                    "skills": {"type": "array"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        cleaned = super().normalize_url(url)
        if "fiverr.com" not in cleaned:
            raise ValueError("Fiverr adapter requires a fiverr.com URL")
        return cleaned

    def login_url(self) -> str:
        return "https://pro.fiverr.com/login"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input[type='email'],input[name='email'],input[id*='email']",
            "password": "input[type='password'],input[name='password'],input[id*='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        if target_type == "gig-search":
            return 5
        return super().scroll_iterations(target_type)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "gig-search": {
                "primary": [
                    "[data-testid='search-results'] article",
                    "[data-test-id='gig-card-layout']",
                ],
                "fallback": [
                    "article[data-impression-collected='true']",
                    ".gig-card-layout",
                ],
            },
            "gig-detail": {
                "primary": [
                    "h1",
                    "[data-testid='gig-overview']",
                ],
                "fallback": [
                    ".gig-page",
                    "[data-testid='GigPackageCards']",
                ],
            },
            "seller-profile": {
                "primary": [
                    "h1",
                    "[data-testid='profile-card']",
                ],
                "fallback": [
                    ".profile-card-wrapper",
                    "[data-testid='user-profile']",
                ],
            },
        }
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "gig-search": """
() => {
  const cards = Array.from(document.querySelectorAll(
    "[data-testid='search-results'] article, [data-test-id='gig-card-layout'], article[data-impression-collected='true'], .gig-card-layout"
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
    query: new URL(window.location.href).searchParams.get("query") || new URL(window.location.href).searchParams.get("q") || "",
    gigs: cards.map((card) => ({
      title: textOf(card, ["h3", "a[aria-label]", "a[href*='/categories/']", "a[href*='/']"]),
      gig_url: hrefOf(card, ["a[href*='/']", "a[aria-label]"]),
      seller_username: textOf(card, ["[data-testid='seller-link']", "a[href^='/users/']", "a[href*='/user/']"]),
      packages: [],
      price: textOf(card, ["[data-testid='price']", "span[class*='price']", "strong"]),
    })).filter((gig) => gig.title || gig.gig_url)
  };
}
""",
            "gig-detail": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  return {
    title: pickText("h1", "[data-testid='gig-title']", "[data-testid='gig-overview'] h1"),
    gig_url: window.location.href,
    seller_username: pickText("[data-testid='seller-link']", "a[href^='/users/']", "a[href*='/user/']"),
    packages: Array.from(document.querySelectorAll("[data-testid='GigPackageCards'] [data-testid='package-card'], [data-testid='GigPackageCards'] article, [data-testid='gig-package']"))
      .map((el) => (el.innerText || "").trim())
      .filter(Boolean)
      .slice(0, 3)
  };
}
""",
            "seller-profile": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const ratingText = pickText("[data-testid='rating-score']", "[data-testid='profile-card'] [class*='rating']", "[class*='rating-score']");
  return {
    username: pickText("h1", "[data-testid='profile-card'] h1", "[data-testid='user-profile'] h1"),
    profile_url: window.location.href,
    rating: ratingText,
    skills: Array.from(document.querySelectorAll("[data-testid='skill-tag'], [class*='skill-tag'], a[href*='skills']"))
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
        if target_type == "gig-search":
            parsed_url = urlparse(target_url)
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("query", [""])[0]
                or parse_qs(parsed_url.query).get("q", [""])[0]
            )
            gigs: list[dict[str, object]] = []
            for raw_gig in structured.get("gigs", []):
                if not isinstance(raw_gig, dict):
                    continue
                title = self._as_string(raw_gig.get("title"))
                gig_url = self._as_string(raw_gig.get("gig_url"))
                if not title and not gig_url:
                    continue
                gigs.append(
                    {
                        "title": title,
                        "gig_url": gig_url,
                        "seller_username": self._as_string(raw_gig.get("seller_username")),
                        "packages": self._as_string_list(raw_gig.get("packages")),
                        "price": self._as_string(raw_gig.get("price")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "gigs": gigs,
                    "pagination_token": self._as_string(structured.get("pagination_token")),
                },
            )

        if target_type == "gig-detail":
            payload = {
                "title": self._as_string(structured.get("title"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "gig_url": self._as_string(structured.get("gig_url")) or target_url,
                "packages": self._as_string_list(structured.get("packages")),
                "seller_username": self._as_string(structured.get("seller_username")),
            }
            return self.validate_payload(target_type, payload)

        rating_value = self._coerce_rating(structured.get("rating"))
        payload = {
            "username": self._as_string(structured.get("username"))
            or self._as_string(main_content.get("title"))
            or self._as_string(navigation.get("title")),
            "profile_url": self._as_string(structured.get("profile_url")) or target_url,
            "rating": rating_value,
            "skills": self._as_string_list(structured.get("skills")),
        }
        return self.validate_payload(target_type, payload)

    @staticmethod
    def _coerce_rating(value: object) -> float:
        raw = value if isinstance(value, str) else str(value or "")
        cleaned = ""
        for char in raw:
            if char.isdigit() or char == ".":
                cleaned += char
            elif cleaned:
                break
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
