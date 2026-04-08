"""Marketplace adapters for specialized extraction products."""

from .amazon import AmazonAdapter
from .github import GitHubAdapter
from .google_search import GoogleSearchAdapter
from .hackernews import HackerNewsAdapter
from .linkedin import LinkedInAdapter
from .news import NewsAdapter
from .reddit import RedditAdapter

__all__ = [
    "AmazonAdapter",
    "GitHubAdapter",
    "GoogleSearchAdapter",
    "HackerNewsAdapter",
    "LinkedInAdapter",
    "NewsAdapter",
    "RedditAdapter",
]
