from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from ...core.models import ProductProfile, SessionSpec
from ...marketplaces.amazon import AmazonAdapter
from ...marketplaces.github import GitHubAdapter
from ...marketplaces.google_search import GoogleSearchAdapter
from ...marketplaces.hackernews import HackerNewsAdapter
from ...marketplaces.linkedin import LinkedInAdapter
from ...marketplaces.news import NewsAdapter
from ...marketplaces.reddit import RedditAdapter
from ...storage.marketplace_store import MarketplaceStore


MARKETPLACE_PRODUCT = ProductProfile(
    slug="marketplace",
    display_name="Conduit Marketplace Browser",
    description="Specialized audited browser product for marketplace extraction workflows.",
    supported_actions=(
        "marketplace_list",
        "marketplace_targets",
        "marketplace_plan",
        "marketplace_create_job",
        "marketplace_get_job",
        "marketplace_list_jobs",
        "marketplace_create_account",
        "marketplace_list_accounts",
        "marketplace_create_proxy",
        "marketplace_list_proxies",
        "marketplace_get_proxy",
        "marketplace_test_proxy",
        "marketplace_save_session",
        "marketplace_get_session",
        "marketplace_list_sessions",
        "marketplace_bootstrap_session",
        "marketplace_execute_job",
        "marketplace_enqueue_job",
        "marketplace_queue_status",
        "marketplace_get_result",
        "marketplace_list_results",
        "marketplace_export_result",
    ),
)


class MarketplaceService:
    def __init__(self, db_path: Path, session_pool: Any | None = None) -> None:
        self._store = MarketplaceStore(db_path=db_path)
        self._session_pool = session_pool
        self._adapters = {
            "amazon": AmazonAdapter(),
            "github": GitHubAdapter(),
            "google_search": GoogleSearchAdapter(),
            "hackernews": HackerNewsAdapter(),
            "linkedin": LinkedInAdapter(),
            "news": NewsAdapter(),
            "reddit": RedditAdapter(),
        }

    def list_marketplaces(self) -> dict[str, Any]:
        return {
            "product": MARKETPLACE_PRODUCT.to_dict(),
            "marketplaces": [
                {
                    "slug": adapter.slug,
                    "display_name": adapter.display_name,
                    "targets": adapter.list_targets(),
                }
                for adapter in self._adapters.values()
            ],
        }

    def list_targets(self, marketplace: str) -> dict[str, Any]:
        adapter = self._require_adapter(marketplace)
        return {
            "marketplace": marketplace,
            "targets": adapter.list_targets(),
        }

    def build_plan(
        self,
        marketplace: str,
        target_type: str,
        target_url: str,
        account_id: str | None = None,
        proxy_label: str | None = None,
    ) -> dict[str, Any]:
        adapter = self._require_adapter(marketplace)
        effective_proxy_label = self._resolve_effective_proxy_label(
            account_id=account_id,
            proxy_label=proxy_label,
        )
        session_spec = SessionSpec(
            session_key=self._build_session_key(
                marketplace=marketplace,
                account_id=account_id,
                proxy_label=effective_proxy_label,
            ),
            product="marketplace",
            marketplace=marketplace,
            account_id=account_id,
            proxy_label=effective_proxy_label,
            metadata={
                "target_type": target_type,
                "target_url": target_url,
            },
        )
        plan = adapter.build_plan(
            target_type=target_type,
            target_url=target_url,
            account_id=account_id,
            proxy_label=effective_proxy_label,
            session_id=session_spec.session_key,
        )
        plan["session"] = {
            "allocation": "deferred",
            "lease_id": None,
            "spec": session_spec.to_dict(),
        }
        return plan

    def create_job(
        self,
        marketplace: str,
        target_type: str,
        target_url: str,
        account_id: str | None = None,
        proxy_label: str | None = None,
        request_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = request_payload or {}
        effective_proxy_label = self._resolve_effective_proxy_label(
            account_id=account_id,
            proxy_label=proxy_label,
        )
        plan = self.build_plan(
            marketplace=marketplace,
            target_type=target_type,
            target_url=target_url,
            account_id=account_id,
            proxy_label=effective_proxy_label,
        )
        job = self._store.create_job(
            marketplace=marketplace,
            target_type=target_type,
            target_url=plan["target_url"],
            request_payload=payload,
            plan=plan,
            account_id=account_id or "",
            proxy_label=effective_proxy_label or "",
            session_id=plan["session"]["spec"]["session_key"],
            warnings=[],
        )
        return {"job": job}

    def create_account(
        self,
        marketplace: str,
        display_name: str,
        credential_key: str = "",
        proxy_label: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_adapter(marketplace)
        account = self._store.create_account(
            marketplace=marketplace,
            display_name=display_name,
            credential_key=credential_key,
            proxy_label=proxy_label,
            metadata=metadata or {},
        )
        return {"account": account}

    def list_accounts(self, marketplace: str | None = None) -> dict[str, Any]:
        if marketplace:
            self._require_adapter(marketplace)
        return {"accounts": self._store.list_accounts(marketplace=marketplace)}

    def create_proxy(
        self,
        label: str,
        host: str,
        port: int,
        *,
        protocol: str = "http",
        username: str = "",
        password: str = "",
        kind: str = "http",
        state: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        label = (label or "").strip()
        host = (host or "").strip()
        if not label:
            raise ValueError("Proxy label is required")
        if not host:
            raise ValueError("Proxy host is required")
        if int(port) <= 0:
            raise ValueError("Proxy port must be greater than 0")
        proxy = self._store.save_proxy(
            label=label,
            host=host,
            port=int(port),
            protocol=protocol,
            username=username,
            password=password,
            kind=kind,
            state=state,
            metadata=metadata or {},
        )
        return {"proxy": proxy}

    def list_proxies(self, state: str | None = None) -> dict[str, Any]:
        return {"proxies": self._store.list_proxies(state=state)}

    def get_proxy(self, label: str) -> dict[str, Any]:
        proxy = self._store.get_proxy_by_label(label)
        if proxy is None:
            raise ValueError(f"Unknown marketplace proxy label: {label}")
        return {"proxy": proxy}

    def get_runtime_proxy(self, label: str) -> dict[str, Any]:
        proxy = self._store.get_proxy_by_label(label, include_secret=True)
        if proxy is None:
            raise ValueError(f"Unknown marketplace proxy label: {label}")
        if proxy.get("state") == "cooldown" and float(proxy.get("cooldown_until", 0.0) or 0.0) > time.time():
            raise RuntimeError(
                f"Marketplace proxy {label!r} is cooling down until {proxy['cooldown_until']}"
            )
        return proxy

    def update_proxy_state(
        self,
        label: str,
        *,
        state: str,
        cooldown_until: float | None = None,
        last_failure_class: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        proxy = self._store.get_proxy_by_label(label, include_secret=True)
        if proxy is None:
            raise ValueError(f"Unknown marketplace proxy label: {label}")
        updated = self._store.update_proxy_state(
            proxy["id"],
            state=state,
            cooldown_until=cooldown_until,
            last_failure_class=last_failure_class,
            metadata=metadata or {},
        )
        if updated is None:
            raise ValueError(f"Unknown marketplace proxy label: {label}")
        return {"proxy": updated}

    def get_account(self, account_id: str) -> dict[str, Any]:
        account = self._store.get_account(account_id)
        if account is None:
            raise ValueError(f"Unknown marketplace account: {account_id}")
        return {"account": account}

    def update_account_status(
        self,
        account_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account = self._store.update_account_status(account_id, status=status, metadata=metadata or {})
        if account is None:
            raise ValueError(f"Unknown marketplace account: {account_id}")
        return {"account": account}

    def save_session(
        self,
        account_id: str,
        label: str,
        cookie_path: str,
        state: str = "fresh",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account = self._store.get_account(account_id)
        if account is None:
            raise ValueError(f"Unknown marketplace account: {account_id}")
        session = self._store.save_session(
            account_id=account_id,
            label=label,
            cookie_path=cookie_path,
            state=state,
            metadata=metadata or {},
        )
        return {"session": session}

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self._store.get_saved_session(session_id)
        if session is None:
            raise ValueError(f"Unknown marketplace session: {session_id}")
        return {"session": session}

    def update_session_state(
        self,
        session_id: str,
        state: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._store.update_saved_session_state(
            session_id,
            state=state,
            metadata=metadata or {},
        )
        if session is None:
            raise ValueError(f"Unknown marketplace session: {session_id}")
        return {"session": session}

    def list_sessions(
        self,
        marketplace: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        if marketplace:
            self._require_adapter(marketplace)
        sessions = self._store.list_saved_sessions(
            marketplace=marketplace,
            account_id=account_id,
        )
        return {"sessions": sessions}

    async def execute_job(
        self,
        job_id: str,
        runner: Callable[[dict[str, Any], dict[str, Any] | None], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        job = self._store.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown marketplace job: {job_id}")
        saved_session = None
        if job.get("account_id"):
            saved_session = self._store.get_latest_saved_session(job["account_id"])
        self._store.update_job_status(job_id, "running")
        try:
            payload = await runner(job, saved_session)
        except Exception as exc:
            warning_parts = [str(exc)]
            failure_class = getattr(exc, "failure_class", "")
            artifact_path = getattr(exc, "artifact_path", "")
            if failure_class:
                warning_parts.append(f"failure_class={failure_class}")
            if artifact_path:
                warning_parts.append(f"artifact_path={artifact_path}")
                self._store.save_result(
                    job_id=job_id,
                    records=[],
                    proof_bundle_path="",
                    artifact_path=artifact_path,
                )
            self._store.update_job_status(job_id, "failed", warnings=warning_parts)
            raise
        warnings = payload.get("warnings", [])
        result = self._store.save_result(
            job_id=job_id,
            records=payload.get("records", []),
            proof_bundle_path=payload.get("proof_bundle_path", ""),
            artifact_path=payload.get("artifact_path", ""),
        )
        updated_job = self._store.update_job_status(job_id, "completed", warnings=warnings) or self._store.get_job(job_id)
        return {"job": updated_job, "result": result}

    def get_result(self, result_id: str) -> dict[str, Any]:
        result = self._store.get_result(result_id)
        if result is None:
            raise ValueError(f"Unknown marketplace result: {result_id}")
        return {"result": result}

    def list_results(self, job_id: str | None = None) -> dict[str, Any]:
        return {"results": self._store.list_results(job_id=job_id)}

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self._store.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown marketplace job: {job_id}")
        return {"job": job}

    def list_jobs(self, marketplace: str | None = None, status: str | None = None) -> dict[str, Any]:
        return {
            "jobs": self._store.list_jobs(marketplace=marketplace, status=status),
        }

    def get_adapter(self, marketplace: str):
        return self._require_adapter(marketplace)

    def export_result(
        self,
        result_id: str,
        fmt: str,
        output_dir: Path,
    ) -> dict[str, Any]:
        result = self._store.get_result(result_id)
        if result is None:
            raise ValueError(f"Unknown marketplace result: {result_id}")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if fmt == "jsonl":
            output_path = output_dir / f"{result_id}.jsonl"
            lines = [json.dumps(record, ensure_ascii=True) for record in result["records"]]
            output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        elif fmt == "csv":
            output_path = output_dir / f"{result_id}.csv"
            fieldnames: list[str] = []
            for record in result["records"]:
                for key in record.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)
            with output_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames or ["empty"])
                writer.writeheader()
                if fieldnames:
                    for record in result["records"]:
                        writer.writerow(
                            {
                                key: json.dumps(value, ensure_ascii=True)
                                if isinstance(value, (dict, list))
                                else value
                                for key, value in record.items()
                            }
                        )
        else:
            raise ValueError(f"Unsupported export format: {fmt!r}. Valid: jsonl, csv")

        return {
            "result_id": result_id,
            "format": fmt,
            "path": str(output_path),
            "record_count": len(result["records"]),
        }

    def _require_adapter(self, marketplace: str):
        adapter = self._adapters.get((marketplace or "").lower())
        if adapter is None:
            valid = ", ".join(sorted(self._adapters))
            raise ValueError(f"Unsupported marketplace: {marketplace!r}. Valid: {valid}")
        return adapter

    def _resolve_effective_proxy_label(
        self,
        *,
        account_id: str | None,
        proxy_label: str | None,
    ) -> str | None:
        if proxy_label:
            return proxy_label
        if account_id:
            account = self._store.get_account(account_id)
            if account and account.get("proxy_label"):
                return account["proxy_label"]
        return None

    def _build_session_key(
        self,
        *,
        marketplace: str,
        account_id: str | None,
        proxy_label: str | None,
    ) -> str:
        account_segment = account_id or "public"
        proxy_segment = proxy_label or "default"
        return f"marketplace:{marketplace}:account:{account_segment}:proxy:{proxy_segment}"
