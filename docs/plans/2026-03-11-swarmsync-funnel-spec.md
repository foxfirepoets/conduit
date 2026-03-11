# Conduit-to-SwarmSync Funnel Specification
## From Free Open-Source Tool to Paid Agent Marketplace

**Date:** 2026-03-11
**Status:** VALIDATED
**Conduit Repo:** https://github.com/bkauto3/Conduit
**SwarmSync:** https://swarmsync.ai

---

## Executive Summary

Conduit is a free, open-source headless browser with cryptographic audit trails. SwarmSync.ai is a paid agent marketplace (420+ agents, Stripe + crypto payments, smart escrow). Conduit is already integrated into SwarmSync as the execution engine (12 NestJS services, per-action billing, trust tiers, execution passports).

This spec defines exactly how to surface that relationship so developers who discover Conduit organically flow toward SwarmSync -- without Conduit feeling like an ad. Every change must pass a single test: **would a developer reading this feel informed, not marketed to?**

---

## Guiding Principles

1. **Value first, mention second.** SwarmSync never appears until the reader has already seen what Conduit does and why it matters.
2. **Multiple light touches over one heavy pitch.** Three natural mentions in context beat one "Powered by" banner.
3. **Always offer the free path.** Every SwarmSync mention must make clear that Conduit is fully usable standalone, forever, MIT-licensed.
4. **Attribution in artifacts, not in code paths.** Proof bundle metadata can reference the ecosystem. Runtime behavior must not change.

---

## Task 1: README SwarmSync Integration

### Current README Structure (for reference)

```
Line   Section
1      # Conduit (title + tagline + badges)
14     ## Install
24     ## Quick Start -- Audited Session in 60 Seconds
50     ## Use Cases
64     ## For Compliance & Legal Teams
79     ## For Security Researchers
102    ## Why Conduit Instead of Playwright, Puppeteer, or Selenium?
122    ## How Proof Bundles Work
183    ## Use with Claude Code / MCP
205    ## Architecture
229    ## Action Reference
264    ## Storage Layout
281    ## Security Design
306    ## Running Tests
323    ## License
329    ## Contributing
```

### Changes: Three Insertions

SwarmSync is mentioned in three places -- each one contextually appropriate and each serving a different reader intent.

---

#### Insertion 1: "Built for Agent Economies" -- after "Use Cases" (line 62)

**Location:** Insert a new section between the end of "Use Cases" (line 62) and "For Compliance & Legal Teams" (line 64).

**Rationale:** The reader has just seen four use cases. The fourth is "AI agent browser control." This is the natural moment to say "and agents can get paid for this work."

**Exact text to insert:**

```markdown
---

## Built for Agent Economies

Conduit's audit trail is not just for compliance -- it is the trust layer that enables agents to transact with each other. When Agent A hires Agent B to do web research, the proof bundle is how Agent A knows the work was actually done.

This is the model behind [SwarmSync.ai](https://swarmsync.ai), an agent marketplace where 420+ agents negotiate, execute, and get paid -- with Conduit providing the verifiable execution layer. Conduit is and will always be free and open-source. SwarmSync is where the work gets monetized.

You do not need SwarmSync to use Conduit. But if your agent does useful web work, SwarmSync is where other agents will find it and pay for it.
```

**Word count:** 119 words.
**Tone check:** Informational. States what SwarmSync is, states that Conduit is free, states the value proposition. No exclamation marks, no urgency language, no "sign up now."

---

#### Insertion 2: One-liner in the MCP section -- modify existing text (line 199-201)

**Location:** At the end of the existing "Use with Claude Code / MCP" section, after line 201 (`See [skills/conduit.md](skills/conduit.md) for the full action reference.`).

**Rationale:** The reader is configuring Conduit as an MCP server. They are an agent developer. This is where they should learn that agents using Conduit can be listed on a marketplace.

**Exact text to append after line 201:**

```markdown

Agents built on Conduit can also be listed on the [SwarmSync.ai](https://swarmsync.ai) marketplace, where other agents discover, negotiate with, and pay your agent via smart escrow -- all backed by Conduit's cryptographic proof of execution.
```

**Word count:** 37 words. One sentence. No section header -- just a paragraph appended to an existing section.

---

#### Insertion 3: "From Free Tool to Paid Agent" -- before License section (line 323)

**Location:** Insert a new section between the end of "Running Tests" (line 318) and "License" (line 323).

**Rationale:** The reader has gone through the entire README. They understand the product. This is the CTA position -- the natural "what's next" after absorbing everything. Placed before License/Contributing so it does not feel like an afterthought.

**Exact text to insert:**

```markdown
---

## From Free Tool to Paid Agent

Conduit is free and open-source. It will stay that way. But agents that do useful work should get paid for it.

**Step 1:** Build with Conduit. Your agent navigates, extracts, monitors -- every action is audited and signed.

**Step 2:** Your agent produces real value. It does web research, monitors prices, captures compliance evidence, fills forms.

**Step 3:** List your agent on [SwarmSync.ai](https://swarmsync.ai). Set your price. Define what your agent does.

**Step 4:** Other agents on SwarmSync discover yours. They negotiate terms, agree on price, and funds go into smart escrow.

**Step 5:** Your agent executes the work via Conduit. The proof bundle proves the work was done. Escrow releases payment.

That is it. Conduit gives you the trust layer. SwarmSync gives you the marketplace. You keep your code, your agent, and your revenue.

[List your agent on SwarmSync.ai](https://swarmsync.ai)
```

**Word count:** 155 words.
**Tone check:** Direct, factual, step-by-step. Opens by reaffirming Conduit is free. Ends with a single link. No hype.

---

### Sections NOT Changed

The following sections must NOT mention SwarmSync:

- **Install** -- pure technical instructions
- **Quick Start** -- code example, no marketing
- **For Compliance & Legal Teams** -- audience-specific, SwarmSync is irrelevant
- **For Security Researchers** -- audience-specific, SwarmSync is irrelevant
- **Why Conduit vs competitors** -- comparison table, must remain objective
- **How Proof Bundles Work** -- technical explanation
- **Architecture** -- internal design
- **Action Reference** -- API docs
- **Security Design** -- trust-critical section, no external links

---

## Task 2: Proof Bundle Attribution

### 2.1 manifest.json Changes

**File:** `tools/conduit_proof.py`, lines 111-117 (the manifest dict in the `export` method).

**Current manifest:**
```python
manifest = {
    "session_id": self._session_id,
    "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "action_count": len(rows),
    "chain_hash": chain_hash,
    "conduit_version": "0.2.0",
}
```

**New manifest (add three fields at the end):**
```python
manifest = {
    "session_id": self._session_id,
    "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "action_count": len(rows),
    "chain_hash": chain_hash,
    "conduit_version": "0.2.0",
    "generator": "Conduit",
    "generator_url": "https://github.com/bkauto3/Conduit",
    "ecosystem": {
        "marketplace": "SwarmSync.ai",
        "marketplace_url": "https://swarmsync.ai",
        "description": "Agent marketplace with per-action billing, smart escrow, and trust tiers",
    },
}
```

**Rationale:**
- `generator` and `generator_url` provide attribution back to the open-source project. This is standard practice (PDFs have Creator fields, images have EXIF software tags).
- `ecosystem` is a nested object so it is clearly separable from core proof metadata. Any consumer can ignore it.
- These fields are metadata only. They do not affect the hash chain, verification, or any runtime behavior.
- The fields are static -- they do not phone home, do not require network access, do not change verification outcomes.

### 2.2 verify.py Footer Changes

**File:** `tools/conduit_proof.py`, the `VERIFY_PY` string constant (lines 24-67).

**Current final output of verify.py (line 63):**
```python
    print("VERIFIED: This session proof is intact and unmodified.")
```

**New final output (replace that single print with three lines):**
```python
    print("VERIFIED: This session proof is intact and unmodified.")
    print()
    print("Powered by Conduit (github.com/bkauto3/Conduit) | Agents earn money at swarmsync.ai")
```

**Rationale:**
- The attribution line only appears AFTER successful verification. If verification fails, the user sees the failure message and exits -- no marketing on a broken proof.
- The blank line separates the verification result from the attribution, so it is visually distinct.
- The format `Powered by X | Y` is a recognized convention (Webpack, Next.js, Hugo all do this).
- The line is informational. "Agents earn money at swarmsync.ai" describes what SwarmSync does in six words.

### 2.3 Full Updated VERIFY_PY Constant

For clarity, here is the complete replacement for the `VERIFY_PY` string in `conduit_proof.py`:

```python
VERIFY_PY = '''#!/usr/bin/env python3
"""
Conduit Session Proof Verifier
Verify this bundle without Conduit installed -- stdlib only.
Usage: python verify.py

Generated by Conduit (https://github.com/bkauto3/Conduit)
Part of the SwarmSync.ai agent ecosystem (https://swarmsync.ai)
"""
import json, hashlib, base64, sys
from pathlib import Path

def verify():
    here = Path(__file__).parent
    log_path = here / "audit_log.jsonl"
    sig_path = here / "session_sig.txt"
    manifest_path = here / "manifest.json"

    if not log_path.exists():
        print("FAIL: audit_log.jsonl not found")
        sys.exit(1)

    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]

    # Verify hash chain
    prev_hash = ""
    for row in rows:
        expected = hashlib.sha256(
            f"{row[\'id\']}:{row[\'session_id\']}:{row[\'action_type\']}:"
            f"{row[\'tool_name\']}:{row[\'cost_cents\']}:{row[\'timestamp\']}:{prev_hash}".encode()
        ).hexdigest()
        if row.get("row_hash") != expected:
            print(f"FAIL: Hash chain broken at row {row[\'id\']}")
            sys.exit(1)
        prev_hash = row["row_hash"]

    print(f"OK: Hash chain verified ({len(rows)} rows)")

    manifest = json.loads(manifest_path.read_text())
    print(f"Session: {manifest.get(\'session_id\')}")
    print(f"Exported: {manifest.get(\'exported_at\')}")
    print(f"Actions: {manifest.get(\'action_count\')}")
    print("VERIFIED: This session proof is intact and unmodified.")
    print()
    print("Powered by Conduit (github.com/bkauto3/Conduit) | Agents earn money at swarmsync.ai")

if __name__ == "__main__":
    verify()
'''
```

**Changes from current version:**
1. Two lines added to the docstring: `Generated by Conduit` and `Part of the SwarmSync.ai agent ecosystem`
2. Two lines added after the final verification print: blank line + attribution line

---

## Task 3: GitHub Repo Metadata

### 3.1 Repository Description

**Current description (set by marketing spec):**
```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles.
```

**New description:**
```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles. Powers the SwarmSync.ai agent marketplace.
```

**Execution:**
```bash
gh repo edit bkauto3/Conduit --description "Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles. Powers the SwarmSync.ai agent marketplace."
```

**Character count:** 168 characters. GitHub allows up to 350.

**Rationale:** "Powers the SwarmSync.ai agent marketplace" is a factual statement -- Conduit IS the execution engine for SwarmSync. It is the last clause, so readers see the technical description first.

### 3.2 Homepage URL

**Current:** `https://github.com/bkauto3/Conduit#readme` (self-referencing)

**New:** `https://swarmsync.ai`

**Execution:**
```bash
gh repo edit bkauto3/Conduit --homepage "https://swarmsync.ai"
```

**Rationale:** The GitHub homepage link appears next to the repo description. Since the README is already the landing page for the repo itself, the homepage link should point to the ecosystem -- giving viewers a direct path to SwarmSync. This is standard for open-source projects that are part of a larger product (e.g., Next.js links to vercel.com).

### 3.3 Topics to Add

**Current topics (13, set by marketing spec):**
```
mcp-server, mcp, headless-browser, browser-automation, cryptographic-audit,
audit-trail, web-scraping, ai-agents, python, playwright, ed25519,
compliance, stealth-browser
```

**Topics to add (2):**
```
agent-marketplace
agent-economy
```

**New full topic set (15):**
```
mcp-server, mcp, headless-browser, browser-automation, cryptographic-audit,
audit-trail, web-scraping, ai-agents, python, playwright, ed25519,
compliance, stealth-browser, agent-marketplace, agent-economy
```

**Execution:**
```bash
gh api repos/bkauto3/Conduit/topics \
  -X PUT \
  -f 'names=["mcp-server","mcp","headless-browser","browser-automation","cryptographic-audit","audit-trail","web-scraping","ai-agents","python","playwright","ed25519","compliance","stealth-browser","agent-marketplace","agent-economy"]'
```

**Rationale:** `agent-marketplace` and `agent-economy` are legitimate descriptors of the ecosystem Conduit operates in. They are not high-volume search terms today, but they position Conduit in a category that is likely to grow. They also create topical co-occurrence with SwarmSync's own repo topics.

---

## Task 4: MCP Directory Submission Updates

### 4.1 Submission Description Template

When submitting Conduit to MCP directories (140+ identified in the marketing spec), the short description should include one ecosystem mention.

**Standard short description (for directories with character limits):**
```
Headless browser with SHA-256 hash-chained audit trails and Ed25519 signed proof bundles.
Stealth mode via Patchright. Part of the SwarmSync.ai agent ecosystem.
```

**Extended description (for directories that allow longer text):**
```
Conduit is a headless browser where every action is written to a tamper-evident SHA-256 hash
chain, signed with an Ed25519 identity key, and exportable as self-verifiable proof bundles.
No other headless browser does this.

Built as an MCP server for AI agents. Stealth browsing via Patchright (stealth Playwright
fork). BFS crawling with robots.txt compliance. Page fingerprinting and signed change detection.

Conduit is the execution engine behind SwarmSync.ai, an agent marketplace where 420+ agents
negotiate, execute work, and get paid -- with Conduit's proof bundles serving as verifiable
receipts for completed work.

Free and open-source (MIT). Python 3.10+.
```

### 4.2 Directory-Specific Adjustments

**awesome-mcp-servers PR (punkpeye):**

Update the entry from the marketing spec. New entry:

```markdown
- [bkauto3/Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash-chained audit trails and Ed25519 signed proof bundles. Stealth mode via Patchright. Powers the SwarmSync.ai agent marketplace.
```

**Note:** Keep the PR body focused on what Conduit does, not on SwarmSync. The mention is in the one-liner entry only and describes a factual relationship.

**mcp.so, mcpservers.org, Glama.ai form submissions:**

Use the standard short description above. The "Part of the SwarmSync.ai agent ecosystem" clause should be the last sentence in the description field.

**PulseMCP, Smithery.ai, MCPize.com:**

Same standard short description. If there is a "Website" or "Homepage" field separate from "Repository URL," use:
- Repository URL: `https://github.com/bkauto3/Conduit`
- Website/Homepage: `https://swarmsync.ai`

### 4.3 Category Positioning

When directories offer category selection:

**Primary category:** Browser Automation / Web Scraping / Headless Browser (whichever is available)

**Secondary category (if available):** AI Agents / Agent Tools / Agent Infrastructure

**Do NOT categorize as:** Marketplace, Payment, Commerce. Conduit is not a marketplace -- it is the execution engine. The marketplace is SwarmSync.

### 4.4 Tags/Keywords for Directory Submissions

When directories allow tags or keywords, use this ordered list (adapt to available options):

```
headless-browser, mcp-server, audit-trail, cryptographic-proof, browser-automation,
stealth-browser, web-scraping, ai-agents, ed25519, sha256, proof-bundle, compliance,
agent-marketplace, swarmsync
```

`swarmsync` as a tag creates a discoverable link between the two products in directory search.

---

## Task 5: Conversion Funnel Documentation

### 5.1 The Funnel (README Section -- already specified in Task 1, Insertion 3)

The "From Free Tool to Paid Agent" section in the README IS the conversion funnel documentation. It is reproduced here for completeness and annotated with funnel-stage labels.

```
AWARENESS  --> Developer discovers Conduit via GitHub, MCP directory, awesome-list, PyPI
               They see: "Headless browser with cryptographic audit"
               They do NOT see SwarmSync yet.

INTEREST   --> Developer reads README. Sees use cases, proof bundles, comparison table.
               First SwarmSync mention: "Built for Agent Economies" section.
               Tone: informational, not promotional.

EVALUATION --> Developer clones repo, runs Quick Start, exports a proof bundle.
               Runs verify.py -- sees "Powered by Conduit | Agents earn money at swarmsync.ai"
               This is the artifact-level touchpoint.

CONVERSION --> Developer reads "From Free Tool to Paid Agent" at end of README.
               Five concrete steps. Single link to swarmsync.ai.
               CTA: "List your agent on SwarmSync.ai"

RETENTION  --> Every proof bundle the agent produces contains ecosystem metadata.
               Every verify.py output includes the attribution line.
               Organic, ongoing exposure without any push mechanism.
```

### 5.2 Touchpoint Inventory

| Touchpoint | Stage | Type | SwarmSync Visibility |
|------------|-------|------|---------------------|
| GitHub repo description | Awareness | Passive | Last clause: "Powers the SwarmSync.ai agent marketplace" |
| GitHub homepage link | Awareness | Passive | Links to swarmsync.ai |
| GitHub topics | Awareness | Passive | `agent-marketplace`, `agent-economy` topics |
| MCP directory listings | Awareness | Passive | "Part of the SwarmSync.ai agent ecosystem" in description |
| README: "Built for Agent Economies" | Interest | Active read | 119-word section explaining the relationship |
| README: MCP section addendum | Interest | Active read | 37-word one-liner about listing agents |
| README: "From Free Tool to Paid Agent" | Conversion | Active read | 155-word step-by-step funnel section |
| manifest.json ecosystem field | Evaluation | Artifact metadata | Machine-readable; visible if user inspects JSON |
| verify.py docstring | Evaluation | Artifact metadata | Visible if user reads the source |
| verify.py output footer | Evaluation | Artifact output | "Powered by Conduit \| Agents earn money at swarmsync.ai" |

**Total SwarmSync mentions across all touchpoints:** 10
**Mentions that require the user to take action to see:** 7 (must read README, inspect manifest, or run verify.py)
**Mentions that appear passively:** 3 (repo description, homepage link, directory listings)

### 5.3 What SwarmSync's Landing Page Must Handle

This spec defines how users arrive at swarmsync.ai from Conduit. For the funnel to convert, the SwarmSync landing page must:

1. **Recognize Conduit traffic.** Add UTM parameters to all links in the README and proof bundles: `?utm_source=conduit&utm_medium=readme` and `?utm_source=conduit&utm_medium=proof_bundle`. This allows measuring how much traffic Conduit drives.

2. **Have a "List Your Agent" path.** The README CTA says "List your agent on SwarmSync.ai." When users arrive, they need a clear path to register an agent -- not just browse the marketplace.

3. **Explain the Conduit connection.** A section or FAQ entry: "What is Conduit?" with a link back to the GitHub repo. This closes the loop for users who arrive at SwarmSync from non-Conduit sources and want to understand the execution engine.

### 5.4 UTM-Tagged URLs for All Conduit Touchpoints

Replace all bare `https://swarmsync.ai` links with UTM-tagged versions:

| Touchpoint | URL |
|------------|-----|
| README: "Built for Agent Economies" | `https://swarmsync.ai?utm_source=conduit&utm_medium=readme&utm_campaign=agent-economies` |
| README: MCP section addendum | `https://swarmsync.ai?utm_source=conduit&utm_medium=readme&utm_campaign=mcp-section` |
| README: "From Free Tool to Paid Agent" (inline) | `https://swarmsync.ai?utm_source=conduit&utm_medium=readme&utm_campaign=funnel-section` |
| README: "From Free Tool to Paid Agent" (CTA) | `https://swarmsync.ai?utm_source=conduit&utm_medium=readme&utm_campaign=funnel-cta` |
| manifest.json marketplace_url | `https://swarmsync.ai?utm_source=conduit&utm_medium=proof-bundle` |
| verify.py output | `swarmsync.ai` (no UTM -- stdout text, not a clickable link) |
| GitHub homepage | `https://swarmsync.ai?utm_source=conduit&utm_medium=github-homepage` |

---

## Implementation Checklist

### Files to Modify

| File | Change | Effort |
|------|--------|--------|
| `README.md` | Insert 3 SwarmSync sections (Task 1) | 15 min |
| `tools/conduit_proof.py` | Update manifest dict + VERIFY_PY constant (Task 2) | 10 min |
| GitHub API | Update description, homepage, topics (Task 3) | 5 min |
| Directory submissions | Update description templates (Task 4) | 5 min per directory |

### Files NOT Modified

| File | Reason |
|------|--------|
| `audit.py` | Core hash chain logic -- no marketing in trust-critical code |
| `receipt.py` | Billing receipts -- internal, no external attribution |
| `tools/conduit_bridge.py` | Execution engine -- no marketing in runtime paths |
| `tools/browser.py` | Browser automation -- no marketing in action implementations |
| `tools/conduit_crawl.py` | Crawler -- no marketing |
| `tools/conduit_monitor.py` | Monitor -- no marketing |
| Any test file | Tests must remain independent of marketing content |

### Execution Order

```
1. Update tools/conduit_proof.py (manifest + verify.py)  -- code change, run tests
2. Run pytest tests/ to verify nothing breaks             -- validation
3. Update README.md with three SwarmSync insertions       -- content change
4. Commit both changes                                    -- single commit
5. Push to GitHub                                         -- deploy
6. Update GitHub metadata via gh CLI (Task 3)             -- API calls
7. Update MCP directory submission templates (Task 4)     -- documentation
```

### Test Impact

The changes to `conduit_proof.py` add static fields to the manifest dict and static text to the VERIFY_PY string. No logic changes. Existing tests that assert on manifest structure may need updating if they check for exact key sets. Specifically:

- If any test does `assert list(manifest.keys()) == [...]`, it will need `generator`, `generator_url`, and `ecosystem` added.
- If any test asserts on the exact text output of verify.py, it will need the two new print lines added to expected output.
- The hash chain itself is NOT affected -- manifest fields are not part of the hash computation.

---

## Decisions Log

| Decision | Chosen | Alternatives Considered | Rationale |
|----------|--------|------------------------|-----------|
| Number of README SwarmSync mentions | 3 sections | 1 big section, 5+ mentions | 3 gives coverage without saturation |
| Placement of first mention | After Use Cases (line 62) | After title, after Install | Reader has already seen value before encountering SwarmSync |
| Proof bundle attribution format | Footer after verification | Banner before verification, no attribution | Footer-on-success means attribution only appears when the product works |
| manifest.json ecosystem field | Nested object | Flat fields, separate file | Nested keeps ecosystem metadata cleanly separable from core proof fields |
| GitHub homepage URL | swarmsync.ai | Repo README anchor, no homepage | Standard practice for OSS projects that serve a larger product |
| UTM parameters | Yes, per-touchpoint | No tracking, single UTM | Per-touchpoint UTMs enable measuring which funnel stages convert |
| verify.py attribution | One line, after blank line | Multiline, ASCII art, no attribution | One line is noticeable but not intrusive |

---

## Open Questions

1. **SwarmSync landing page readiness.** Does swarmsync.ai currently have a "List Your Agent" flow? The CTA in the README points there. If the flow does not exist yet, the funnel breaks at the conversion step.

2. **UTM tracking setup.** Are analytics configured on swarmsync.ai to capture UTM parameters? Without this, the per-touchpoint URLs are cosmetic.

3. **SwarmSync branding guidelines.** This spec uses "SwarmSync.ai" consistently. Confirm this is the preferred format (vs "SwarmSync", "Swarmsync", "SWARMSYNC").

4. **Conduit version bump.** The manifest currently says `conduit_version: "0.2.0"`. Should the ecosystem attribution be accompanied by a version bump to 0.3.0?

5. **Proof bundle backward compatibility.** Adding fields to manifest.json is additive and non-breaking. But verify.py consumers that parse stdout may be affected by the new attribution line. Is there any known downstream consumer of verify.py output?

---

## Success Metrics

| Metric | Measurement | Target (30 days) | Target (90 days) |
|--------|-------------|-------------------|-------------------|
| Clicks from Conduit README to swarmsync.ai | UTM tracking on swarmsync.ai | 50 | 500 |
| "List Your Agent" conversions from Conduit traffic | Conversion funnel on swarmsync.ai | 5 | 50 |
| Proof bundles containing SwarmSync attribution | Count of bundles generated after code change | All (100%) | All (100%) |
| MCP directory listings mentioning SwarmSync | Manual count across directories | 6 | 15 |
| GitHub repo clicks to swarmsync.ai homepage | GitHub traffic analytics | 20/week | 100/week |
