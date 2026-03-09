"""
cato/api/routes.py — Central API routing registration.

Import and call register_all_routes(app) to attach every API endpoint
to an aiohttp Application instance.
"""

from __future__ import annotations

import logging
from aiohttp import web

logger = logging.getLogger(__name__)


def register_all_routes(app: web.Application) -> None:
    """Attach all API routes to the given aiohttp Application."""
    from cato.api.websocket_handler import register_routes as register_coding_agent
    register_coding_agent(app)
    logger.info("All API routes registered")
