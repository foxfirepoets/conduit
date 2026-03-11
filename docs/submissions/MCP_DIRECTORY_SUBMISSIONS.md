# Conduit - Directory Submission Guide

All ready-to-submit entries for MCP directories, awesome-lists, and registries.

**Project:** Conduit
**GitHub:** https://github.com/bkauto3/Conduit
**Homepage:** https://swarmsync.ai/conduit
**License:** MIT
**Language:** Python 3.10+
**Version:** 0.2.0

---

## Standard Descriptions

### Short (for directories with character limits)

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### Long (for directories allowing more)

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle. Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents. 26 actions across 4 waves. Robots.txt compliant crawling. Budget enforcement. Sensitive input auto-redaction. Part of the SwarmSync.ai agent ecosystem.
```

### MCP Server Configuration

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

---

## 1. awesome-mcp-servers (punkpeye/awesome-mcp-servers)

**Repository:** https://github.com/punkpeye/awesome-mcp-servers

### Table Row (add to Browser Automation section)

```markdown
| [Conduit](https://github.com/bkauto3/Conduit) | Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth (Patchright). Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem. |
```

### PR Title

```
Add Conduit - headless browser with cryptographic audit trails
```

### Commit Message

```
Add Conduit to Browser Automation section

Conduit is a headless browser MCP server with SHA-256 hash chain +
Ed25519 audit trails. Built on Patchright (stealth Playwright fork).
Every action is recorded in a tamper-evident chain and exportable as
self-verifiable proof bundles.
```

### PR Body

```markdown
## Add Conduit

**Category:** Browser Automation

**What is Conduit?**

Conduit is a headless browser MCP server with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle.

**Key differentiators from other browser MCP servers:**

- **Cryptographic audit trail** — SHA-256 hash chain on every action, not just logging
- **Ed25519-signed proof bundles** — self-verifiable with zero dependencies (stdlib-only `verify.py` ships inside the bundle)
- **Stealth** — built on Patchright (stealth Playwright fork), not raw Playwright
- **26 actions across 4 waves** — core browser, interaction, extraction, advanced (crawl, fingerprint, change detection)
- **Robots.txt compliant** — BFS crawler honors robots.txt and Crawl-delay
- **Budget enforcement** — built-in billing ledger prevents runaway agent costs
- **Sensitive input auto-redaction** — passwords, tokens, API keys automatically redacted in audit chain

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit
- License: MIT
- Language: Python 3.10+

Part of the SwarmSync.ai agent ecosystem.
```

---

## 2. PulseMCP (pulsemcp.com)

**Submission URL:** https://pulsemcp.com (submit via their website form)

### Submission Form Content

| Field | Value |
|-------|-------|
| **Server Name** | Conduit |
| **GitHub URL** | https://github.com/bkauto3/Conduit |
| **Homepage URL** | https://swarmsync.ai/conduit |
| **Category** | Browser Automation |
| **License** | MIT |
| **Language** | Python |
| **Short Description** | Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem. |

### Long Description (if field available)

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle. Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents. 26 actions across 4 waves. Robots.txt compliant crawling. Budget enforcement. Sensitive input auto-redaction. Part of the SwarmSync.ai agent ecosystem.

Key features:
- SHA-256 hash-chained audit log on every browser action
- Ed25519-signed session proofs exportable as .tar.gz bundles
- Self-verifiable proof bundles (stdlib-only verify.py, zero dependencies)
- Stealth browser engine (Patchright, stealth Playwright fork)
- 26 actions: navigate, click, type, extract, eval, crawl, fingerprint, change detection, web search
- Robots.txt compliant BFS crawler with adaptive rate limiting
- Budget enforcement via billing ledger
- Sensitive input auto-redaction (passwords, tokens, API keys)
- Multi-engine web search (DuckDuckGo, Brave, Exa, Tavily)
- Academic search (Semantic Scholar, arXiv)
```

### MCP Config (if field available)

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

### Tags/Keywords

```
browser-automation, headless-browser, audit-trail, cryptographic-proof, stealth-browser, web-scraping, mcp-server, ai-agent, ed25519, hash-chain, proof-bundle, playwright
```

---

## 3. Smithery.ai (smithery.ai)

**Submission URL:** https://smithery.ai (submit via their platform)

### Listing Content

| Field | Value |
|-------|-------|
| **Name** | Conduit |
| **Repository** | https://github.com/bkauto3/Conduit |
| **Homepage** | https://swarmsync.ai/conduit |
| **Category** | Browser Automation |
| **License** | MIT |
| **Runtime** | Python 3.10+ |

### Description

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle. Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents. 26 actions across 4 waves. Robots.txt compliant crawling. Budget enforcement. Sensitive input auto-redaction. Part of the SwarmSync.ai agent ecosystem.
```

### Installation

```bash
git clone https://github.com/bkauto3/Conduit.git
cd Conduit
pip install -r requirements.txt
```

### Configuration

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

### Tools / Actions

```
Wave 0 (Core): navigate, click, type, fill, extract, screenshot
Wave 1 (Interaction): scroll, wait, wait_for, key_press, hover, select_option, handle_dialog, navigate_back, console_messages
Wave 2 (Extraction): eval, extract_main, extract_structured, output_to_file, accessibility_snapshot, network_requests
Wave 3 (Advanced): map, crawl, fingerprint, check_changed, export_proof
Wave 4 (CAPTCHA): detect_captcha, solve_captcha, solve_captcha_vision
Wave 5 (Proxy): rotate_proxy
Wave 6 (Search): web_search, academic_search
```

---

## 4. mcp.so

**Submission URL:** https://mcp.so (submit via their website)

### Listing Content

| Field | Value |
|-------|-------|
| **Name** | Conduit |
| **GitHub URL** | https://github.com/bkauto3/Conduit |
| **Website** | https://swarmsync.ai/conduit |
| **Category** | Browser Automation |
| **License** | MIT |
| **Language** | Python |

### Description

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### Detailed Description

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle. Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents.

Features:
- SHA-256 hash-chained audit log
- Ed25519-signed session proofs
- Self-verifiable proof bundles (zero dependencies)
- Stealth browser (Patchright)
- 26 actions across 4 waves
- Robots.txt compliant BFS crawler
- Budget enforcement
- Sensitive input auto-redaction
- Multi-engine web search
- Academic search (Semantic Scholar, arXiv)

Part of the SwarmSync.ai agent ecosystem.
```

### Configuration

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

---

## 5. Glama.ai (glama.ai/mcp/servers)

**Submission URL:** https://glama.ai/mcp/servers (submit via their platform)

### Listing Content

| Field | Value |
|-------|-------|
| **Server Name** | Conduit |
| **GitHub Repository** | https://github.com/bkauto3/Conduit |
| **Website** | https://swarmsync.ai/conduit |
| **Category** | Browser Automation |
| **License** | MIT |
| **Language** | Python |

### Short Description

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### Full Description

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle. Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents. 26 actions across 4 waves. Robots.txt compliant crawling. Budget enforcement. Sensitive input auto-redaction. Part of the SwarmSync.ai agent ecosystem.
```

### Server Configuration

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

### Key Features

```
- Cryptographic audit trail (SHA-256 hash chain + Ed25519 signatures)
- Self-verifiable proof bundles (stdlib-only verifier, zero dependencies)
- Stealth browser engine (Patchright, stealth Playwright fork)
- 26 browser actions across 4 waves
- Robots.txt compliant BFS crawling
- Budget enforcement and billing ledger
- Sensitive input auto-redaction
- Multi-engine web search (DuckDuckGo, Brave, Exa, Tavily)
- Academic search (Semantic Scholar, arXiv)
- Page fingerprinting and change detection
```

---

## 6. mcpservers.org

**Submission URL:** https://mcpservers.org (submit via their website)

### Listing Content

| Field | Value |
|-------|-------|
| **Name** | Conduit |
| **URL** | https://github.com/bkauto3/Conduit |
| **Homepage** | https://swarmsync.ai/conduit |
| **Category** | Browser Automation |
| **License** | MIT |
| **Language** | Python 3.10+ |

### Description

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### Long Description

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle.

Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents. 26 actions across 4 waves. Robots.txt compliant crawling. Budget enforcement. Sensitive input auto-redaction.

Use cases:
- Compliance automation (SOC 2, SOX, GDPR, HIPAA audit trails)
- Security research (forensic session capture with signed evidence)
- AI agent browser control (budget enforcement, full action replay)
- Web monitoring (signed change detection with cryptographic proof)
- Site mapping and bulk extraction (robots.txt compliant BFS crawl)

Part of the SwarmSync.ai agent ecosystem.
```

### Configuration

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

---

## 7. MCPize.com

**Submission URL:** https://mcpize.com (submit via their website)

### Listing Content

| Field | Value |
|-------|-------|
| **Server Name** | Conduit |
| **GitHub** | https://github.com/bkauto3/Conduit |
| **Website** | https://swarmsync.ai/conduit |
| **Category** | Browser Automation |
| **License** | MIT |
| **Language** | Python |

### Description

```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### Detailed Description

```
Conduit is the only headless browser with a cryptographic audit layer. Every action — navigate, click, type, extract, eval — is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle. Built on Patchright (stealth Playwright fork). Designed as the browser engine for autonomous AI agents. 26 actions across 4 waves. Robots.txt compliant crawling. Budget enforcement. Sensitive input auto-redaction. Part of the SwarmSync.ai agent ecosystem.
```

### Installation

```bash
git clone https://github.com/bkauto3/Conduit.git
cd Conduit
pip install -r requirements.txt
```

### Configuration

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

---

## 8. mcp-get (michaellatman/mcp-get)

**Repository:** https://github.com/michaellatman/mcp-get

### Registry Entry Format

The mcp-get registry uses a JSON format. Submit a PR adding to `packages/packages.json`:

```json
{
  "name": "conduit-browser",
  "description": "Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth. Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.",
  "runtime": "python",
  "command": "python",
  "args": ["-m", "tools.conduit_bridge"],
  "sourceUrl": "https://github.com/bkauto3/Conduit",
  "homepage": "https://swarmsync.ai/conduit",
  "license": "MIT"
}
```

### PR Title

```
Add conduit-browser - headless browser with cryptographic audit trails
```

### Commit Message

```
feat: add conduit-browser to registry

Conduit is a headless browser MCP server with SHA-256 hash chain +
Ed25519 audit trails. Self-verifiable proof bundles. Built on Patchright
(stealth Playwright fork). MIT licensed.
```

### PR Body

```markdown
## Add conduit-browser

**Package name:** conduit-browser
**Runtime:** Python 3.10+
**License:** MIT

**Description:**

Conduit is a headless browser MCP server with a cryptographic audit layer. Every action is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle.

**Key features:**
- SHA-256 hash-chained audit log on every browser action
- Ed25519-signed session proofs
- Self-verifiable proof bundles (zero external dependencies)
- Stealth browser engine (Patchright, stealth Playwright fork)
- 26 browser actions across 4 waves
- Robots.txt compliant crawling
- Budget enforcement
- Sensitive input auto-redaction

**Links:**
- Repository: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit

Part of the SwarmSync.ai agent ecosystem.

**MCP Configuration:**

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```
```

---

## 9. awesome-claude-code (on GitHub)

**Repository:** https://github.com/anthropics/awesome-claude-code (or community fork)

### Entry (add to MCP Servers section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth (Patchright). Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - headless browser MCP server with cryptographic audit trails
```

### Commit Message

```
Add Conduit to MCP Servers section

Conduit is a headless browser with SHA-256 hash chain + Ed25519 audit
trails, built as an MCP server. Stealth browser engine (Patchright).
Self-verifiable proof bundles. MIT licensed.
```

### PR Body

```markdown
## Add Conduit to MCP Servers

Conduit is a headless browser MCP server with a cryptographic audit layer. Designed for AI agents that need browser automation with verifiable proof of execution.

**Why it belongs here:**
- Purpose-built as an MCP server for Claude Code and other AI agents
- Every browser action is recorded in a tamper-evident SHA-256 hash chain
- Ed25519-signed session proofs exportable as self-verifiable bundles
- Stealth browser engine (Patchright, stealth Playwright fork)
- 26 actions: navigate, click, type, extract, eval, crawl, fingerprint, change detection, web search
- Budget enforcement prevents runaway agent costs
- MIT licensed, Python 3.10+

**MCP Configuration:**

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit

Part of the SwarmSync.ai agent ecosystem.
```

---

## 10. awesome-headless-browsers

**Repository:** Search GitHub for `awesome-headless-browsers`

### Entry (add to Headless Browsers section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash chain + Ed25519 audit trails. Built on Patchright (stealth Playwright fork). Self-verifiable proof bundles. MCP server for AI agents. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - headless browser with cryptographic audit layer
```

### Commit Message

```
Add Conduit to headless browsers list

Conduit is a headless browser with SHA-256 hash chain + Ed25519 audit
trails. Built on Patchright (stealth Playwright fork). Exports
self-verifiable proof bundles. MIT licensed, Python 3.10+.
```

### PR Body

```markdown
## Add Conduit

Conduit is the only headless browser with a cryptographic audit layer. Every action is recorded in a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and exportable as a self-verifiable proof bundle.

**What makes it different:**
- Every browser action (navigate, click, type, extract, eval) is hash-chained and signed
- Proof bundles are self-verifiable with zero dependencies (stdlib-only `verify.py`)
- Built on Patchright (stealth Playwright fork) for anti-detection
- Designed as an MCP server for autonomous AI agents
- Robots.txt compliant BFS crawling with adaptive rate limiting
- Budget enforcement and sensitive input auto-redaction
- MIT licensed, Python 3.10+

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit

Part of the SwarmSync.ai agent ecosystem.
```

---

## 11. awesome-security

**Repository:** https://github.com/sbilly/awesome-security (or similar)

### Entry (add to Web Security / Audit Tools section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with tamper-evident SHA-256 hash chain + Ed25519 audit trails. Self-verifiable proof bundles for forensic session capture, compliance automation (SOC 2, GDPR, HIPAA), and security research. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - headless browser with cryptographic audit trails for security research
```

### Commit Message

```
Add Conduit to Web Security / Audit Tools

Conduit is a headless browser with tamper-evident SHA-256 hash chain +
Ed25519 audit trails. Designed for forensic session capture, compliance
automation, and security research. MIT licensed.
```

### PR Body

```markdown
## Add Conduit

**Category:** Web Security / Audit Tools

Conduit is a headless browser with a cryptographic audit layer designed for security research, forensic session capture, and compliance automation.

**Security-relevant features:**
- **Tamper-evident audit trail** — SHA-256 hash chain where each entry's hash depends on the previous. Changing any entry breaks the entire chain.
- **Ed25519-signed sessions** — Session identity key signs the final chain hash. Non-repudiable proof of execution.
- **Self-verifiable proof bundles** — `.tar.gz` archives with stdlib-only `verify.py`. Zero trust in Conduit itself required.
- **Full JS source in audit chain** — The `eval` action stores the complete JavaScript source verbatim, not just the result. Proves exactly what code executed.
- **Stealth browser** — Built on Patchright (stealth Playwright fork) for researching anti-bot systems.
- **SSRF protection** — RFC-1918 and loopback IPs blocked. HTTP/HTTPS only.
- **Sensitive input auto-redaction** — Passwords, tokens, API keys automatically redacted before audit logging.

**Use cases:**
- Forensic web session capture with signed, chained evidence
- SOC 2 / SOX / GDPR / HIPAA compliance automation
- Security research with cryptographic proof of findings
- Litigation support with tamper-evident web evidence
- Documenting web-based exploits and injected scripts

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit
- License: MIT

Part of the SwarmSync.ai agent ecosystem.
```

---

## 12. awesome-ai-agents

**Repository:** Search GitHub for `awesome-ai-agents` (e.g., e2b-dev/awesome-ai-agents)

### Entry (add to Agent Tooling / Infrastructure section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser engine for autonomous AI agents with SHA-256 hash chain + Ed25519 audit trails. Stealth (Patchright). Self-verifiable proof bundles. Budget enforcement. MCP server. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - audited headless browser for AI agents
```

### Commit Message

```
Add Conduit to Agent Tooling section

Conduit is a headless browser MCP server for AI agents with SHA-256
hash chain + Ed25519 audit trails. Budget enforcement, stealth browser,
self-verifiable proof bundles. MIT licensed.
```

### PR Body

```markdown
## Add Conduit

**Category:** Agent Tooling / Infrastructure

Conduit is a headless browser designed as the browser engine for autonomous AI agents. Every action is cryptographically audited, budget-enforced, and exportable as verifiable proof.

**Why agents need this:**
- **Trust layer for agent-to-agent work** — When Agent A hires Agent B to do web research, the proof bundle proves the work was done
- **Budget enforcement** — Built-in billing ledger prevents runaway costs from autonomous agents
- **Full action replay** — Every navigate, click, type, extract, eval is hash-chained and signed
- **Self-verifiable proofs** — Proof bundles verify with stdlib-only Python, zero external dependencies
- **Stealth** — Patchright (stealth Playwright fork) avoids anti-bot detection
- **MCP server** — Drop-in integration with Claude Code, Claude Desktop, and any MCP-compatible agent

**26 actions across 4 waves:**
- Core: navigate, click, type, fill, extract, screenshot
- Interaction: scroll, wait, key_press, hover, select_option, handle_dialog
- Extraction: eval (full JS source in chain), extract_main, crawl, fingerprint
- Advanced: map, check_changed, export_proof, web_search, academic_search

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit
- License: MIT
- Agent Marketplace: https://swarmsync.ai

Part of the SwarmSync.ai agent ecosystem.
```

---

## 13. awesome-playwright

**Repository:** https://github.com/mxschmitt/awesome-playwright (or similar)

### Entry (add to Related Projects section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser built on Patchright (stealth Playwright fork) with SHA-256 hash chain + Ed25519 audit trails. Self-verifiable proof bundles. MCP server for AI agents. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - Patchright-based browser with cryptographic audit trails
```

### Commit Message

```
Add Conduit to Related Projects

Conduit is a headless browser built on Patchright (stealth Playwright
fork) with SHA-256 hash chain + Ed25519 audit trails. Exports
self-verifiable proof bundles. MCP server for AI agents. MIT licensed.
```

### PR Body

```markdown
## Add Conduit

**Category:** Related Projects

Conduit is a headless browser built on [Patchright](https://github.com/nicenemo/patchright) (stealth Playwright fork) that adds a cryptographic audit layer to browser automation.

**How it relates to Playwright:**
- Built on Patchright, which is a stealth fork of Playwright
- Uses Playwright's Chromium automation under the hood
- Adds SHA-256 hash-chained audit logging on every Playwright action
- Adds Ed25519-signed session proofs
- Adds self-verifiable proof bundle export
- Wraps Playwright actions with budget enforcement and auto-redaction

**What it adds on top of Playwright:**
- Tamper-evident audit trail on navigate, click, type, fill, extract, eval, screenshot
- Full JavaScript source stored verbatim in the audit chain (not just return values)
- BFS site crawling with robots.txt compliance
- Page fingerprinting and signed change detection
- MCP server interface for AI agent integration
- Budget enforcement via billing ledger

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit
- License: MIT

Part of the SwarmSync.ai agent ecosystem.
```

---

## 14. awesome-web-scraping

**Repository:** https://github.com/lorien/awesome-web-scraping (or similar)

### Entry (add to Headless Browsers section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth (Patchright). Robots.txt compliant BFS crawling. Self-verifiable proof bundles. MCP server for AI agents. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - audited headless browser with stealth and robots.txt compliance
```

### Commit Message

```
Add Conduit to Headless Browsers section

Conduit is a stealth headless browser (Patchright) with SHA-256 hash
chain + Ed25519 audit trails. Robots.txt compliant BFS crawling.
Self-verifiable proof bundles. MIT licensed, Python 3.10+.
```

### PR Body

```markdown
## Add Conduit

**Category:** Headless Browsers (Python)

Conduit is a headless browser with a cryptographic audit layer, designed for web extraction with verifiable proof of what was scraped and when.

**Web scraping features:**
- **Stealth browser** — Built on Patchright (stealth Playwright fork) for anti-detection
- **Robots.txt compliant** — BFS crawler checks robots.txt before every URL, honors Crawl-delay
- **Adaptive rate limiting** — Exponential backoff on 429/503 responses
- **Readability extraction** — `extract_main` strips nav/ads/footers, optional Markdown output
- **Structured extraction** — `extract_structured` with JSON schema validation
- **BFS site crawling** — `map` discovers all reachable URLs, `crawl` extracts content in bulk
- **Page fingerprinting** — SHA-256 fingerprints with timestamp/nonce normalization
- **Change detection** — `check_changed` re-fingerprints and logs signed `PAGE_MUTATION` events
- **Multi-engine search** — DuckDuckGo, Brave, Exa, Tavily with query-type routing

**Audit features (unique to Conduit):**
- SHA-256 hash chain on every action
- Ed25519-signed session proofs
- Self-verifiable proof bundles (zero dependencies)
- Sensitive input auto-redaction

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit
- License: MIT
- Language: Python 3.10+

Part of the SwarmSync.ai agent ecosystem.
```

---

## 15. awesome-python

**Repository:** https://github.com/vinta/awesome-python

### Entry (add to Web Scraping / Web Crawling section)

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash chain + Ed25519 audit trails. Stealth (Patchright). Self-verifiable proof bundles. Part of the SwarmSync.ai agent ecosystem.
```

### PR Title

```
Add Conduit - headless browser with cryptographic audit trails
```

### Commit Message

```
Add Conduit to Web Crawling section

Conduit is a headless browser with SHA-256 hash chain + Ed25519 audit
trails built on Patchright (stealth Playwright fork). Self-verifiable
proof bundles. MIT licensed, Python 3.10+.
```

### PR Body

```markdown
## Add Conduit

**Category:** Web Crawling / Web Content Extracting

Conduit is a Python headless browser library with a cryptographic audit layer. Built on Patchright (stealth Playwright fork).

**What it does:**
- Headless browser automation with stealth (anti-detection)
- SHA-256 hash-chained audit log on every action
- Ed25519-signed session proofs
- Self-verifiable proof bundles (stdlib-only, zero external dependencies)
- BFS site crawling with robots.txt compliance
- Readability-style content extraction with Markdown output
- Structured extraction with JSON schema validation
- Page fingerprinting and change detection
- Multi-engine web search (DuckDuckGo, Brave, Exa, Tavily)
- Budget enforcement and sensitive input auto-redaction
- MCP server interface for AI agent integration

**Requirements:** Python 3.10+
**License:** MIT
**Dependencies:** patchright

**Links:**
- GitHub: https://github.com/bkauto3/Conduit
- Homepage: https://swarmsync.ai/conduit

Part of the SwarmSync.ai agent ecosystem.
```

---

## Quick Reference: All PR Titles

| # | Directory | PR Title |
|---|-----------|----------|
| 1 | awesome-mcp-servers | `Add Conduit - headless browser with cryptographic audit trails` |
| 2 | PulseMCP | (web form submission) |
| 3 | Smithery.ai | (web form submission) |
| 4 | mcp.so | (web form submission) |
| 5 | Glama.ai | (web form submission) |
| 6 | mcpservers.org | (web form submission) |
| 7 | MCPize.com | (web form submission) |
| 8 | mcp-get | `Add conduit-browser - headless browser with cryptographic audit trails` |
| 9 | awesome-claude-code | `Add Conduit - headless browser MCP server with cryptographic audit trails` |
| 10 | awesome-headless-browsers | `Add Conduit - headless browser with cryptographic audit layer` |
| 11 | awesome-security | `Add Conduit - headless browser with cryptographic audit trails for security research` |
| 12 | awesome-ai-agents | `Add Conduit - audited headless browser for AI agents` |
| 13 | awesome-playwright | `Add Conduit - Patchright-based browser with cryptographic audit trails` |
| 14 | awesome-web-scraping | `Add Conduit - audited headless browser with stealth and robots.txt compliance` |
| 15 | awesome-python | `Add Conduit - headless browser with cryptographic audit trails` |

---

## Quick Reference: All Commit Messages

| # | Directory | Commit Message |
|---|-----------|----------------|
| 1 | awesome-mcp-servers | `Add Conduit to Browser Automation section` |
| 8 | mcp-get | `feat: add conduit-browser to registry` |
| 9 | awesome-claude-code | `Add Conduit to MCP Servers section` |
| 10 | awesome-headless-browsers | `Add Conduit to headless browsers list` |
| 11 | awesome-security | `Add Conduit to Web Security / Audit Tools` |
| 12 | awesome-ai-agents | `Add Conduit to Agent Tooling section` |
| 13 | awesome-playwright | `Add Conduit to Related Projects` |
| 14 | awesome-web-scraping | `Add Conduit to Headless Browsers section` |
| 15 | awesome-python | `Add Conduit to Web Crawling section` |

---

## Submission Checklist

- [ ] **1. awesome-mcp-servers** — Fork, add table row, submit PR
- [ ] **2. PulseMCP** — Submit via web form at pulsemcp.com
- [ ] **3. Smithery.ai** — Submit via platform at smithery.ai
- [ ] **4. mcp.so** — Submit via web form at mcp.so
- [ ] **5. Glama.ai** — Submit via platform at glama.ai/mcp/servers
- [ ] **6. mcpservers.org** — Submit via web form at mcpservers.org
- [ ] **7. MCPize.com** — Submit via web form at mcpize.com
- [ ] **8. mcp-get** — Fork, add JSON entry, submit PR
- [ ] **9. awesome-claude-code** — Fork, add list entry, submit PR
- [ ] **10. awesome-headless-browsers** — Fork, add list entry, submit PR
- [ ] **11. awesome-security** — Fork, add list entry, submit PR
- [ ] **12. awesome-ai-agents** — Fork, add list entry, submit PR
- [ ] **13. awesome-playwright** — Fork, add list entry, submit PR
- [ ] **14. awesome-web-scraping** — Fork, add list entry, submit PR
- [ ] **15. awesome-python** — Fork, add list entry, submit PR
