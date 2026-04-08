"""Comprehensive tests for the 7 Conduit marketplace adapters.

Covers: instantiation, list_targets, selector_map, extraction_script,
normalize_url, scroll_iterations, transform_extraction, validate_payload,
service registration, and build_plan integration.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Package shim — lets relative imports inside tools/marketplaces/* resolve
# ---------------------------------------------------------------------------
CONDUIT_ROOT = Path(__file__).parent.parent
if "cato" not in sys.modules:
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    sys.modules["cato"] = cato_pkg

# ---------------------------------------------------------------------------
# Adapter imports
# ---------------------------------------------------------------------------
from cato.tools.marketplaces.linkedin import LinkedInAdapter
from cato.tools.marketplaces.amazon import AmazonAdapter
from cato.tools.marketplaces.google_search import GoogleSearchAdapter
from cato.tools.marketplaces.github import GitHubAdapter
from cato.tools.marketplaces.reddit import RedditAdapter
from cato.tools.marketplaces.hackernews import HackerNewsAdapter
from cato.tools.marketplaces.news import NewsAdapter
from cato.tools.marketplaces.base import MarketplaceAdapter, TargetDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_EMPTY_MAIN: dict = {"title": "", "text": ""}
_EMPTY_NAV: dict = {"title": ""}

ALL_ADAPTERS = [
    LinkedInAdapter(),
    AmazonAdapter(),
    GoogleSearchAdapter(),
    GitHubAdapter(),
    RedditAdapter(),
    HackerNewsAdapter(),
    NewsAdapter(),
]

ALL_ADAPTER_IDS = [a.slug for a in ALL_ADAPTERS]


# ===========================================================================
# 1. Adapter instantiation
# ===========================================================================

def test_linkedin_adapter_instantiates():
    adapter = LinkedInAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


def test_amazon_adapter_instantiates():
    adapter = AmazonAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


def test_google_search_adapter_instantiates():
    adapter = GoogleSearchAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


def test_github_adapter_instantiates():
    adapter = GitHubAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


def test_reddit_adapter_instantiates():
    adapter = RedditAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


def test_hackernews_adapter_instantiates():
    adapter = HackerNewsAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


def test_news_adapter_instantiates():
    adapter = NewsAdapter()
    assert isinstance(adapter.slug, str) and adapter.slug
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.schema_version, str) and adapter.schema_version
    assert isinstance(adapter.target_definitions, tuple) and len(adapter.target_definitions) > 0


# ===========================================================================
# 2. list_targets() returns valid structure
# ===========================================================================

@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=ALL_ADAPTER_IDS)
def test_list_targets_returns_valid_structure(adapter):
    targets = adapter.list_targets()
    assert isinstance(targets, list)
    assert len(targets) > 0
    for target in targets:
        assert isinstance(target, dict)
        for key in ("key", "label", "description", "login_required", "output_schema"):
            assert key in target, f"Missing key {key!r} in target {target}"
        schema = target["output_schema"]
        assert "required" in schema, f"output_schema missing 'required' for target {target['key']}"
        assert "properties" in schema, f"output_schema missing 'properties' for target {target['key']}"


# ===========================================================================
# 3. selector_map() coverage — parametrized by adapter + target_type
# ===========================================================================

def _adapter_target_pairs():
    """Yield (adapter, target_type) for all adapters and all their targets."""
    pairs = []
    for adapter in ALL_ADAPTERS:
        for td in adapter.target_definitions:
            pairs.append(pytest.param(adapter, td.key, id=f"{adapter.slug}/{td.key}"))
    return pairs


@pytest.mark.parametrize("adapter,target_type", _adapter_target_pairs())
def test_selector_map_structure(adapter, target_type):
    smap = adapter.selector_map(target_type)
    assert isinstance(smap, dict), f"{adapter.slug}/{target_type}: selector_map should return dict"
    assert "primary" in smap, f"{adapter.slug}/{target_type}: selector_map missing 'primary'"
    assert isinstance(smap["primary"], list) and len(smap["primary"]) > 0, (
        f"{adapter.slug}/{target_type}: 'primary' should be a non-empty list"
    )
    assert "fallback" in smap, f"{adapter.slug}/{target_type}: selector_map missing 'fallback'"
    assert isinstance(smap["fallback"], list), (
        f"{adapter.slug}/{target_type}: 'fallback' should be a list"
    )


# ===========================================================================
# 4. extraction_script() returns valid JS
# ===========================================================================

@pytest.mark.parametrize("adapter,target_type", _adapter_target_pairs())
def test_extraction_script_is_valid_js(adapter, target_type):
    script = adapter.extraction_script(target_type)
    assert isinstance(script, str) and len(script) > 0, (
        f"{adapter.slug}/{target_type}: extraction_script should return a non-empty string"
    )
    assert "() =>" in script, (
        f"{adapter.slug}/{target_type}: extraction_script should contain an arrow function '() =>'"
    )
    assert "return" in script, (
        f"{adapter.slug}/{target_type}: extraction_script should contain a 'return' statement"
    )
    # Sanity: no bare "= undefined" literal assignments
    assert "= undefined" not in script, (
        f"{adapter.slug}/{target_type}: extraction_script contains bare '= undefined' assignment"
    )


# ===========================================================================
# 5. normalize_url() validation — adapters with domain restriction
# ===========================================================================

def test_linkedin_normalize_url_valid():
    adapter = LinkedInAdapter()
    # Should not raise
    result = adapter.normalize_url("https://www.linkedin.com/search/results/people/?keywords=engineer")
    assert "linkedin.com" in result


def test_linkedin_normalize_url_wrong_domain():
    adapter = LinkedInAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("https://www.example.com/profile")


def test_linkedin_normalize_url_empty():
    adapter = LinkedInAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


def test_amazon_normalize_url_valid():
    adapter = AmazonAdapter()
    result = adapter.normalize_url("https://www.amazon.com/s?k=laptop")
    assert "amazon." in result


def test_amazon_normalize_url_wrong_domain():
    adapter = AmazonAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("https://www.ebay.com/sch/i.html?_nkw=laptop")


def test_amazon_normalize_url_empty():
    adapter = AmazonAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


def test_google_search_normalize_url_valid():
    adapter = GoogleSearchAdapter()
    result = adapter.normalize_url("https://www.google.com/search?q=python")
    assert "google." in result


def test_google_search_normalize_url_wrong_domain():
    adapter = GoogleSearchAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("https://www.bing.com/search?q=python")


def test_google_search_normalize_url_empty():
    adapter = GoogleSearchAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


def test_github_normalize_url_valid():
    adapter = GitHubAdapter()
    result = adapter.normalize_url("https://github.com/torvalds/linux")
    assert "github.com" in result


def test_github_normalize_url_wrong_domain():
    adapter = GitHubAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("https://gitlab.com/torvalds/linux")


def test_github_normalize_url_empty():
    adapter = GitHubAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


def test_reddit_normalize_url_valid():
    adapter = RedditAdapter()
    result = adapter.normalize_url("https://www.reddit.com/r/python/")
    assert "reddit.com" in result


def test_reddit_normalize_url_wrong_domain():
    adapter = RedditAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("https://www.lemmy.world/c/python")


def test_reddit_normalize_url_empty():
    adapter = RedditAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


def test_hackernews_normalize_url_valid():
    adapter = HackerNewsAdapter()
    result = adapter.normalize_url("https://news.ycombinator.com/")
    assert "ycombinator.com" in result


def test_hackernews_normalize_url_wrong_domain():
    adapter = HackerNewsAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("https://www.lobste.rs/")


def test_hackernews_normalize_url_empty():
    adapter = HackerNewsAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


# News adapter accepts any URL — just test empty raises
def test_news_normalize_url_any_domain_accepted():
    adapter = NewsAdapter()
    result = adapter.normalize_url("https://techcrunch.com/2025/01/01/test-article")
    assert result  # non-empty


def test_news_normalize_url_empty():
    adapter = NewsAdapter()
    with pytest.raises(ValueError):
        adapter.normalize_url("")


# ===========================================================================
# 6. scroll_iterations() — returns non-negative int; feed/search > 0 where overridden
# ===========================================================================

@pytest.mark.parametrize("adapter,target_type", _adapter_target_pairs())
def test_scroll_iterations_non_negative(adapter, target_type):
    result = adapter.scroll_iterations(target_type)
    assert isinstance(result, int), (
        f"{adapter.slug}/{target_type}: scroll_iterations should return int"
    )
    assert result >= 0, (
        f"{adapter.slug}/{target_type}: scroll_iterations should be >= 0"
    )


def test_linkedin_search_targets_return_nonzero_scroll():
    adapter = LinkedInAdapter()
    assert adapter.scroll_iterations("people-search") > 0
    assert adapter.scroll_iterations("job-search") > 0


def test_amazon_search_targets_return_nonzero_scroll():
    adapter = AmazonAdapter()
    assert adapter.scroll_iterations("product-search") > 0
    assert adapter.scroll_iterations("product-reviews") > 0


def test_google_search_all_targets_return_nonzero_scroll():
    adapter = GoogleSearchAdapter()
    for td in adapter.target_definitions:
        assert adapter.scroll_iterations(td.key) > 0, (
            f"GoogleSearchAdapter/{td.key} should have scroll_iterations > 0"
        )


def test_reddit_feed_and_search_return_nonzero_scroll():
    adapter = RedditAdapter()
    assert adapter.scroll_iterations("subreddit-feed") > 0
    assert adapter.scroll_iterations("search-results") > 0


def test_hackernews_always_returns_zero_scroll():
    adapter = HackerNewsAdapter()
    for td in adapter.target_definitions:
        assert adapter.scroll_iterations(td.key) == 0, (
            f"HackerNewsAdapter/{td.key} should always return 0 scroll iterations"
        )


def test_news_homepage_returns_nonzero_scroll():
    adapter = NewsAdapter()
    assert adapter.scroll_iterations("homepage") > 0


# ===========================================================================
# 7. transform_extraction() with minimal valid payload
# ===========================================================================

def test_linkedin_people_search_transform():
    adapter = LinkedInAdapter()
    result = adapter.transform_extraction(
        target_type="people-search",
        target_url="https://www.linkedin.com/search/results/people/?keywords=python+developer",
        structured_payload={"query": "python developer", "people": []},
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert "query" in result
    assert "people" in result
    assert result.get("schema_version") == "linkedin.v1"
    assert result.get("record_type") == "linkedin.people-search"


def test_linkedin_person_profile_transform():
    adapter = LinkedInAdapter()
    result = adapter.transform_extraction(
        target_type="person-profile",
        target_url="https://www.linkedin.com/in/janesmith",
        structured_payload={
            "name": "Jane Smith",
            "profile_url": "https://www.linkedin.com/in/janesmith",
        },
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert result["name"] == "Jane Smith"
    assert "profile_url" in result
    assert result.get("schema_version") == "linkedin.v1"
    assert result.get("record_type") == "linkedin.person-profile"


def test_amazon_product_search_transform():
    adapter = AmazonAdapter()
    result = adapter.transform_extraction(
        target_type="product-search",
        target_url="https://www.amazon.com/s?k=laptop",
        structured_payload={"query": "laptop", "products": []},
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert "query" in result
    assert "products" in result
    assert result.get("schema_version") == "amazon.v1"
    assert result.get("record_type") == "amazon.product-search"


def test_amazon_product_detail_transform():
    adapter = AmazonAdapter()
    result = adapter.transform_extraction(
        target_type="product-detail",
        target_url="https://www.amazon.com/dp/B01ABCDEFG/",
        structured_payload={
            "title": "Test Laptop",
            "asin": "B01ABCDEFG",
            "product_url": "https://www.amazon.com/dp/B01ABCDEFG/",
        },
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert result["title"] == "Test Laptop"
    assert result["asin"] == "B01ABCDEFG"
    assert "product_url" in result
    assert result.get("schema_version") == "amazon.v1"
    assert result.get("record_type") == "amazon.product-detail"


def test_google_search_web_search_transform():
    adapter = GoogleSearchAdapter()
    result = adapter.transform_extraction(
        target_type="web-search",
        target_url="https://www.google.com/search?q=python",
        structured_payload={"query": "python", "results": []},
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert result["query"] == "python"
    assert "results" in result
    assert result.get("schema_version") == "google_search.v1"
    assert result.get("record_type") == "google_search.web-search"


def test_github_repo_detail_transform():
    adapter = GitHubAdapter()
    result = adapter.transform_extraction(
        target_type="repo-detail",
        target_url="https://github.com/torvalds/linux",
        structured_payload={
            "owner": "torvalds",
            "repo_name": "linux",
            "repo_url": "https://github.com/torvalds/linux",
        },
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert result["owner"] == "torvalds"
    assert "repo_name" in result
    assert "repo_url" in result
    assert result.get("schema_version") == "github.v1"
    assert result.get("record_type") == "github.repo-detail"


def test_reddit_subreddit_feed_transform():
    adapter = RedditAdapter()
    result = adapter.transform_extraction(
        target_type="subreddit-feed",
        target_url="https://www.reddit.com/r/python/",
        structured_payload={"subreddit": "python", "posts": []},
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert "subreddit" in result
    assert "posts" in result
    assert result.get("schema_version") == "reddit.v1"
    assert result.get("record_type") == "reddit.subreddit-feed"


def test_hackernews_frontpage_transform():
    adapter = HackerNewsAdapter()
    result = adapter.transform_extraction(
        target_type="frontpage",
        target_url="https://news.ycombinator.com/",
        structured_payload={"stories": []},
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert "stories" in result
    assert result.get("schema_version") == "hackernews.v1"
    assert result.get("record_type") == "hackernews.frontpage"


def test_news_article_transform():
    adapter = NewsAdapter()
    result = adapter.transform_extraction(
        target_type="article",
        target_url="https://techcrunch.com/2025/01/01/test-article",
        structured_payload={
            "title": "Test Article",
            "article_url": "https://techcrunch.com/2025/01/01/test-article",
        },
        main_content=_EMPTY_MAIN,
        navigation=_EMPTY_NAV,
    )
    assert isinstance(result, dict)
    assert result["title"] == "Test Article"
    assert "article_url" in result
    assert result.get("schema_version") == "news.v1"
    assert result.get("record_type") == "news.article"


# ===========================================================================
# 8. Service integration — all 7 adapters registered
# ===========================================================================

def test_service_registers_all_seven_adapters(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    result = service.list_marketplaces()
    slugs = {item["slug"] for item in result["marketplaces"]}
    expected = {"amazon", "github", "google_search", "hackernews", "linkedin", "news", "reddit"}
    assert expected == slugs


def test_service_does_not_register_deprecated_adapters(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    result = service.list_marketplaces()
    slugs = {item["slug"] for item in result["marketplaces"]}
    assert "fiverr" not in slugs
    assert "upwork" not in slugs


# ===========================================================================
# 9. build_plan() integration per adapter
# ===========================================================================

def test_linkedin_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="linkedin",
        target_type="people-search",
        target_url="https://www.linkedin.com/search/results/people/?keywords=engineer",
    )
    assert plan["marketplace"] == "linkedin"
    assert plan["target_type"] == "people-search"
    assert "session" in plan


def test_amazon_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="amazon",
        target_type="product-search",
        target_url="https://www.amazon.com/s?k=laptop",
    )
    assert plan["marketplace"] == "amazon"
    assert plan["target_type"] == "product-search"
    assert "session" in plan


def test_google_search_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="google_search",
        target_type="web-search",
        target_url="https://www.google.com/search?q=python",
    )
    assert plan["marketplace"] == "google_search"
    assert plan["target_type"] == "web-search"
    assert "session" in plan


def test_github_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="github",
        target_type="repo-detail",
        target_url="https://github.com/torvalds/linux",
    )
    assert plan["marketplace"] == "github"
    assert plan["target_type"] == "repo-detail"
    assert "session" in plan


def test_reddit_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="reddit",
        target_type="subreddit-feed",
        target_url="https://www.reddit.com/r/python/",
    )
    assert plan["marketplace"] == "reddit"
    assert plan["target_type"] == "subreddit-feed"
    assert "session" in plan


def test_hackernews_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="hackernews",
        target_type="frontpage",
        target_url="https://news.ycombinator.com/",
    )
    assert plan["marketplace"] == "hackernews"
    assert plan["target_type"] == "frontpage"
    assert "session" in plan


def test_news_build_plan(tmp_path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="news",
        target_type="article",
        target_url="https://techcrunch.com/2025/01/01/test-article",
    )
    assert plan["marketplace"] == "news"
    assert plan["target_type"] == "article"
    assert "session" in plan


# ===========================================================================
# 10. validate_payload() — accepts valid, rejects invalid (missing required field)
# ===========================================================================

# --- LinkedIn ---

def test_linkedin_validate_payload_people_search_valid():
    adapter = LinkedInAdapter()
    payload = {"query": "python developer", "people": []}
    result = adapter.validate_payload("people-search", payload)
    assert result["query"] == "python developer"
    assert result["schema_version"] == "linkedin.v1"


def test_linkedin_validate_payload_people_search_missing_required():
    adapter = LinkedInAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("people-search", {"query": "python developer"})  # missing 'people'


def test_linkedin_validate_payload_person_profile_valid():
    adapter = LinkedInAdapter()
    payload = {"name": "Jane Smith", "profile_url": "https://www.linkedin.com/in/janesmith"}
    result = adapter.validate_payload("person-profile", payload)
    assert result["name"] == "Jane Smith"
    assert result["record_type"] == "linkedin.person-profile"


def test_linkedin_validate_payload_person_profile_missing_required():
    adapter = LinkedInAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("person-profile", {"name": "Jane Smith"})  # missing 'profile_url'


# --- Amazon ---

def test_amazon_validate_payload_product_search_valid():
    adapter = AmazonAdapter()
    payload = {"query": "laptop", "products": []}
    result = adapter.validate_payload("product-search", payload)
    assert result["query"] == "laptop"
    assert result["record_type"] == "amazon.product-search"


def test_amazon_validate_payload_product_search_missing_required():
    adapter = AmazonAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("product-search", {"query": "laptop"})  # missing 'products'


def test_amazon_validate_payload_product_detail_valid():
    adapter = AmazonAdapter()
    payload = {
        "title": "Test Laptop",
        "asin": "B01ABCDEFG",
        "product_url": "https://www.amazon.com/dp/B01ABCDEFG/",
    }
    result = adapter.validate_payload("product-detail", payload)
    assert result["asin"] == "B01ABCDEFG"
    assert result["record_type"] == "amazon.product-detail"


def test_amazon_validate_payload_product_detail_missing_required():
    adapter = AmazonAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("product-detail", {"title": "Test Laptop", "asin": "B01ABCDEFG"})  # missing 'product_url'


# --- Google Search ---

def test_google_search_validate_payload_web_search_valid():
    adapter = GoogleSearchAdapter()
    payload = {"query": "python", "results": []}
    result = adapter.validate_payload("web-search", payload)
    assert result["query"] == "python"
    assert result["record_type"] == "google_search.web-search"


def test_google_search_validate_payload_web_search_missing_required():
    adapter = GoogleSearchAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("web-search", {"query": "python"})  # missing 'results'


def test_google_search_validate_payload_news_search_valid():
    adapter = GoogleSearchAdapter()
    payload = {"query": "ai news", "articles": []}
    result = adapter.validate_payload("news-search", payload)
    assert result["query"] == "ai news"
    assert result["record_type"] == "google_search.news-search"


def test_google_search_validate_payload_news_search_missing_required():
    adapter = GoogleSearchAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("news-search", {"query": "ai news"})  # missing 'articles'


# --- GitHub ---

def test_github_validate_payload_repo_detail_valid():
    adapter = GitHubAdapter()
    payload = {
        "owner": "torvalds",
        "repo_name": "linux",
        "repo_url": "https://github.com/torvalds/linux",
    }
    result = adapter.validate_payload("repo-detail", payload)
    assert result["owner"] == "torvalds"
    assert result["record_type"] == "github.repo-detail"


def test_github_validate_payload_repo_detail_missing_required():
    adapter = GitHubAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("repo-detail", {"owner": "torvalds", "repo_name": "linux"})  # missing 'repo_url'


def test_github_validate_payload_repo_search_valid():
    adapter = GitHubAdapter()
    payload = {"query": "python web framework", "repos": []}
    result = adapter.validate_payload("repo-search", payload)
    assert result["record_type"] == "github.repo-search"


def test_github_validate_payload_repo_search_missing_required():
    adapter = GitHubAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("repo-search", {"query": "python web framework"})  # missing 'repos'


# --- Reddit ---

def test_reddit_validate_payload_subreddit_feed_valid():
    adapter = RedditAdapter()
    payload = {"subreddit": "python", "posts": []}
    result = adapter.validate_payload("subreddit-feed", payload)
    assert result["subreddit"] == "python"
    assert result["record_type"] == "reddit.subreddit-feed"


def test_reddit_validate_payload_subreddit_feed_missing_required():
    adapter = RedditAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("subreddit-feed", {"subreddit": "python"})  # missing 'posts'


def test_reddit_validate_payload_post_detail_valid():
    adapter = RedditAdapter()
    payload = {
        "title": "Python 3.14 released",
        "post_url": "https://www.reddit.com/r/python/comments/abc123/python_314_released/",
    }
    result = adapter.validate_payload("post-detail", payload)
    assert result["title"] == "Python 3.14 released"
    assert result["record_type"] == "reddit.post-detail"


def test_reddit_validate_payload_post_detail_missing_required():
    adapter = RedditAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("post-detail", {"title": "Python 3.14 released"})  # missing 'post_url'


# --- HackerNews ---

def test_hackernews_validate_payload_frontpage_valid():
    adapter = HackerNewsAdapter()
    payload = {"stories": []}
    result = adapter.validate_payload("frontpage", payload)
    assert "stories" in result
    assert result["record_type"] == "hackernews.frontpage"


def test_hackernews_validate_payload_frontpage_missing_required():
    adapter = HackerNewsAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("frontpage", {})  # missing 'stories'


def test_hackernews_validate_payload_story_detail_valid():
    adapter = HackerNewsAdapter()
    payload = {
        "title": "Show HN: My new tool",
        "story_url": "https://example.com/tool",
    }
    result = adapter.validate_payload("story-detail", payload)
    assert result["title"] == "Show HN: My new tool"
    assert result["record_type"] == "hackernews.story-detail"


def test_hackernews_validate_payload_story_detail_missing_required():
    adapter = HackerNewsAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("story-detail", {"title": "Show HN: My new tool"})  # missing 'story_url'


# --- News ---

def test_news_validate_payload_article_valid():
    adapter = NewsAdapter()
    payload = {
        "title": "Test Article",
        "article_url": "https://example.com/article",
    }
    result = adapter.validate_payload("article", payload)
    assert result["title"] == "Test Article"
    assert result["record_type"] == "news.article"


def test_news_validate_payload_article_missing_required():
    adapter = NewsAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("article", {"title": "Test Article"})  # missing 'article_url'


def test_news_validate_payload_homepage_valid():
    adapter = NewsAdapter()
    payload = {"articles": []}
    result = adapter.validate_payload("homepage", payload)
    assert "articles" in result
    assert result["record_type"] == "news.homepage"


def test_news_validate_payload_homepage_missing_required():
    adapter = NewsAdapter()
    with pytest.raises(ValueError):
        adapter.validate_payload("homepage", {})  # missing 'articles'


# ===========================================================================
# Bonus: get_target() raises ValueError for unknown target_type
# ===========================================================================

@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=ALL_ADAPTER_IDS)
def test_get_target_raises_for_unknown_type(adapter):
    with pytest.raises(ValueError):
        adapter.get_target("nonexistent-target-type-xyz")


# ===========================================================================
# Bonus: All target_definitions have TargetDefinition type
# ===========================================================================

@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=ALL_ADAPTER_IDS)
def test_target_definitions_are_target_definition_instances(adapter):
    for td in adapter.target_definitions:
        assert isinstance(td, TargetDefinition), (
            f"{adapter.slug}: expected TargetDefinition, got {type(td)}"
        )
        assert isinstance(td.key, str) and td.key
        assert isinstance(td.label, str) and td.label
        assert isinstance(td.description, str) and td.description
        assert isinstance(td.login_required, bool)
        assert isinstance(td.output_schema, dict)


# ===========================================================================
# Bonus: All adapters are subclasses of MarketplaceAdapter
# ===========================================================================

@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=ALL_ADAPTER_IDS)
def test_all_adapters_subclass_marketplace_adapter(adapter):
    assert isinstance(adapter, MarketplaceAdapter)


# ===========================================================================
# Bonus: schema_version is set on validated payloads
# ===========================================================================

@pytest.mark.parametrize("adapter,target_type", _adapter_target_pairs())
def test_validate_payload_sets_schema_version(adapter, target_type):
    """validate_payload always stamps schema_version onto the result."""
    td = adapter.get_target(target_type)
    # Build minimal payload satisfying required fields
    required = td.output_schema.get("required", [])
    props = td.output_schema.get("properties", {})
    minimal: dict = {}
    for key in required:
        prop_type = props.get(key, {}).get("type", "string")
        if prop_type == "string":
            minimal[key] = "test"
        elif prop_type == "array":
            minimal[key] = []
        elif prop_type == "integer":
            minimal[key] = 0
        elif prop_type == "number":
            minimal[key] = 0.0
        elif prop_type == "boolean":
            minimal[key] = False
        elif prop_type == "object":
            minimal[key] = {}
        else:
            minimal[key] = "test"

    result = adapter.validate_payload(target_type, minimal)
    assert "schema_version" in result, (
        f"{adapter.slug}/{target_type}: validate_payload should set 'schema_version'"
    )
    assert "record_type" in result, (
        f"{adapter.slug}/{target_type}: validate_payload should set 'record_type'"
    )
    assert result["record_type"] == f"{adapter.slug}.{target_type}", (
        f"{adapter.slug}/{target_type}: record_type should be '{adapter.slug}.{target_type}'"
    )
