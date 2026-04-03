from __future__ import annotations

import time
from typing import Any

from .models import SessionLease, SessionSpec


class BrowserSessionPool:
    """
    Metadata-only session pool for product orchestration.

    The current Conduit runtime still uses a single live browser context.
    This pool tracks future per-job session intent now so the runtime can be
    upgraded incrementally without changing product-layer contracts.
    """

    def __init__(self) -> None:
        self._leases: dict[str, SessionLease] = {}

    def acquire(self, spec: SessionSpec) -> SessionLease:
        lease = SessionLease.create(spec)
        self._leases[lease.lease_id] = lease
        return lease

    def release(self, lease_id: str) -> dict[str, Any]:
        lease = self._leases.get(lease_id)
        if lease is None:
            return {"released": False, "error": f"Unknown session lease: {lease_id}"}
        lease.status = "released"
        lease.released_at = time.time()
        return {"released": True, "lease": lease.to_dict()}

    def get(self, lease_id: str) -> SessionLease | None:
        return self._leases.get(lease_id)

    def list(self, product: str | None = None) -> list[dict[str, Any]]:
        leases = list(self._leases.values())
        if product:
            leases = [lease for lease in leases if lease.spec.product == product]
        return [lease.to_dict() for lease in leases]
