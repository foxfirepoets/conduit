"""
tests/test_web_search.py

Tests for WebSearchTool multi-engine search.
DDG API tests use real HTTP (no browser). Other engine tests are structural
(verify they return correct types when no API key configured).
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import uuid
from pathlib import Path

import pytest

CONDUIT_ROOT = Path(__file__).parent.parent


def _load_web_search_mod():
    """Load web_search.py directly (not via cato package shim)."""
    mod_name = "web_search_test_mod"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name,
        str(CONDUIT_ROOT / "tools" / "web_search.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Register BEFORE exec so @dataclass can resolve cls.__module__ via sys.modules
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _bootstrap(tmp_db: Path) -> None:
    import importlib.util as ilu
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)
    if "cato.platform" not in sys.modules:
        platform_mod = types.ModuleType("cato.platform")
        platform_mod.get_data_dir = lambda: tmp_db.parent
        sys.modules["cato.platform"] = platform_mod
        cato_pkg.platform = platform_mod
    if "cato.audit" not in sys.modules:
        spec = ilu.spec_from_file_location("cato.audit", str(CONDUIT_ROOT / "audit.py"), submodule_search_locations=[])
        assert spec and spec.loader
        mod = ilu.module_from_spec(spec)
        mod.__package__ = "cato"
        sys.modules["cato.audit"] = mod
        spec.loader.exec_module(mod)
        cato_pkg.audit = mod
    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules.setdefault("cato.tools", tools_pkg)
    cato_pkg.tools = tools_pkg
    for mod_name, file_name in [
        ("cato.tools.browser", "browser.py"),
        ("cato.tools.conduit_bridge", "conduit_bridge.py"),
        ("cato.tools.conduit_crawl", "conduit_crawl.py"),
        ("cato.tools.conduit_monitor", "conduit_monitor.py"),
        ("cato.tools.conduit_proof", "conduit_proof.py"),
    ]:
        if mod_name not in sys.modules:
            spec = ilu.spec_from_file_location(mod_name, str(CONDUIT_ROOT / "tools" / file_name), submodule_search_locations=[])
            assert spec and spec.loader
            mod = ilu.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("web_search") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def ws():
    """WebSearchTool instance."""
    mod = _load_web_search_mod()
    return mod.WebSearchTool()


@pytest.fixture(scope="module")
def ws_mod():
    return _load_web_search_mod()


class TestClassifyQuery:

    def test_code_query(self, ws_mod):
        assert ws_mod.classify_query("python error ImportError") == "code"

    def test_news_query(self, ws_mod):
        assert ws_mod.classify_query("latest news today") == "news"

    def test_academic_query(self, ws_mod):
        assert ws_mod.classify_query("arxiv paper on transformers") == "academic"

    def test_general_query(self, ws_mod):
        assert ws_mod.classify_query("best coffee shops in Seattle") == "general"

    def test_github_is_code(self, ws_mod):
        assert ws_mod.classify_query("github anthropic claude api") == "code"


class TestSearchResult:

    def test_search_result_dataclass(self, ws_mod):
        r = ws_mod.SearchResult(title="Test", url="https://example.com", snippet="A snippet", source_engine="ddg_api", rank=0)
        assert r.title == "Test"
        assert r.url == "https://example.com"
        assert r.confidence == 0.0

    def test_heuristic_confidence_edu_bonus(self, ws_mod):
        r = ws_mod.SearchResult(title="MIT", url="https://mit.edu/paper", snippet="research paper", source_engine="ddg_api", rank=0)
        score = ws_mod._heuristic_confidence("research paper", r)
        assert score > 0.5, f"EDU domain should get confidence bonus: {score}"

    def test_heuristic_confidence_rank_decay(self, ws_mod):
        r0 = ws_mod.SearchResult(title="First", url="https://example.com", snippet="", source_engine="ddg_api", rank=0)
        r5 = ws_mod.SearchResult(title="Sixth", url="https://example.com", snippet="", source_engine="ddg_api", rank=5)
        s0 = ws_mod._heuristic_confidence("test", r0)
        s5 = ws_mod._heuristic_confidence("test", r5)
        assert s0 > s5, "Higher rank should have higher confidence"


class TestDDGApi:

    def test_ddg_api_returns_list(self, ws):
        """DDG API returns a list (may be empty on network issues)."""
        results = ws._search_ddg_api("python programming")
        assert isinstance(results, list), f"Expected list, got: {type(results)}"

    def test_ddg_api_results_have_url(self, ws):
        results = ws._search_ddg_api("python programming language")
        for r in results:
            assert r.url.startswith("http"), f"Result URL invalid: {r.url!r}"
            assert r.source_engine == "ddg_api"

    def test_ddg_api_no_crash_on_nonsense_query(self, ws):
        """Even a nonsense query should not crash."""
        results = ws._search_ddg_api("xyzzy_totally_nonexistent_query_12345abcdef")
        assert isinstance(results, list)


class TestNoKeyProviders:

    def test_brave_returns_empty_without_key(self, ws):
        import os
        saved = os.environ.pop("BRAVE_API_KEY", None)
        try:
            results = ws._search_brave("test query")
            assert results == [], f"Brave without key should return []: {results}"
        finally:
            if saved:
                os.environ["BRAVE_API_KEY"] = saved

    def test_exa_returns_empty_without_key(self, ws):
        import os
        saved = os.environ.pop("EXA_API_KEY", None)
        try:
            results = ws._search_exa("test query")
            assert results == [], f"Exa without key should return []: {results}"
        finally:
            if saved:
                os.environ["EXA_API_KEY"] = saved

    def test_tavily_returns_empty_without_key(self, ws):
        import os
        saved = os.environ.pop("TAVILY_API_KEY", None)
        try:
            results = ws._search_tavily("test query")
            assert results == [], f"Tavily without key should return []: {results}"
        finally:
            if saved:
                os.environ["TAVILY_API_KEY"] = saved


class TestSearchFallbackChain:

    def test_search_returns_list(self, ws):
        results = ws.search("python programming")
        assert isinstance(results, list)

    def test_search_results_sorted_by_confidence(self, ws):
        results = ws.search("python programming tutorial")
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i+1].confidence, (
                    f"Results not sorted by confidence at index {i}"
                )

    def test_search_async_works(self, ws):
        results = asyncio.get_event_loop().run_until_complete(
            ws.search_async("test query")
        )
        assert isinstance(results, list)


class TestAcademicSearch:

    def test_arxiv_returns_list(self, ws):
        """arXiv API returns a list (may be empty on network issues)."""
        results = ws._search_arxiv("transformer attention mechanism")
        assert isinstance(results, list)

    def test_arxiv_results_have_required_fields(self, ws):
        results = ws._search_arxiv("neural network")
        for r in results:
            assert r.source_engine == "arxiv"
            assert r.url.startswith("http"), f"arXiv URL invalid: {r.url!r}"
            assert isinstance(r.title, str)

    def test_semantic_scholar_returns_list(self, ws):
        results = ws._search_semantic_scholar("attention is all you need")
        assert isinstance(results, list)

    def test_semantic_scholar_source_engine(self, ws):
        results = ws._search_semantic_scholar("deep learning")
        for r in results:
            assert r.source_engine == "semantic_scholar"

    def test_pubmed_returns_list(self, ws):
        results = ws._search_pubmed("COVID-19 vaccine efficacy")
        assert isinstance(results, list)

    def test_pubmed_urls_point_to_pubmed(self, ws):
        results = ws._search_pubmed("cancer immunotherapy")
        for r in results:
            assert "pubmed.ncbi.nlm.nih.gov" in r.url, f"PubMed URL wrong: {r.url!r}"

    def test_classify_query_arxiv_trigger(self, ws_mod):
        assert ws_mod.classify_query("arxiv paper on BERT") == "academic"

    def test_classify_query_pubmed_trigger(self, ws_mod):
        assert ws_mod.classify_query("pubmed systematic review diabetes") == "academic"

    def test_academic_chain_used_for_academic_query(self, ws):
        """Academic query type routes through academic chain."""
        results = ws.search("arxiv transformer neural network", query_type="academic")
        assert isinstance(results, list)
        # If any results came back, they should be from academic sources
        for r in results:
            assert r.source_engine in ("arxiv", "semantic_scholar", "pubmed", "exa", "ddg_api", "brave")
