# Agent-Only Marketing Channels for Conduit
## Validated Design Document

**Date:** 2026-03-12
**Status:** VALIDATED
**Repo:** https://github.com/bkauto3/Conduit
**PyPI:** conduit-browser (v0.2.1)
**Context:** Multi-agent brainstorm synthesis

---

## 1. Agent-Only Discovery Channels -- Complete Taxonomy

This is the exhaustive list of every surface where an AI agent (not a human browsing a website) programmatically discovers tools. Organized by discovery mechanism.

### Category A: MCP Registries

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **Official MCP Registry** (modelcontextprotocol.io) | `server.json` in repo root; registry crawls GitHub repos with `mcp-server` topic | YES -- `server.json` exists, `<!-- mcp-name: io.github.bkauto3/conduit -->` in README | Already listed. Verify entry is current with v0.2.1 | CRITICAL |
| **awesome-mcp-servers** (punkpeye) | Agents parse README.md via GitHub API raw content | YES (per prior submission docs) | PR submitted or pending -- verify status | CRITICAL |
| **wong2/awesome-mcp-servers** | GitHub API raw content parse | Per submission docs, entry prepared | Submit PR if not done | CRITICAL |
| **mcp.so** | Web form submission; agents discover via site search API | Per submission docs, entry prepared | Submit via web form | HIGH |
| **Glama.ai** | API at glama.ai/mcp/servers; agents query by category | Per submission docs, entry prepared | Submit via "Add Server" | HIGH |
| **Smithery.ai** | smithery.ai API; agent queries tool registry | Per submission docs, entry prepared | Submit via platform | HIGH |
| **PulseMCP** | pulsemcp.com API/web; agents discover via search | Per submission docs, entry prepared | Submit via web form | HIGH |
| **mcpservers.org** | Web index; agents parse | Per submission docs, entry prepared | Submit via web form | MEDIUM |
| **MCPize.com** | Web index; agents parse | Per submission docs, entry prepared | Submit via web form | MEDIUM |
| **mcp-get** (michaellatman/mcp-get) | `packages.json` in repo; agents read via GitHub API or npm | Per submission docs, PR prepared | Submit PR to packages.json | HIGH |

**Key insight:** The `server.json` file in the repo root is the single most important machine-readable discovery artifact. It follows the official MCP server schema. Agents that want to discover MCP servers will either (a) query the official registry which ingests this file, or (b) crawl GitHub repos with the `mcp-server` topic and look for `server.json`.

### Category B: A2A Protocol Discovery

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **Google A2A Protocol** (Agent-to-Agent) | `/.well-known/agent.json` on a domain; agent fetches this file to discover capabilities | NO | Create `agent.json` conforming to A2A spec; host at swarmsync.ai/.well-known/agent.json | HIGH |
| **AgentConnect** (Linux Foundation) | Service mesh discovery; agents query registry | NO | Monitor spec maturity; too early to implement (pre-1.0) | LOW |
| **FIPA ACL** (legacy agent protocol) | Agent message passing | NO | Not relevant -- legacy standard, no modern adoption | LOW |

**Action for A2A:** The Google A2A protocol is the most important emerging standard. When an agent visits `https://swarmsync.ai/.well-known/agent.json`, it should find:

```json
{
  "name": "Conduit",
  "description": "Headless browser with cryptographic audit trails. SHA-256 hash chain, Ed25519 signatures, self-verifiable proof bundles.",
  "url": "https://github.com/bkauto3/Conduit",
  "version": "0.2.1",
  "capabilities": [
    "web-navigation",
    "web-extraction",
    "cryptographic-proof",
    "page-monitoring",
    "site-crawling"
  ],
  "authentication": {
    "type": "none",
    "note": "MIT licensed, free, no auth required"
  },
  "endpoints": {
    "mcp": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "transport": "stdio"
    }
  }
}
```

### Category C: Package Manager Metadata

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **PyPI** (pypi.org/project/conduit-browser) | `pip search` (deprecated), PyPI JSON API (`/pypi/conduit-browser/json`), pip install resolution | YES -- v0.2.1 published | Verify classifiers, keywords, description are optimized for agent queries | CRITICAL |
| **PyPI Classifiers** | Agents filter by `Topic :: Security :: Cryptography`, `Topic :: Internet :: WWW/HTTP :: Browsers` | YES -- classifiers set | Already optimized. Consider adding `Framework :: AsyncIO` classifier | MEDIUM |
| **PyPI Keywords** | Agents search keyword index | YES -- 10 keywords set | Already includes: headless-browser, audit-trail, cryptographic-proof, mcp-server, ai-agent, web-automation, stealth-browser, hash-chain, ed25519, proof-bundle | HIGH |
| **npm** (npmjs.com) | `npm search`; agents querying JS ecosystem | NO | Not applicable -- Conduit is Python-only. No action needed unless a JS wrapper is built | LOW |
| **Homebrew** | `brew search`; limited agent use | NO | Create Homebrew formula after v1.0 | LOW |
| **conda-forge** | `conda search`; used by data science agents | NO | Create conda recipe after PyPI traction confirmed | LOW |

**Missing PyPI keywords to add:** `merkle-tree`, `aivs`, `micro-proof`, `bundle-chaining`, `js-delta`. These are the AIVS-specific terms that no competitor owns in the keyword space.

### Category D: GitHub API Discoverability

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **GitHub Topics** | `GET /repos/{owner}/{repo}/topics`; agents search by topic | YES -- 13 topics set (mcp-server, mcp, headless-browser, browser-automation, cryptographic-audit, audit-trail, web-scraping, ai-agents, python, playwright, ed25519, compliance, stealth-browser) | Already set. Consider adding: `merkle-tree`, `proof-of-execution` | HIGH |
| **GitHub Description** | `GET /repos/{owner}/{repo}` -- `description` field; agents parse this | YES -- "Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles." | Evaluate whether to add AIVS-Micro (see Section 2 below) | HIGH |
| **GitHub README** | GitHub API raw content; many agents parse README for tool descriptions | YES -- comprehensive README | Ensure first 3 sentences are agent-parseable (they are) | HIGH |
| **GitHub Releases** | `GET /repos/{owner}/{repo}/releases`; agents check for activity | NO -- no releases tagged | Create v0.2.1 GitHub Release with changelog | HIGH |
| **GitHub Actions / CI badges** | Agents check for CI passing status | PARTIAL -- badge exists but is static, not linked to real CI | Set up GitHub Actions for pytest; replace static badge with dynamic one | MEDIUM |

**Critical gap: No GitHub Releases.** Agents evaluating tool maturity often check `releases` via the GitHub API. A repo with zero releases looks abandoned. Tag v0.2.1 immediately.

### Category E: .well-known Files and Web Standards

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **/.well-known/ai.txt** | HTTP GET to domain; agents read capabilities | NO (Conduit has no web domain; swarmsync.ai might) | Create at swarmsync.ai/.well-known/ai.txt with Conduit tool reference | MEDIUM |
| **/.well-known/agent.json** (A2A) | HTTP GET to domain | NO | See Category B above | HIGH |
| **robots.txt** (meta) | Agents read to check crawl permissions | NO (no domain) | Not applicable for a CLI tool; relevant only for swarmsync.ai | LOW |
| **Schema.org / JSON-LD** | Agents parse structured data from web pages | NO | Add SoftwareApplication schema to swarmsync.ai/conduit page | MEDIUM |
| **OpenAPI / API spec** | Agents discover via openapi.json | NO | Not applicable -- Conduit is stdio MCP, not HTTP API | LOW |

### Category F: LLM Training Data / Web Corpus Presence

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **LLM training data** (GPT, Claude, Gemini) | Model has learned about the tool from pre-training corpus | PARTIAL -- README is on GitHub (indexed), PyPI page exists, but zero blog posts, zero Stack Overflow answers, zero tutorials | Write 2-3 technical blog posts; answer related Stack Overflow questions; get mentioned in third-party articles | HIGH |
| **RAG pipelines** (Perplexity, ChatGPT Browse, Gemini Search) | Agent searches web in real-time; finds indexed pages | PARTIAL -- GitHub README is indexed; PyPI page is indexed | Ensure swarmsync.ai/conduit has a dedicated page with rich text (not just a redirect) | HIGH |
| **Common Crawl / WARC** | Large-scale web corpus used for training data | MINIMAL | More web presence = more training data inclusion in future models | MEDIUM |
| **Wikipedia** | Agents cite and reference Wikipedia; presence = credibility | NO | Too early -- need notability (press coverage, citations) before creating a Wikipedia article | LOW |
| **Stack Overflow** | Agents search SO for tool recommendations | NO | Answer questions about "audited browser automation", "cryptographic proof of web actions", link to Conduit | HIGH |

**Key insight:** The single most impactful thing for LLM discoverability is getting Conduit mentioned in contexts where agents search. When an agent asks "I need an auditable browser" or "how do I prove what a web scraper did", the answer needs to include Conduit. This means: Stack Overflow answers, blog posts indexed by search engines, and mentions in existing tool comparison articles.

### Category G: Agent Framework Default Tool Lists

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **LangChain Tools** | `from langchain_community.tools import ...`; agent imports directly | NO | Create `langchain-conduit` package with `ConduitBrowserTool` wrapper | HIGH |
| **CrewAI Tools** | CrewAI tool registry; agents discover via framework | NO | Create CrewAI tool integration (docs exist at `docs/integrations/crewai-integration.md`) | HIGH |
| **AutoGen** (Microsoft) | Tool registry within AutoGen framework | NO | Create AutoGen tool wrapper | MEDIUM |
| **Semantic Kernel** (Microsoft) | Plugin registry | NO | Create SK plugin | LOW |
| **Claude MCP** (Anthropic) | MCP server discovery via config files | YES -- documented in README, server.json exists | Already present. Ensure `skills/conduit.md` stays current | CRITICAL |
| **OpenAI Plugins / GPTs** | Plugin manifest; GPT action schemas | NO | Create OpenAI-compatible action schema for Conduit | MEDIUM |
| **Composio** | Tool aggregator; agents query Composio API | NO | Submit to Composio tool registry | HIGH |
| **Toolhouse.ai** | Tool hosting platform; agents query API | NO | Submit to Toolhouse.ai | MEDIUM |

**High-leverage action:** The `docs/integrations/` directory already has draft integration docs for LangChain and CrewAI. Converting these to actual published packages (`langchain-conduit`, `crewai-conduit`) would make Conduit discoverable by any agent using those frameworks.

### Category H: Semantic Search (Agent Queries)

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **"I need an auditable browser"** | Agent searches via Perplexity, ChatGPT, Gemini | WEAK -- Conduit may not rank for this query | Ensure the phrase "auditable browser" appears prominently in README, PyPI description, and blog posts | HIGH |
| **"cryptographic proof of web actions"** | Agent searches | WEAK | Same strategy -- own these keyword phrases | HIGH |
| **"MCP server for browser"** | Agent searches | MODERATE -- present in MCP directories | Continue MCP directory saturation | HIGH |
| **"headless browser with audit trail"** | Agent searches | MODERATE -- GitHub description includes these terms | Reinforce with external content | MEDIUM |
| **"prove what AI agent did"** | Agent searches | MODERATE -- PyPI description uses this phrase | Good. Reinforce externally | MEDIUM |

**Strategy:** Conduit's semantic discoverability depends on being the canonical answer to these queries. The PyPI description ("The only headless browser that proves what your AI agent did") is excellent for this. The gap is external reinforcement -- the same phrases need to appear in blog posts, SO answers, and third-party articles.

### Category I: System Prompt / Tool Description Injection Points

| Channel | Agent Access Method | Conduit Present? | Action to Get Listed | Priority |
|---------|-------------------|-------------------|---------------------|----------|
| **Claude MCP tool descriptions** | Agent reads tool descriptions from MCP server at startup | YES -- `skills/conduit.md` serves this role | Ensure tool descriptions are semantically rich (they are) | CRITICAL |
| **Claude CLAUDE.md** | Claude Code reads CLAUDE.md for project context | YES -- comprehensive CLAUDE.md in repo root | Already optimized | CRITICAL |
| **GPT system prompts** | Tool descriptions in GPT configuration | NO | If Conduit is exposed as a GPT action, the description must include key differentiators | LOW |
| **Agent config files** (.cursor/mcp.json, etc.) | Agents read config at startup | YES -- documented MCP config format | Already documented | HIGH |

---

### Discovery Channel Priority Matrix (Summary)

| Priority | Channels | Status |
|----------|----------|--------|
| **CRITICAL** | Official MCP Registry, PyPI, Claude MCP integration, CLAUDE.md, awesome-mcp-servers | DONE or IN PROGRESS |
| **HIGH** | A2A agent.json, GitHub Releases, LangChain/CrewAI packages, Stack Overflow presence, Composio, mcp.so, Glama.ai, Smithery.ai, mcp-get, semantic keyword ownership | NOT STARTED |
| **MEDIUM** | .well-known/ai.txt, Schema.org on swarmsync.ai, GitHub Actions CI, conda-forge, AutoGen, Toolhouse.ai, mcpservers.org, MCPize.com | NOT STARTED |
| **LOW** | npm, Homebrew, Wikipedia, FIPA ACL, AgentConnect, Semantic Kernel, GPT plugins | DEFERRED |

---

## 2. README / Description Audit

### Current GitHub Description (129 chars)

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles.
```

### What the Description Does Not Mention

- AIVS-Micro (6-field micro proofs)
- Merkle trees (for crawl proof verification)
- Bundle chaining (scan chain linking)
- JS Delta (JavaScript change detection)
- 30+ actions across 7 waves
- Budget enforcement
- Robots.txt compliance

### Three Options

#### Option A: Keep Current (Do Not Clutter)

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles.
```

**Trade-off:**
- PRO: Clean, scannable, hits the big differentiators (crypto audit + MCP + stealth + proofs)
- PRO: Already indexed by search engines and LLMs at this text
- PRO: GitHub descriptions have a 350-char limit; 129 chars leaves room but is already dense
- CON: Agents searching for "merkle tree browser" or "micro proof" will not match
- CON: Does not signal the AIVS capabilities that are unique
- VERDICT: Safe but leaves discovery value on the table

#### Option B: Update with New Features (Additive)

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles. AIVS-Micro proofs. Merkle trees. Bundle chaining.
```
(183 characters)

**Trade-off:**
- PRO: Adds three unique AIVS keywords that no competitor has
- PRO: Still under the 350-char limit
- PRO: Agents searching for "merkle tree" or "micro proof" now match
- CON: Reads like a feature list, not a value proposition
- CON: AIVS-Micro is not a known term outside Conduit -- agents will not search for it
- CON: Dilutes the core message
- VERDICT: More discoverable but less compelling

#### Option C: Completely Rethink the Tagline (Value-First)

```
The only headless browser that proves what your AI agent did. Cryptographic audit trails, self-verifiable proof bundles, stealth automation. MCP server.
```
(152 characters)

**Trade-off:**
- PRO: Leads with value ("proves what your AI agent did"), not technology
- PRO: Matches the exact query an agent or developer would use: "prove what agent did"
- PRO: Still hits the key technical terms (cryptographic, proof bundles, MCP, stealth)
- CON: Drops explicit mention of SHA-256, Ed25519, hash chain -- the technical credibility signals
- CON: "The only" is a claim that could become false
- CON: Does not mention AIVS-specific features
- VERDICT: Best for human developers; slightly worse for agents doing keyword matching

### Recommendation

**Option A for the GitHub description. Option C for the PyPI description (which already uses Option C's framing).**

Rationale: The GitHub description is parsed by agents doing keyword matching against specific technical terms. SHA-256, Ed25519, hash chain, MCP server, stealth, proof bundles -- these are the exact strings agents search for. The AIVS-specific terms (micro proof, merkle tree, bundle chaining) are too Conduit-specific to drive discovery; no agent is searching for "AIVS-Micro" because only Conduit uses that term.

Instead, add AIVS discoverability through:
1. PyPI keywords (add: `merkle-tree`, `micro-proof`, `bundle-chaining`)
2. GitHub topics (add: `merkle-tree`, `proof-of-execution`)
3. A dedicated AIVS section in the README (see Section 5)

---

## 3. Feature Uniqueness Ranking

Ranked from most unique (no competitor has this) to least unique (others have similar).

### Tier 1: Truly Unique (No Competitor)

**1. Full JavaScript source stored verbatim in the audit hash chain**
- Uniqueness: 10/10
- Reasoning: No other headless browser logs the actual JS code that executed. Playwright, Puppeteer, Selenium -- they log that JS ran and what it returned. Conduit logs WHAT RAN. This is the single strongest differentiator. It enables forensic proof of "this exact code executed on this page at this time."
- Competitor gap: Complete. Zero alternatives exist.

**2. Self-verifiable proof bundles (stdlib-only verify.py ships inside the bundle)**
- Uniqueness: 9.5/10
- Reasoning: The proof bundle is self-contained. No Conduit installation, no pip install, no external dependencies. Just `python verify.py`. The verification logic travels WITH the evidence. This is like a notarized document that carries its own notary. No other browser tool does this.
- Competitor gap: Playwright has tracing but it is not self-verifiable. No other tool ships a verifier inside the evidence package.

**3. AIVS-Micro (6-field minimal cryptographic proof, ~200 bytes)**
- Uniqueness: 9/10
- Reasoning: A micro proof that fits in a DNS TXT record or HTTP header. URL + DOM hash + timestamp + signature + scanner version hash + scan origin. No other tool produces proofs this small. Useful for continuous monitoring at 15-minute intervals without storage bloat.
- Competitor gap: Complete. The concept of a "micro proof" for browser sessions does not exist elsewhere.

**4. Bundle chaining (scan chain linking successive proof bundles)**
- Uniqueness: 9/10
- Reasoning: Each proof bundle references the SHA-256 hash of the previous bundle, creating a chain of chains. This means you can prove not just what happened in one session but the entire sequence of sessions over time. No other tool links proof bundles into a scan chain.
- Competitor gap: Complete. Blockchain-adjacent concept applied to browser sessions.

### Tier 2: Rare (Very Few Competitors)

**5. Merkle trees for crawl proof verification**
- Uniqueness: 8/10
- Reasoning: When Conduit crawls 100 pages, it builds a Merkle tree over the page hashes. This enables selective verification -- you can prove one specific page was part of the crawl without downloading the entire proof bundle. Useful for large crawls where full verification is expensive.
- Competitor gap: Merkle trees are well-known in blockchain; novel in browser automation.

**6. SHA-256 hash-chained audit log (tamper-evident)**
- Uniqueness: 7/10
- Reasoning: Hash chains are a known concept but no other headless browser implements one on every action. The closest competitor is generic audit logging (which is append-only but not hash-chained, so tampering is not mathematically detectable).
- Competitor gap: Concept is known; application to browser sessions is unique.

**7. Ed25519 digital signatures on sessions**
- Uniqueness: 7/10
- Reasoning: Ed25519 is standard cryptography. What is unique is applying it to browser session integrity. No other browser tool signs sessions with a persistent identity key.
- Competitor gap: Cryptographic signing exists elsewhere; applying it to browser automation is novel.

### Tier 3: Differentiated (Competitors Exist but Conduit's Implementation Is Superior)

**8. Stealth (Patchright fork)**
- Uniqueness: 5/10
- Reasoning: Patchright exists independently. Several other tools use stealth patches (undetected-chromedriver, etc.). Conduit's advantage is combining stealth with the audit layer -- you get anti-detection AND cryptographic proof.
- Competitor gap: Stealth is not unique; stealth + audit is.

**9. Built-in budget enforcement (billing ledger)**
- Uniqueness: 5/10
- Reasoning: OpenAI and other agent platforms have spending limits. What is unique is per-action cost tracking in a browser tool, integrated with the audit chain so costs are tamper-evident too.
- Competitor gap: Concept exists; per-action browser billing is novel.

**10. Sensitive input auto-redaction**
- Uniqueness: 4/10
- Reasoning: Other tools have credential redaction. Conduit's implementation is automatic and covers a broad set of patterns. Not unique but well-implemented.
- Competitor gap: Small.

**11. Robots.txt compliant BFS crawler**
- Uniqueness: 3/10
- Reasoning: Scrapy, Crawlee, and many other crawlers are robots.txt compliant. Conduit's version is tightly integrated with the audit layer.
- Competitor gap: Many alternatives.

**12. MCP server**
- Uniqueness: 3/10
- Reasoning: Multiple browser MCP servers exist (Playwright MCP, Browserbase, Browser MCP). Conduit's differentiator is the audit layer, not the MCP interface itself.
- Competitor gap: Many alternatives. The audit layer is the moat.

### Positioning Implications

The marketing message should lead with features 1-4 (truly unique, zero competitors):

> **Conduit is the only browser that proves what ran.** Full JS source in the audit chain. Self-verifiable proof bundles. Micro proofs in 200 bytes. Chain your proofs across sessions.

Features 5-7 (rare) are strong supporting evidence. Features 8-12 are table stakes that should be mentioned but not led with.

---

## 4. Self-Marketing Specification

### Concept

Conduit uses itself to submit to directories, filling forms and clicking buttons -- and the proof bundle from each submission becomes a demo artifact showing what Conduit can do. The act of marketing IS the product demo.

### System Design

#### Input

A JSON manifest of target directories:

```json
{
  "targets": [
    {
      "id": "pulsemcp",
      "name": "PulseMCP",
      "url": "https://pulsemcp.com/submit",
      "type": "web_form",
      "fields": {
        "name": "Conduit",
        "url": "https://github.com/bkauto3/Conduit",
        "description": "The only headless browser that proves what your AI agent did...",
        "category": "Browser Automation"
      },
      "submit_selector": "button[type='submit']",
      "success_indicator": ".success-message"
    },
    {
      "id": "mcp_so",
      "name": "mcp.so",
      "url": "https://mcp.so/submit",
      "type": "web_form",
      "fields": {
        "type_select": "MCP Server",
        "name": "Conduit",
        "url": "https://github.com/bkauto3/Conduit",
        "config": "{...}"
      },
      "submit_selector": "#submit",
      "success_indicator": "text:Thank you"
    }
  ]
}
```

#### Process: The Exact Action Sequence

For each target in the manifest:

```python
async def self_market(bridge: ConduitBridge, target: dict) -> dict:
    """
    Conduit submits itself to a directory and exports the proof.
    The proof bundle IS the demo artifact.
    """
    session_results = []

    # Step 1: Navigate to the submission page
    nav = await bridge.execute({
        "action": "navigate",
        "url": target["url"]
    })
    session_results.append(("navigate", nav))

    # Step 2: Screenshot the empty form (before state)
    await bridge.execute({
        "action": "screenshot",
        "path": f"submission_{target['id']}_before.png"
    })

    # Step 3: Fill each form field
    for field_selector, field_value in target["fields"].items():
        if field_selector.endswith("_select"):
            # Dropdown select
            await bridge.execute({
                "action": "select_option",
                "selector": f"#{field_selector.replace('_select', '')}",
                "value": field_value
            })
        else:
            await bridge.execute({
                "action": "fill",
                "selector": f"#{field_selector}",
                "text": field_value
            })

    # Step 4: Screenshot the filled form (after state)
    await bridge.execute({
        "action": "screenshot",
        "path": f"submission_{target['id']}_filled.png"
    })

    # Step 5: Click submit
    await bridge.execute({
        "action": "click",
        "selector": target["submit_selector"]
    })

    # Step 6: Wait for success indicator
    await bridge.execute({
        "action": "wait_for",
        "condition": "selector" if target["success_indicator"].startswith(".")
                    else "text",
        "value": target["success_indicator"].replace("text:", ""),
        "timeout_ms": 10000
    })

    # Step 7: Screenshot the success page
    await bridge.execute({
        "action": "screenshot",
        "path": f"submission_{target['id']}_success.png"
    })

    # Step 8: Export the proof bundle
    proof = await bridge.execute({
        "action": "export_proof",
        "output_dir": f"proofs/submissions/{target['id']}"
    })

    # Step 9: Export a micro proof for the submission
    micro = await bridge.execute({
        "action": "export_micro",
        "url": target["url"],
        "dom_hash": nav.get("content_hash", ""),
        "scan_origin": "self-marketing"
    })

    return {
        "target": target["name"],
        "proof_bundle": proof["path"],
        "micro_proof": micro.get("micro_proof"),
        "screenshots": [
            f"submission_{target['id']}_before.png",
            f"submission_{target['id']}_filled.png",
            f"submission_{target['id']}_success.png"
        ],
        "action_count": proof["action_count"],
        "chain_hash": proof["chain_hash"]
    }
```

#### Output

For each submission, Conduit produces:

1. **Proof bundle** (.tar.gz) -- cryptographic evidence that the submission happened
2. **Micro proof** -- 200-byte minimal proof suitable for embedding in a README or API response
3. **Screenshots** -- before, filled, and success states
4. **Manifest** -- JSON summary of all submissions with proof hashes

#### Meta-Value: Proof Bundles as Demo Artifacts

This is the recursive marketing loop:

1. Conduit submits itself to Directory X
2. The submission creates a proof bundle
3. The proof bundle is published in the repo under `proofs/submissions/`
4. The README links to these proofs as examples: "Here is cryptographic proof that Conduit submitted itself to PulseMCP. Verify it yourself: `python verify.py`"
5. A developer browsing the README sees a REAL proof bundle from a REAL task
6. This is more convincing than any synthetic demo

**README section to add:**

```markdown
## Real-World Proof Bundles

Conduit submitted itself to these directories -- and each submission
produced a cryptographic proof bundle you can verify:

| Directory | Proof Bundle | Verify |
|-----------|-------------|--------|
| PulseMCP | [proof](proofs/submissions/pulsemcp/) | `cd proofs/submissions/pulsemcp && python verify.py` |
| mcp.so | [proof](proofs/submissions/mcp_so/) | `cd proofs/submissions/mcp_so && python verify.py` |
| Glama.ai | [proof](proofs/submissions/glama/) | `cd proofs/submissions/glama && python verify.py` |

These are not synthetic examples. Each bundle is the actual proof
from when Conduit submitted itself. Every click, every form fill,
every page load -- hash-chained and signed.
```

#### Safety Considerations

- All form submissions must go through human approval (Conduit's `safety_mode: strict` already requires this for irreversible actions)
- The self-marketing script should be run with `--dry-run` first to verify selectors
- Proof bundles should be reviewed before publishing to ensure no sensitive data leaked
- Rate limiting: one submission per directory per day maximum

---

## 5. Updated README Section Proposals

### 5a. New Section: "Advanced Proof Features"

Insert after the existing "How Proof Bundles Work" section (after line ~196 in current README):

```markdown
## Advanced Proof Features

### AIVS-Micro -- Minimal Cryptographic Proofs

For continuous monitoring, full proof bundles are overkill. AIVS-Micro
produces a 6-field proof in ~200 bytes -- small enough for a DNS TXT
record or HTTP response header.

```python
micro = await bridge.execute({
    "action": "export_micro",
    "url": "https://example.com",
    "dom_hash": fingerprint["fingerprint"]
})
print(micro["micro_proof"])
# {
#   "url": "https://example.com",
#   "dom_hash": "sha256:a3f9...",
#   "timestamp": "2026-03-12T00:00:00.000000000Z",
#   "signature": "ed25519:base64...",
#   "scanner_version_hash": "sha256:7b1a...",
#   "scan_origin": "local"
# }
```

Six fields. Signed. Verifiable. A third party with your public key can
confirm: this scan happened, at this time, on this page, in this state.

### Bundle Chaining -- Linked Proof History

Each proof bundle includes the SHA-256 hash of the previous bundle,
creating a chain of chains. Modify or delete any prior bundle and the
link breaks.

```python
# First export
proof1 = await bridge.execute({"action": "export_proof"})

# ... more work ...

# Second export -- automatically references proof1
proof2 = await bridge.execute({"action": "export_proof"})
# proof2 contains "previous_bundle_hash" pointing to proof1
```

This is useful for continuous monitoring: prove not just what happened
in one session, but the unbroken sequence of all sessions over time.

### Merkle Trees -- Selective Crawl Verification

When Conduit crawls 100 pages, it builds a Merkle tree over the page
hashes. A verifier can prove any single page was part of the crawl
without downloading the full proof bundle.

```python
# Crawl produces page hashes
crawl = await bridge.execute({
    "action": "crawl",
    "url": "https://docs.example.com",
    "max_depth": 2
})

# Export with Merkle tree
proof = await bridge.execute({
    "action": "export_proof",
    "page_hashes": crawl.get("page_hashes", [])
})
# proof["merkle_root"] is the single hash representing all pages
```

The Merkle tree is included in the proof bundle as `merkle_tree.json`.
```

### 5b. New Section: "JS Delta -- Track What Changed"

Insert in the Wave 2 action reference (after the `eval` action description, around line ~258):

```markdown
- **`js_delta`** -- Execute JavaScript and compare to a previous result. Returns the diff. Useful for tracking DOM mutations, cookie changes, or localStorage state over time. The delta itself is stored in the audit chain.
```

### 5c. Updated Comparison Table Row

Add to the existing comparison table (after line ~133):

```markdown
| AIVS-Micro (200-byte proofs) | Yes | No | No | No |
| Merkle tree crawl proofs | Yes | No | No | No |
| Bundle chaining (scan chain) | Yes | No | No | No |
```

### 5d. New Section: "What Only Conduit Has"

Insert after the comparison table, before "How Proof Bundles Work":

```markdown
### What Only Conduit Has

No other headless browser offers any of these:

1. **Full JS source in the audit chain** -- Prove exactly what code ran, not just that code ran
2. **Self-verifiable proof bundles** -- The verifier ships inside the evidence. Zero dependencies
3. **AIVS-Micro** -- 200-byte signed proofs for continuous monitoring at scale
4. **Bundle chaining** -- Link proof bundles into an unbroken chain across sessions
5. **Merkle tree crawl proofs** -- Verify any single page from a 1000-page crawl

These are not incremental improvements over Playwright or Puppeteer.
They are capabilities that do not exist anywhere else.
```

---

## Decisions Log

| # | Decision | Chosen | Alternatives | Rationale |
|---|----------|--------|-------------|-----------|
| 1 | GitHub description | Keep current (Option A) | Update with AIVS terms, rewrite as value-first | Technical keywords in description serve agent keyword matching better than value propositions |
| 2 | AIVS discoverability | Add via PyPI keywords + GitHub topics + README section | Add to GitHub description | More surface area without cluttering the primary description |
| 3 | Self-marketing scope | Form submission only (web forms) | Also include GitHub PR creation | PRs require git operations; form submissions are the natural Conduit use case |
| 4 | README additions | Add 3 new sections (~250 words total) | Full README rewrite | Existing README is strong; additive changes only (YAGNI) |
| 5 | Feature positioning lead | JS source in audit chain (most unique) | Self-verifiable proofs, AIVS-Micro | True uniqueness (zero competitors) is the strongest positioning anchor |
| 6 | A2A protocol | Implement agent.json on swarmsync.ai | Wait for spec maturity | Google A2A is gaining adoption; early presence is low-cost, high-optionality |

---

## Open Questions

1. **A2A agent.json hosting:** Does swarmsync.ai have the ability to serve static files at `/.well-known/agent.json`?
2. **GitHub Releases:** Has v0.2.1 been tagged as a GitHub Release? If not, this is the highest-impact 2-minute action available.
3. **LangChain/CrewAI packages:** The integration docs exist at `docs/integrations/`. What is the timeline for publishing actual packages?
4. **Self-marketing execution:** Who approves the form submissions before Conduit clicks "submit"?
5. **Stack Overflow strategy:** Which specific SO questions should be targeted for answers mentioning Conduit?

---

## Implementation Priority (Next Actions)

| # | Action | Effort | Impact | Dependency |
|---|--------|--------|--------|------------|
| 1 | Tag v0.2.1 as GitHub Release | 2 min | HIGH -- agents check releases for maturity signal | None |
| 2 | Add PyPI keywords: merkle-tree, micro-proof, bundle-chaining | 5 min | MEDIUM -- searchability for AIVS terms | None |
| 3 | Add GitHub topics: merkle-tree, proof-of-execution | 2 min | MEDIUM -- searchability | None |
| 4 | Add "Advanced Proof Features" README section | 20 min | HIGH -- documents AIVS capabilities | None |
| 5 | Add "What Only Conduit Has" README section | 10 min | HIGH -- positioning clarity | None |
| 6 | Create agent.json for A2A on swarmsync.ai | 30 min | HIGH -- emerging standard | swarmsync.ai access |
| 7 | Build self-marketing submission manifest | 1 hr | HIGH -- recursive demo value | Target selector research |
| 8 | Publish langchain-conduit package | 2-4 hr | VERY HIGH -- framework integration | LangChain API familiarity |
| 9 | Write first Stack Overflow answer | 30 min | HIGH -- LLM training corpus | Find right questions |
| 10 | Verify all MCP directory submissions are live | 1 hr | HIGH -- close existing gaps | Directory account access |

---

*Generated by SoSpec multi-agent brainstorm synthesis, 2026-03-12*
