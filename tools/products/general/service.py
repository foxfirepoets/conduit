from __future__ import annotations

from ...core.models import ProductProfile


GENERAL_PRODUCT = ProductProfile(
    slug="general",
    display_name="Conduit Browser",
    description="General-purpose audited browser for arbitrary web automation and research.",
    supported_actions=(
        "navigate",
        "click",
        "type",
        "fill",
        "extract_main",
        "crawl",
        "fingerprint",
        "export_proof",
    ),
)
