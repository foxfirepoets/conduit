# Conduit Proof Bundles: A Compliance Framework Mapping for SOC 2, HIPAA, SOX, and GDPR

**Audience:** GRC professionals, internal auditors, legal counsel, compliance officers
**Reading time:** ~12 minutes

---

## The Problem With Automated Evidence

Every compliance framework built in the last decade assumes that when a control operates, a human was watching — or at minimum, that a system produced a trustworthy log. That assumption is breaking down.

Organizations now rely on automated agents to perform tasks that were once manual: checking vendor portals, verifying configuration states, filling out forms, monitoring for regulatory changes, and testing that privacy deletion requests were honored. These agents browse the web, click buttons, read pages, and take actions. They do the work.

But they produce no verifiable evidence that they did it.

A screenshot can be edited in thirty seconds. A log file can be modified by anyone with file system access. A PDF export from a vendor portal carries no cryptographic chain of custody. When your auditor asks "how do you know this control ran last Tuesday?" the honest answer, for most automation today, is: "we have a log file and you'll have to trust it."

That is not what compliance frameworks are designed to accept.

Conduit is an open-source headless browser built specifically to close this gap. Every action an automated agent takes through Conduit — every navigation, click, form fill, and page read — is cryptographically recorded in a **proof bundle**: a self-contained, tamper-evident package of evidence that any auditor can independently verify with a single Python script and no external dependencies.

This post maps Conduit's proof bundle capabilities directly to specific regulatory requirements across SOC 2, HIPAA, SOX, and GDPR, so compliance professionals can evaluate exactly where Conduit fits in their evidence programs.

---

## What Is a Conduit Proof Bundle?

Before mapping to frameworks, it helps to understand what a proof bundle actually contains. Think of it as a notarized logbook where tearing out any page makes the tampering immediately obvious — not because someone checks the pages by hand, but because each page's identifier is mathematically derived from the page before it.

A proof bundle is a directory containing five files:

**`audit_log.jsonl`** — The complete record of every action taken during the session. Each line is a JSON object containing the action type, timestamp, session ID, inputs, outputs, and a SHA-256 hash. The hash of each row is computed over the row's content plus the hash of the previous row. This is the hash chain. If any record is modified, deleted, or inserted, every hash after that point becomes invalid — the tampering is mathematically detectable.

**`manifest.json`** — Session metadata including the agent identity, session start and end times, total action count, and the final hash in the chain. This is the "seal" of the logbook.

**`public_key.pem`** — The Ed25519 public key corresponding to the private identity key stored in `~/.cato/conduit_identity.key`. Ed25519 is an elliptic curve signature scheme used in TLS, SSH, and most modern security infrastructure.

**`session_sig.txt`** — An Ed25519 digital signature over the final chain hash from `manifest.json`. This cryptographically binds the agent's identity to the complete record of what happened. A valid signature proves: (1) the holder of the private key authorized this session, and (2) the audit log has not been altered since signing.

**`verify.py`** — A self-contained verifier written in Python standard library only, with zero external dependencies. Any auditor can run `python verify.py` and receive a pass/fail verdict, the chain integrity status, the signature validity, and the complete action timeline.

The critical property: verification requires no connection to Conduit's servers, no license, no account. The proof bundle is forensically self-sufficient.

---

## SOC 2 Mapping

SOC 2 reports on Trust Services Criteria (TSC). The criteria most relevant to automated agent activity fall under the Common Criteria (CC) category.

### CC7.2 — System Operations: Change Detection

**The requirement:** The entity monitors system components and the operation of those components for anomalies that are indicative of malicious acts, natural disasters, and errors affecting the entity's ability to meet its objectives.

**How Conduit addresses it:** Conduit's `fingerprint` action computes a hash of a web page's content state and stores it in the audit log. The `check_changed` action compares the current state against a stored fingerprint and emits a `PAGE_MUTATION` event — signed into the audit log — when a change is detected.

For a SOC 2 auditor examining a web monitoring control, this produces a CC7.2-aligned artifact: a signed, timestamped record proving that the monitored system was checked at a specific time, that the check ran successfully, and that any detected mutation was logged at the moment of detection. The signature prevents retroactive modification of detection timestamps — a critical gap in most screenshot-based monitoring approaches.

### CC6.1 — Logical and Physical Access Controls

**The requirement:** The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events.

**How Conduit addresses it:** The audit log records every navigation event, every element interaction (click, fill, hover), and every page read — producing a complete access record for every web-based system the agent touches. For compliance purposes, this answers the auditor's question: "what did this automated account access, and when?"

Because the log is hash-chained and signed, the access record cannot be pruned after the fact. An agent cannot "forget" to log an access it shouldn't have made.

### CC8.1 — Change Management

**The requirement:** The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures.

**How Conduit addresses it:** When an automated agent makes a web-based configuration change — updating a setting in a SaaS portal, modifying an access control list, changing a notification threshold — the proof bundle documents the before-state (captured by a `read` or `fingerprint` action before the change), the specific actions taken (the `click` and `fill` events), and the after-state (a subsequent read or fingerprint confirming the change took effect).

This is the evidence chain that change management controls require: what was the state before, what actions were taken, what is the state after, and who (or what identity) performed the change. Proof bundles satisfy all four.

### CC7.1 — System Monitoring

**The requirement:** The entity uses detection and monitoring procedures to identify changes to configurations or the unexpected removal of software.

**How Conduit addresses it:** Scheduled Conduit agents performing web monitoring checks produce time-series proof bundles. The hash chain within each bundle proves the monitoring occurred in the sequence recorded. Across a set of bundles, auditors can verify that monitoring ran on the required schedule, that each check produced a valid signed output, and that any anomalies were recorded at the time of detection rather than reconstructed later.

---

## HIPAA Security Rule Mapping

The HIPAA Security Rule (45 CFR Part 164) applies to covered entities and business associates that access, create, or transmit electronic protected health information (ePHI). For organizations whose automated agents interact with health-related web systems, proof bundles address several implementation specifications directly.

### 164.312(b) — Audit Controls (Required)

**The requirement:** Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use ePHI.

**How Conduit addresses it:** The hash-chained `audit_log.jsonl` is the audit control. It records every action taken by the agent with timestamps, session identifiers, action types, inputs, and outputs. Because the log is append-only during session execution and then signed, it satisfies the "record" requirement. The `verify.py` script satisfies the "examine" requirement — providing a structured, reproducible way to inspect and validate the log.

The critical HIPAA-specific property here is that the audit mechanism cannot be selectively disabled for specific actions. The hash chain means any gap in the record — any deleted entry — invalidates every subsequent hash and is detected by the verifier. You cannot audit-log only the actions that look good.

### 164.312(c)(1) — Integrity (Required)

**The requirement:** Implement policies and procedures to protect ePHI from improper alteration or destruction.

**How Conduit addresses it:** The SHA-256 hash chain provides mathematical integrity guarantees over the audit record. SHA-256 is a one-way function: given a hash, you cannot reconstruct the input, and changing any input bit produces a completely different hash. Because each row's hash depends on every previous row, modifying a single character in a single record invalidates the entire chain from that point forward. `verify.py` will report exactly which record broke the chain.

The Ed25519 signature over the final chain hash extends this integrity guarantee to the manifest: anyone who alters the manifest to make a broken chain appear valid will find that the signature no longer matches the modified manifest. Both layers of integrity are independently verifiable.

### 164.312(d) — Person or Entity Authentication (Required)

**The requirement:** Implement procedures to verify that a person or entity seeking access to ePHI is the one claimed.

**How Conduit addresses it:** Each Conduit installation generates an Ed25519 keypair stored in `~/.cato/conduit_identity.key`. The public key is embedded in every proof bundle as `public_key.pem`. The session signature in `session_sig.txt` proves that the holder of the corresponding private key authorized and produced the session record.

For compliance purposes, this means each proof bundle carries a verifiable identity claim. An organization can maintain a registry of authorized agent identity keys — similar to a certificate authority — and verify that any proof bundle presented as evidence was produced by an authorized agent identity, not a rogue process or a fabricated record.

### 164.312(e)(1) — Transmission Security (Required)

**The requirement:** Implement technical security measures to guard against unauthorized access to ePHI that is being transmitted over an electronic communications network.

**How Conduit addresses it:** Proof bundles are designed for offline verification. They require no network connection to validate — the `verify.py` script operates entirely on the local bundle contents. This means that when proof bundles are archived or transmitted for audit review, the verification process itself does not create a second transmission pathway for sensitive data. The auditor downloads the bundle once and verifies locally, forever.

---

## SOX Section 404 Mapping

Section 404 of the Sarbanes-Oxley Act requires management to assess the effectiveness of internal control over financial reporting (ICFR), with external auditor attestation. The relevant operational layer for automated agent activity is IT General Controls (ITGCs).

### IT General Controls — Evidence of Control Operation

ITGCs typically cover logical access, change management, and computer operations. For automated controls that operate through web interfaces, the standing question in every SOX audit is: "how do you evidence that the control ran?"

Manual screenshots have been accepted as ITGC evidence for years, but they carry a well-known weakness: they are trivially editable. An auditor accepting a screenshot as evidence is accepting the organization's representation that the screenshot is authentic. There is no cryptographic basis for that acceptance.

Conduit proof bundles replace screenshots with evidence that has a cryptographic basis. The hash chain proves the sequence of events. The signature proves the identity of the executing agent. The `verify.py` output is a machine-readable attestation that either passes or fails — there is no ambiguity.

### Automated Control Testing

A common ITGC pattern for web-based financial systems is periodic automated testing: an agent logs into the system, checks that access controls are configured correctly, and records the result. With Conduit, the proof bundle produced by this test is itself the test evidence — not a downstream artifact, but the actual record of what happened during the test.

For SOX purposes, this means the control test evidence and the control test execution are the same object. There is no gap between "the test ran" and "we have evidence the test ran."

### Evidence Retention

SOX requires that ICFR documentation and evidence be retained for seven years. Proof bundles are designed for long-term archival: the format is JSON (text, human-readable, no proprietary dependencies), the signature uses a widely supported cryptographic algorithm (Ed25519), and the verifier is a single Python file that requires only the standard library.

An archived proof bundle will be verifiable in ten years by anyone with Python installed. There is no vendor lock-in, no expiring license, no format that requires proprietary software to read.

---

## GDPR Article 30 Mapping

Article 30 of the GDPR requires controllers and processors to maintain records of processing activities (RoPA). For organizations using automated agents to interact with web systems that process personal data, proof bundles provide an activity-level record that supports both RoPA maintenance and individual rights fulfillment.

### Records of Processing Activities (Article 30)

**The requirement:** Records must describe the purposes of processing, categories of data subjects, categories of personal data, recipients, transfers to third countries, retention periods, and security measures.

**How Conduit addresses it:** A proof bundle for an agent session that processes personal data contains an exact record of every web page accessed, every form filled, every data element read or submitted. This is not a high-level description of processing activities — it is the primary record of what actually occurred. Organizations can use proof bundles as the evidentiary foundation for Article 30 documentation, with the cryptographic chain providing assurance that the records accurately reflect the actual processing.

### Right of Erasure Verification (Article 17)

When a data subject exercises their right to erasure, organizations must be able to demonstrate that deletion was performed. For web-based systems, this typically means an agent navigating to the user account, performing the deletion, and capturing evidence of completion.

A Conduit proof bundle of that agent session is a verifiable record of the deletion: the pages navigated, the actions taken, the confirmation displayed. The Ed25519 signature means that record cannot be fabricated after the fact — it was produced by a specific agent identity at a specific time, and any modification to the record breaks the cryptographic chain.

This is meaningfully stronger evidence than a screenshot attached to a ticket.

---

## How to Use Conduit for Compliance Workflows

### Installation

```bash
pip install conduit-browser
```

### Example: Compliance Monitoring Agent

```python
import asyncio
from conduit import Conduit

async def run_compliance_check():
    async with Conduit() as browser:
        # Navigate to monitored system
        await browser.navigate("https://your-compliance-portal.example.com")

        # Fingerprint the current state
        fingerprint = await browser.fingerprint()

        # Read the current configuration values
        config_values = await browser.read(selector=".config-panel")

        # Check whether the page has changed since last run
        changed = await browser.check_changed(
            previous_hash=fingerprint["hash"],
            selector=".config-panel"
        )

        # Export proof bundle
        bundle_path = await browser.export_proof_bundle(
            output_dir="./compliance-evidence",
            label="weekly-config-check"
        )

        return bundle_path

asyncio.run(run_compliance_check())
```

### Verifying a Proof Bundle

After exporting, any party — your auditor, your legal team, a third-party assessor — can verify the bundle with no installation beyond Python:

```
$ python verify.py

Conduit Proof Bundle Verifier
==============================
Session ID:     a3f7c891-2d4e-4b1a-9c8f-7e3d1a2b5c6d
Agent Identity: [public key fingerprint]
Actions:        47 recorded

Chain Integrity:  PASS (47/47 hashes valid)
Signature:        PASS (Ed25519 signature verified)
Timestamps:       2026-03-11T14:23:01Z — 2026-03-11T14:24:18Z

VERDICT: VERIFIED — This proof bundle has not been tampered with.
```

A failed verification looks like:

```
Chain Integrity:  FAIL — Hash mismatch at record 23
                  Expected: 8a4f2c...
                  Got:      9b3e1d...

VERDICT: INVALID — This proof bundle has been modified.
```

The output is deterministic, human-readable, and produces no output to external systems.

A complete compliance auditor example is available at `examples/compliance_auditor.py` in the Conduit repository.

---

## Conduit vs. Manual Screenshots: Evidence Quality Comparison

| Evidence Property | Manual Screenshots | Conduit Proof Bundles |
|---|---|---|
| **Tamper-evident** | No — editable in any image editor | Yes — SHA-256 hash chain, any modification detected |
| **Independently verifiable** | No — requires trust in the producer | Yes — `verify.py`, zero dependencies, no network |
| **Timestamped** | OS file metadata (editable) | Hash-chained timestamps (tamper-evident) |
| **Chain of custody** | None — no cryptographic binding | Built-in — Ed25519 signature binds identity to record |
| **Automation-friendly** | No — requires human to take and name | Yes — produced automatically by every Conduit session |
| **Archivable long-term** | Image files degrade, formats change | JSON + signature, readable indefinitely with Python |
| **Auditor self-service** | Auditor depends on you to provide context | Auditor runs `python verify.py` independently |
| **Selective omission detectable** | No — you can simply not take a screenshot | Yes — any gap in the hash chain is detected |
| **Regulatory defensibility** | Accepted by convention, not by logic | Cryptographically grounded, arguable in any forum |

The practical difference matters most at the margins: when a finding is contested, when evidence is requested months after the fact, or when a control's operation needs to be proven to a party that has no reason to trust your organization's representations. Cryptographic evidence does not require trust — it requires only the public key and the `verify.py` file.

---

## Getting Started

Conduit is open-source and available now.

**GitHub:** [https://github.com/bkauto3/Conduit](https://github.com/bkauto3/Conduit)

**PyPI:**
```bash
pip install conduit-browser
```

**MCP Registry:** `io.github.bkauto3/conduit`

For compliance use cases, start with:

1. Review `examples/compliance_auditor.py` for a working reference implementation
2. Run a test session against a non-sensitive system and verify the output with `verify.py`
3. Identify the controls in your current program that rely on screenshot or log-based evidence
4. Replace those evidence collection steps with Conduit sessions

The proof bundle format is designed to slot into existing evidence management workflows — it is a directory of files, not a proprietary vault. Archive it wherever you archive compliance evidence today.

---

## A Note on Scope

Conduit proves what an agent did. It does not prove that what the agent did was correct, complete, or sufficient to satisfy a regulatory requirement. The compliance mapping in this document identifies where Conduit's evidence properties align with specific regulatory requirements — not that using Conduit automatically satisfies those requirements.

As with all compliance tooling, implementation context matters. A hash-chained audit log is a strong audit control; whether it satisfies 164.312(b) in your specific environment depends on the scope of your system, the nature of the ePHI involved, and your organization's broader control environment.

What Conduit guarantees is the integrity and authenticity of the record of what happened. What you do with that record — and whether what happened was appropriate — remains a human judgment.

---

*Conduit is open-source software released under the MIT License. Nothing in this post constitutes legal advice. Consult qualified legal counsel for compliance determinations specific to your organization.*
