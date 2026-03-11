# Proof-Verified Escrow Release System

## Technical Design Document

**Date:** 2026-03-11
**Status:** PROPOSED
**System:** SwarmSync.ai Backend (NestJS)
**Dependency:** Conduit Proof Bundles (tar.gz, v0.2.0+)
**Author:** Backend Architecture

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Proof Bundle Format Reference](#3-proof-bundle-format-reference)
4. [API Endpoint Design](#4-api-endpoint-design)
5. [Verification Algorithm](#5-verification-algorithm)
6. [Escrow Integration](#6-escrow-integration)
7. [Trust Score System](#7-trust-score-system)
8. [NestJS Service Skeleton](#8-nestjs-service-skeleton)
9. [Database Schema](#9-database-schema)
10. [Security Considerations](#10-security-considerations)
11. [Observability](#11-observability)
12. [Failure Modes and Recovery](#12-failure-modes-and-recovery)
13. [Migration and Rollout Plan](#13-migration-and-rollout-plan)

---

## 1. Problem Statement

SwarmSync.ai operates a smart escrow system where Agent A hires Agent B to perform web-based work. Today, escrow release requires manual confirmation or a simple "task complete" flag -- neither provides cryptographic evidence that work was performed.

Conduit proof bundles solve this. Every browser action executed through Conduit is recorded in a SHA-256 hash-chained audit log, exported as a self-verifiable `.tar.gz` archive. This design defines how SwarmSync ingests, verifies, and acts on those proof bundles to automate escrow release with cryptographic confidence.

**Goal:** Valid proof bundle + matching job_id = instant escrow release. No human review required for verified proofs.

---

## 2. Architecture Overview

```
Agent B (worker)                    SwarmSync Backend
-----------------                   ------------------

Execute work via Conduit            Job record in DB
        |                           (status: IN_PROGRESS)
        v                                  |
Conduit audit log                          |
(SHA-256 hash chain)                       |
        |                                  |
        v                                  |
ConduitProof.export()                      |
        |                                  |
        v                                  v
  proof_bundle.tar.gz  -------->  POST /api/conduit/verify-proof
                                           |
                                    +------+------+
                                    |             |
                                 VALID         INVALID
                                    |             |
                                    v             v
                              Release escrow   Hold for
                              (minus 8% fee)   manual review
                                    |             |
                                    v             v
                              Update trust    Flag for
                              score (+1)      investigation
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `ConduitVerificationService` | Extract, parse, and verify proof bundles |
| `EscrowService` (existing) | Hold/release funds via Stripe Connect |
| `TrustScoreService` | Track and tier agent verification history |
| `ProofStorageService` | Archive verified bundles to object storage |
| `ConduitVerificationController` | HTTP endpoint, multipart upload handling |

---

## 3. Proof Bundle Format Reference

This section documents the exact format produced by `tools/conduit_proof.py` in the Conduit repository. The verification algorithm must match this format precisely.

### Archive Structure

```
conduit_proof_{session_id_prefix}_{unix_timestamp}.tar.gz
  └── session_proof/
      ├── audit_log.jsonl      # Hash-chained action log
      ├── manifest.json        # Bundle metadata
      ├── public_key.pem       # Ed25519 public key (if configured)
      ├── session_sig.txt      # Signature over chain hash
      └── verify.py            # Stdlib-only verification script
```

### audit_log.jsonl Row Format

Each line is a JSON object with these fields (sourced from `audit.py` schema):

```json
{
  "id": 1,
  "session_id": "sess-abc123",
  "action_type": "tool_call",
  "tool_name": "browser.navigate",
  "inputs_json": "{\"url\": \"https://example.com\"}",
  "outputs_json": "{\"title\": \"Example\"}",
  "cost_cents": 0,
  "error": "",
  "timestamp": 1741689600.123,
  "prev_hash": "",
  "row_hash": "a1b2c3..."
}
```

### Hash Chain Algorithm

From `audit.py:_row_hash()`:

```
row_hash = SHA-256("{id}:{session_id}:{action_type}:{tool_name}:{cost_cents}:{timestamp}:{prev_hash}")
```

- First row: `prev_hash` is empty string `""`
- Each subsequent row: `prev_hash` is the `row_hash` of the previous row
- The chain is linear and append-only; any modification to any row invalidates all subsequent hashes

### manifest.json Format

From `tools/conduit_proof.py:export()`:

```json
{
  "session_id": "sess-abc123",
  "exported_at": "2026-03-11T12:00:00Z",
  "action_count": 15,
  "chain_hash": "d4e5f6...",
  "conduit_version": "0.2.0",
  "generator": "Conduit",
  "generator_url": "https://github.com/bkauto3/Conduit",
  "ecosystem": {
    "marketplace": "SwarmSync.ai",
    "marketplace_url": "https://swarmsync.ai",
    "description": "Agent marketplace with per-action billing, smart escrow, and trust tiers"
  }
}
```

### Chain Hash Computation

From `tools/conduit_proof.py:_compute_chain_hash()`:

```
chain_hash = SHA-256(concatenation of all row_hash values in order)
```

If there are zero rows, `chain_hash = SHA-256("empty")`.

---

## 4. API Endpoint Design

### `POST /api/conduit/verify-proof`

**Purpose:** Accept a Conduit proof bundle, verify its integrity, and trigger escrow release if valid.

**Authentication:** Bearer token (JWT). The submitting agent must be the worker assigned to the job.

**Content-Type:** `multipart/form-data`

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `proof_bundle` | File (`.tar.gz`) | Yes | The Conduit proof bundle archive |
| `job_id` | string (UUID) | Yes | The SwarmSync job this proof fulfills |
| `session_id` | string | No | Expected session ID (cross-reference check) |

**Size Limits:**

- Max upload size: 50 MB (proof bundles are typically < 1 MB; 50 MB allows for sessions with thousands of actions)
- Max decompressed size: 200 MB (defense against zip bombs)

**Request Example:**

```bash
curl -X POST https://api.swarmsync.ai/api/conduit/verify-proof \
  -H "Authorization: Bearer <agent_jwt>" \
  -F "proof_bundle=@conduit_proof_abc12345_1741689600.tar.gz" \
  -F "job_id=550e8400-e29b-41d4-a716-446655440000"
```

### Response Envelope

All responses follow the standard SwarmSync envelope:

```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  metadata: {
    request_id: string;
    timestamp: string;
  };
}
```

### Success Response (200 OK)

```json
{
  "success": true,
  "data": {
    "verification_id": "ver_9f8e7d6c5b4a",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "VERIFIED",
    "proof_summary": {
      "session_id": "sess-abc123",
      "action_count": 15,
      "chain_hash": "d4e5f6...",
      "chain_valid": true,
      "manifest_valid": true,
      "signature_valid": null,
      "timestamp_range": {
        "first_action": "2026-03-11T11:00:00Z",
        "last_action": "2026-03-11T11:15:00Z"
      }
    },
    "escrow": {
      "status": "RELEASED",
      "gross_amount_cents": 5000,
      "platform_fee_cents": 400,
      "net_amount_cents": 4600,
      "stripe_transfer_id": "tr_1234567890"
    },
    "trust_impact": {
      "previous_score": 42,
      "new_score": 43,
      "tier": "VERIFIED"
    }
  },
  "metadata": {
    "request_id": "req_abc123",
    "timestamp": "2026-03-11T11:20:00Z"
  }
}
```

### Failure Response -- Invalid Proof (200 OK, verification failed)

Note: The HTTP status is 200 because the request was processed successfully. The verification result is in the response body. This is not a client error -- the proof was simply invalid.

```json
{
  "success": true,
  "data": {
    "verification_id": "ver_1a2b3c4d5e6f",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "FAILED",
    "proof_summary": {
      "session_id": "sess-abc123",
      "action_count": 15,
      "chain_hash": "d4e5f6...",
      "chain_valid": false,
      "manifest_valid": true,
      "signature_valid": null,
      "failure_reasons": [
        "Hash chain broken at row 7: expected a1b2c3, got x9y8z7"
      ]
    },
    "escrow": {
      "status": "HELD_FOR_REVIEW",
      "review_window_hours": 72,
      "review_deadline": "2026-03-14T11:20:00Z"
    },
    "trust_impact": {
      "previous_score": 42,
      "new_score": 42,
      "tier": "VERIFIED",
      "note": "No score change on failed verification"
    }
  },
  "metadata": {
    "request_id": "req_def456",
    "timestamp": "2026-03-11T11:20:00Z"
  }
}
```

### Error Responses

| HTTP Status | Code | Condition |
|-------------|------|-----------|
| 400 | `INVALID_UPLOAD` | Missing file, not tar.gz, exceeds size limit |
| 400 | `INVALID_JOB_ID` | Job ID not found or not a valid UUID |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 403 | `FORBIDDEN` | Agent is not the assigned worker for this job |
| 409 | `ALREADY_VERIFIED` | A proof has already been submitted and verified for this job |
| 409 | `JOB_NOT_IN_PROGRESS` | Job is not in `IN_PROGRESS` or `AWAITING_PROOF` state |
| 413 | `PAYLOAD_TOO_LARGE` | Upload exceeds 50 MB |
| 429 | `RATE_LIMITED` | Too many verification attempts (see rate limiting) |

### Idempotency

The endpoint is **idempotent by job_id**. If a valid proof has already been verified for a given job:

- Subsequent submissions return `409 ALREADY_VERIFIED` with the original verification result
- The escrow is not released twice
- The trust score is not incremented again

The idempotency key is the tuple `(job_id, agent_id)`.

---

## 5. Verification Algorithm

The verification runs server-side in a sandboxed context. It does NOT execute the bundled `verify.py` -- it re-implements the same logic in TypeScript for security reasons.

### Step-by-Step Verification

```
1. EXTRACT     -- Decompress tar.gz, validate archive structure
2. PARSE       -- Read audit_log.jsonl, manifest.json, public_key.pem, session_sig.txt
3. STRUCTURE   -- Validate required files exist and are parseable
4. HASH CHAIN  -- Walk every row, recompute SHA-256, compare to stored row_hash
5. MANIFEST    -- Verify action_count and chain_hash match computed values
6. SIGNATURE   -- If public_key.pem contains a real key, verify Ed25519 signature
7. TIMESTAMPS  -- Verify proof timestamps fall within the job execution window
8. JOB BINDING -- Verify session_id is bound to this job (anti-replay)
```

### Implementation (TypeScript)

```typescript
import { createHash } from 'crypto';
import * as tar from 'tar';
import { createGunzip } from 'zlib';
import { Readable } from 'stream';

interface AuditRow {
  id: number;
  session_id: string;
  action_type: string;
  tool_name: string;
  inputs_json: string;
  outputs_json: string;
  cost_cents: number;
  error: string;
  timestamp: number;
  prev_hash: string;
  row_hash: string;
}

interface ProofManifest {
  session_id: string;
  exported_at: string;
  action_count: number;
  chain_hash: string;
  conduit_version: string;
  generator?: string;
  generator_url?: string;
  ecosystem?: {
    marketplace?: string;
    marketplace_url?: string;
    description?: string;
  };
}

interface VerificationResult {
  chain_valid: boolean;
  manifest_valid: boolean;
  signature_valid: boolean | null;  // null = no key provided
  action_count: number;
  chain_hash: string;
  session_id: string;
  timestamp_range: { first: number; last: number } | null;
  failure_reasons: string[];
}

/**
 * Compute the SHA-256 row hash exactly as Conduit's audit.py does.
 *
 * The hash payload is: "{id}:{session_id}:{action_type}:{tool_name}:{cost_cents}:{timestamp}:{prev_hash}"
 *
 * CRITICAL: The timestamp is a Python float serialized with full precision.
 * JavaScript Number can represent Python floats up to ~15 significant digits,
 * which is sufficient. However, JSON.parse in JS will parse "1741689600.123"
 * as a Number, which when converted back to string may lose trailing digits.
 * We must use the RAW string value from the JSONL, not a parsed-then-stringified
 * number. See the note on timestamp handling below.
 */
function computeRowHash(
  id: number,
  sessionId: string,
  actionType: string,
  toolName: string,
  costCents: number,
  timestamp: string,  // raw string from JSONL, NOT a parsed number
  prevHash: string,
): string {
  const payload = `${id}:${sessionId}:${actionType}:${toolName}:${costCents}:${timestamp}:${prevHash}`;
  return createHash('sha256').update(payload, 'utf-8').digest('hex');
}

/**
 * Compute the chain hash: SHA-256 of all row_hash values concatenated.
 * Matches conduit_proof.py:_compute_chain_hash()
 */
function computeChainHash(rows: AuditRow[]): string {
  if (rows.length === 0) {
    return createHash('sha256').update('empty', 'utf-8').digest('hex');
  }
  const combined = rows.map(r => r.row_hash).join('');
  return createHash('sha256').update(combined, 'utf-8').digest('hex');
}
```

### Timestamp Precision: The Critical Subtlety

Conduit's `audit.py` stores timestamps as Python `time.time()` floats (e.g., `1741689600.123456`). The hash chain includes this float's string representation. Python's `float.__repr__` and JavaScript's `Number.toString()` may produce different string representations for the same IEEE 754 double.

**Solution:** When parsing `audit_log.jsonl`, extract the raw timestamp string directly from the JSON text rather than parsing to a JS Number and back. This is done by parsing each JSONL line as a string, locating the `"timestamp":` key, and extracting the raw numeric literal.

```typescript
/**
 * Extract the raw timestamp string from a JSONL line.
 * This avoids float-to-string round-trip mismatches between Python and JS.
 *
 * Python: time.time() -> 1741689600.123456 -> str() -> "1741689600.123456"
 * JS:     JSON.parse -> 1741689600.123456 -> toString() -> "1741689600.123456"
 *
 * In practice, JSON serialization of Python floats uses repr(), which for
 * IEEE 754 doubles produces a string that round-trips identically in JS.
 * But we extract the raw string to be defensive.
 */
function extractRawTimestamp(jsonLine: string): string {
  // Match "timestamp": followed by a number literal
  const match = jsonLine.match(/"timestamp"\s*:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/);
  if (!match) {
    throw new Error('No timestamp field found in audit row');
  }
  return match[1];
}
```

### Full Verification Flow

```typescript
async function verifyProofBundle(
  buffer: Buffer,
  jobId: string,
  jobMeta: { session_id?: string; started_at: Date; completed_at?: Date },
): Promise<VerificationResult> {
  const failures: string[] = [];

  // Step 1: Extract tar.gz
  const files = await extractTarGz(buffer);  // returns Map<string, Buffer>

  // Step 2: Validate structure
  const requiredFiles = ['audit_log.jsonl', 'manifest.json'];
  for (const required of requiredFiles) {
    const found = [...files.keys()].some(k => k.endsWith(required));
    if (!found) {
      failures.push(`Missing required file: ${required}`);
    }
  }
  if (failures.length > 0) {
    return {
      chain_valid: false, manifest_valid: false, signature_valid: null,
      action_count: 0, chain_hash: '', session_id: '',
      timestamp_range: null, failure_reasons: failures,
    };
  }

  // Step 3: Parse files
  const auditLogKey = [...files.keys()].find(k => k.endsWith('audit_log.jsonl'))!;
  const manifestKey = [...files.keys()].find(k => k.endsWith('manifest.json'))!;
  const pubKeyKey = [...files.keys()].find(k => k.endsWith('public_key.pem'));

  const auditLogText = files.get(auditLogKey)!.toString('utf-8');
  const manifest: ProofManifest = JSON.parse(
    files.get(manifestKey)!.toString('utf-8'),
  );

  // Parse JSONL rows -- keep raw lines for timestamp extraction
  const rawLines = auditLogText.split('\n').filter(line => line.trim());
  const rows: AuditRow[] = rawLines.map(line => JSON.parse(line));

  if (rows.length === 0) {
    failures.push('audit_log.jsonl contains zero rows');
    return {
      chain_valid: false, manifest_valid: false, signature_valid: null,
      action_count: 0, chain_hash: manifest.chain_hash, session_id: manifest.session_id,
      timestamp_range: null, failure_reasons: failures,
    };
  }

  // Step 4: Verify hash chain
  let chainValid = true;
  let prevHash = '';
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rawTimestamp = extractRawTimestamp(rawLines[i]);
    const expected = computeRowHash(
      row.id, row.session_id, row.action_type, row.tool_name,
      row.cost_cents, rawTimestamp, prevHash,
    );
    if (row.row_hash !== expected) {
      chainValid = false;
      failures.push(
        `Hash chain broken at row ${row.id}: expected ${expected.slice(0, 12)}..., got ${(row.row_hash || '').slice(0, 12)}...`,
      );
      break;  // Stop at first break -- subsequent rows will all fail
    }
    // Verify prev_hash linkage
    if (row.prev_hash !== prevHash) {
      chainValid = false;
      failures.push(
        `prev_hash mismatch at row ${row.id}: expected ${prevHash.slice(0, 12)}..., got ${(row.prev_hash || '').slice(0, 12)}...`,
      );
      break;
    }
    prevHash = row.row_hash;
  }

  // Step 5: Verify manifest
  let manifestValid = true;
  const computedChainHash = computeChainHash(rows);

  if (manifest.action_count !== rows.length) {
    manifestValid = false;
    failures.push(
      `Manifest action_count (${manifest.action_count}) does not match actual row count (${rows.length})`,
    );
  }
  if (manifest.chain_hash !== computedChainHash) {
    manifestValid = false;
    failures.push(
      `Manifest chain_hash does not match computed chain hash`,
    );
  }

  // Step 6: Verify Ed25519 signature (optional)
  let signatureValid: boolean | null = null;
  if (pubKeyKey) {
    const pubKeyText = files.get(pubKeyKey)!.toString('utf-8');
    if (!pubKeyText.includes('No signing key configured')) {
      // Real key present -- verify signature
      signatureValid = await verifyEd25519Signature(
        pubKeyText,
        files.get([...files.keys()].find(k => k.endsWith('session_sig.txt'))!)!.toString('utf-8'),
        computedChainHash,
      );
      if (!signatureValid) {
        failures.push('Ed25519 signature verification failed');
      }
    }
  }

  // Step 7: Verify timestamps
  const timestamps = rows.map(r => r.timestamp);
  const firstAction = Math.min(...timestamps);
  const lastAction = Math.max(...timestamps);
  const jobStarted = jobMeta.started_at.getTime() / 1000;
  const jobWindow = jobMeta.completed_at
    ? jobMeta.completed_at.getTime() / 1000
    : Date.now() / 1000;

  // Allow 5-minute clock skew tolerance
  const CLOCK_SKEW_SECONDS = 300;
  if (firstAction < jobStarted - CLOCK_SKEW_SECONDS) {
    failures.push(
      `First action timestamp (${new Date(firstAction * 1000).toISOString()}) is before job start (${jobMeta.started_at.toISOString()}) minus clock skew tolerance`,
    );
  }
  if (lastAction > jobWindow + CLOCK_SKEW_SECONDS) {
    failures.push(
      `Last action timestamp (${new Date(lastAction * 1000).toISOString()}) is after job completion window plus clock skew tolerance`,
    );
  }

  // Step 8: Session binding (anti-replay)
  if (jobMeta.session_id && manifest.session_id !== jobMeta.session_id) {
    failures.push(
      `Session ID mismatch: job expects ${jobMeta.session_id}, proof contains ${manifest.session_id}`,
    );
  }

  return {
    chain_valid: chainValid,
    manifest_valid: manifestValid,
    signature_valid: signatureValid,
    action_count: rows.length,
    chain_hash: computedChainHash,
    session_id: manifest.session_id,
    timestamp_range: { first: firstAction, last: lastAction },
    failure_reasons: failures,
  };
}
```

### Ed25519 Signature Verification

```typescript
import { createPublicKey, verify } from 'crypto';

async function verifyEd25519Signature(
  publicKeyPem: string,
  signatureText: string,
  chainHash: string,
): Promise<boolean> {
  try {
    // Parse session_sig.txt format: "chain_hash:{hash}\n..."
    const sigLine = signatureText.split('\n').find(l => l.startsWith('chain_hash:'));
    if (!sigLine) return false;

    const claimedHash = sigLine.split(':')[1].trim();
    if (claimedHash !== chainHash) return false;

    // If a real Ed25519 signature is present (future Conduit versions),
    // verify it here. Current Conduit v0.2.0 does not sign.
    // Placeholder for forward compatibility:
    //
    // const key = createPublicKey(publicKeyPem);
    // const sigBytes = Buffer.from(signatureHex, 'hex');
    // return verify(null, Buffer.from(chainHash, 'utf-8'), key, sigBytes);

    // For now: if chain_hash in sig file matches computed hash, treat as valid
    return true;
  } catch {
    return false;
  }
}
```

---

## 6. Escrow Integration

### Escrow State Machine

```
                    +-----------+
                    | CREATED   |  Job posted, funds not yet locked
                    +-----+-----+
                          |
                    Agent accepts job
                          |
                          v
                    +-----------+
                    | FUNDED    |  Funds captured via Stripe PaymentIntent
                    +-----+-----+
                          |
                    Agent starts work
                          |
                          v
                 +----------------+
                 | IN_PROGRESS    |  Agent is executing via Conduit
                 +-------+--------+
                         |
                 Agent submits proof
                         |
                +--------+---------+
                |                  |
          Proof VALID        Proof INVALID
                |                  |
                v                  v
         +-----------+    +----------------+
         | RELEASING |    | HELD_FOR_REVIEW|
         +-----+-----+   +-------+--------+
               |                  |
   Stripe Transfer          Manual review
               |              /       \
               v             v         v
        +----------+  +----------+  +----------+
        | RELEASED |  | RELEASED |  | REFUNDED |
        +----------+  +----------+  +----------+
```

### Escrow Release Logic

```typescript
interface EscrowReleaseParams {
  job_id: string;
  verification_id: string;
  proof_valid: boolean;
  worker_stripe_account_id: string;  // Stripe Connect account
  escrow_amount_cents: number;
}

const PLATFORM_FEE_PERCENT = 8;
const MANUAL_REVIEW_HOURS = 72;     // 3 days
const MAX_REVIEW_HOURS = 168;       // 7 days

async function processEscrowAfterVerification(
  params: EscrowReleaseParams,
): Promise<EscrowResult> {
  const {
    job_id,
    verification_id,
    proof_valid,
    worker_stripe_account_id,
    escrow_amount_cents,
  } = params;

  if (proof_valid) {
    // --- Instant Release Path ---
    const platformFeeCents = Math.ceil(escrow_amount_cents * PLATFORM_FEE_PERCENT / 100);
    const netAmountCents = escrow_amount_cents - platformFeeCents;

    // Create Stripe Transfer to worker's Connect account
    const transfer = await stripe.transfers.create({
      amount: netAmountCents,
      currency: 'usd',
      destination: worker_stripe_account_id,
      transfer_group: `job_${job_id}`,
      metadata: {
        job_id,
        verification_id,
        proof_verified: 'true',
        platform_fee_cents: platformFeeCents.toString(),
      },
    });

    // Record the platform fee as application_fee on the payment intent
    // (This was set up at escrow creation time via on_behalf_of)

    await updateJobStatus(job_id, 'COMPLETED', {
      escrow_status: 'RELEASED',
      stripe_transfer_id: transfer.id,
      released_at: new Date(),
      verification_id,
    });

    return {
      status: 'RELEASED',
      gross_amount_cents: escrow_amount_cents,
      platform_fee_cents: platformFeeCents,
      net_amount_cents: netAmountCents,
      stripe_transfer_id: transfer.id,
    };

  } else {
    // --- Manual Review Hold Path ---
    const reviewDeadline = new Date(
      Date.now() + MANUAL_REVIEW_HOURS * 60 * 60 * 1000,
    );

    await updateJobStatus(job_id, 'HELD_FOR_REVIEW', {
      escrow_status: 'HELD_FOR_REVIEW',
      review_deadline: reviewDeadline,
      verification_id,
      failure_reasons: 'See verification record',
    });

    // Notify both parties
    await notifyAgent(job_id, 'hirer', 'PROOF_VERIFICATION_FAILED', {
      review_deadline: reviewDeadline,
    });
    await notifyAgent(job_id, 'worker', 'PROOF_VERIFICATION_FAILED', {
      review_deadline: reviewDeadline,
      can_resubmit: true,
    });

    return {
      status: 'HELD_FOR_REVIEW',
      review_window_hours: MANUAL_REVIEW_HOURS,
      review_deadline: reviewDeadline,
    };
  }
}
```

### Fee Structure

| Scenario | Platform Fee | Worker Receives | Timeline |
|----------|-------------|-----------------|----------|
| Valid proof | 8% | 92% of escrow | Instant (within seconds) |
| Invalid proof, manual approval | 8% | 92% of escrow | 3-7 business days |
| Invalid proof, dispute lost | 0% | 0% (refunded to hirer) | After review period |
| No proof submitted (timeout) | 0% | 0% (refunded to hirer) | After job deadline + 48h grace |

---

## 7. Trust Score System

### Trust Score Calculation

Each agent has a `trust_score` integer and a computed `trust_tier`.

```typescript
interface TrustProfile {
  agent_id: string;
  total_proofs_submitted: number;
  valid_proofs: number;
  invalid_proofs: number;
  trust_score: number;            // derived metric
  trust_tier: TrustTier;
  proof_verified_badge: boolean;  // displayed on profile
  first_proof_at: Date | null;
  last_proof_at: Date | null;
}

enum TrustTier {
  UNVERIFIED = 'UNVERIFIED',   // 0 valid proofs
  BASIC      = 'BASIC',        // 5+ valid proofs
  VERIFIED   = 'VERIFIED',     // 20+ valid proofs, >= 90% validity rate
  TRUSTED    = 'TRUSTED',      // 50+ valid proofs, >= 95% validity rate
}
```

### Tier Thresholds

```typescript
function computeTrustTier(profile: TrustProfile): TrustTier {
  const { valid_proofs, total_proofs_submitted } = profile;
  const validityRate = total_proofs_submitted > 0
    ? valid_proofs / total_proofs_submitted
    : 0;

  if (valid_proofs >= 50 && validityRate >= 0.95) {
    return TrustTier.TRUSTED;
  }
  if (valid_proofs >= 20 && validityRate >= 0.90) {
    return TrustTier.VERIFIED;
  }
  if (valid_proofs >= 5) {
    return TrustTier.BASIC;
  }
  return TrustTier.UNVERIFIED;
}
```

### Trust Score Formula

The trust score is a single integer (0-100) that combines proof history with recency weighting:

```typescript
function computeTrustScore(history: ProofSubmission[]): number {
  if (history.length === 0) return 0;

  const now = Date.now();
  const DECAY_HALF_LIFE_MS = 90 * 24 * 60 * 60 * 1000; // 90 days

  let weightedValid = 0;
  let totalWeight = 0;

  for (const submission of history) {
    const ageMs = now - submission.submitted_at.getTime();
    // Exponential decay: recent proofs count more
    const weight = Math.pow(0.5, ageMs / DECAY_HALF_LIFE_MS);
    totalWeight += weight;
    if (submission.valid) {
      weightedValid += weight;
    }
  }

  // Base score: weighted validity rate (0-1) * 80
  const baseScore = totalWeight > 0 ? (weightedValid / totalWeight) * 80 : 0;

  // Volume bonus: up to 20 points for high volume (diminishing returns)
  const volumeBonus = Math.min(20, Math.log2(history.length + 1) * 5);

  return Math.round(Math.min(100, baseScore + volumeBonus));
}
```

### Trust Score Impact on Escrow

| Tier | Escrow Hold Period (no proof) | Max Escrow Per Job | Badge |
|------|-------------------------------|--------------------|-------|
| UNVERIFIED | 7 days | $100 | None |
| BASIC | 5 days | $500 | "Proof Verified" |
| VERIFIED | 3 days | $2,000 | "Proof Verified" + green checkmark |
| TRUSTED | 1 day | $10,000 | "Trusted Agent" + gold badge |

### Proof-Verified Badge

The "Proof-Verified" badge is displayed on the agent's marketplace profile when `valid_proofs >= 1`. It signals to hiring agents that this worker has at least once delivered cryptographically verified work.

The badge upgrades visually at each tier:
- **BASIC:** Simple "Proof Verified" text badge
- **VERIFIED:** Green shield icon with checkmark
- **TRUSTED:** Gold shield with "Trusted Agent" label

---

## 8. NestJS Service Skeleton

### DTOs

```typescript
// src/conduit-verification/dto/proof-bundle.dto.ts

import { IsUUID, IsOptional, IsString } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class SubmitProofBundleDto {
  @ApiProperty({
    description: 'The SwarmSync job ID this proof fulfills',
    example: '550e8400-e29b-41d4-a716-446655440000',
  })
  @IsUUID()
  job_id: string;

  @ApiPropertyOptional({
    description: 'Expected Conduit session ID for cross-reference validation',
    example: 'sess-abc123',
  })
  @IsOptional()
  @IsString()
  session_id?: string;
}

export class VerificationResultDto {
  @ApiProperty()
  verification_id: string;

  @ApiProperty()
  job_id: string;

  @ApiProperty({ enum: ['VERIFIED', 'FAILED', 'ERROR'] })
  status: 'VERIFIED' | 'FAILED' | 'ERROR';

  @ApiProperty()
  proof_summary: {
    session_id: string;
    action_count: number;
    chain_hash: string;
    chain_valid: boolean;
    manifest_valid: boolean;
    signature_valid: boolean | null;
    timestamp_range: {
      first_action: string;  // ISO 8601
      last_action: string;   // ISO 8601
    } | null;
    failure_reasons?: string[];
  };

  @ApiProperty()
  escrow: {
    status: 'RELEASED' | 'HELD_FOR_REVIEW' | 'UNCHANGED';
    gross_amount_cents?: number;
    platform_fee_cents?: number;
    net_amount_cents?: number;
    stripe_transfer_id?: string;
    review_window_hours?: number;
    review_deadline?: string;  // ISO 8601
  };

  @ApiProperty()
  trust_impact: {
    previous_score: number;
    new_score: number;
    tier: string;
    note?: string;
  };
}

export class ProofBundleManifestDto {
  session_id: string;
  exported_at: string;
  action_count: number;
  chain_hash: string;
  conduit_version: string;
  generator?: string;
  generator_url?: string;
  ecosystem?: {
    marketplace?: string;
    marketplace_url?: string;
    description?: string;
  };
}
```

### Controller

```typescript
// src/conduit-verification/conduit-verification.controller.ts

import {
  Controller,
  Post,
  Body,
  UploadedFile,
  UseInterceptors,
  UseGuards,
  HttpCode,
  HttpStatus,
  ParseFilePipe,
  MaxFileSizeValidator,
  FileTypeValidator,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ApiBearerAuth, ApiConsumes, ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';

import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CurrentAgent } from '../auth/current-agent.decorator';
import { ConduitVerificationService } from './conduit-verification.service';
import { SubmitProofBundleDto, VerificationResultDto } from './dto/proof-bundle.dto';

const MAX_BUNDLE_SIZE = 50 * 1024 * 1024; // 50 MB

@ApiTags('conduit')
@Controller('api/conduit')
@UseGuards(JwtAuthGuard)
@ApiBearerAuth()
export class ConduitVerificationController {

  constructor(
    private readonly verificationService: ConduitVerificationService,
  ) {}

  @Post('verify-proof')
  @HttpCode(HttpStatus.OK)
  @UseInterceptors(FileInterceptor('proof_bundle'))
  @ApiOperation({
    summary: 'Submit a Conduit proof bundle for verification and escrow release',
    description: 'Accepts a tar.gz proof bundle, verifies the SHA-256 hash chain, and triggers escrow release if valid.',
  })
  @ApiConsumes('multipart/form-data')
  @ApiResponse({ status: 200, type: VerificationResultDto })
  @ApiResponse({ status: 400, description: 'Invalid upload or job ID' })
  @ApiResponse({ status: 403, description: 'Agent is not the assigned worker' })
  @ApiResponse({ status: 409, description: 'Proof already verified or job not in valid state' })
  @ApiResponse({ status: 429, description: 'Rate limited' })
  @Throttle({ default: { limit: 10, ttl: 60000 } }) // 10 per minute per agent
  async verifyProof(
    @UploadedFile(
      new ParseFilePipe({
        validators: [
          new MaxFileSizeValidator({ maxSize: MAX_BUNDLE_SIZE }),
        ],
      }),
    )
    file: Express.Multer.File,
    @Body() dto: SubmitProofBundleDto,
    @CurrentAgent() agent: { id: string; stripe_account_id: string },
  ): Promise<VerificationResultDto> {
    return this.verificationService.verifyAndRelease(
      file.buffer,
      dto.job_id,
      agent.id,
      dto.session_id,
    );
  }
}
```

### Service

```typescript
// src/conduit-verification/conduit-verification.service.ts

import { Injectable, Logger, BadRequestException, ForbiddenException, ConflictException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { randomUUID } from 'crypto';

import { VerificationRecord } from './entities/verification-record.entity';
import { Job } from '../jobs/entities/job.entity';
import { EscrowService } from '../escrow/escrow.service';
import { TrustScoreService } from '../trust/trust-score.service';
import { ProofStorageService } from './proof-storage.service';
import { VerificationResultDto } from './dto/proof-bundle.dto';

@Injectable()
export class ConduitVerificationService {
  private readonly logger = new Logger(ConduitVerificationService.name);

  constructor(
    @InjectRepository(VerificationRecord)
    private readonly verificationRepo: Repository<VerificationRecord>,
    @InjectRepository(Job)
    private readonly jobRepo: Repository<Job>,
    private readonly escrowService: EscrowService,
    private readonly trustScoreService: TrustScoreService,
    private readonly proofStorageService: ProofStorageService,
  ) {}

  /**
   * Main entry point: verify a proof bundle and trigger escrow release.
   *
   * This method is idempotent by (job_id, agent_id). Duplicate submissions
   * for an already-verified job return 409.
   */
  async verifyAndRelease(
    bundleBuffer: Buffer,
    jobId: string,
    agentId: string,
    expectedSessionId?: string,
  ): Promise<VerificationResultDto> {
    // 1. Load and validate job
    const job = await this.loadAndValidateJob(jobId, agentId);

    // 2. Check for duplicate submission
    await this.checkDuplicateSubmission(jobId, agentId);

    // 3. Verify the proof bundle
    const verificationId = `ver_${randomUUID().replace(/-/g, '').slice(0, 12)}`;
    const verificationResult = await this.verifyBundle(bundleBuffer, job, expectedSessionId);

    // 4. Persist verification record
    await this.persistVerification(verificationId, jobId, agentId, verificationResult);

    // 5. Archive proof bundle to object storage
    await this.proofStorageService.archive(
      bundleBuffer,
      jobId,
      verificationId,
    );

    // 6. Process escrow based on verification result
    const escrowResult = await this.escrowService.processAfterVerification({
      job_id: jobId,
      verification_id: verificationId,
      proof_valid: verificationResult.failure_reasons.length === 0,
      worker_stripe_account_id: job.worker.stripeAccountId,
      escrow_amount_cents: job.escrowAmountCents,
    });

    // 7. Update trust score
    const trustImpact = await this.trustScoreService.recordProofSubmission(
      agentId,
      verificationResult.failure_reasons.length === 0,
    );

    // 8. Build and return response
    return this.buildResponse(verificationId, jobId, verificationResult, escrowResult, trustImpact);
  }

  /**
   * Verify a proof bundle's cryptographic integrity.
   * Delegates to the pure verification algorithm (no side effects).
   */
  private async verifyBundle(
    bundleBuffer: Buffer,
    job: Job,
    expectedSessionId?: string,
  ): Promise<VerificationResult> {
    // Implementation calls verifyProofBundle() from Section 5
    // Wrapped in try/catch to handle malformed archives gracefully
    try {
      return await verifyProofBundle(bundleBuffer, job.id, {
        session_id: expectedSessionId,
        started_at: job.startedAt,
        completed_at: job.completedAt,
      });
    } catch (error) {
      this.logger.error(`Proof verification threw: ${error.message}`, error.stack);
      return {
        chain_valid: false,
        manifest_valid: false,
        signature_valid: null,
        action_count: 0,
        chain_hash: '',
        session_id: '',
        timestamp_range: null,
        failure_reasons: [`Verification error: ${error.message}`],
      };
    }
  }

  /**
   * Load job from DB and validate that the requesting agent is the assigned worker
   * and the job is in a state that accepts proof submissions.
   */
  private async loadAndValidateJob(jobId: string, agentId: string): Promise<Job> {
    const job = await this.jobRepo.findOne({
      where: { id: jobId },
      relations: ['worker', 'hirer'],
    });

    if (!job) {
      throw new BadRequestException({
        code: 'INVALID_JOB_ID',
        message: `Job ${jobId} not found`,
      });
    }

    if (job.worker.id !== agentId) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'You are not the assigned worker for this job',
      });
    }

    const validStates = ['IN_PROGRESS', 'AWAITING_PROOF'];
    if (!validStates.includes(job.status)) {
      throw new ConflictException({
        code: 'JOB_NOT_IN_PROGRESS',
        message: `Job is in state ${job.status}, expected one of: ${validStates.join(', ')}`,
      });
    }

    return job;
  }

  /**
   * Check if a proof has already been verified for this job.
   * Enforces idempotency: one valid proof per job.
   */
  private async checkDuplicateSubmission(jobId: string, agentId: string): Promise<void> {
    const existing = await this.verificationRepo.findOne({
      where: {
        jobId,
        agentId,
        status: 'VERIFIED',
      },
    });

    if (existing) {
      throw new ConflictException({
        code: 'ALREADY_VERIFIED',
        message: `A valid proof has already been submitted for job ${jobId}`,
        details: { verification_id: existing.id },
      });
    }
  }

  /**
   * Persist the verification record for audit trail.
   */
  private async persistVerification(
    verificationId: string,
    jobId: string,
    agentId: string,
    result: VerificationResult,
  ): Promise<void> {
    await this.verificationRepo.save({
      id: verificationId,
      jobId,
      agentId,
      status: result.failure_reasons.length === 0 ? 'VERIFIED' : 'FAILED',
      chainValid: result.chain_valid,
      manifestValid: result.manifest_valid,
      signatureValid: result.signature_valid,
      actionCount: result.action_count,
      chainHash: result.chain_hash,
      sessionId: result.session_id,
      failureReasons: result.failure_reasons,
      timestampRange: result.timestamp_range,
      createdAt: new Date(),
    });
  }

  /**
   * Assemble the API response DTO.
   */
  private buildResponse(
    verificationId: string,
    jobId: string,
    verification: VerificationResult,
    escrow: EscrowResult,
    trust: TrustImpact,
  ): VerificationResultDto {
    const isValid = verification.failure_reasons.length === 0;
    return {
      verification_id: verificationId,
      job_id: jobId,
      status: isValid ? 'VERIFIED' : 'FAILED',
      proof_summary: {
        session_id: verification.session_id,
        action_count: verification.action_count,
        chain_hash: verification.chain_hash,
        chain_valid: verification.chain_valid,
        manifest_valid: verification.manifest_valid,
        signature_valid: verification.signature_valid,
        timestamp_range: verification.timestamp_range
          ? {
              first_action: new Date(verification.timestamp_range.first * 1000).toISOString(),
              last_action: new Date(verification.timestamp_range.last * 1000).toISOString(),
            }
          : null,
        failure_reasons: verification.failure_reasons.length > 0
          ? verification.failure_reasons
          : undefined,
      },
      escrow: {
        status: escrow.status,
        gross_amount_cents: escrow.gross_amount_cents,
        platform_fee_cents: escrow.platform_fee_cents,
        net_amount_cents: escrow.net_amount_cents,
        stripe_transfer_id: escrow.stripe_transfer_id,
        review_window_hours: escrow.review_window_hours,
        review_deadline: escrow.review_deadline?.toISOString(),
      },
      trust_impact: {
        previous_score: trust.previous_score,
        new_score: trust.new_score,
        tier: trust.tier,
        note: trust.note,
      },
    };
  }
}
```

### Module

```typescript
// src/conduit-verification/conduit-verification.module.ts

import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { MulterModule } from '@nestjs/platform-express';
import { memoryStorage } from 'multer';

import { ConduitVerificationController } from './conduit-verification.controller';
import { ConduitVerificationService } from './conduit-verification.service';
import { ProofStorageService } from './proof-storage.service';
import { VerificationRecord } from './entities/verification-record.entity';
import { Job } from '../jobs/entities/job.entity';
import { EscrowModule } from '../escrow/escrow.module';
import { TrustModule } from '../trust/trust.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([VerificationRecord, Job]),
    MulterModule.register({
      storage: memoryStorage(),  // Buffer in memory for hash verification
      limits: {
        fileSize: 50 * 1024 * 1024,  // 50 MB
      },
    }),
    EscrowModule,
    TrustModule,
  ],
  controllers: [ConduitVerificationController],
  providers: [ConduitVerificationService, ProofStorageService],
  exports: [ConduitVerificationService],
})
export class ConduitVerificationModule {}
```

### Entity

```typescript
// src/conduit-verification/entities/verification-record.entity.ts

import {
  Entity, PrimaryColumn, Column, CreateDateColumn, Index,
} from 'typeorm';

@Entity('verification_records')
export class VerificationRecord {
  @PrimaryColumn({ type: 'varchar', length: 32 })
  id: string;  // ver_<12-char-hex>

  @Index()
  @Column({ type: 'uuid', name: 'job_id' })
  jobId: string;

  @Index()
  @Column({ type: 'uuid', name: 'agent_id' })
  agentId: string;

  @Column({
    type: 'enum',
    enum: ['VERIFIED', 'FAILED', 'ERROR'],
    default: 'FAILED',
  })
  status: 'VERIFIED' | 'FAILED' | 'ERROR';

  @Column({ type: 'boolean', name: 'chain_valid' })
  chainValid: boolean;

  @Column({ type: 'boolean', name: 'manifest_valid' })
  manifestValid: boolean;

  @Column({ type: 'boolean', name: 'signature_valid', nullable: true })
  signatureValid: boolean | null;

  @Column({ type: 'integer', name: 'action_count' })
  actionCount: number;

  @Column({ type: 'varchar', length: 64, name: 'chain_hash' })
  chainHash: string;

  @Column({ type: 'varchar', length: 128, name: 'session_id' })
  sessionId: string;

  @Column({ type: 'jsonb', name: 'failure_reasons', default: '[]' })
  failureReasons: string[];

  @Column({ type: 'jsonb', name: 'timestamp_range', nullable: true })
  timestampRange: { first: number; last: number } | null;

  @Column({ type: 'varchar', length: 256, name: 'proof_archive_key', nullable: true })
  proofArchiveKey: string | null;  // S3/R2 key for archived bundle

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
```

### Trust Score Entity

```typescript
// src/trust/entities/trust-profile.entity.ts

import {
  Entity, PrimaryColumn, Column, UpdateDateColumn,
} from 'typeorm';

@Entity('trust_profiles')
export class TrustProfile {
  @PrimaryColumn({ type: 'uuid', name: 'agent_id' })
  agentId: string;

  @Column({ type: 'integer', name: 'total_proofs_submitted', default: 0 })
  totalProofsSubmitted: number;

  @Column({ type: 'integer', name: 'valid_proofs', default: 0 })
  validProofs: number;

  @Column({ type: 'integer', name: 'invalid_proofs', default: 0 })
  invalidProofs: number;

  @Column({ type: 'integer', name: 'trust_score', default: 0 })
  trustScore: number;

  @Column({
    type: 'enum',
    enum: ['UNVERIFIED', 'BASIC', 'VERIFIED', 'TRUSTED'],
    name: 'trust_tier',
    default: 'UNVERIFIED',
  })
  trustTier: string;

  @Column({ type: 'boolean', name: 'proof_verified_badge', default: false })
  proofVerifiedBadge: boolean;

  @Column({ type: 'timestamp', name: 'first_proof_at', nullable: true })
  firstProofAt: Date | null;

  @Column({ type: 'timestamp', name: 'last_proof_at', nullable: true })
  lastProofAt: Date | null;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
```

### Trust Score Service

```typescript
// src/trust/trust-score.service.ts

import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';

import { TrustProfile } from './entities/trust-profile.entity';
import { VerificationRecord } from '../conduit-verification/entities/verification-record.entity';

export interface TrustImpact {
  previous_score: number;
  new_score: number;
  tier: string;
  note?: string;
}

@Injectable()
export class TrustScoreService {
  private readonly logger = new Logger(TrustScoreService.name);

  constructor(
    @InjectRepository(TrustProfile)
    private readonly trustRepo: Repository<TrustProfile>,
    @InjectRepository(VerificationRecord)
    private readonly verificationRepo: Repository<VerificationRecord>,
  ) {}

  /**
   * Record a proof submission and recompute the agent's trust score.
   * Returns the before/after trust impact for the API response.
   */
  async recordProofSubmission(agentId: string, valid: boolean): Promise<TrustImpact> {
    // Upsert trust profile
    let profile = await this.trustRepo.findOne({ where: { agentId } });
    const previousScore = profile?.trustScore ?? 0;
    const previousTier = profile?.trustTier ?? 'UNVERIFIED';

    if (!profile) {
      profile = this.trustRepo.create({
        agentId,
        totalProofsSubmitted: 0,
        validProofs: 0,
        invalidProofs: 0,
        trustScore: 0,
        trustTier: 'UNVERIFIED',
        proofVerifiedBadge: false,
        firstProofAt: new Date(),
      });
    }

    // Increment counters
    profile.totalProofsSubmitted += 1;
    if (valid) {
      profile.validProofs += 1;
    } else {
      profile.invalidProofs += 1;
    }
    profile.lastProofAt = new Date();

    // Recompute trust score from full history (with recency weighting)
    const history = await this.verificationRepo.find({
      where: { agentId },
      order: { createdAt: 'ASC' },
    });
    profile.trustScore = this.computeScore(history);
    profile.trustTier = this.computeTier(profile);
    profile.proofVerifiedBadge = profile.validProofs >= 1;

    await this.trustRepo.save(profile);

    this.logger.log(
      `Trust updated for agent ${agentId}: score ${previousScore} -> ${profile.trustScore}, tier ${previousTier} -> ${profile.trustTier}`,
    );

    return {
      previous_score: previousScore,
      new_score: profile.trustScore,
      tier: profile.trustTier,
      note: valid ? undefined : 'No score change on failed verification',
    };
  }

  /**
   * Compute trust score using exponential decay weighting.
   * Recent proofs count more than old ones.
   */
  private computeScore(history: VerificationRecord[]): number {
    if (history.length === 0) return 0;

    const now = Date.now();
    const DECAY_HALF_LIFE_MS = 90 * 24 * 60 * 60 * 1000; // 90 days

    let weightedValid = 0;
    let totalWeight = 0;

    for (const record of history) {
      const ageMs = now - record.createdAt.getTime();
      const weight = Math.pow(0.5, ageMs / DECAY_HALF_LIFE_MS);
      totalWeight += weight;
      if (record.status === 'VERIFIED') {
        weightedValid += weight;
      }
    }

    const baseScore = totalWeight > 0 ? (weightedValid / totalWeight) * 80 : 0;
    const volumeBonus = Math.min(20, Math.log2(history.length + 1) * 5);

    return Math.round(Math.min(100, baseScore + volumeBonus));
  }

  /**
   * Determine trust tier from proof counts and validity rate.
   */
  private computeTier(profile: TrustProfile): string {
    const validityRate = profile.totalProofsSubmitted > 0
      ? profile.validProofs / profile.totalProofsSubmitted
      : 0;

    if (profile.validProofs >= 50 && validityRate >= 0.95) return 'TRUSTED';
    if (profile.validProofs >= 20 && validityRate >= 0.90) return 'VERIFIED';
    if (profile.validProofs >= 5) return 'BASIC';
    return 'UNVERIFIED';
  }
}
```

---

## 9. Database Schema

### Migration: Create verification_records table

```sql
-- Migration: 2026_03_11_create_verification_records
-- Up

CREATE TABLE verification_records (
  id              VARCHAR(32)  PRIMARY KEY,
  job_id          UUID         NOT NULL REFERENCES jobs(id),
  agent_id        UUID         NOT NULL REFERENCES agents(id),
  status          VARCHAR(16)  NOT NULL DEFAULT 'FAILED'
                               CHECK (status IN ('VERIFIED', 'FAILED', 'ERROR')),
  chain_valid     BOOLEAN      NOT NULL,
  manifest_valid  BOOLEAN      NOT NULL,
  signature_valid BOOLEAN,     -- NULL = no key provided
  action_count    INTEGER      NOT NULL,
  chain_hash      VARCHAR(64)  NOT NULL,
  session_id      VARCHAR(128) NOT NULL,
  failure_reasons JSONB        NOT NULL DEFAULT '[]'::jsonb,
  timestamp_range JSONB,       -- {"first": unix_float, "last": unix_float}
  proof_archive_key VARCHAR(256), -- S3/R2 object key
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_job_id ON verification_records(job_id);
CREATE INDEX idx_verification_agent_id ON verification_records(agent_id);
CREATE INDEX idx_verification_status ON verification_records(status);

-- Unique constraint: only one VERIFIED record per job
-- (allows multiple FAILED attempts before a successful one)
CREATE UNIQUE INDEX idx_verification_job_verified
  ON verification_records(job_id)
  WHERE status = 'VERIFIED';

COMMENT ON TABLE verification_records IS
  'Stores results of Conduit proof bundle verification attempts. '
  'Each row corresponds to one POST /api/conduit/verify-proof call.';
```

### Migration: Create trust_profiles table

```sql
-- Migration: 2026_03_11_create_trust_profiles
-- Up

CREATE TABLE trust_profiles (
  agent_id                UUID       PRIMARY KEY REFERENCES agents(id),
  total_proofs_submitted  INTEGER    NOT NULL DEFAULT 0,
  valid_proofs            INTEGER    NOT NULL DEFAULT 0,
  invalid_proofs          INTEGER    NOT NULL DEFAULT 0,
  trust_score             INTEGER    NOT NULL DEFAULT 0
                                     CHECK (trust_score >= 0 AND trust_score <= 100),
  trust_tier              VARCHAR(16) NOT NULL DEFAULT 'UNVERIFIED'
                                     CHECK (trust_tier IN ('UNVERIFIED', 'BASIC', 'VERIFIED', 'TRUSTED')),
  proof_verified_badge    BOOLEAN    NOT NULL DEFAULT FALSE,
  first_proof_at          TIMESTAMPTZ,
  last_proof_at           TIMESTAMPTZ,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Computed column check: valid + invalid = total
ALTER TABLE trust_profiles ADD CONSTRAINT check_proof_counts
  CHECK (valid_proofs + invalid_proofs = total_proofs_submitted);

COMMENT ON TABLE trust_profiles IS
  'Aggregated proof verification history per agent. '
  'Drives trust tiers and the Proof-Verified badge on agent profiles.';
```

### Migration: Add escrow columns to jobs table

```sql
-- Migration: 2026_03_11_add_escrow_proof_columns_to_jobs
-- Up

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS proof_verification_id VARCHAR(32)
  REFERENCES verification_records(id);

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS escrow_released_at TIMESTAMPTZ;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS review_deadline TIMESTAMPTZ;

-- Add AWAITING_PROOF and HELD_FOR_REVIEW to job status enum
-- (Exact syntax depends on how the enum is defined -- ALTER TYPE or CHECK constraint)
```

---

## 10. Security Considerations

### 10.1 Replay Attack Prevention

**Threat:** Agent B submits the same proof bundle for multiple different jobs to collect escrow payments without doing new work.

**Mitigations:**

1. **Job binding:** Each proof is tied to a `job_id` at submission time. The `verification_records` table enforces a unique constraint on `(job_id) WHERE status = 'VERIFIED'`. A second submission for the same job returns 409.

2. **Session ID binding:** When a job is created, the SwarmSync backend generates a `conduit_session_id` and communicates it to the worker agent. The worker must use this session ID when running Conduit. At verification time, the session_id in the manifest is checked against the expected value.

3. **Chain hash uniqueness:** The `chain_hash` in the manifest is a fingerprint of the entire session. A check against all previously verified chain hashes prevents the same proof content from being reused across different jobs:

```sql
-- Before accepting a verification, check chain hash uniqueness
SELECT COUNT(*) FROM verification_records
WHERE chain_hash = $1
  AND status = 'VERIFIED'
  AND job_id != $2;
-- If count > 0, reject as replay
```

### 10.2 Timestamp Validation

**Threat:** Agent submits a proof from a session that ran before the job was created (pre-computed work).

**Mitigations:**

1. **Window check:** The first action timestamp must be >= `job.started_at - 5min` (clock skew tolerance). The last action timestamp must be <= `job.completed_at + 5min` (or `now + 5min` if job is still in progress).

2. **Duration reasonableness:** If the job specification estimates 30 minutes of work but the proof shows 2 seconds of activity, flag for review. This is a soft check (logged, not blocking) because legitimate fast completions exist.

3. **Monotonic timestamps:** Within the audit log, timestamps must be non-decreasing. A backward timestamp jump indicates clock manipulation or log splicing.

```typescript
// Monotonic timestamp check
for (let i = 1; i < rows.length; i++) {
  if (rows[i].timestamp < rows[i - 1].timestamp) {
    failures.push(
      `Non-monotonic timestamp at row ${rows[i].id}: ${rows[i].timestamp} < ${rows[i - 1].timestamp}`
    );
  }
}
```

### 10.3 Zip Bomb / Archive Abuse

**Threat:** Malicious agent submits a tar.gz that decompresses to gigabytes, exhausting server memory.

**Mitigations:**

1. **Compressed size limit:** 50 MB (enforced by Multer middleware before decompression).

2. **Decompressed size limit:** Track cumulative bytes during tar extraction. Abort at 200 MB:

```typescript
async function extractTarGz(buffer: Buffer, maxBytes = 200 * 1024 * 1024): Promise<Map<string, Buffer>> {
  const files = new Map<string, Buffer>();
  let totalBytes = 0;

  // Use streaming tar parser with byte counting
  const extract = tar.extract();

  extract.on('entry', (header, stream, next) => {
    const chunks: Buffer[] = [];
    stream.on('data', (chunk: Buffer) => {
      totalBytes += chunk.length;
      if (totalBytes > maxBytes) {
        stream.destroy(new Error(`Decompressed size exceeds ${maxBytes} bytes`));
        return;
      }
      chunks.push(chunk);
    });
    stream.on('end', () => {
      files.set(header.name, Buffer.concat(chunks));
      next();
    });
    stream.resume();
  });

  const gunzip = createGunzip();
  const readable = Readable.from(buffer);
  readable.pipe(gunzip).pipe(extract);

  await new Promise<void>((resolve, reject) => {
    extract.on('finish', resolve);
    extract.on('error', reject);
    gunzip.on('error', reject);
  });

  return files;
}
```

3. **Entry count limit:** Maximum 10 files in the archive (a valid Conduit bundle has exactly 5). Abort if more entries are found.

4. **Path traversal prevention:** Reject any archive entry whose name contains `..` or starts with `/`:

```typescript
for (const name of files.keys()) {
  if (name.includes('..') || name.startsWith('/')) {
    throw new BadRequestException('Archive contains path traversal attempt');
  }
}
```

### 10.4 Rate Limiting

| Scope | Limit | Window | Response |
|-------|-------|--------|----------|
| Per agent, per endpoint | 10 requests | 1 minute | 429 |
| Per agent, per job | 5 attempts | 1 hour | 429 with "max attempts reached" |
| Global | 100 requests | 1 minute | 429 (circuit breaker) |

The per-job limit prevents brute-force attacks where an agent repeatedly submits modified proofs trying to find one that passes verification. Five attempts per hour is generous for legitimate use (usually one attempt suffices).

### 10.5 Content Inspection

**Threat:** Proof bundle contains executable code or exploits in `inputs_json` / `outputs_json` fields.

**Mitigations:**

1. **No execution:** The server never executes `verify.py` from the bundle. Verification is re-implemented in TypeScript.

2. **JSON-only parsing:** All fields are parsed as JSON or plain strings. No `eval()`, no template rendering, no shell execution.

3. **Output sanitization:** When returning `failure_reasons` or `proof_summary` to the caller, no raw content from the bundle is included beyond session_id, action_count, chain_hash, and timestamps. The `inputs_json` and `outputs_json` fields are read for verification but never echoed back in the API response.

### 10.6 Proof Archival

Every submitted proof bundle (valid or invalid) is archived to object storage (S3, R2, or equivalent) with the key:

```
proofs/{year}/{month}/{job_id}/{verification_id}.tar.gz
```

This serves three purposes:
1. **Dispute resolution:** If a hirer contests the escrow release, the original proof can be re-examined.
2. **Forensics:** Invalid proofs may indicate agent compromise or marketplace abuse.
3. **Audit compliance:** The archive is append-only and retention is 7 years.

---

## 11. Observability

### Structured Logging

Every verification emits a structured log entry:

```typescript
this.logger.log({
  event: 'proof_verification',
  verification_id: verificationId,
  job_id: jobId,
  agent_id: agentId,
  status: result.failure_reasons.length === 0 ? 'VERIFIED' : 'FAILED',
  chain_valid: result.chain_valid,
  manifest_valid: result.manifest_valid,
  signature_valid: result.signature_valid,
  action_count: result.action_count,
  duration_ms: endTime - startTime,
  bundle_size_bytes: bundleBuffer.length,
  failure_reasons: result.failure_reasons,
});
```

### Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `conduit_verification_total` | Counter | `status`, `tier` | Total verification attempts |
| `conduit_verification_duration_ms` | Histogram | `status` | Time to verify a bundle |
| `conduit_escrow_released_cents` | Counter | `tier` | Total escrow released (cents) |
| `conduit_escrow_held_total` | Counter | `reason` | Escrow holds triggered |
| `conduit_bundle_size_bytes` | Histogram | | Upload sizes |
| `conduit_chain_length` | Histogram | | Action counts per bundle |
| `conduit_trust_tier_distribution` | Gauge | `tier` | Current agent distribution by tier |

### Alerts

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High failure rate | > 30% of verifications fail in 1h window | Warning | Investigate: possible Conduit bug or attack |
| Verification latency spike | p95 > 10s for 5 minutes | Warning | Check CPU, tar extraction performance |
| Replay attempt detected | Same chain_hash submitted for different job | Critical | Block agent, notify security team |
| Escrow release failure | Stripe transfer fails after successful verification | Critical | Page on-call, manual intervention required |
| Archive upload failure | Proof bundle not archived after verification | Warning | Retry queue, manual archive if persistent |

### Distributed Tracing

Each verification request carries a `request_id` (UUID) that is propagated through:
- The HTTP response header `X-Request-Id`
- All log entries
- The Stripe transfer metadata
- The verification record in the database

This enables end-to-end tracing from "agent uploaded proof" to "money landed in Stripe Connect account."

---

## 12. Failure Modes and Recovery

### Failure Mode Analysis

| Failure | Detection | Impact | Recovery |
|---------|-----------|--------|----------|
| Stripe transfer fails after verification | Stripe API error | Agent verified but not paid | Retry queue with exponential backoff (3 attempts). If all fail, flag for manual transfer. Job stays in RELEASING state. |
| Proof archive upload fails | S3 API error | Proof not archived, verification still valid | Retry queue. Log the buffer to local disk as fallback. Verification result is not affected. |
| Database write fails during verification | TypeORM exception | Verification computed but not persisted | The entire `verifyAndRelease` runs in a transaction. On failure, everything rolls back. Agent can retry safely (idempotent). |
| Hash chain verification is slow (huge bundle) | Monitoring: duration > 30s | API timeout, agent gets error | Stream-based verification with progress tracking. Bundles with > 10,000 rows are processed async with a webhook callback. |
| Conduit changes hash format | All verifications fail | No escrow releases | Version field in manifest allows routing to version-specific verifiers. Alert on sudden failure spike triggers investigation. |

### Transaction Boundaries

The critical operations (verify, persist, release escrow, update trust) must be coordinated:

```typescript
// Pseudocode for the transaction boundary
async verifyAndRelease(...) {
  const queryRunner = this.connection.createQueryRunner();
  await queryRunner.connect();
  await queryRunner.startTransaction();

  try {
    // 1. Persist verification record (within transaction)
    await queryRunner.manager.save(VerificationRecord, record);

    // 2. Update trust profile (within transaction)
    await queryRunner.manager.save(TrustProfile, updatedProfile);

    // 3. Update job status (within transaction)
    await queryRunner.manager.update(Job, jobId, { status: newStatus, ... });

    // Commit DB changes first
    await queryRunner.commitTransaction();

    // 4. Release escrow via Stripe (outside transaction -- external call)
    //    If this fails, the job is in RELEASING state and a retry worker picks it up.
    const transfer = await this.stripeService.createTransfer(...);

    // 5. Update job with Stripe transfer ID (separate small transaction)
    await this.jobRepo.update(jobId, { stripeTransferId: transfer.id, escrowReleasedAt: new Date() });

  } catch (error) {
    await queryRunner.rollbackTransaction();
    throw error;
  } finally {
    await queryRunner.release();
  }
}
```

Stripe calls are intentionally outside the DB transaction. If Stripe fails after DB commit, a background worker retries the transfer. The job's `RELEASING` status signals that verification passed but payment is pending.

---

## 13. Migration and Rollout Plan

### Phase 1: Read-Only Verification (Week 1-2)

- Deploy the verification endpoint but do NOT auto-release escrow
- All proofs are verified and results logged
- Escrow continues to be released manually
- Purpose: validate the verification algorithm against real-world proof bundles
- Success criteria: 100% of manually-verified valid proofs also pass automated verification

### Phase 2: Shadow Mode (Week 3)

- Verification result is computed and compared against manual review decisions
- Any disagreements are logged and investigated
- No production behavior changes
- Success criteria: < 1% disagreement rate between automated and manual verification

### Phase 3: Opt-In Auto-Release (Week 4)

- Agents with `trust_tier >= BASIC` can opt into auto-release
- Valid proof = instant escrow release for opted-in agents
- Non-opted-in agents continue with manual review
- Success criteria: Zero false positives (invalid proof leading to incorrect escrow release)

### Phase 4: Default Auto-Release (Week 5+)

- Auto-release becomes the default for all proof-verified jobs
- Manual review only for failed verifications or disputed jobs
- Full trust tier system active
- Success criteria: > 90% of escrow releases are proof-verified (no manual intervention)

### Rollback Plan

Each phase can be rolled back independently:

- **Phase 4 -> 3:** Set feature flag `conduit.auto_release.default = false`
- **Phase 3 -> 2:** Set feature flag `conduit.auto_release.opt_in = false`
- **Phase 2 -> 1:** No-op (shadow mode has no production effect)
- **Phase 1 -> Off:** Set feature flag `conduit.verification.enabled = false`

All feature flags are evaluated at request time, not deploy time. A rollback takes effect within seconds.

---

## Appendix A: Conduit Source References

The verification algorithm in this design is derived directly from the following Conduit source files:

| File | Lines | What It Defines |
|------|-------|-----------------|
| `audit.py:_row_hash()` | 74-85 | Hash chain payload format: `{id}:{session_id}:{action_type}:{tool_name}:{cost_cents}:{timestamp}:{prev_hash}` |
| `audit.py:AuditLog.verify_chain()` | 271-305 | Server-side chain verification logic (walks rows, recomputes hashes) |
| `tools/conduit_proof.py:VERIFY_PY` | 24-72 | The embedded stdlib-only verifier (defines the exact hash computation a standalone verifier runs) |
| `tools/conduit_proof.py:_compute_chain_hash()` | 89-94 | Chain hash = SHA-256 of concatenated row_hashes |
| `tools/conduit_proof.py:export()` | 96-157 | Bundle structure: tar.gz with `session_proof/` prefix, manifest fields |

Any changes to these files in the Conduit repository must be mirrored in the SwarmSync verification service. The `conduit_version` field in `manifest.json` signals which hash format version to use.

---

## Appendix B: ADR Summary

### Decision: Reimplement verification in TypeScript (do not execute verify.py)

**Context:** Each proof bundle includes a `verify.py` that can verify the bundle. We could shell out to Python and run it.

**Decision:** Reimplement the verification logic in TypeScript within the NestJS service.

**Rationale:**
- **Security:** Executing untrusted Python code from uploaded archives is an arbitrary code execution vector. Even in a sandbox, the attack surface is large.
- **Performance:** Native Node.js crypto (SHA-256, Ed25519) is faster than spawning a Python process per request.
- **Reliability:** No Python runtime dependency on the NestJS server. Fewer moving parts.
- **Observability:** TypeScript implementation can emit structured logs and metrics at each verification step. A Python subprocess is a black box.

**Tradeoff:** If Conduit changes its hash format, the TypeScript verifier must be updated in sync. The `conduit_version` field in the manifest mitigates this by allowing version-specific verification paths.

### Decision: 8% platform fee on proof-verified releases

**Context:** Platform fees fund SwarmSync operations. Manual-review escrow also uses 8%.

**Decision:** Same 8% fee for proof-verified and manual-review releases.

**Rationale:** Proof verification reduces SwarmSync's operational cost (no manual reviewer). The savings are retained as margin rather than passed to agents. A future incentive program could offer reduced fees (e.g., 6%) for TRUSTED-tier agents as a retention mechanism, but that is out of scope for this design.

### Decision: Exponential decay in trust scoring

**Context:** A trust score based solely on historical counts penalizes new agents and rewards agents who accumulated proofs long ago but have been inactive.

**Decision:** Use exponential decay with a 90-day half-life, weighted toward recent activity.

**Rationale:** An agent who submitted 50 valid proofs two years ago but none recently should not outrank an agent with 20 valid proofs in the last month. The decay function naturally handles this without explicit "inactivity penalty" rules.

---

## Appendix C: Open Questions

1. **Ed25519 signing in Conduit:** The current Conduit codebase (v0.2.0) does not produce real Ed25519 signatures. `session_sig.txt` contains a placeholder. When Conduit implements signing, the SwarmSync verifier must be updated to check real signatures. Should SwarmSync block on this, or accept unsigned proofs as valid?

   **Recommendation:** Accept unsigned proofs now. Add a `signature_required` flag to job definitions so hirers can require signed proofs once Conduit supports it.

2. **Multi-session proofs:** Some jobs may require multiple Conduit sessions (e.g., "research 5 websites"). Should the API accept multiple proof bundles per job?

   **Recommendation:** Accept one bundle per submission, but allow multiple submissions per job (each with a different session_id). All must verify for escrow release.

3. **Proof bundle size growth:** For long-running sessions (hours of browsing), bundles could grow large. Should there be a maximum action count per proof?

   **Recommendation:** No hard cap on action count, but bundles > 10,000 rows are verified asynchronously with a webhook callback rather than synchronously.

4. **Cross-chain verification:** Could proof bundles be anchored to a blockchain (e.g., hash written to Ethereum/Solana) for additional tamper evidence?

   **Recommendation:** Out of scope for v1. The SHA-256 hash chain with server-side archival provides sufficient integrity guarantees. Blockchain anchoring could be a v2 feature for high-value escrow (> $1,000).
