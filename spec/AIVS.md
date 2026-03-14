# Agentic Integrity Verification Standard (AIVS) v1.0

**A self-verifiable, portable format for cryptographic proof of AI agent sessions.**

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Status** | Draft |
| **Date** | 2026-03-14 |
| **License** | Apache 2.0 |
| **Authors** | bkauto3 |
| **Repository** | https://github.com/bkauto3/Conduit |
| **Reference Implementation** | `tools/conduit_proof.py` |

---

## Abstract

The Agentic Integrity Verification Standard (AIVS) defines a portable, self-verifiable archive format for cryptographic proof of AI agent sessions. An AIVS bundle is a gzip-compressed tar archive containing a SHA-256 hash-chained audit log, an Ed25519 digital signature over the chain, a machine-readable manifest, and an embedded verification script that requires only Python 3 standard library to execute.

AIVS also defines **AIVS-Micro**: a minimal 6-field attestation (~200 bytes) for continuous monitoring, embedded widgets, and API responses where a full session bundle is not required.

AIVS enables any party to independently verify that:

1. Every action in the session is accounted for and unmodified (hash chain integrity)
2. No actions have been inserted, deleted, or reordered (sequential chaining)
3. The session was produced by a specific cryptographic identity (Ed25519 signature)
4. All of the above can be verified offline, without network access, and without installing any software beyond Python 3 (self-verification)

---

## 1. Motivation

### 1.1 Problem Statement

AI agents increasingly perform consequential actions on behalf of humans: navigating websites, filling forms, executing JavaScript, extracting data, and making purchases. Existing observability platforms (OpenTelemetry, LangSmith, Langfuse) log these actions but provide no cryptographic guarantees that the logs are complete, unmodified, or authentic.

Regulatory frameworks mandate audit trails but do not prescribe formats:

- **EU AI Act Article 19** requires automatically generated logs for high-risk AI systems but specifies no format.
- **ISO/IEC 42001:2023 Annex A.6.2.8** requires event logging but defines no data structure.
- **NIST AI RMF** requires documentation and audit trails but deliberately avoids prescribing formats.

This creates a gap: organizations that must prove what their AI agents did have no standard way to produce, exchange, or verify that proof.

### 1.2 Design Goals

| Goal | Rationale |
|------|-----------|
| **Self-verifiable** | Proof bundles must be verifiable without contacting any server, blockchain, or authority. |
| **Portable** | A single file that can be emailed, stored, or submitted to any system. |
| **Tamper-evident** | Modifying any action in the log must be detectable. |
| **Zero dependencies** | Verification must require only Python 3 standard library. Signature verification MAY use the `cryptography` library. |
| **Session-level** | Covers an entire session (sequence of actions), not individual action receipts. |
| **Lightweight profile** | AIVS-Micro provides a ~200-byte attestation for high-frequency monitoring without full bundle overhead. |
| **Domain-agnostic** | Applicable to any AI agent performing any type of action, not limited to commerce, trading, or specific tools. |

### 1.3 Relationship to Existing Standards

AIVS is complementary to, not competitive with, existing work:

| Standard | Scope | AIVS Relationship |
|----------|-------|-------------------|
| W3C Verifiable Credentials 2.0 | Identity claims | AIVS bundles could be wrapped as a VC `credentialSubject` |
| IETF SCITT (draft-ietf-scitt-architecture) | Supply chain transparency logs | AIVS bundles could be registered as SCITT signed statements |
| C2PA v2.2 | Media asset provenance | AIVS applies the same manifest-chain concept to agent actions |
| VAP (draft-ailex-vap-legal-ai-provenance) | AI decision provenance for regulated industries | AIVS covers interactive agent sessions (browser, tool calls); VAP covers model decision trails for legal/regulatory filing. Non-overlapping scope. |
| Agent Action Receipts (AAR) | Individual action receipts | AIVS provides session-level aggregation of action-level records |
| Certificate Transparency (RFC 6962) | Append-only Merkle logs | AIVS's hash chain is a simplified linear variant; Merkle tree extension is possible |
| EU AI Act Article 19 | Audit log requirements | AIVS is a concrete format that satisfies Article 19's content requirements |

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Session** | A bounded sequence of actions performed by a single AI agent instance, identified by a `session_id`. |
| **Action** | A single operation performed by the agent (e.g., navigate to URL, click element, execute JavaScript). |
| **Audit Row** | A JSON object recording one action with its inputs, outputs, timestamp, cost, and hash chain fields. |
| **Hash Chain** | A sequence of audit rows where each row's hash depends on the previous row's hash, forming a tamper-evident chain. |
| **Chain Hash** | A single SHA-256 hash computed over all row hashes, serving as a fingerprint of the entire session. |
| **Proof Bundle** | A `.tar.gz` archive containing the audit log, signature, manifest, public key, and verifier script. Also called an AIVS Full Bundle. |
| **AIVS-Micro** | A minimal 6-field JSON proof (~200 bytes) for a single-URL scan attestation. |
| **Identity Key** | An Ed25519 keypair used to sign the chain hash or micro-proof payload. |
| **Scanner Version Hash** | SHA-256 of the scanner implementation file, binding a proof to a specific code version. |

---

## 3. Hash Chain Specification

### 3.1 Row Hash Computation

Each audit row is identified by a deterministic SHA-256 hash. The hash input is a colon-separated string of exactly seven fields in this order:

```
row_hash = SHA-256(
    "{row_id}:{session_id}:{action_type}:{tool_name}:{cost_cents}:{timestamp}:{prev_hash}"
)
```

The hash is represented as a lowercase hexadecimal string (64 characters).

### 3.2 Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `row_id` | Integer | Monotonically increasing row identifier (1-indexed). |
| `session_id` | String | Unique identifier for the session. |
| `action_type` | String | Classification of the action. Default: `"tool_call"`. |
| `tool_name` | String | Namespaced tool identifier (e.g., `"browser.navigate"`, `"browser.eval"`). |
| `cost_cents` | Integer | Cost of the action in cents. `0` for free actions. |
| `timestamp` | Float | Unix timestamp with fractional seconds (e.g., `1710252645.123456`). |
| `prev_hash` | String | The `row_hash` of the immediately preceding row. Empty string `""` for the first row. |

### 3.3 Chain Integrity Property

For a chain of N rows, modifying any field of row K invalidates `row_hash[K]`, which invalidates `prev_hash[K+1]`, which invalidates `row_hash[K+1]`, and so on through `row_hash[N]`. This means:

- **Insertion** of a row is detectable (changes all subsequent `row_id` values and hashes).
- **Deletion** of a row is detectable (breaks the `prev_hash` link).
- **Reordering** of rows is detectable (changes `prev_hash` linkage).
- **Modification** of any field is detectable (changes the affected row's hash and all subsequent hashes).

### 3.4 Chain Hash Computation

The chain hash is a single SHA-256 hash that fingerprints the entire session:

```
If rows is empty:
    chain_hash = SHA-256(b"empty")
Else:
    combined = concatenate(row_hash[1], row_hash[2], ..., row_hash[N])
    chain_hash = SHA-256(combined.encode("utf-8"))
```

The chain hash is represented as a lowercase hexadecimal string (64 characters).

---

## 4. Audit Row Schema

Each row in the audit log is a JSON object with the following fields:

```json
{
  "id":           1,
  "session_id":   "sess-abc123",
  "action_type":  "tool_call",
  "tool_name":    "browser.navigate",
  "inputs_json":  "{\"url\": \"https://example.com\"}",
  "outputs_json": "{\"title\": \"Example Domain\", \"url\": \"https://example.com/\"}",
  "cost_cents":   0,
  "error":        "",
  "timestamp":    1710252645.123456,
  "prev_hash":    "",
  "row_hash":     "a1b2c3d4e5f6..."
}
```

### 4.1 Field Specifications

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | Integer | Yes | Row identifier, 1-indexed, monotonically increasing. |
| `session_id` | String | Yes | Session identifier. |
| `action_type` | String | Yes | Action classification. |
| `tool_name` | String | Yes | Namespaced tool identifier. |
| `inputs_json` | String | Yes | JSON-encoded action inputs. Sensitive keys MUST be redacted (see Section 4.2). |
| `outputs_json` | String | Yes | JSON-encoded action outputs. MAY be truncated. |
| `cost_cents` | Integer | Yes | Action cost in cents. |
| `error` | String | Yes | Error message if the action failed; empty string if successful. |
| `timestamp` | Float | Yes | Unix timestamp with fractional seconds. |
| `prev_hash` | String | Yes | Previous row's `row_hash`. Empty string for the first row. |
| `row_hash` | String | Yes | This row's computed SHA-256 hash (see Section 3.1). |

### 4.2 Sensitive Input Redaction

Before computing the row hash, implementations MUST redact values for input keys matching any of the following case-insensitive substrings:

```
password, token, api_key, secret, key, authorization,
bearer, credential, passwd, passphrase
```

Redacted values MUST be replaced with the string `"[REDACTED]"`.

### 4.3 Output Truncation

Implementations MAY truncate `outputs_json` to a maximum length. The reference implementation truncates to 2000 characters. Truncation does not affect the hash chain because `outputs_json` is not included in the row hash computation.

> **Note:** Only the seven fields listed in Section 3.1 are included in the hash computation. `inputs_json`, `outputs_json`, and `error` are included in the audit log for informational purposes but are NOT part of the hash chain. This is intentional: it allows output truncation and input redaction without breaking the chain.

### 4.4 JavaScript Source Storage (eval actions)

When an agent executes JavaScript, implementations SHOULD store the full JavaScript source verbatim in `inputs_json` under the key `"js_code"`, along with a `"code_hash"` field containing the SHA-256 of the source. This provides cryptographic proof of exactly what code ran — not merely that JavaScript was executed. The `js_code` field is informational and is NOT included in the row hash computation.

```json
{
  "tool_name":   "browser.eval",
  "inputs_json": "{\"js_code\": \"document.querySelectorAll('h1').length\", \"code_hash\": \"a1b2c3d4...\"}"
}
```

---

## 5. Ed25519 Signature

### 5.1 Signing

The chain hash (Section 3.4) is signed using an Ed25519 private key:

```
signature_bytes = Ed25519_Sign(private_key, chain_hash.encode("utf-8"))
signature_b64   = Base64_Encode(signature_bytes)
```

The signature is 64 bytes (512 bits), encoded as a Base64 ASCII string.

### 5.2 Identity Key

| Property | Value |
|----------|-------|
| Algorithm | Ed25519 (RFC 8032) |
| Private key size | 32 bytes |
| Public key size | 32 bytes |
| Storage format | Raw bytes (not PEM) |
| Public key representation | 64-character lowercase hexadecimal string |
| File permissions | `0600` (owner read/write only) |

### 5.3 Signature File Format

The signature is stored in `session_sig.txt` as a plain text file:

```
chain_hash:{64-char-hex-chain-hash}
signature:{base64-encoded-signature}
```

If signing is unavailable:

```
chain_hash:{64-char-hex-chain-hash}
# Ed25519 signing not available
```

### 5.4 Public Key File Format

The public key is stored in `public_key.pem` as a plain text file:

```
# Ed25519 public key: {64-char-hex-public-key}
```

If no signing key is configured:

```
# No signing key configured
```

### 5.5 Signature is Optional

Implementations MAY produce bundles without Ed25519 signatures. The hash chain provides tamper-evidence independent of the signature. The signature adds identity binding (proof of who produced the bundle).

---

## 6. AIVS Full Bundle Format

### 6.1 Archive Structure

An AIVS Full Bundle is a gzip-compressed tar archive (`.tar.gz`) containing a single directory with five required files:

```
aivs_proof_{session_prefix}_{unix_timestamp}.tar.gz
└── session_proof/
    ├── audit_log.jsonl       # Hash-chained action log
    ├── manifest.json         # Bundle metadata
    ├── session_sig.txt       # Ed25519 signature
    ├── public_key.pem        # Signer's public key
    └── verify.py             # Self-contained verifier (stdlib only)
```

Optional files (included when applicable):

```
    ├── previous_bundle_hash.txt  # SHA-256 of predecessor bundle (scan chain)
    └── merkle_tree.json          # Page-level Merkle tree (crawl proofs)
```

### 6.2 Filename Convention

```
aivs_proof_{session_id[0:8]}_{int(unix_timestamp)}.tar.gz
```

- `session_id[0:8]`: First 8 characters of the session ID.
- `unix_timestamp`: Integer Unix timestamp at export time.

### 6.3 audit_log.jsonl

Newline-delimited JSON (JSONL). Each line is one audit row (Section 4) serialized as a JSON object. Rows MUST be ordered by `id` ascending (chronological order).

### 6.4 manifest.json

A JSON object with the following fields:

```json
{
  "session_id":       "sess-abc123",
  "exported_at":      "2026-03-14T15:30:45Z",
  "action_count":     42,
  "chain_hash":       "a1b2c3d4...",
  "aivs_version":     "1.0",
  "generator":        "Conduit",
  "generator_url":    "https://github.com/bkauto3/Conduit"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | String | Yes | The session identifier. |
| `exported_at` | String | Yes | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`). |
| `action_count` | Integer | Yes | Number of rows in `audit_log.jsonl`. |
| `chain_hash` | String | Yes | 64-character hex chain hash (Section 3.4). |
| `aivs_version` | String | Yes | AIVS specification version (e.g. `"1.0"`). |
| `generator` | String | No | Name of the producing software. |
| `generator_url` | String | No | URL of the producing software. |

Implementations MAY include additional metadata fields in the manifest. Verifiers MUST ignore unrecognized fields.

### 6.5 session_sig.txt

See Section 5.3.

### 6.6 public_key.pem

See Section 5.4.

### 6.7 verify.py

A self-contained Python 3 verification script. Requirements:

- MUST verify the hash chain using only Python 3 standard library (`hashlib`, `json`, `sys`, `pathlib`).
- MAY verify the Ed25519 signature if the `cryptography` library is available.
- MUST exit with code `0` on successful verification.
- MUST exit with code `1` if the hash chain is broken or the signature is invalid.
- MUST print human-readable verification results to stdout.

The embedded verifier is the core differentiator of AIVS: any recipient can verify the bundle by running `python verify.py` with no installation, no network access, and no trust in external services.

### 6.8 Bundle Chaining (optional)

When a session produces multiple sequential bundles (e.g., repeated scans of the same target), each bundle MAY reference its predecessor:

- `previous_bundle_hash.txt`: Contains the SHA-256 hex digest of the prior `.tar.gz` file.
- The `manifest.json` SHOULD include a `"previous_bundle_hash"` field with the same value.

This forms a scan chain: a tamper-evident sequence of bundles where each bundle cryptographically references its predecessor.

### 6.9 Merkle Tree (optional)

For multi-page crawl sessions, implementations MAY include `merkle_tree.json` to enable selective page verification:

```json
{
  "root":       "abc123...",
  "leaf_count": 20,
  "pages": [
    {"url": "https://example.com/", "hash": "def456...", "leaf_index": 0},
    {"url": "https://example.com/about", "hash": "ghi789...", "leaf_index": 1}
  ],
  "tree": [["def456...", "ghi789...", ...], ["parent1...", ...], ["root..."]]
}
```

The Merkle tree is a binary tree over page content hashes. Internal nodes are computed as:

```
parent = SHA-256((left_hash + right_hash).encode("utf-8"))
```

Odd leaves are duplicated (paired with themselves). The root is included in `manifest.json` as `"merkle_root"`.

---

## 7. AIVS-Micro

AIVS-Micro is a minimal single-URL scan attestation. It is the smallest meaningful cryptographic proof — approximately 200 bytes — designed for use cases where a full session bundle is impractical: continuous monitoring, embedded score widgets, API responses, DNS TXT record verification, and cold outreach proof attachments.

### 7.1 Purpose and Use Cases

| Use Case | Why Micro |
|----------|-----------|
| Continuous page monitoring (15-min intervals) | Full bundles at high frequency are too large |
| Embedded score badge / live widget | API response must be lightweight |
| Cold outreach proof attachment | Recipient needs verifiable proof, not a full audit log |
| DNS TXT record verification | Record size limits require minimal format |
| API responses asserting scan freshness | ~200 bytes fits inline in any JSON response |

A third party with the signer's Ed25519 public key can verify from an AIVS-Micro proof:
- The scan happened at the stated time
- The page DOM was in the stated state at that time
- The scan was performed by the declared scanner instance (via scanner version hash)

### 7.2 Micro Proof Format

An AIVS-Micro proof is a JSON object with exactly six fields:

```json
{
  "url":                  "https://example.com",
  "dom_hash":             "sha256:a1b2c3d4e5f6...",
  "timestamp":            "2026-03-14T10:22:01.000000000Z",
  "signature":            "ed25519:BASE64_ENCODED_SIGNATURE",
  "scanner_version_hash": "sha256:def456...",
  "scan_origin":          "local"
}
```

### 7.3 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | String | Yes | The URL that was scanned. |
| `dom_hash` | String | Yes | SHA-256 of the page DOM content, prefixed with `"sha256:"`. |
| `timestamp` | String | Yes | ISO 8601 UTC timestamp with nanosecond precision (`YYYY-MM-DDTHH:MM:SS.nnnnnnnnnZ`). |
| `signature` | String | Yes | Ed25519 signature over the canonical payload (Section 7.4), prefixed with `"ed25519:"` and Base64-encoded. Value is `"unsigned"` if no identity key is available. |
| `scanner_version_hash` | String | Yes | SHA-256 of the scanner implementation file, prefixed with `"sha256:"`. Binds the proof to a specific code version. |
| `scan_origin` | String | Yes | Where the scan originated. Implementations SHOULD use `"local"` for on-device scans. |

### 7.4 Canonical Payload for Signing

The Ed25519 signature is computed over the following pipe-delimited string, encoded as UTF-8:

```
{url}|{dom_hash}|{timestamp}|{scanner_version_hash}|{scan_origin}
```

All fields are used verbatim (including the `"sha256:"` prefix on `dom_hash` and `scanner_version_hash`).

### 7.5 Micro Proof Verification

```
Input: micro_proof JSON object, signer's Ed25519 public key (hex)

1. Reconstruct canonical payload:
   payload = "{url}|{dom_hash}|{timestamp}|{scanner_version_hash}|{scan_origin}"

2. Decode signature:
   sig_b64 = micro_proof["signature"].removeprefix("ed25519:")
   sig_bytes = Base64_Decode(sig_b64)

3. Verify:
   Ed25519_Verify(public_key, sig_bytes, payload.encode("utf-8"))

4. If verification succeeds: PASS
5. If verification fails: FAIL
6. If signature == "unsigned": SKIP (no identity binding)
```

### 7.6 Relationship to Full Bundle

AIVS-Micro and AIVS Full Bundles are complementary, not alternatives:

| Property | AIVS Full Bundle | AIVS-Micro |
|----------|-----------------|------------|
| Contains | Complete action-by-action log | Single-URL scan attestation only |
| Size | Variable (scales with session length) | ~200 bytes |
| Verifier | Embedded `verify.py` (stdlib only) | One Ed25519 verify call |
| Frequency | One per agent session | Can be generated every scan interval |
| Use case | Legal evidence, detailed audit, compliance filing | Monitoring, badges, API responses, cold outreach |
| Offline verification | Yes (embedded verifier) | Yes (single crypto operation) |

A single agent session MAY produce both: a full bundle for the complete audit trail, and one or more micro proofs for individual URLs visited during that session.

---

## 8. Verification Algorithm

### 8.1 Hash Chain Verification (REQUIRED, stdlib only)

```
Input: audit_log.jsonl
Output: PASS or FAIL with row number

prev_hash = ""
for each row in audit_log.jsonl (ordered by id):
    expected = SHA-256(
        "{row.id}:{row.session_id}:{row.action_type}:"
        "{row.tool_name}:{row.cost_cents}:{row.timestamp}:{prev_hash}"
    )
    if row.row_hash != expected:
        FAIL at row.id
    prev_hash = row.row_hash

PASS: all {N} rows verified
```

### 8.2 Ed25519 Signature Verification (OPTIONAL, requires `cryptography`)

```
Input: session_sig.txt, public_key.pem
Output: PASS, FAIL, or SKIP

1. Parse chain_hash and signature from session_sig.txt
2. Parse public key hex from public_key.pem
3. If public key is all zeros ("0" * 64), SKIP
4. Reconstruct Ed25519PublicKey from raw bytes
5. Verify: Ed25519_Verify(public_key, signature, chain_hash.encode("utf-8"))
6. If verification succeeds: PASS
7. If verification fails: FAIL (exit 1)
8. If cryptography library unavailable: SKIP with notice
```

### 8.3 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Hash chain verified. Signature verified (if present and library available). |
| `1` | Hash chain broken OR signature invalid. |

---

## 9. Security Considerations

### 9.1 What AIVS Proves

- **Integrity:** The sequence of actions has not been modified since the bundle was created.
- **Completeness:** No actions have been inserted or deleted from the chain.
- **Ordering:** Actions occurred in the recorded sequence.
- **Identity** (with signature): The bundle was produced by the holder of a specific Ed25519 private key.
- **Code provenance** (eval actions): The exact JavaScript source that executed is recorded verbatim.

### 9.2 What AIVS Does NOT Prove

- **Truthfulness:** AIVS does not prove that the recorded inputs/outputs actually occurred. A malicious agent could fabricate actions and produce a valid chain.
- **Timeliness:** Timestamps are self-reported. AIVS does not include external time attestation (e.g., RFC 3161). Implementations requiring trusted timestamps SHOULD layer RFC 3161 on top.
- **Key authenticity:** AIVS does not include a PKI or certificate chain. The public key in the bundle is self-asserted. Implementations requiring key authenticity SHOULD use a separate trust registry or Verifiable Credentials.
- **Non-repudiation:** Without a trusted timestamp and key binding to a real-world identity, AIVS provides limited non-repudiation. The signer could claim key compromise.

### 9.3 Threat Model

| Threat | Mitigated By |
|--------|-------------|
| Post-hoc modification of action log | Hash chain (Section 3) |
| Deletion of actions | Sequential `prev_hash` chaining |
| Insertion of actions | Sequential `row_id` + `prev_hash` chaining |
| Reordering of actions | `prev_hash` depends on previous `row_hash` |
| Impersonation of agent identity | Ed25519 signature (Section 5) |
| Exposure of sensitive inputs | Mandatory redaction (Section 4.2) |
| Replay of old proof bundle | `session_id` + `timestamp` provide uniqueness |
| Unknown JS code execution | Verbatim JS source storage (Section 4.4) |
| Micro proof tampering | Ed25519 over all six fields' canonical payload |

### 9.4 Recommended Extensions for High-Assurance Use

For use cases requiring stronger guarantees (legal evidence, financial compliance, regulatory submission):

1. **RFC 3161 Timestamps:** Submit the chain hash to an RFC 3161 Time Stamping Authority.
2. **SCITT Registration:** Register the signed chain hash as a SCITT transparent statement.
3. **Verifiable Credentials:** Wrap the proof bundle metadata as a W3C Verifiable Credential.
4. **Merkle Tree Aggregation:** For multi-session audits, aggregate chain hashes into a Merkle tree.

---

## 10. IANA Considerations

This specification defines no new IANA registries. The following existing standards are referenced:

- SHA-256: FIPS 180-4
- Ed25519: RFC 8032
- JSON: RFC 8259
- JSONL: Newline-delimited JSON (de facto standard)
- gzip: RFC 1952
- tar: POSIX.1-2001

---

## 11. References

### Normative

- [RFC 8032] Josefsson, S. and I. Liusvaara, "Edwards-Curve Digital Signature Algorithm (EdDSA)", RFC 8032, January 2017.
- [FIPS 180-4] National Institute of Standards and Technology, "Secure Hash Standard (SHS)", FIPS PUB 180-4, August 2015.
- [RFC 8259] Bray, T., "The JavaScript Object Notation (JSON) Data Interchange Format", RFC 8259, December 2017.

### Informative

- [RFC 6962] Laurie, B., Langley, A., and E. Kasper, "Certificate Transparency", RFC 6962, June 2013.
- [RFC 3161] Adams, C., et al., "Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)", RFC 3161, August 2001.
- [EU AI Act] Regulation (EU) 2024/1689 of the European Parliament, Article 19.
- [ISO 42001] ISO/IEC 42001:2023, Information technology -- Artificial intelligence -- Management system.
- [SCITT] draft-ietf-scitt-architecture-22, Supply Chain Integrity, Transparency, and Trust (SCITT) Architecture.
- [W3C VC] W3C Verifiable Credentials Data Model v2.0, W3C Recommendation, May 2025.
- [C2PA] Coalition for Content Provenance and Authenticity, C2PA Technical Specification v2.2.
- [VAP] draft-ailex-vap-legal-ai-provenance-03, Verifiable AI Provenance Framework and Legal AI Profile, March 2026.
- [AAR] Agent Action Receipts v1.0, https://github.com/Cyberweasel777/agent-action-receipt-spec.

---

## Appendix A: Reference Implementation

The reference implementation is located in the Conduit repository:

| Component | File |
|-----------|------|
| Hash chain (audit log) | `audit.py` |
| Full bundle export | `tools/conduit_proof.py` — `ConduitProof.export()` |
| AIVS-Micro export | `tools/conduit_proof.py` — `ConduitProof.export_micro()` |
| Embedded verifier | `VERIFY_PY` constant in `tools/conduit_proof.py` |
| Ed25519 identity | `tools/conduit_bridge.py` — `ConduitIdentity` |

**Full bundle:**

```python
from tools.conduit_proof import ConduitProof

proof = ConduitProof(audit_log, session_id, public_key_pem, identity)
result = proof.export(output_dir="/path/to/output")
# Returns: {"success": True, "path": "...", "action_count": N, "chain_hash": "..."}
```

**AIVS-Micro:**

```python
micro = proof.export_micro(
    url="https://example.com",
    dom_hash="a1b2c3d4...",
    scan_origin="local",
)
# Returns: {"success": True, "micro_proof": {...}, "payload_signed": "..."}
```

---

## Appendix B: Example verify.py Output

```
$ cd session_proof && python verify.py

Chain OK: 8 actions verified
Signature OK: Ed25519 signature verified
Session: sess-abc123
Exported: 2026-03-14T15:30:45Z
Actions: 8

VERIFIED: This session proof is intact and unmodified.
```

---

## Appendix C: Comparison with Related Formats

| Property | AIVS Full | AIVS-Micro | VAP/LAP | AAR | C2PA | SCITT |
|----------|-----------|------------|---------|-----|------|-------|
| Scope | Session (multi-action) | Single URL scan | AI model decision provenance | Single action | Media asset lifecycle | Supply chain statement |
| Self-verifiable | Yes (embedded verify.py) | Yes (one Ed25519 call) | No (HTTP API required) | No | No (requires SDK) | No (requires transparency service) |
| Offline verification | Yes | Yes | No | Yes | Partial | No |
| Zero dependencies | Yes (stdlib Python) | Yes (one crypto call) | No | No (requires SDK) | No (requires SDK) | No |
| Hash chain | SHA-256 linear chain | N/A (single proof) | SHA-256 per-event + Merkle | No (individual signatures) | Hash binding | Merkle tree |
| Signature | Ed25519 (optional) | Ed25519 (optional) | Ed25519 (required) | Ed25519 (required) | X.509 certificates | COSE signatures |
| Portable archive | .tar.gz | JSON object | .zip | JSON | JUMBF | COSE |
| Interactive agent sessions | Yes | Yes | No | Yes | No | No |
| JS source in chain | Yes (eval actions) | No | No | No | No | No |
| Domain | Any agent action | Any URL scan | Legal/regulated AI | Any agent action | Media content | Supply chain artifacts |

---

## Changelog

### v1.0 (2026-03-14)
- Renamed from CSPF (Conduit Session Proof Format) to AIVS (Agentic Integrity Verification Standard).
- Added Section 7: AIVS-Micro — minimal 6-field scan attestation for continuous monitoring.
- Added Section 4.4: JavaScript source storage semantics for eval actions.
- Added Section 6.8: Bundle chaining (scan chain) specification.
- Added Section 6.9: Merkle tree specification for crawl proofs.
- Added VAP/LAP to Section 1.3 relationship table and Appendix C comparison.
- Updated `aivs_version` field in manifest.json schema.
- Updated filename convention from `conduit_proof_*` to `aivs_proof_*`.

### v0.1 (2026-03-12)
- Initial specification as CSPF v1.0.
