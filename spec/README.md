# AI Visibility Verification Standard (AIVS)

**The open standard for cryptographically verifiable AI agent session proofs.**

---

## What Is AIVS?

AIVS defines two things:

**1. AIVS Full Bundle** — a self-verifiable `.tar.gz` archive that proves exactly what an AI agent did during a session: every URL navigated, every click, every form filled, every piece of JavaScript executed. The bundle contains a SHA-256 hash-chained audit log, an Ed25519 signature, and an embedded `verify.py` script. Anyone can verify it with `python verify.py` — no installation, no network, no trust in external services.

**2. AIVS-Micro** — a minimal 6-field JSON proof (~200 bytes) attesting that a specific URL was scanned at a specific time by a specific scanner instance. Designed for continuous monitoring, live score widgets, API responses, and situations where a full session bundle is impractical.

---

## The Core Differentiator

Every other audit format (SCITT, C2PA, VAP, OpenSSF OMS) requires external infrastructure to verify:

- SCITT requires a Transparency Service
- C2PA requires C2PA tooling
- VAP requires HTTP verification endpoints
- OpenSSF OMS requires Sigstore

**AIVS bundles carry their own verifier.** Extract the archive, run one command:

```bash
tar -xzf aivs_proof_abc12345_1741953000.tar.gz
cd session_proof
python verify.py
```

Output:

```
Chain OK: 42 actions verified
Signature OK: Ed25519 signature verified
Session: sess-abc123
Exported: 2026-03-14T15:30:45Z
Actions: 42

VERIFIED: This session proof is intact and unmodified.
```

No dependencies. No network. No accounts.

---

## Why It Matters

AI agents are performing consequential actions — browsing websites, submitting forms, executing code, making recommendations. There is currently no standard way to prove what an agent did, when it did it, and that the record hasn't been tampered with.

Regulatory frameworks mandate audit trails but prescribe no formats:
- EU AI Act Article 19 requires logs for high-risk AI systems
- ISO/IEC 42001:2023 requires event logging
- NIST AI RMF requires documentation and traceability

AIVS is a concrete format that satisfies these requirements.

---

## Specification

**[AIVS.md](./AIVS.md)** — the full specification

Sections:
1. Motivation and design goals
2. Terminology
3. Hash chain specification (SHA-256 row hash + chain hash)
4. Audit row schema (including JavaScript source storage)
5. Ed25519 signature format
6. AIVS Full Bundle format (archive structure, manifest, optional chaining + Merkle tree)
7. AIVS-Micro format (6-field lightweight attestation)
8. Verification algorithm (with pseudocode)
9. Security considerations (what AIVS proves and does not prove)
10. References

---

## Quick Reference

### Hash Chain

Each audit row hashes itself plus the previous row:

```
row_hash = SHA-256(
    "{row_id}:{session_id}:{action_type}:{tool_name}:{cost_cents}:{timestamp}:{prev_hash}"
)
```

Modifying any row invalidates every subsequent hash — insertion, deletion, and reordering are all detectable.

### Full Bundle Structure

```
aivs_proof_{session_id[0:8]}_{unix_timestamp}.tar.gz
└── session_proof/
    ├── audit_log.jsonl       # Hash-chained JSONL action log
    ├── manifest.json         # Session metadata + chain hash
    ├── session_sig.txt       # Ed25519 signature over chain hash
    ├── public_key.pem        # Signer's public key
    └── verify.py             # stdlib-only self-verifier
```

### AIVS-Micro Structure

```json
{
  "url":                  "https://example.com",
  "dom_hash":             "sha256:a1b2c3...",
  "timestamp":            "2026-03-14T10:22:01.000000000Z",
  "signature":            "ed25519:BASE64...",
  "scanner_version_hash": "sha256:def456...",
  "scan_origin":          "local"
}
```

Signed over: `url|dom_hash|timestamp|scanner_version_hash|scan_origin`

---

## Reference Implementation

The reference implementation is [Conduit](https://github.com/bkauto3/Conduit) — a headless browser engine with a cryptographic audit layer.

| Component | File |
|-----------|------|
| Hash chain | `audit.py` |
| Full bundle export | `tools/conduit_proof.py` → `ConduitProof.export()` |
| AIVS-Micro export | `tools/conduit_proof.py` → `ConduitProof.export_micro()` |
| Ed25519 identity | `tools/conduit_bridge.py` → `ConduitIdentity` |

---

## Relationship to Other Standards

AIVS is complementary to existing work, not competitive with it:

| Standard | Scope | Relationship to AIVS |
|----------|-------|----------------------|
| IETF SCITT | Supply chain transparency registry | AIVS bundles could be registered as SCITT signed statements for external anchoring |
| W3C Verifiable Credentials 2.0 | Identity credential issuance | AIVS bundle metadata could be wrapped as a VC for agent identity binding |
| VAP (draft-ailex-vap-legal-ai-provenance) | AI model decision provenance for legal/regulated industries | Different scope: VAP covers model decisions for regulatory filing; AIVS covers interactive agent sessions with self-contained verification |
| C2PA | Media content provenance | Same manifest-chain concept applied to agent actions instead of media files |
| EU AI Act Article 19 | Audit log mandate | AIVS is a concrete format that satisfies Article 19's content requirements |

---

## Status

- **Specification:** v1.0 Draft
- **Reference implementation:** Conduit v0.2.1+
- **License:** Apache 2.0

---

## Contributing

This specification is maintained in the [Conduit repository](https://github.com/bkauto3/Conduit) under `spec/`.

To propose changes: open an issue or pull request. All substantive changes should update the Changelog in `AIVS.md`.
