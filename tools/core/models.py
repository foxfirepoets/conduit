from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProductProfile:
    slug: str
    display_name: str
    description: str
    supported_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionSpec:
    session_key: str
    product: str
    marketplace: str | None = None
    account_id: str | None = None
    proxy_label: str | None = None
    locale: str = "en-US"
    timezone: str = "America/New_York"
    headless: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionLease:
    lease_id: str
    spec: SessionSpec
    status: str = "ready"
    created_at: float = field(default_factory=time.time)
    released_at: float | None = None

    @classmethod
    def create(cls, spec: SessionSpec) -> "SessionLease":
        return cls(lease_id=uuid.uuid4().hex, spec=spec)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spec"] = self.spec.to_dict()
        return payload
