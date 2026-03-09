"""
tools/web_search.py — Multi-engine web search for Conduit.

Replaces the fragile DuckDuckGo browser scrape with a proper API-based
fallback chain. Zero new pip dependencies — uses stdlib urllib + aiohttp
if available, otherwise falls back to urllib.

Engine priority by query type:
  code    → [exa, brave, ddg_api]
  news    → [tavily, brave, ddg_api]
  academic→ [semantic_scholar, arxiv, exa]
  general → [brave, ddg_api]

API keys sourced from env vars (all optional — unauthenticated DDG is always last resort).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Literal, Optional

logger = logging.getLogger(__name__)

QueryType = Literal["code", "news", "academic", "general"]


@dataclass
class SearchResult:
    """A single search result from any engine."""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source_engine: str = ""
    confidence: float = 0.0
    rank: int = 0
    published_date: str = ""


def classify_query(query: str) -> QueryType:
    """Classify a query into a type for engine routing."""
    q = query.lower()
    code_signals = ("github", "stackoverflow", "docs", "api ", "function", "library",
                    "error", "bug", "exception", "import", "pip ", "npm ", "pypi",
                    "class ", "def ", "async ", "await ")
    academic_signals = ("arxiv", "paper", "doi:", "cite", "journal", "study",
                        "et al", "meta-analysis", "systematic review", "literature review",
                        "peer-reviewed", "abstract", "preprint", "pubmed", "semantic scholar",
                        "research paper", "published in", "acm ", "ieee ", "springer",
                        "nature ", "science ", "cell ", "nejm", "lancet")
    news_signals = ("today", "latest", "breaking", "announced", "just released",
                    "this week", "yesterday", "hours ago", "update:")
    if any(s in q for s in academic_signals):
        return "academic"
    if any(s in q for s in news_signals):
        return "news"
    if any(s in q for s in code_signals):
        return "code"
    return "general"


def _heuristic_confidence(query: str, result: SearchResult) -> float:
    """Score a result by rank, domain authority, and query-term overlap."""
    score = 1.0 / (1 + result.rank)
    url_lower = result.url.lower()
    if any(url_lower.endswith(tld) or f".{tld}/" in url_lower for tld in (".edu", ".gov")):
        score += 0.15
    elif ".org" in url_lower:
        score += 0.10
    # Query term overlap in title + snippet
    terms = query.lower().split()
    combined = (result.title + " " + result.snippet).lower()
    overlap = sum(1 for t in terms if t in combined) / max(len(terms), 1)
    score += overlap * 0.20
    return min(1.0, score)


def _http_get(url: str, headers: dict = None, timeout: int = 10) -> Optional[dict]:
    """Synchronous HTTP GET returning parsed JSON or None on failure."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 429:
                return {"_rate_limited": True}
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"_rate_limited": True}
        logger.debug("HTTP %d for %s", e.code, url)
        return None
    except Exception as exc:
        logger.debug("Request failed for %s: %s", url, exc)
        return None


class WebSearchTool:
    """
    Multi-engine search with fallback chain and rate-limit tracking.
    All search methods are sync (called via asyncio.to_thread or directly).
    """

    def __init__(self) -> None:
        # provider -> timestamp when rate limit expires
        self._rate_limited: dict[str, float] = {}

    def _is_rate_limited(self, provider: str) -> bool:
        expiry = self._rate_limited.get(provider, 0)
        return time.time() < expiry

    def _mark_rate_limited(self, provider: str, seconds: int = 60) -> None:
        self._rate_limited[provider] = time.time() + seconds
        logger.warning("Provider %s rate-limited for %ds", provider, seconds)

    # ------------------------------------------------------------------
    # DDG Instant Answer API (no key, no browser)
    # ------------------------------------------------------------------

    def _search_ddg_api(self, query: str) -> list[SearchResult]:
        """DuckDuckGo Instant Answer JSON API — no API key, no browser."""
        if self._is_rate_limited("ddg_api"):
            return []
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        data = _http_get(url, headers={"User-Agent": "Conduit/1.0"})
        if data is None:
            return []
        if data.get("_rate_limited"):
            self._mark_rate_limited("ddg_api")
            return []
        results = []
        # RelatedTopics contains the actual results
        for i, item in enumerate(data.get("RelatedTopics", [])[:10]):
            if isinstance(item, dict) and item.get("FirstURL") and item.get("Text"):
                results.append(SearchResult(
                    title=item.get("Text", "")[:100],
                    url=item["FirstURL"],
                    snippet=item.get("Text", ""),
                    source_engine="ddg_api",
                    rank=i,
                ))
        # Also include AbstractURL if present
        if data.get("AbstractURL") and data.get("Abstract"):
            results.insert(0, SearchResult(
                title=data.get("Heading", query),
                url=data["AbstractURL"],
                snippet=data["Abstract"],
                source_engine="ddg_api",
                rank=0,
            ))
        return results

    # ------------------------------------------------------------------
    # Brave Search API
    # ------------------------------------------------------------------

    def _search_brave(self, query: str) -> list[SearchResult]:
        """Brave Search API. Key from BRAVE_API_KEY env var."""
        if self._is_rate_limited("brave"):
            return []
        api_key = os.environ.get("BRAVE_API_KEY", "")
        if not api_key:
            return []
        url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count=10"
        data = _http_get(url, headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        })
        if data is None:
            return []
        if data.get("_rate_limited"):
            self._mark_rate_limited("brave")
            return []
        results = []
        for i, item in enumerate(data.get("web", {}).get("results", [])[:10]):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                source_engine="brave",
                rank=i,
                published_date=item.get("age", ""),
            ))
        return results

    # ------------------------------------------------------------------
    # Exa API
    # ------------------------------------------------------------------

    def _search_exa(self, query: str) -> list[SearchResult]:
        """Exa neural search. Key from EXA_API_KEY env var."""
        if self._is_rate_limited("exa"):
            return []
        api_key = os.environ.get("EXA_API_KEY", "")
        if not api_key:
            return []
        payload = json.dumps({
            "query": query,
            "numResults": 10,
            "useAutoprompt": True,
        }).encode()
        req = urllib.request.Request(
            "https://api.exa.ai/search",
            data=payload,
            headers={"Content-Type": "application/json", "x-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self._mark_rate_limited("exa")
            return []
        except Exception:
            return []
        results = []
        for i, item in enumerate(data.get("results", [])[:10]):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("text", "")[:300],
                source_engine="exa",
                rank=i,
                published_date=item.get("publishedDate", ""),
            ))
        return results

    # ------------------------------------------------------------------
    # Tavily API
    # ------------------------------------------------------------------

    def _search_tavily(self, query: str) -> list[SearchResult]:
        """Tavily search API. Key from TAVILY_API_KEY env var."""
        if self._is_rate_limited("tavily"):
            return []
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            return []
        payload = json.dumps({
            "api_key": api_key,
            "query": query,
            "max_results": 10,
        }).encode()
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self._mark_rate_limited("tavily")
            return []
        except Exception:
            return []
        results = []
        for i, item in enumerate(data.get("results", [])[:10]):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", "")[:300],
                source_engine="tavily",
                rank=i,
                published_date=item.get("published_date", ""),
            ))
        return results

    # ------------------------------------------------------------------
    # Academic search backends
    # ------------------------------------------------------------------

    def _search_arxiv(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """arXiv Atom API — no key required. Parses XML with stdlib xml.etree.ElementTree."""
        import xml.etree.ElementTree as ET
        if self._is_rate_limited("arxiv"):
            return []
        url = (
            f"https://export.arxiv.org/api/query"
            f"?search_query=all:{urllib.parse.quote(query)}"
            f"&max_results={max_results}&sortBy=relevance"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Conduit/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("arXiv request failed: %s", exc)
            return []

        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            logger.debug("arXiv XML parse failed: %s", exc)
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        results = []
        for i, entry in enumerate(root.findall("atom:entry", ns)[:max_results]):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            id_el = entry.find("atom:id", ns)
            published_el = entry.find("atom:published", ns)
            authors = [
                a.find("atom:name", ns).text or ""
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            ]
            pdf_link = ""
            for link in entry.findall("atom:link", ns):
                if link.get("type") == "application/pdf":
                    pdf_link = link.get("href", "")
                    break
            arxiv_id = (id_el.text or "").strip()
            if not pdf_link and arxiv_id:
                pdf_url_part = arxiv_id.replace("http://arxiv.org/abs/", "")
                pdf_link = f"https://arxiv.org/pdf/{pdf_url_part}"

            results.append(SearchResult(
                title=(title_el.text or "").strip().replace("\n", " "),
                url=arxiv_id or f"https://arxiv.org/search/?query={urllib.parse.quote(query)}",
                snippet=(summary_el.text or "").strip()[:400],
                source_engine="arxiv",
                rank=i,
                published_date=(published_el.text or "")[:10],
            ))
        return results

    def _search_semantic_scholar(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Semantic Scholar Graph API — free tier, no key required (100 req/5min)."""
        if self._is_rate_limited("semantic_scholar"):
            return []
        fields = "title,authors,year,citationCount,openAccessPdf,venue,externalIds"
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/search"
            f"?query={urllib.parse.quote(query)}&limit={max_results}&fields={fields}"
        )
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
        headers = {"User-Agent": "Conduit/1.0"}
        if api_key:
            headers["x-api-key"] = api_key

        data = _http_get(url, headers=headers, timeout=15)
        if data is None:
            return []
        if data.get("_rate_limited"):
            self._mark_rate_limited("semantic_scholar", seconds=120)
            return []

        results = []
        for i, paper in enumerate(data.get("data", [])[:max_results]):
            authors = [a.get("name", "") for a in paper.get("authors", [])[:5]]
            pdf_url = ""
            if paper.get("openAccessPdf"):
                pdf_url = paper["openAccessPdf"].get("url", "")
            doi = ""
            if paper.get("externalIds"):
                doi = paper["externalIds"].get("DOI", "")
            snippet_parts = []
            if authors:
                snippet_parts.append(f"Authors: {', '.join(authors)}")
            if paper.get("year"):
                snippet_parts.append(f"Year: {paper['year']}")
            if paper.get("citationCount") is not None:
                snippet_parts.append(f"Citations: {paper['citationCount']}")
            if paper.get("venue"):
                snippet_parts.append(f"Venue: {paper['venue']}")

            results.append(SearchResult(
                title=paper.get("title", ""),
                url=pdf_url or f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}",
                snippet=" | ".join(snippet_parts),
                source_engine="semantic_scholar",
                rank=i,
                published_date=str(paper.get("year", "")),
            ))
        return results

    def _search_pubmed(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """PubMed eUtils API — no key required, 3 req/sec."""
        if self._is_rate_limited("pubmed"):
            return []
        # Step 1: esearch to get PMIDs
        search_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&term={urllib.parse.quote(query)}&retmode=json&retmax={max_results}"
        )
        search_data = _http_get(search_url, headers={"User-Agent": "Conduit/1.0"}, timeout=15)
        if not search_data or search_data.get("_rate_limited"):
            if search_data and search_data.get("_rate_limited"):
                self._mark_rate_limited("pubmed", seconds=30)
            return []

        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        # Step 2: esummary to get titles
        ids_str = ",".join(pmids[:max_results])
        summary_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=json"
        )
        summary_data = _http_get(summary_url, headers={"User-Agent": "Conduit/1.0"}, timeout=15)
        if not summary_data:
            return []

        results = []
        result_map = summary_data.get("result", {})
        for i, pmid in enumerate(pmids[:max_results]):
            paper = result_map.get(pmid, {})
            if not paper or pmid == "uids":
                continue
            authors = [a.get("name", "") for a in paper.get("authors", [])[:3]]
            pub_date = paper.get("pubdate", "")[:10]
            results.append(SearchResult(
                title=paper.get("title", "").rstrip("."),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                snippet=f"Authors: {', '.join(authors)} | Journal: {paper.get('source', '')} | {pub_date}",
                source_engine="pubmed",
                rank=i,
                published_date=pub_date,
            ))
        return results

    # ------------------------------------------------------------------
    # Main search dispatcher
    # ------------------------------------------------------------------

    def search(self, query: str, query_type: QueryType = None) -> list[SearchResult]:
        """
        Execute search using ordered fallback chain for the query type.
        Returns list of SearchResult (may be empty if all providers fail).
        """
        if query_type is None:
            query_type = classify_query(query)

        chains = {
            "code":     [self._search_exa, self._search_brave, self._search_ddg_api],
            "news":     [self._search_tavily, self._search_brave, self._search_ddg_api],
            "academic": [self._search_semantic_scholar, self._search_arxiv, self._search_exa, self._search_ddg_api],
            "general":  [self._search_brave, self._search_ddg_api],
        }
        chain = chains.get(query_type, chains["general"])

        all_results: list[SearchResult] = []
        for provider_fn in chain:
            try:
                results = provider_fn(query)
                if results:
                    all_results.extend(results)
                    break  # First provider with results wins
            except Exception as exc:
                logger.debug("Provider %s failed: %s", provider_fn.__name__, exc)
                continue

        # Score and sort by confidence
        for r in all_results:
            r.confidence = _heuristic_confidence(query, r)
        all_results.sort(key=lambda r: r.confidence, reverse=True)
        return all_results[:10]

    async def search_async(self, query: str, query_type: QueryType = None) -> list[SearchResult]:
        """Async wrapper — runs sync search in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query, query_type)
