from __future__ import annotations

from pathlib import Path

import asyncio
import json
import time
from types import SimpleNamespace

import pytest


def test_marketplace_service_lists_supported_marketplaces(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    result = service.list_marketplaces()

    slugs = {item["slug"] for item in result["marketplaces"]}
    assert result["product"]["slug"] == "marketplace"
    assert {"upwork", "fiverr"} <= slugs


def test_marketplace_plan_allocates_session_metadata(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    plan = service.build_plan(
        marketplace="upwork",
        target_type="job-search",
        target_url="https://www.upwork.com/nx/search/jobs/?q=python",
    )

    assert plan["marketplace"] == "upwork"
    assert plan["target_type"] == "job-search"
    assert plan["login_required"] is True
    assert plan["session"]["allocation"] == "deferred"
    assert plan["session"]["lease_id"] is None
    assert plan["session"]["spec"]["product"] == "marketplace"
    assert plan["session"]["spec"]["marketplace"] == "upwork"


def test_marketplace_plan_reuses_session_key_for_same_account(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    first = service.build_plan(
        marketplace="upwork",
        target_type="job-search",
        target_url="https://www.upwork.com/nx/search/jobs/?q=python",
        account_id="acct-123",
        proxy_label="us-az-1",
    )
    second = service.build_plan(
        marketplace="upwork",
        target_type="job-detail",
        target_url="https://www.upwork.com/jobs/~abc123",
        account_id="acct-123",
        proxy_label="us-az-1",
    )

    assert first["session"]["spec"]["session_key"] == second["session"]["spec"]["session_key"]
    assert "acct-123" in first["session"]["spec"]["session_key"]


def test_marketplace_plan_inherits_account_proxy_label(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    account = service.create_account(
        marketplace="upwork",
        display_name="Proxy Account",
        proxy_label="tor-local",
    )["account"]

    plan = service.build_plan(
        marketplace="upwork",
        target_type="job-search",
        target_url="https://www.upwork.com/nx/search/jobs/?q=python",
        account_id=account["id"],
    )

    assert plan["session"]["spec"]["proxy_label"] == "tor-local"


def test_marketplace_job_persists_to_store(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    created = service.create_job(
        marketplace="fiverr",
        target_type="gig-detail",
        target_url="https://www.fiverr.com/example/gig-title",
        request_payload={"source": "test"},
    )

    job = created["job"]
    fetched = service.get_job(job["id"])["job"]
    jobs = service.list_jobs(marketplace="fiverr")["jobs"]

    assert fetched["id"] == job["id"]
    assert fetched["plan"]["marketplace"] == "fiverr"
    assert fetched["request"]["source"] == "test"
    assert fetched["session_id"] == fetched["plan"]["session"]["spec"]["session_key"]
    assert any(item["id"] == job["id"] for item in jobs)


def test_marketplace_account_and_session_round_trip(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    account = service.create_account(
        marketplace="upwork",
        display_name="Primary Upwork",
        credential_key="UPWORK_MAIN",
        proxy_label="us-az-1",
        metadata={"region": "us"},
    )["account"]
    session = service.save_session(
        account_id=account["id"],
        label="warm-login",
        cookie_path=str(tmp_path / "warm-login.json"),
        metadata={"freshness": "manual"},
    )["session"]

    listed_accounts = service.list_accounts(marketplace="upwork")["accounts"]
    fetched_session = service.get_session(session["id"])["session"]
    listed_sessions = service.list_sessions(marketplace="upwork")["sessions"]

    assert any(item["id"] == account["id"] for item in listed_accounts)
    assert fetched_session["account_id"] == account["id"]
    assert any(item["id"] == session["id"] for item in listed_sessions)


def test_marketplace_proxy_round_trip(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    proxy = service.create_proxy(
        label="tor-local",
        host="127.0.0.1",
        port=3128,
        kind="tor",
        metadata={"source": "docker"},
    )["proxy"]

    fetched = service.get_proxy("tor-local")["proxy"]
    listed = service.list_proxies()["proxies"]
    runtime = service.get_runtime_proxy("tor-local")

    assert proxy["label"] == "tor-local"
    assert fetched["host"] == "127.0.0.1"
    assert any(item["label"] == "tor-local" for item in listed)
    assert runtime["port"] == 3128


def test_marketplace_runtime_proxy_rejects_active_cooldown(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    service.create_proxy(
        label="tor-local",
        host="127.0.0.1",
        port=3128,
        kind="tor",
    )
    service.update_proxy_state(
        "tor-local",
        state="cooldown",
        cooldown_until=time.time() + 120,
        last_failure_class="hard_block.cloudflare",
    )

    with pytest.raises(RuntimeError, match="cooling down"):
        service.get_runtime_proxy("tor-local")


def test_marketplace_service_updates_account_and_session_state(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    account = service.create_account(
        marketplace="upwork",
        display_name="Primary Upwork",
        credential_key="UPWORK_MAIN",
    )["account"]
    session = service.save_session(
        account_id=account["id"],
        label="active",
        cookie_path=str(tmp_path / "active.json"),
    )["session"]

    updated_account = service.update_account_status(
        account["id"],
        status="needs_login",
        metadata={"last_login_error": "expired"},
    )["account"]
    updated_session = service.update_session_state(
        session["id"],
        state="stale",
        metadata={"last_error": "expired"},
    )["session"]

    assert updated_account["status"] == "needs_login"
    assert updated_account["metadata"]["last_login_error"] == "expired"
    assert updated_session["state"] == "stale"
    assert updated_session["metadata"]["last_error"] == "expired"


def test_upwork_adapter_transforms_job_detail_payload():
    from cato.tools.marketplaces.upwork import UpworkAdapter

    adapter = UpworkAdapter()
    payload = adapter.transform_extraction(
        target_type="job-detail",
        target_url="https://www.upwork.com/jobs/~abc123",
        structured_payload={
            "title": "Python Developer",
            "description": "Build an API integration",
            "job_url": "https://www.upwork.com/jobs/~abc123",
            "budget": "$500",
        },
        main_content={"title": "", "text": ""},
        navigation={"title": ""},
    )

    assert payload["title"] == "Python Developer"
    assert payload["job_url"].endswith("~abc123")


def test_fiverr_adapter_transforms_seller_profile_payload():
    from cato.tools.marketplaces.fiverr import FiverrAdapter

    adapter = FiverrAdapter()
    payload = adapter.transform_extraction(
        target_type="seller-profile",
        target_url="https://www.fiverr.com/example_seller",
        structured_payload={
            "username": "example_seller",
            "profile_url": "https://www.fiverr.com/example_seller",
            "rating": "4.9 (120 reviews)",
            "skills": ["SEO", "Content Writing"],
        },
        main_content={"title": "", "text": ""},
        navigation={"title": ""},
    )

    assert payload["username"] == "example_seller"
    assert payload["rating"] == 4.9
    assert payload["skills"] == ["SEO", "Content Writing"]


def test_marketplace_service_executes_job_and_persists_result(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    job = service.create_job(
        marketplace="upwork",
        target_type="freelancer-profile",
        target_url="https://www.upwork.com/freelancers/~example",
    )["job"]

    async def runner(job_payload, saved_session):
        assert saved_session is None
        return {
            "records": [{"target_url": job_payload["target_url"], "title": "Example Freelancer"}],
            "artifact_path": str(tmp_path / "artifact.png"),
            "warnings": [],
        }

    executed = asyncio.run(service.execute_job(job["id"], runner))
    listed_results = service.list_results(job_id=job["id"])["results"]

    assert executed["job"]["status"] == "completed"
    assert executed["result"]["job_id"] == job["id"]
    assert listed_results[0]["job_id"] == job["id"]


def test_marketplace_service_exports_result_jsonl(tmp_path: Path):
    from cato.tools.products.marketplace.service import MarketplaceService

    service = MarketplaceService(db_path=tmp_path / "cato.db")
    job = service.create_job(
        marketplace="fiverr",
        target_type="gig-detail",
        target_url="https://pro.fiverr.com/example/gig",
    )["job"]

    async def runner(job_payload, saved_session):
        return {
            "records": [{"title": "Gig Title", "record_type": "fiverr.gig-detail"}],
            "warnings": [],
        }

    executed = asyncio.run(service.execute_job(job["id"], runner))
    exported = service.export_result(
        result_id=executed["result"]["id"],
        fmt="jsonl",
        output_dir=tmp_path / "exports",
    )

    assert exported["format"] == "jsonl"
    assert Path(exported["path"]).exists()
    assert "Gig Title" in Path(exported["path"]).read_text(encoding="utf-8")


def test_marketplace_plan_does_not_allocate_pool_leases(tmp_path: Path):
    from cato.tools.core.session_pool import BrowserSessionPool
    from cato.tools.products.marketplace.service import MarketplaceService

    pool = BrowserSessionPool()
    service = MarketplaceService(db_path=tmp_path / "cato.db", session_pool=pool)

    service.build_plan(
        marketplace="upwork",
        target_type="job-detail",
        target_url="https://www.upwork.com/jobs/example",
    )
    service.build_plan(
        marketplace="fiverr",
        target_type="gig-detail",
        target_url="https://www.fiverr.com/example/gig-title",
    )

    assert pool.list() == []


def test_marketplace_store_connect_is_idempotent(tmp_path: Path):
    from cato.tools.storage.marketplace_store import MarketplaceStore

    store = MarketplaceStore(db_path=tmp_path / "cato.db")
    store.connect()
    first_conn = store._conn
    store.connect()

    assert store._conn is first_conn
    store.close()


def test_browser_tool_supports_session_specific_directories(tmp_path: Path):
    from cato.tools.browser import BrowserTool, ProxyConfig

    tool = BrowserTool(
        data_dir=tmp_path,
        profile_dir=tmp_path / "profiles" / "worker-a",
        screenshot_dir=tmp_path / "artifacts" / "screens",
        pdf_dir=tmp_path / "artifacts" / "pdfs",
        session_dir=tmp_path / "sessions" / "worker-a",
        proxy_config=ProxyConfig(host="127.0.0.1", port=3128),
    )

    assert tool._profile_dir == tmp_path / "profiles" / "worker-a"
    assert tool._screenshot_dir == tmp_path / "artifacts" / "screens"
    assert tool._session_dir == tmp_path / "sessions" / "worker-a"
    assert tool._profile_dir.exists()
    assert tool._screenshot_dir.exists()
    assert tool._pdf_dir.exists()
    assert tool._session_dir.exists()
    assert tool._explicit_proxy_config is not None
    assert tool._explicit_proxy_config.port == 3128


def test_marketplace_worker_pool_isolates_workers_by_session_key(tmp_path: Path):
    from cato.tools.products.marketplace.worker_pool import MarketplaceBrowserWorkerPool

    pool = MarketplaceBrowserWorkerPool(tmp_path)
    worker_a = pool.acquire("upwork:job-search:https://www.upwork.com/jobs/1")
    worker_b = pool.acquire("upwork:job-search:https://www.upwork.com/jobs/2")
    worker_a_again = pool.acquire("upwork:job-search:https://www.upwork.com/jobs/1")

    assert worker_a is worker_a_again
    assert worker_a is not worker_b
    assert worker_a._profile_dir != worker_b._profile_dir


def test_marketplace_worker_pool_hashes_long_session_keys(tmp_path: Path):
    from cato.tools.products.marketplace.worker_pool import MarketplaceBrowserWorkerPool

    pool = MarketplaceBrowserWorkerPool(tmp_path)
    prefix = "marketplace:upwork:account:acct-123:proxy:default:" + ("x" * 100)
    worker_a = pool.acquire(prefix + "a")
    worker_b = pool.acquire(prefix + "b")

    assert worker_a._profile_dir != worker_b._profile_dir


def test_marketplace_worker_pool_recreates_worker_when_proxy_route_changes(tmp_path: Path):
    from cato.tools.products.marketplace.worker_pool import MarketplaceBrowserWorkerPool

    pool = MarketplaceBrowserWorkerPool(tmp_path)
    worker_a = pool.acquire("marketplace:upwork:account:test", proxy_config={"host": "127.0.0.1", "port": 3128})
    worker_b = pool.acquire("marketplace:upwork:account:test", proxy_config={"host": "127.0.0.1", "port": 4128})

    assert worker_a is not worker_b
    assert worker_a._profile_dir != worker_b._profile_dir


def test_conduit_bridge_exposes_marketplace_actions(tmp_path: Path):
    from cato.tools.conduit_bridge import ConduitBridge

    bridge = ConduitBridge("marketplace-test", data_dir=tmp_path)
    payload = asyncio.run(
        bridge.execute({"action": "marketplace_targets", "marketplace": "upwork"})
    )
    result = json.loads(payload)

    assert result["marketplace"] == "upwork"
    assert any(target["key"] == "job-search" for target in result["targets"])


def test_conduit_bridge_marketplace_account_actions(tmp_path: Path):
    from cato.tools.conduit_bridge import ConduitBridge

    bridge = ConduitBridge("marketplace-account-test", data_dir=tmp_path)
    created_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_create_account",
                "marketplace": "fiverr",
                "display_name": "Fiverr Seller Account",
                "credential_key": "FIVERR_MAIN",
            }
        )
    )
    created = json.loads(created_payload)
    account_id = created["account"]["id"]

    listed_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_list_accounts",
                "marketplace": "fiverr",
            }
        )
    )
    listed = json.loads(listed_payload)

    saved_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_save_session",
                "account_id": account_id,
                "label": "seller-login",
                "cookie_path": str(tmp_path / "seller-login.json"),
            }
        )
    )
    saved = json.loads(saved_payload)

    sessions_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_list_sessions",
                "marketplace": "fiverr",
            }
        )
    )
    sessions = json.loads(sessions_payload)

    assert any(item["id"] == account_id for item in listed["accounts"])
    assert saved["session"]["account_id"] == account_id
    assert any(item["id"] == saved["session"]["id"] for item in sessions["sessions"])


def test_conduit_bridge_marketplace_proxy_actions(tmp_path: Path):
    from cato.tools.conduit_bridge import ConduitBridge

    bridge = ConduitBridge("marketplace-proxy-test", data_dir=tmp_path)
    created_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_create_proxy",
                "label": "tor-local",
                "host": "127.0.0.1",
                "port": 3128,
                "kind": "tor",
            }
        )
    )
    created = json.loads(created_payload)

    listed_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_list_proxies",
            }
        )
    )
    listed = json.loads(listed_payload)

    fetched_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_get_proxy",
                "label": "tor-local",
            }
        )
    )
    fetched = json.loads(fetched_payload)

    assert created["proxy"]["label"] == "tor-local"
    assert any(item["label"] == "tor-local" for item in listed["proxies"])
    assert fetched["proxy"]["host"] == "127.0.0.1"


def test_conduit_bridge_marketplace_bootstrap_session_with_stubbed_browser(tmp_path: Path):
    from cato.tools.conduit_bridge import ConduitBridge

    bridge = ConduitBridge("marketplace-bootstrap-test", data_dir=tmp_path)
    created_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_create_account",
                "marketplace": "upwork",
                "display_name": "Primary Upwork",
                "credential_key": "UPWORK_MAIN",
            }
        )
    )
    account_id = json.loads(created_payload)["account"]["id"]

    class FakeWorkerPool:
        def __init__(self, worker):
            self.worker = worker
            self.acquired: list[tuple[str, object]] = []
            self.released: list[tuple[str, bool]] = []

        def acquire(self, session_key: str, proxy_config=None):
            self.acquired.append((session_key, proxy_config))
            return self.worker

        async def release(self, session_key: str, keep_alive: bool = True):
            self.released.append((session_key, keep_alive))

    async def fake_save_cookies(label="default"):
        cookie_path = tmp_path / f"{label}.json"
        cookie_path.write_text("[]", encoding="utf-8")
        return {"success": True, "path": str(cookie_path)}

    async def fake_login_flow(browser_tool, adapter, credential_key, target_url):
        return {"success": True, "final_url": "https://www.upwork.com/nx/search/jobs/"}

    fake_browser = SimpleNamespace(_save_cookies=fake_save_cookies)
    bridge._marketplace_worker_pool = FakeWorkerPool(fake_browser)
    bridge._run_marketplace_login_flow = fake_login_flow
    bridge.navigate = lambda url, retry_on_auth=False: asyncio.sleep(0, result={"url": url, "title": "Upwork"})

    payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_bootstrap_session",
                "account_id": account_id,
                "target_url": "https://www.upwork.com/nx/search/jobs/?q=copywriter",
            }
        )
    )
    result = json.loads(payload)

    assert result["session"]["account_id"] == account_id
    assert result["session"]["state"] == "fresh"
    assert bridge._marketplace_worker_pool.acquired[0][1] is None


def test_conduit_bridge_marketplace_queue_status(tmp_path: Path):
    from cato.tools.conduit_bridge import ConduitBridge

    async def scenario():
        bridge = ConduitBridge("marketplace-queue-test", data_dir=tmp_path)

        async def fake_execute(job_id):
            await asyncio.sleep(0)
            return {"job": {"id": job_id, "status": "completed"}}

        bridge.marketplace_execute_job = fake_execute
        queued = await bridge.marketplace_enqueue_job("job-123")
        await asyncio.sleep(0)
        status = await bridge.marketplace_queue_status("job-123")
        return queued, status

    queued, status = asyncio.run(scenario())

    assert queued["status"] in {"queued", "running", "completed"}
    assert status["status"] == "completed"


def test_conduit_bridge_marketplace_execute_job_with_stubbed_browser(tmp_path: Path):
    from cato.tools.conduit_bridge import ConduitBridge

    bridge = ConduitBridge("marketplace-run-test", data_dir=tmp_path)
    asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_create_proxy",
                "label": "tor-local",
                "host": "127.0.0.1",
                "port": 3128,
                "kind": "tor",
            }
        )
    )
    created_payload = asyncio.run(
        bridge.execute(
            {
                "action": "marketplace_create_job",
                "marketplace": "fiverr",
                "target_type": "gig-detail",
                "target_url": "https://www.fiverr.com/example/gig-title",
                "proxy_label": "tor-local",
            }
        )
    )
    job = json.loads(created_payload)["job"]

    fake_browser = SimpleNamespace(
        _dispatch=None,
        _ensure_browser=None,
        _browser=SimpleNamespace(add_cookies=None),
    )

    class FakeWorkerPool:
        def __init__(self, worker):
            self.worker = worker
            self.acquired: list[tuple[str, object]] = []
            self.released: list[tuple[str, bool]] = []

        def acquire(self, session_key: str, proxy_config=None):
            self.acquired.append((session_key, proxy_config))
            return self.worker

        async def release(self, session_key: str, keep_alive: bool = True):
            self.released.append((session_key, keep_alive))

    async def fake_browser_boot():
        return None

    async def fake_add_cookies(cookies):
        return None

    async def fake_dispatch(action, kwargs):
        if action == "detect_captcha":
            return {"detected": False, "type": None}
        raise AssertionError(f"Unexpected dispatch action: {action}")

    fake_browser._dispatch = fake_dispatch
    fake_browser._ensure_browser = fake_browser_boot
    fake_browser._browser.add_cookies = fake_add_cookies

    async def fake_navigate(url, retry_on_auth=True):
        return {"url": url, "title": "Gig Title"}

    async def fake_eval(js_code):
        return {
            "success": True,
            "result": {
                "title": "Gig Title",
                "gig_url": "https://www.fiverr.com/example/gig-title",
                "seller_username": "seller_alpha",
                "packages": ["Basic", "Standard", "Premium"],
            },
        }

    async def fake_extract_main(max_chars=5000, fmt="text", provenance_mode=False):
        return {
            "title": "Gig Title",
            "text": "Marketplace body",
            "content_hash": "abc123",
            "fetched_at": 1.0,
            "http_status": 200,
            "links_found": 4,
        }

    async def fake_screenshot(path=None):
        return {"path": str(tmp_path / "marketplace_run.png")}

    observed_proof_sessions: list[str] = []

    def fake_export_proof(output_dir=None, previous_bundle_path=None, page_hashes=None):
        observed_proof_sessions.append(bridge._session_id)
        return {
            "success": True,
            "path": str(tmp_path / "proofs" / "marketplace-run.tar.gz"),
        }

    fake_pool = FakeWorkerPool(fake_browser)
    bridge._marketplace_worker_pool = fake_pool
    bridge.navigate = fake_navigate
    bridge.eval = fake_eval
    bridge.extract_main = fake_extract_main
    bridge.screenshot = fake_screenshot
    bridge.export_proof = fake_export_proof

    executed_payload = asyncio.run(
        bridge.execute({"action": "marketplace_execute_job", "job_id": job["id"]})
    )
    executed = json.loads(executed_payload)
    results_payload = asyncio.run(
        bridge.execute({"action": "marketplace_list_results", "job_id": job["id"]})
    )
    results = json.loads(results_payload)

    assert executed["job"]["status"] == "completed"
    assert executed["result"]["job_id"] == job["id"]
    assert executed["result"]["proof_bundle_path"].endswith("marketplace-run.tar.gz")
    assert fake_pool.acquired[0][0] == job["session_id"]
    assert fake_pool.acquired[0][1]["label"] == "tor-local"
    assert fake_pool.acquired[0][1]["host"] == "127.0.0.1"
    assert fake_pool.released == [(job["session_id"], False)]
    assert observed_proof_sessions == [f"marketplace-run-test:marketplace-job:{job['id']}"]
    assert executed["result"]["records"][0]["seller_username"] == "seller_alpha"
    assert executed["result"]["records"][0]["extraction_strategy"] == "adapter"
    assert executed["result"]["records"][0]["proof_bundle_path"].endswith("marketplace-run.tar.gz")
    assert executed["result"]["records"][0]["worker_session_key"] == job["session_id"]
    assert executed["result"]["records"][0]["proxy"]["label"] == "tor-local"
    assert results["results"][0]["job_id"] == job["id"]


def test_conduit_bridge_normalizes_imported_browser_cookies():
    from cato.tools.conduit_bridge import ConduitBridge

    normalized = ConduitBridge._normalize_imported_cookies(
        [
            {
                "domain": ".upwork.com",
                "expirationDate": 1775250463.409032,
                "hostOnly": False,
                "httpOnly": True,
                "name": "secure_cookie",
                "path": "/nx/find-work/",
                "sameSite": "unspecified",
                "secure": True,
                "session": False,
                "value": "abc",
            },
            {
                "domain": ".fiverr.com",
                "hostOnly": False,
                "httpOnly": False,
                "name": "cross_site",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": True,
                "value": "def",
            },
            {
                "domain": ".example.com",
                "hostOnly": True,
                "httpOnly": False,
                "name": "host_only_cookie",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": False,
                "session": False,
                "expirationDate": "invalid",
                "value": "ghi",
            },
        ]
    )

    assert len(normalized["cookies"]) == 3
    assert normalized["cookies"][0]["domain"] == ".upwork.com"
    assert "sameSite" not in normalized["cookies"][0]
    assert normalized["cookies"][0]["expires"] == 1775250463.409032
    assert normalized["cookies"][1]["sameSite"] == "None"
    assert normalized["cookies"][2]["domain"] == "example.com"
    assert normalized["cookies"][2]["sameSite"] == "Lax"
    assert "expires" not in normalized["cookies"][2]
    assert normalized["normalized"] >= 4
    assert any("coerced SameSite=None to Lax" in warning for warning in normalized["warnings"])
    assert any("invalid expirationDate dropped" in warning for warning in normalized["warnings"])


def test_conduit_mcp_server_exposes_marketplace_tools():
    import conduit_mcp_server

    tool_names = {tool.name for tool in conduit_mcp_server.TOOLS}

    assert "conduit_marketplace_list" in tool_names
    assert "conduit_marketplace_plan" in tool_names
    assert "conduit_marketplace_get_job" in tool_names
    assert "conduit_marketplace_get_session" in tool_names
    assert "conduit_marketplace_get_result" in tool_names
    assert "conduit_marketplace_create_proxy" in tool_names
    assert "conduit_marketplace_test_proxy" in tool_names
    assert "conduit_marketplace_bootstrap_session" in tool_names
    assert "conduit_marketplace_enqueue_job" in tool_names
    assert "conduit_marketplace_export_result" in tool_names


def test_conduit_mcp_server_dispatches_marketplace_plan():
    import conduit_mcp_server

    class FakeBridge:
        def __init__(self):
            self.calls: list[dict[str, object]] = []

        async def execute(self, args):
            self.calls.append(args)
            return json.dumps({"ok": True, "args": args})

    fake_bridge = FakeBridge()
    previous_bridge = conduit_mcp_server._bridge
    conduit_mcp_server._bridge = fake_bridge
    try:
        payload = asyncio.run(
            conduit_mcp_server._dispatch(
                "conduit_marketplace_plan",
                {
                    "marketplace": "upwork",
                    "target_type": "job-search",
                    "target_url": "https://www.upwork.com/nx/search/jobs/?q=python",
                },
            )
        )
    finally:
        conduit_mcp_server._bridge = previous_bridge

    result = json.loads(payload)

    assert result["ok"] is True
    assert fake_bridge.calls[0]["action"] == "marketplace_plan"
    assert fake_bridge.calls[0]["marketplace"] == "upwork"
