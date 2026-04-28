# Conduit Session Proof Format (CSPF) v1.0

**A self-verifiable, portable format for cryptographic proof of AI agent sessions.**

|Field|Value|
|-|-|
|**Version**|1.0|
|**Status**|Draft|
|**Date**|2026-03-12|
|**License**|Apache 2.0|
|**Authors**|bkauto3|
|**Repository**|https://github.com/bkauto3/Conduit|
|**Reference Implementation**|`tools/conduit\_proof.py`|

\---

## Abstract

The Conduit Session Proof Format (CSPF) defines a portable, self-verifiable archive format for cryptographic proof of AI agent sessions. A CSPF bundle is a gzip-compressed tar archive containing a SHA-256 hash-chained audit log, an Ed25519 digital signature over the chain, a machine-readable manifest, and an embedded verification script that requires only Python 3 standard library to execute.

CSPF enables any party to independently verify that:

1. Every action in the session is accounted for and unmodified (hash chain integrity)
2. No actions have been inserted, deleted, or reordered (sequential chaining)
3. The session was produced by a specific cryptographic identity (Ed25519 signature)
4. All of the above can be verified offline, without network access, and without installing any software beyond Python 3 (self-verification)

\---

## 1\. Motivation

### 1.1 Problem Statement

AI agents increasingly perform consequential actions on behalf of humans: navigating websites, filling forms, executing JavaScript, extracting data, and making purchases. Existing observability platforms (OpenTelemetry, LangSmith, Langfuse) log these actions but provide no cryptographic guarantees that the logs are complete, unmodified, or authentic.

Regulatory frameworks mandate audit trails but do not prescribe formats:

* **EU AI Act Article 19** requires automatically generated logs for high-risk AI systems but specifies no format.
* **ISO/IEC 42001:2023 Annex A.6.2.8** requires event logging but defines no data structure.
* **NIST AI RMF** requires documentation and audit trails but deliberately avoids prescribing formats.

This creates a gap: organizations that must prove what their AI agents did have no standard way to produce, exchange, or verify that proof.

### 1.2 Design Goals

|Goal|Rationale|
|-|-|
|**Self-verifiable**|Proof bundles must be verifiable without contacting any server, blockchain, or authority.|
|**Portable**|A single file that can be emailed, stored, or submitted to any system.|
|**Tamper-evident**|Modifying any action in the log must be detectable.|
|**Zero dependencies**|Verification must require only Python 3 standard library. Signature verification MAY use the `cryptography` library.|
|**Session-level**|Covers an entire session (sequence of actions), not individual action receipts.|
|**Domain-agnostic**|Applicable to any AI agent performing any type of action, not limited to commerce, trading, or specific tools.|

### 1.3 Relationship to Existing Standards

CSPF is complementary to, not competitive with, existing work:

|Standard|Scope|CSPF Relationship|
|-|-|-|
|W3C Verifiable Credentials 2.0|Identity claims|CSPF could be wrapped as a VC `credentialSubject`|
|IETF SCITT (draft-ietf-scitt-architecture)|Supply chain transparency logs|CSPF bundles could be registered as SCITT signed statements|
|C2PA v2.2|Media asset provenance|CSPF applies the same manifest-chain concept to agent actions|
|Agent Action Receipts (AAR)|Individual action receipts|CSPF provides session-level aggregation of action-level records|
|Certificate Transparency (RFC 6962)|Append-only Merkle logs|CSPF's hash chain is a simplified linear variant; Merkle tree extension is possible|
|EU AI Act Article 19|Audit log requirements|CSPF is a concrete format that satisfies Article 19's content requirements|

\---

## 2\. Terminology

|Term|Definition|
|-|-|
|**Session**|A bounded sequence of actions performed by a single AI agent instance, identified by a `session\_id`.|
|**Action**|A single operation performed by the agent (e.g., navigate to URL, click element, execute JavaScript).|
|**Audit Row**|A JSON object recording one action with its inputs, outputs, timestamp, cost, and hash chain fields.|
|**Hash Chain**|A sequence of audit rows where each row's hash depends on the previous row's hash, forming a tamper-evident chain.|
|**Chain Hash**|A single SHA-256 hash computed over all row hashes, serving as a fingerprint of the entire session.|
|**Proof Bundle**|A `.tar.gz` archive containing the audit log, signature, manifest, public key, and verifier script.|
|**Identity Key**|An Ed25519 keypair used to sign the chain hash.|

\---

## 3\. Hash Chain Specification

### 3.1 Row Hash Computation

Each audit row is identified by a deterministic SHA-256 hash. The hash input is a colon-separated string of exactly seven fields in this order:

```
row\_hash = SHA-256(
    "{row\_id}:{session\_id}:{action\_type}:{tool\_name}:{cost\_cents}:{timestamp}:{prev\_hash}"
)
```

The hash is represented as a lowercase hexadecimal string (64 characters).

### 3.2 Field Definitions

|Field|Type|Description|
|-|-|-|
|`row\_id`|Integer|Monotonically increasing row identifier (1-indexed).|
|`session\_id`|String|Unique identifier for the session.|
|`action\_type`|String|Classification of the action. Default: `"tool\_call"`.|
|`tool\_name`|String|Namespaced tool identifier (e.g., `"browser.navigate"`, `"browser.eval"`).|
|`cost\_cents`|Integer|Cost of the action in cents. `0` for free actions.|
|`timestamp`|Float|Unix timestamp with fractional seconds (e.g., `1710252645.123456`).|
|`prev\_hash`|String|The `row\_hash` of the immediately preceding row. Empty string `""` for the first row.|

### 3.3 Chain Integrity Property

For a chain of N rows, modifying any field of row K invalidates `row\_hash\[K]`, which invalidates `prev\_hash\[K+1]`, which invalidates `row\_hash\[K+1]`, and so on through `row\_hash\[N]`. This means:

* **Insertion** of a row is detectable (changes all subsequent `row\_id` values and hashes).
* **Deletion** of a row is detectable (breaks the `prev\_hash` link).
* **Reordering** of rows is detectable (changes `prev\_hash` linkage).
* **Modification** of any field is detectable (changes the affected row's hash and all subsequent hashes).

### 3.4 Chain Hash Computation

The chain hash is a single SHA-256 hash that fingerprints the entire session:

```
If rows is empty:
    chain\_hash = SHA-256(b"empty")
Else:
    combined = concatenate(row\_hash\[1], row\_hash\[2], ..., row\_hash\[N])
    chain\_hash = SHA-256(combined.encode("utf-8"))
```

The chain hash is represented as a lowercase hexadecimal string (64 characters).

\---

## 4\. Audit Row Schema

Each row in the audit log is a JSON object with the following fields:

```json
{
  "id":           1,
  "session\_id":   "sess-abc123",
  "action\_type":  "tool\_call",
  "tool\_name":    "browser.navigate",
  "inputs\_json":  "{\\"url\\": \\"https://example.com\\"}",
  "outputs\_json": "{\\"title\\": \\"Example Domain\\", \\"url\\": \\"https://example.com/\\"}",
  "cost\_cents":   0,
  "error":        "",
  "timestamp":    1710252645.123456,
  "prev\_hash":    "",
  "row\_hash":     "a1b2c3d4e5f6..."
}
```

### 4.1 Field Specifications

|Field|Type|Required|Description|
|-|-|-|-|
|`id`|Integer|Yes|Row identifier, 1-indexed, monotonically increasing.|
|`session\_id`|String|Yes|Session identifier.|
|`action\_type`|String|Yes|Action classification.|
|`tool\_name`|String|Yes|Namespaced tool identifier.|
|`inputs\_json`|String|Yes|JSON-encoded action inputs. Sensitive keys MUST be redacted (see Section 4.2).|
|`outputs\_json`|String|Yes|JSON-encoded action outputs. MAY be truncated.|
|`cost\_cents`|Integer|Yes|Action cost in cents.|
|`error`|String|Yes|Error message if the action failed; empty string if successful.|
|`timestamp`|Float|Yes|Unix timestamp with fractional seconds.|
|`prev\_hash`|String|Yes|Previous row's `row\_hash`. Empty string for the first row.|
|`row\_hash`|String|Yes|This row's computed SHA-256 hash (see Section 3.1).|

### 4.2 Sensitive Input Redaction

Before computing the row hash, implementations MUST redact values for input keys matching any of the following case-insensitive substrings:

```
password, token, api\_key, secret, key, authorization,
bearer, credential, passwd, passphrase
```

Redacted values MUST be replaced with the string `"\[REDACTED]"`.

### 4.3 Output Truncation

Implementations MAY truncate `outputs\_json` to a maximum length. The reference implementation truncates to 2000 characters. Truncation does not affect the hash chain because `outputs\_json` is not included in the row hash computation.

> \*\*Note:\*\* Only the seven fields listed in Section 3.1 are included in the hash computation. `inputs\_json`, `outputs\_json`, and `error` are included in the audit log for informational purposes but are NOT part of the hash chain. This is intentional: it allows output truncation and input redaction without breaking the chain.

\---

## 5\. Ed25519 Signature

### 5.1 Signing

The chain hash (Section 3.4) is signed using an Ed25519 private key:

```
signature\_bytes = Ed25519\_Sign(private\_key, chain\_hash.encode("utf-8"))
signature\_b64   = Base64\_Encode(signature\_bytes)
```

The signature is 64 bytes (512 bits), encoded as a Base64 ASCII string.

### 5.2 Identity Key

|Property|Value|
|-|-|
|Algorithm|Ed25519 (RFC 8032)|
|Private key size|32 bytes|
|Public key size|32 bytes|
|Storage format|Raw bytes (not PEM)|
|Public key representation|64-character lowercase hexadecimal string|
|File permissions|`0600` (owner read/write only)|

### 5.3 Signature File Format

The signature is stored in `session\_sig.txt` as a plain text file:

```
chain\_hash:{64-char-hex-chain-hash}
signature:{base64-encoded-signature}
```

If signing is unavailable:

```
chain\_hash:{64-char-hex-chain-hash}
# Ed25519 signing not available
```

### 5.4 Public Key File Format

The public key is stored in `public\_key.pem` as a plain text file:

```
# Ed25519 public key: {64-char-hex-public-key}
```

If no signing key is configured:

```
# No signing key configured
```

### 5.5 Signature is Optional

Implementations MAY produce bundles without Ed25519 signatures. The hash chain provides tamper-evidence independent of the signature. The signature adds identity binding (proof of who produced the bundle).

\---

## 6\. Proof Bundle Format

### 6.1 Archive Structure

A CSPF proof bundle is a gzip-compressed tar archive (`.tar.gz`) containing a single directory with five files:

```
conduit\_proof\_{session\_prefix}\_{unix\_timestamp}.tar.gz
└── session\_proof/
    ├── audit\_log.jsonl       # Hash-chained action log
    ├── manifest.json         # Bundle metadata
    ├── session\_sig.txt       # Ed25519 signature
    ├── public\_key.pem        # Signer's public key
    └── verify.py             # Self-contained verifier (stdlib only)
```

### 6.2 Filename Convention

```
conduit\_proof\_{session\_id\[0:8]}\_{int(unix\_timestamp)}.tar.gz
```

* `session\_id\[0:8]`: First 8 characters of the session ID.
* `unix\_timestamp`: Integer Unix timestamp at export time.

### 6.3 audit\_log.jsonl

Newline-delimited JSON (JSONL). Each line is one audit row (Section 4) serialized as a JSON object. Rows MUST be ordered by `id` ascending (chronological order).

### 6.4 manifest.json

A JSON object with the following fields:

```json
{
  "session\_id":       "sess-abc123",
  "exported\_at":      "2026-03-12T15:30:45Z",
  "action\_count":     42,
  "chain\_hash":       "a1b2c3d4...",
  "conduit\_version":  "0.2.0",
  "generator":        "Conduit",
  "generator\_url":    "https://github.com/bkauto3/Conduit"
}
```

|Field|Type|Required|Description|
|-|-|-|-|
|`session\_id`|String|Yes|The session identifier.|
|`exported\_at`|String|Yes|ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`).|
|`action\_count`|Integer|Yes|Number of rows in `audit\_log.jsonl`.|
|`chain\_hash`|String|Yes|64-character hex chain hash (Section 3.4).|
|`conduit\_version`|String|No|Version of the producing software.|
|`generator`|String|No|Name of the producing software.|
|`generator\_url`|String|No|URL of the producing software.|

Implementations MAY include additional metadata fields in the manifest. Verifiers MUST ignore unrecognized fields.

### 6.5 session\_sig.txt

See Section 5.3.

### 6.6 public\_key.pem

See Section 5.4.

### 6.7 verify.py

A self-contained Python 3 verification script. Requirements:

* MUST verify the hash chain using only Python 3 standard library (`hashlib`, `json`, `sys`, `pathlib`).
* MAY verify the Ed25519 signature if the `cryptography` library is available.
* MUST exit with code `0` on successful verification.
* MUST exit with code `1` if the hash chain is broken or the signature is invalid.
* MUST print human-readable verification results to stdout.

The embedded verifier is the core differentiator of CSPF: any recipient can verify the bundle by running `python verify.py` with no installation, no network access, and no trust in external services.

\---

## 7\. Verification Algorithm

### 7.1 Hash Chain Verification (REQUIRED, stdlib only)

```
Input: audit\_log.jsonl
Output: PASS or FAIL with row number

prev\_hash = ""
for each row in audit\_log.jsonl (ordered by id):
    expected = SHA-256(
        "{row.id}:{row.session\_id}:{row.action\_type}:"
        "{row.tool\_name}:{row.cost\_cents}:{row.timestamp}:{prev\_hash}"
    )
    if row.row\_hash != expected:
        FAIL at row.id
    prev\_hash = row.row\_hash

PASS: all {N} rows verified
```

### 7.2 Ed25519 Signature Verification (OPTIONAL, requires `cryptography`)

```
Input: session\_sig.txt, public\_key.pem
Output: PASS, FAIL, or SKIP

1. Parse chain\_hash and signature from session\_sig.txt
2. Parse public key hex from public\_key.pem
3. If public key is all zeros ("0" \* 64), SKIP
4. Reconstruct Ed25519PublicKey from raw bytes
5. Verify: Ed25519\_Verify(public\_key, signature, chain\_hash.encode("utf-8"))
6. If verification succeeds: PASS
7. If verification fails: FAIL (exit 1)
8. If cryptography library unavailable: SKIP with notice
```

### 7.3 Exit Codes

|Code|Meaning|
|-|-|
|`0`|Hash chain verified. Signature verified (if present and library available).|
|`1`|Hash chain broken OR signature invalid.|

\---

## 8\. Security Considerations

### 8.1 What CSPF Proves

* **Integrity:** The sequence of actions has not been modified since the bundle was created.
* **Completeness:** No actions have been inserted or deleted from the chain.
* **Ordering:** Actions occurred in the recorded sequence.
* **Identity** (with signature): The bundle was produced by the holder of a specific Ed25519 private key.

### 8.2 What CSPF Does NOT Prove

* **Truthfulness:** CSPF does not prove that the recorded inputs/outputs actually occurred. A malicious agent could fabricate actions and produce a valid chain.
* **Timeliness:** Timestamps are self-reported. CSPF does not include external time attestation (e.g., RFC 3161). Implementations requiring trusted timestamps SHOULD layer RFC 3161 on top.
* **Key authenticity:** CSPF does not include a PKI or certificate chain. The public key in the bundle is self-asserted. Implementations requiring key authenticity SHOULD use a separate trust registry or Verifiable Credentials.
* **Non-repudiation:** Without a trusted timestamp and key binding to a real-world identity, CSPF provides limited non-repudiation. The signer could claim key compromise.

### 8.3 Threat Model

|Threat|Mitigated By|
|-|-|
|Post-hoc modification of action log|Hash chain (Section 3)|
|Deletion of actions|Sequential `prev\_hash` chaining|
|Insertion of actions|Sequential `row\_id` + `prev\_hash` chaining|
|Reordering of actions|`prev\_hash` depends on previous `row\_hash`|
|Impersonation of agent identity|Ed25519 signature (Section 5)|
|Exposure of sensitive inputs|Mandatory redaction (Section 4.2)|
|Replay of old proof bundle|`session\_id` + `timestamp` provide uniqueness|

### 8.4 Recommended Extensions for High-Assurance Use

For use cases requiring stronger guarantees (legal evidence, financial compliance, regulatory submission):

1. **RFC 3161 Timestamps:** Submit the chain hash to an RFC 3161 Time Stamping Authority.
2. **SCITT Registration:** Register the signed chain hash as a SCITT transparent statement.
3. **Verifiable Credentials:** Wrap the proof bundle metadata as a W3C Verifiable Credential.
4. **Merkle Tree Aggregation:** For multi-session audits, aggregate chain hashes into a Merkle tree.

\---

## 9\. IANA Considerations

This specification defines no new IANA registries. The following existing standards are referenced:

* SHA-256: FIPS 180-4
* Ed25519: RFC 8032
* JSON: RFC 8259
* JSONL: Newline-delimited JSON (de facto standard)
* gzip: RFC 1952
* tar: POSIX.1-2001

\---

## 10\. References

### Normative

* \[RFC 8032] Josefsson, S. and I. Liusvaara, "Edwards-Curve Digital Signature Algorithm (EdDSA)", RFC 8032, January 2017.
* \[FIPS 180-4] National Institute of Standards and Technology, "Secure Hash Standard (SHS)", FIPS PUB 180-4, August 2015.
* \[RFC 8259] Bray, T., "The JavaScript Object Notation (JSON) Data Interchange Format", RFC 8259, December 2017.

### Informative

* \[RFC 6962] Laurie, B., Langley, A., and E. Kasper, "Certificate Transparency", RFC 6962, June 2013.
* \[RFC 3161] Adams, C., et al., "Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)", RFC 3161, August 2001.
* \[EU AI Act] Regulation (EU) 2024/1689 of the European Parliament, Article 19.
* \[ISO 42001] ISO/IEC 42001:2023, Information technology -- Artificial intelligence -- Management system.
* \[SCITT] draft-ietf-scitt-architecture-22, Supply Chain Integrity, Transparency, and Trust (SCITT) Architecture.
* \[W3C VC] W3C Verifiable Credentials Data Model v2.0, W3C Recommendation, May 2025.
* \[C2PA] Coalition for Content Provenance and Authenticity, C2PA Technical Specification v2.2.
* \[AAR] Agent Action Receipts v1.0, https://github.com/Cyberweasel777/agent-action-receipt-spec.

\---

## Appendix A: Reference Implementation

The reference implementation is located at `tools/conduit\_proof.py` in the Conduit repository. Key entry point:

```python
from tools.conduit\_proof import ConduitProof

proof = ConduitProof(audit\_log, session\_id, public\_key\_pem, identity)
result = proof.export(output\_dir="/path/to/output")
# Returns: {"success": True, "path": "...", "action\_count": N, "chain\_hash": "..."}
```

## Appendix B: Example verify.py Output

```
$ cd session\_proof \&\& python verify.py

Chain OK: 8 actions verified
Signature OK: Ed25519 signature verified
Session: cold-proof-abc123
Exported: 2026-03-12T15:30:45Z
Actions: 8

VERIFIED: This session proof is intact and unmodified.
```

## Appendix C: Comparison with Related Formats

|Property|CSPF|AAR|C2PA|SCITT|
|-|-|-|-|-|
|Scope|Session (multi-action)|Single action|Media asset lifecycle|Supply chain statement|
|Self-verifiable|Yes (embedded verify.py)|No|No (requires SDK)|No (requires transparency service)|
|Offline verification|Yes|Yes|Partial|No|
|Zero dependencies|Yes (stdlib Python)|No (requires SDK)|No (requires SDK)|No|
|Hash chain|SHA-256 linear chain|No (individual signatures)|Hash binding|Merkle tree|
|Signature|Ed25519 (optional)|Ed25519 (required)|X.509 certificates|COSE signatures|
|Portable archive|.tar.gz|JSON|JUMBF|COSE|
|Domain|Any agent action|Any agent action|Media content|Supply chain artifacts|

\---

## Changelog

### v1.0 (2026-03-12)

* Initial specification.

