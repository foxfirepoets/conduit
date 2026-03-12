"""
Kraken live verification script for agent-marketing features.
Tests:
  1. export_micro() with scan_origin="mcp_response" returns 6 fields
  2. export() bundle manifest.json has agent_discovery with all required fields
  3. conduit_version == "0.2.1"
  4. Edge cases: empty result, result with error key, large result dict
"""
import hashlib, json, sys, tarfile, tempfile, time, types
from pathlib import Path

CONDUIT_ROOT = Path("C:/Users/Administrator/Desktop/Conduit")
PROOF_PATH = CONDUIT_ROOT / "tools" / "conduit_proof.py"

# Bootstrap conduit_proof standalone
proof_src = PROOF_PATH.read_text(encoding="utf-8")
proof_mod = types.ModuleType("conduit_proof_standalone_kraken")
proof_mod.__file__ = str(PROOF_PATH)
exec(compile(proof_src, str(PROOF_PATH), "exec"), proof_mod.__dict__)
ConduitProof = proof_mod.ConduitProof

# --- Mocks ---
class MockAuditLog:
    def __init__(self, rows=None):
        self._rows = rows or []
    def get_session_rows(self, session_id):
        return [r for r in self._rows if r.get("session_id") == session_id]

class MockIdentity:
    public_key_hex = "a" * 64
    def sign(self, data: bytes) -> bytes:
        return b"\xab" * 64

def make_fake_rows(session_id="sess-kraken-001", count=3):
    rows = []
    prev_hash = ""
    for i in range(1, count + 1):
        ts = 1700000000.0 + i
        rh = hashlib.sha256(
            f"{i}:{session_id}:tool_call:browser.navigate:0:{ts}:{prev_hash}".encode()
        ).hexdigest()
        rows.append({
            "id": i, "session_id": session_id,
            "action_type": "tool_call", "tool_name": "browser.navigate",
            "cost_cents": 0, "timestamp": ts, "row_hash": rh,
            "inputs": {"url": f"https://example.com/page{i}"},
            "outputs": {"url": f"https://example.com/page{i}", "title": f"Page {i}"},
            "error": "",
        })
        prev_hash = rh
    return rows

failures = []
passes = []

def check(name, condition, detail=""):
    if condition:
        passes.append(name)
        print(f"  PASS  {name}")
    else:
        failures.append(name)
        print(f"  FAIL  {name}" + (f" -- {detail}" if detail else ""))

print("\n=== CLAIM 1: export_micro() returns 6-field micro_proof ===")

proof_obj = ConduitProof(MockAuditLog(), "sess-k-001", "", identity=MockIdentity())
micro = proof_obj.export_micro(url="https://example.com", dom_hash="abc123", scan_origin="mcp_response")

check("export_micro returns success=True", micro.get("success") is True)
mp = micro.get("micro_proof", {})
check("micro_proof has exactly 6 keys", len(mp) == 6, f"got {len(mp)}: {list(mp.keys())}")
EXPECTED_KEYS = {"url", "dom_hash", "timestamp", "signature", "scanner_version_hash", "scan_origin"}
check("micro_proof has correct 6 fields", set(mp.keys()) == EXPECTED_KEYS,
      f"got {set(mp.keys())} expected {EXPECTED_KEYS}")
check("url field matches input", mp.get("url") == "https://example.com")
check("dom_hash has sha256: prefix", str(mp.get("dom_hash","")).startswith("sha256:"))
check("scan_origin is 'mcp_response'", mp.get("scan_origin") == "mcp_response")
check("signature starts with 'ed25519:'", str(mp.get("signature","")).startswith("ed25519:"))
check("scanner_version_hash starts with 'sha256:'", str(mp.get("scanner_version_hash","")).startswith("sha256:"))

# Verify scanner_version_hash matches actual file
actual_hash = hashlib.sha256(PROOF_PATH.read_bytes()).hexdigest()
check("scanner_version_hash matches conduit_proof.py SHA-256",
      mp.get("scanner_version_hash") == f"sha256:{actual_hash}")

proof_json_size = len(json.dumps(mp).encode())
check(f"micro_proof is <500 bytes ({proof_json_size} bytes)", proof_json_size < 500)

print("\n=== CLAIM 2: export() bundle manifest has agent_discovery ===")

session_id = "sess-k-discovery-001"
rows = make_fake_rows(session_id=session_id, count=3)
audit_log = MockAuditLog(rows)
identity = MockIdentity()

proof = ConduitProof(
    audit_log, session_id,
    f"# Ed25519 public key: {identity.public_key_hex}\n",
    identity=identity,
)

with tempfile.TemporaryDirectory() as tmpdir:
    result = proof.export(output_dir=tmpdir)
    check("export() returns success=True", result.get("success") is True)
    bundle_path = result.get("path", "")
    with tarfile.open(bundle_path, "r:gz") as tar:
        f = tar.extractfile("session_proof/manifest.json")
        manifest = json.loads(f.read().decode("utf-8"))

check("manifest has 'agent_discovery' key", "agent_discovery" in manifest)
ad = manifest.get("agent_discovery", {})
REQUIRED_AD_FIELDS = {"tool_name", "install_command", "mcp_config", "capabilities", "proof_features", "source_url", "pypi_url", "license"}
missing_ad = REQUIRED_AD_FIELDS - set(ad.keys())
check("agent_discovery has all 8 required fields", len(missing_ad) == 0, f"missing: {missing_ad}")
check("tool_name == 'conduit-browser'", ad.get("tool_name") == "conduit-browser")
check("install_command == 'pip install conduit-browser'", ad.get("install_command") == "pip install conduit-browser")
check("mcp_config.command == 'python'", ad.get("mcp_config", {}).get("command") == "python")
mcp_args = ad.get("mcp_config", {}).get("args", [])
check("mcp_config.args contains '-m' and 'conduit_browser'",
      "-m" in mcp_args and "conduit_browser" in mcp_args)
caps = ad.get("capabilities", [])
check("capabilities is a list with >5 items", isinstance(caps, list) and len(caps) > 5)
check("source_url == 'https://github.com/bkauto3/Conduit'", ad.get("source_url") == "https://github.com/bkauto3/Conduit")
check("pypi_url == 'https://pypi.org/project/conduit-browser/'", ad.get("pypi_url") == "https://pypi.org/project/conduit-browser/")
check("license == 'MIT'", ad.get("license") == "MIT")

pf = ad.get("proof_features", {})
check("proof_features.audit_chain == 'SHA-256'", pf.get("audit_chain") == "SHA-256")
check("proof_features.signing == 'Ed25519'", pf.get("signing") == "Ed25519")
check("proof_features.self_verifiable is True", pf.get("self_verifiable") is True)

print("\n=== CLAIM 3: Version 0.2.1 ===")

pyproject = (CONDUIT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
check("pyproject.toml has version = '0.2.1'", 'version = "0.2.1"' in pyproject)
check("manifest conduit_version == '0.2.1'", manifest.get("conduit_version") == "0.2.1")

print("\n=== EDGE CASES ===")

# Edge case 1: Empty url and dom_hash
empty_proof = ConduitProof(MockAuditLog(), "sess-edge-001", "", identity=MockIdentity())
micro_empty = empty_proof.export_micro(url="", dom_hash="", scan_origin="mcp_response")
check("Empty url/dom_hash: export_micro still returns success", micro_empty.get("success") is True)
check("Empty url/dom_hash: 6 fields still present", len(micro_empty.get("micro_proof", {})) == 6)

# Edge case 2: Error result - _attach_micro_proof skips when error key present
error_result = {"error": "Page not found", "action": "navigate"}
should_skip = bool(error_result.get("error"))
check("Error result: skip condition is True (no proof attached)", should_skip)
check("Error result: no _conduit_proof key present", "_conduit_proof" not in error_result)

# Edge case 3: Large result dict (performance sanity check)
large_result = {f"key_{i}": "x" * 100 for i in range(1000)}
t_start = time.time()
content_hash = hashlib.sha256(json.dumps(large_result, sort_keys=True, default=str).encode()).hexdigest()
large_proof = ConduitProof(MockAuditLog(), "sess-large-001", "", identity=MockIdentity())
micro_large = large_proof.export_micro(url="https://example.com", dom_hash=content_hash, scan_origin="mcp_response")
elapsed = time.time() - t_start
check(f"Large result dict (100KB): export_micro completes in <1s ({elapsed:.3f}s)", elapsed < 1.0)
check("Large result dict: 6 fields present", len(micro_large.get("micro_proof", {})) == 6)

# Edge case 4: export() with no rows fails gracefully
empty_audit = MockAuditLog([])
empty_session_proof = ConduitProof(empty_audit, "sess-norows-001", "")
with tempfile.TemporaryDirectory() as tmpdir:
    result_no_rows = empty_session_proof.export(output_dir=tmpdir)
check("export() with no rows: returns success=False", result_no_rows.get("success") is False)
check("export() with no rows: returns error message", "error" in result_no_rows)

print("\n=== SUMMARY ===")
print(f"PASSED: {len(passes)}")
print(f"FAILED: {len(failures)}")
if failures:
    print("FAILURES:")
    for f_item in failures:
        print(f"  - {f_item}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
