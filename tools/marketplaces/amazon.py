from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .base import MarketplaceAdapter, TargetDefinition


class AmazonAdapter(MarketplaceAdapter):
    slug = "amazon"
    display_name = "Amazon"
    schema_version = "amazon.v1"
    target_definitions = (
        TargetDefinition(
            key="product-search",
            label="Product search results",
            description="Amazon search result pages listing products.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["query", "products"],
                "properties": {
                    "query": {"type": "string"},
                    "products": {"type": "array"},
                    "page": {"type": "integer"},
                },
            },
        ),
        TargetDefinition(
            key="product-detail",
            label="Product detail",
            description="Amazon product detail page with price, ratings, and feature bullets.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["title", "asin", "product_url"],
                "properties": {
                    "title": {"type": "string"},
                    "asin": {"type": "string"},
                    "product_url": {"type": "string"},
                    "price": {"type": "string"},
                    "rating": {"type": "number"},
                    "review_count": {"type": "integer"},
                    "availability": {"type": "string"},
                    "brand": {"type": "string"},
                    "features": {"type": "array"},
                },
            },
        ),
        TargetDefinition(
            key="product-reviews",
            label="Product reviews",
            description="Amazon customer reviews page for a product.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["asin", "reviews"],
                "properties": {
                    "asin": {"type": "string"},
                    "reviews": {"type": "array"},
                    "overall_rating": {"type": "number"},
                    "total_reviews": {"type": "string"},
                },
            },
        ),
        TargetDefinition(
            key="seller-profile",
            label="Seller profile",
            description="Amazon seller storefront with feedback rating and count.",
            login_required=False,
            output_schema={
                "type": "object",
                "required": ["seller_name", "seller_url"],
                "properties": {
                    "seller_name": {"type": "string"},
                    "seller_url": {"type": "string"},
                    "rating": {"type": "number"},
                    "feedback_count": {"type": "string"},
                    "positive_feedback_pct": {"type": "string"},
                },
            },
        ),
    )

    def normalize_url(self, url: str) -> str:
        import re as _re
        cleaned = super().normalize_url(url)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Amazon adapter only accepts http/https URLs")
        if not _re.search(r"(?:^|\.)amazon\.[a-z]{2,}$", parsed.netloc):
            raise ValueError("Amazon adapter requires an amazon.* URL")
        return cleaned

    def login_url(self) -> str:
        return "https://www.amazon.com/ap/signin"

    def login_selectors(self) -> dict[str, str]:
        return {
            "username": "input#ap_email,input[name='email'],input[type='email']",
            "password": "input#ap_password,input[name='password'],input[type='password']",
        }

    def scroll_iterations(self, target_type: str) -> int:
        if target_type in ("product-search", "product-reviews"):
            return 4
        return super().scroll_iterations(target_type)

    def selector_map(self, target_type: str) -> dict[str, list[str]]:
        selectors = {
            "product-search": {
                "primary": [
                    "[data-component-type='s-search-result']",
                    ".s-result-item[data-asin]",
                ],
                "fallback": [
                    ".s-main-slot .s-result-item",
                    "div[data-index]",
                ],
            },
            "product-detail": {
                "primary": [
                    "#productTitle",
                    "#priceblock_ourprice,#priceblock_dealprice,.a-price",
                    "#acrCustomerReviewText",
                ],
                "fallback": [
                    "#centerCol",
                    "#ppd",
                    "#dp",
                ],
            },
            "product-reviews": {
                "primary": [
                    "[data-hook='review']",
                    ".review",
                ],
                "fallback": [
                    "#cm_cr-review_list div[data-hook]",
                    ".review-views .a-section",
                ],
            },
            "seller-profile": {
                "primary": [
                    ".a-section.a-spacing-none .a-row",
                    "#seller-name",
                ],
                "fallback": [
                    "#sellerProfileTriggerId",
                    ".mbcMerchantName",
                ],
            },
        }
        if target_type not in selectors:
            raise ValueError(f"No selector map for target type: {target_type!r}")
        return selectors[target_type]

    def extraction_script(self, target_type: str) -> str:
        scripts = {
            "product-search": """
() => {
  const cards = Array.from(document.querySelectorAll(
    "[data-component-type='s-search-result'], .s-result-item[data-asin]"
  )).filter((el) => el.getAttribute("data-asin") && el.getAttribute("data-asin").length > 0).slice(0, 20);
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
  const parseRating = (text) => {
    const m = text.match(/([0-9]+\\.?[0-9]*)/);
    return m ? parseFloat(m[1]) : 0;
  };
  return {
    query: new URL(window.location.href).searchParams.get("k") || new URL(window.location.href).searchParams.get("field-keywords") || "",
    page: parseInt(new URL(window.location.href).searchParams.get("page") || "1", 10),
    products: cards.map((card) => {
      const asin = card.getAttribute("data-asin") || "";
      const ratingEl = card.querySelector("[aria-label*='stars'], .a-icon-star-small, .a-icon-star");
      const ratingText = ratingEl ? (ratingEl.getAttribute("aria-label") || ratingEl.innerText || "") : "";
      const priceText = textOf(card, [
        ".a-price .a-offscreen",
        ".a-price-whole",
        ".a-color-price",
        "span.a-price"
      ]);
      const reviewCountText = textOf(card, [
        "[aria-label*='ratings']",
        ".a-size-base.s-underline-text",
        ".a-link-normal .a-size-base"
      ]);
      const reviewCountMatch = reviewCountText.replace(/,/g, "").match(/([0-9]+)/);
      return {
        title: textOf(card, [
          "h2 a span",
          "h2 span.a-size-medium",
          "h2",
          "a.a-link-normal span"
        ]),
        product_url: hrefOf(card, ["h2 a", "a.a-link-normal[href*='/dp/']"]),
        asin: asin,
        price: priceText,
        rating: parseRating(ratingText),
        review_count: reviewCountMatch ? parseInt(reviewCountMatch[1], 10) : 0,
        is_sponsored: !!card.querySelector("[data-component-type='sp-sponsored-result'], .puis-sponsored-label-text, .s-label-popover-default")
      };
    }).filter((p) => p.title || p.asin)
  };
}
""",
            "product-detail": """
() => {
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText) return el.innerText.trim();
    }
    return "";
  };
  const parseRating = (text) => {
    const m = text.match(/([0-9]+\\.?[0-9]*)/);
    return m ? parseFloat(m[1]) : 0;
  };
  const parseReviewCount = (text) => {
    const cleaned = text.replace(/,/g, "");
    const m = cleaned.match(/([0-9]+)/);
    return m ? parseInt(m[1], 10) : 0;
  };
  const asinFromUrl = () => {
    const m = window.location.pathname.match(/\\/dp\\/([A-Z0-9]{10})/i);
    return m ? m[1] : "";
  };
  const asinInput = document.querySelector("#ASIN,input[name='ASIN']");
  const asin = (asinInput ? asinInput.value : "") || asinFromUrl();
  const ratingEl = document.querySelector("#acrPopover, #averageCustomerReviews .a-icon-star, #cmsr_a_star_count");
  const ratingText = ratingEl ? (ratingEl.getAttribute("title") || ratingEl.innerText || "") : "";
  const priceText = pickText(
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price .a-offscreen",
    "#price_inside_buybox",
    ".a-color-price"
  );
  const reviewCountText = pickText(
    "#acrCustomerReviewText",
    "#ratings-count",
    "span[data-hook='total-review-count']"
  );
  const features = Array.from(document.querySelectorAll(
    "#feature-bullets ul li span.a-list-item, #feature-bullets li:not(.aok-hidden) span"
  )).map((el) => (el.innerText || "").trim()).filter((t) => t && !t.includes("Make sure this fits")).slice(0, 10);
  return {
    title: pickText("#productTitle", "h1#title", "span#productTitle"),
    asin: asin,
    product_url: window.location.href.split("?")[0],
    price: priceText,
    rating: parseRating(ratingText),
    review_count: parseReviewCount(reviewCountText),
    availability: pickText(
      "#availability span",
      "#outOfStock span",
      "#buybox-see-all-buying-choices .a-declarative",
      "#merchantInfoFeature_feature_div span"
    ),
    brand: pickText(
      "#bylineInfo",
      "a#bylineInfo",
      "tr.po-brand td.a-span9 span",
      "#brand"
    ),
    features: features
  };
}
""",
            "product-reviews": """
() => {
  const asinFromUrl = () => {
    const m = window.location.pathname.match(/\\/dp\\/([A-Z0-9]{10})/i) || window.location.pathname.match(/product-reviews\\/([A-Z0-9]{10})/i);
    return m ? m[1] : "";
  };
  const parseRating = (text) => {
    const m = text.match(/([0-9]+\\.?[0-9]*)/);
    return m ? parseFloat(m[1]) : 0;
  };
  const reviewCards = Array.from(document.querySelectorAll("[data-hook='review'], .review")).slice(0, 15);
  const overallRatingEl = document.querySelector("[data-hook='rating-out-of-text'], #acrPopover, .reviewNumericalSummary .a-icon-star");
  const overallRatingText = overallRatingEl ? (overallRatingEl.getAttribute("title") || overallRatingEl.innerText || "") : "";
  const totalReviewsEl = document.querySelector("[data-hook='total-review-count'], #filter-info-section span, #acrCustomerReviewText");
  return {
    asin: asinFromUrl(),
    overall_rating: parseRating(overallRatingText),
    total_reviews: totalReviewsEl ? totalReviewsEl.innerText.trim() : "",
    reviews: reviewCards.map((card) => {
      const ratingEl = card.querySelector("[data-hook='review-star-rating'], [data-hook='cmps-review-star-rating'], i.review-rating");
      const ratingText = ratingEl ? (ratingEl.getAttribute("class") || ratingEl.innerText || "") : "";
      const ratingMatch = ratingText.match(/([0-9]+\\.?[0-9]*)/);
      const bodyEl = card.querySelector("[data-hook='review-body'] span, .review-text-content span, .review-text");
      const bodyText = bodyEl ? bodyEl.innerText.trim() : "";
      return {
        reviewer_name: (card.querySelector(".a-profile-name, [data-hook='genome-widget'] span") || {}).innerText || "",
        rating: ratingMatch ? parseFloat(ratingMatch[1]) : 0,
        title: (card.querySelector("[data-hook='review-title'] span:not(.a-icon-alt), .review-title") || {}).innerText || "",
        body: bodyText.slice(0, 500),
        verified_purchase: !!card.querySelector("[data-hook='avp-badge'], .a-color-success"),
        date: (card.querySelector("[data-hook='review-date'], .review-date") || {}).innerText || ""
      };
    })
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
  const parseRating = (text) => {
    const m = text.match(/([0-9]+\\.?[0-9]*)/);
    return m ? parseFloat(m[1]) : 0;
  };
  const ratingText = pickText(
    ".a-icon-star .a-icon-alt",
    "#seller-rating .a-icon-star",
    "[data-action='star-rating'] .a-icon-alt",
    ".feedbackRating .a-icon-alt"
  );
  const positivePctText = pickText(
    ".positive-feedback",
    "#seller-feedback-summary .a-size-large",
    ".a-size-large.a-color-base"
  );
  const feedbackCountText = pickText(
    "#seller-feedback-summary .a-size-medium",
    ".feedback-count",
    "span.a-size-medium.a-color-secondary"
  );
  return {
    seller_name: pickText(
      "#sellerName",
      "#seller-name",
      ".mbcMerchantName",
      "h1",
      ".a-size-extra-large"
    ),
    seller_url: window.location.href.split("?")[0],
    rating: parseRating(ratingText),
    feedback_count: feedbackCountText,
    positive_feedback_pct: positivePctText
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

        if target_type == "product-search":
            parsed_url = urlparse(target_url)
            query = (
                self._as_string(structured.get("query"))
                or parse_qs(parsed_url.query).get("k", [""])[0]
                or parse_qs(parsed_url.query).get("field-keywords", [""])[0]
            )
            page_raw = structured.get("page")
            try:
                page = int(page_raw) if page_raw is not None else 1
            except (TypeError, ValueError):
                page = 1
            if page < 1:
                page = 1
            products: list[dict[str, object]] = []
            for raw in structured.get("products", []):
                if not isinstance(raw, dict):
                    continue
                title = self._as_string(raw.get("title"))
                asin = self._as_string(raw.get("asin"))
                if not title and not asin:
                    continue
                products.append(
                    {
                        "title": title,
                        "product_url": self._as_string(raw.get("product_url")),
                        "asin": asin,
                        "price": self._as_string(raw.get("price")),
                        "rating": self._coerce_rating(raw.get("rating")),
                        "review_count": self._coerce_int(raw.get("review_count")),
                        "is_sponsored": bool(raw.get("is_sponsored")),
                    }
                )
            return self.validate_payload(
                target_type,
                {
                    "query": query,
                    "products": products,
                    "page": page,
                },
            )

        if target_type == "product-detail":
            # ASIN fallback: extract from URL pattern /dp/XXXXXXXXXX/
            asin_from_url = ""
            asin_match = re.search(r"/dp/([A-Z0-9]{10})", target_url, re.IGNORECASE)
            if asin_match:
                asin_from_url = asin_match.group(1).upper()

            review_count_raw = structured.get("review_count")
            payload = {
                "title": self._as_string(structured.get("title"))
                or self._as_string(main_content.get("title"))
                or self._as_string(navigation.get("title")),
                "asin": self._as_string(structured.get("asin")) or asin_from_url,
                "product_url": self._as_string(structured.get("product_url")) or target_url,
                "price": self._as_string(structured.get("price")),
                "rating": self._coerce_rating(structured.get("rating")),
                "review_count": self._coerce_int(review_count_raw),
                "availability": self._as_string(structured.get("availability")),
                "brand": self._as_string(structured.get("brand")),
                "features": self._as_string_list(structured.get("features")),
            }
            return self.validate_payload(target_type, payload)

        if target_type == "product-reviews":
            # ASIN fallback from URL
            asin_from_url = ""
            asin_match = re.search(r"/dp/([A-Z0-9]{10})|product-reviews/([A-Z0-9]{10})", target_url, re.IGNORECASE)
            if asin_match:
                asin_from_url = (asin_match.group(1) or asin_match.group(2) or "").upper()

            reviews: list[dict[str, object]] = []
            for raw in structured.get("reviews", []):
                if not isinstance(raw, dict):
                    continue
                reviews.append(
                    {
                        "reviewer_name": self._as_string(raw.get("reviewer_name")),
                        "rating": self._coerce_rating(raw.get("rating")),
                        "title": self._as_string(raw.get("title")),
                        "body": self._as_string(raw.get("body")),
                        "verified_purchase": bool(raw.get("verified_purchase")),
                        "date": self._as_string(raw.get("date")),
                    }
                )
            payload = {
                "asin": self._as_string(structured.get("asin")) or asin_from_url,
                "reviews": reviews,
                "overall_rating": self._coerce_rating(structured.get("overall_rating")),
                "total_reviews": self._as_string(structured.get("total_reviews")),
            }
            return self.validate_payload(target_type, payload)

        # seller-profile
        payload = {
            "seller_name": self._as_string(structured.get("seller_name"))
            or self._as_string(main_content.get("title"))
            or self._as_string(navigation.get("title")),
            "seller_url": self._as_string(structured.get("seller_url")) or target_url,
            "rating": self._coerce_rating(structured.get("rating")),
            "feedback_count": self._as_string(structured.get("feedback_count")),
            "positive_feedback_pct": self._as_string(structured.get("positive_feedback_pct")),
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

    @staticmethod
    def _coerce_int(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        raw = value if isinstance(value, str) else str(value or "")
        cleaned = raw.replace(",", "")
        m = re.search(r"([0-9]+)", cleaned)
        try:
            return int(m.group(1)) if m else 0
        except (AttributeError, ValueError):
            return 0
