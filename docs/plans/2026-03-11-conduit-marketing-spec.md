# Conduit Marketing Specification
## Concrete, Agent-Executable Distribution Plan

**Date:** 2026-03-11
**Status:** VALIDATED
**Repo:** https://github.com/bkauto3/Conduit

---

## Current State (Verified 2026-03-11)

| Attribute | Current Value |
|-----------|---------------|
| Stars | 0 |
| Forks | 0 |
| Topics | None |
| About/Description | Empty |
| License file | Missing |
| pyproject.toml | Missing |
| setup.py | Missing |
| Homepage URL | Empty |
| Wiki | Disabled |
| Issues | 0 |
| PRs | 0 |

The repo is invisible. GitHub search, PyPI, and every MCP directory return nothing for Conduit. The README is excellent technically but is not discoverable.

---

## 1. GitHub Optimization

### 1.1 Repository Topics [AGENT-AUTO]

Set these topics via GitHub API (`gh api repos/bkauto3/Conduit/topics -X PUT`):

```
mcp-server
mcp
headless-browser
browser-automation
cryptographic-audit
audit-trail
web-scraping
ai-agents
python
playwright
ed25519
compliance
stealth-browser
```

**Rationale:** These are the intersection of (a) what people actually search for on GitHub, (b) Conduit's real capabilities, and (c) co-topics found in the mcp-server ecosystem (9,162 repos). The topics `mcp-server`, `mcp`, `ai-agents`, `python` are the four highest-frequency co-topics in that ecosystem.

**Execution:**
```bash
gh api repos/bkauto3/Conduit/topics \
  -X PUT \
  -f 'names=["mcp-server","mcp","headless-browser","browser-automation","cryptographic-audit","audit-trail","web-scraping","ai-agents","python","playwright","ed25519","compliance","stealth-browser"]'
```

### 1.2 About Section (Description) [AGENT-AUTO]

**Proposed (150 chars):**
```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles.
```
(129 characters)

**Execution:**
```bash
gh repo edit bkauto3/Conduit --description "Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents. Stealth. Self-verifiable proof bundles."
```

### 1.3 Homepage URL [AGENT-AUTO]

Set to the repo itself (until a docs site exists):
```bash
gh repo edit bkauto3/Conduit --homepage "https://github.com/bkauto3/Conduit#readme"
```

### 1.4 License File [AGENT-AUTO]

**Critical gap.** No LICENSE file means:
- Many awesome-lists reject unlicensed repos
- PyPI requires a license classifier
- Enterprises will not evaluate it

**Recommendation:** MIT License (maximizes adoption, standard for browser automation tools, Playwright itself is Apache-2.0).

**Execution:** Create `LICENSE` file with MIT text, add license field to future pyproject.toml.

### 1.5 Badges for README [AGENT-AUTO]

Add to top of README.md, below the H1:

```markdown
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
```

### 1.6 README Changes [AGENT-ASSIST]

The current README is strong for **agent developers** but weak for two other audiences:

**Audience Analysis:**

| Audience | Current README Serves? | Gap |
|----------|----------------------|-----|
| Agent developers | YES -- excellent quick start, action reference, architecture | Missing: pip install instruction, MCP config snippet |
| Security researchers | PARTIAL -- proof bundles explained well | Missing: dedicated "Security Research" section with forensic use cases |
| Compliance officers | WEAK -- one paragraph in "Use Cases" | Missing: regulatory language, standards mapping (SOC 2, HIPAA audit trail), proof bundle as compliance artifact |

**Specific README changes needed:**

1. **Add installation section** (currently missing entirely -- no `pip install`, no `git clone`, no requirements.txt):
```markdown
## Installation
git clone https://github.com/bkauto3/Conduit.git
cd Conduit
pip install -r requirements.txt
```

2. **Add MCP configuration snippet** for Claude Desktop / Claude Code:
```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "conduit_bridge"],
      "env": {}
    }
  }
}
```

3. **Add "For Compliance Teams" section** (~100 words) mapping proof bundles to audit requirements.

4. **Add "For Security Researchers" section** (~100 words) on forensic session replay.

---

## 2. MCP Directory Listings

### 2.1 Directories Identified

| Directory | URL | Size | Submission Method | Automatable? |
|-----------|-----|------|-------------------|-------------|
| awesome-mcp-servers (punkpeye) | github.com/punkpeye/awesome-mcp-servers | 9k+ stars | PR to README.md | [AGENT-AUTO] fork + PR |
| mcpservers.org (wong2) | mcpservers.org/submit | 3.7k stars | Web form | [AGENT-ASSIST] agent fills, human submits |
| mcp.so | mcp.so/submit | 18,410 servers | Web form (Name, URL, Type, Config) | [AGENT-ASSIST] agent fills, human submits |
| Glama.ai | glama.ai/mcp/servers | 18,983 servers | "Add Server" button | [AGENT-ASSIST] agent fills, human submits |
| Smithery.ai | smithery.ai | Major directory | Unknown (rate-limited during research) | [HUMAN-NEEDED] needs manual investigation |
| Official MCP Registry | modelcontextprotocol.io | Canonical | Pointed to by official repo | [HUMAN-NEEDED] likely requires application |

### 2.2 awesome-mcp-servers PR (punkpeye) [AGENT-AUTO]

**Target category:** `Browser Automation`

**Entry format** (matches existing style):
```markdown
- [bkauto3/Conduit](https://github.com/bkauto3/Conduit) 🐍 🏠 - Headless browser with SHA-256 hash-chained audit trails and Ed25519 signed proof bundles. Stealth mode via Patchright.
```

Where: `🐍` = Python, `🏠` = runs locally

**PR process:**
1. Fork `punkpeye/awesome-mcp-servers`
2. Branch: `add-conduit-browser`
3. Add entry alphabetically in `Browser Automation` section
4. PR title: `Add Conduit - audited headless browser`
5. PR body: Brief description of what Conduit is and why it fits

**Requirements verified:**
- Alphabetical ordering: Yes (between entries starting with B-C)
- Format consistency: Matches existing entries
- No minimum star count stated in CONTRIBUTING.md

### 2.3 mcpservers.org [AGENT-ASSIST]

**Form fields to fill:**
- **Server Name:** Conduit
- **Short Description:** Headless browser with cryptographic audit trails (SHA-256 + Ed25519). Stealth mode, self-verifiable proof bundles, page fingerprinting. MCP server for AI agents.
- **Link:** https://github.com/bkauto3/Conduit
- **Category:** web-scraping (closest match from: search, web-scraping, communication, productivity, development, database, cloud-service, file-system, cloud-storage, version-control, other)
- **Contact Email:** [owner's email needed]

**Cost:** Free (paid $39 option for faster review + badge -- owner's decision)

### 2.4 mcp.so [AGENT-ASSIST]

**Form fields to fill:**
- **Type:** MCP Server
- **Name:** Conduit
- **URL:** https://github.com/bkauto3/Conduit
- **Server Config:** (MCP JSON config snippet from section 1.6)

### 2.5 Glama.ai [AGENT-ASSIST]

Navigate to glama.ai/mcp/servers, click "Add Server", provide GitHub URL. Categories to target: Browser Automation, Web Scraping.

---

## 3. Awesome-List PRs

### 3.1 Target Lists (Ranked by Impact)

| List | Stars | Category for Conduit | Effort | Impact |
|------|-------|---------------------|--------|--------|
| punkpeye/awesome-mcp-servers | 9k+ | Browser Automation | Low | HIGH -- primary audience |
| dhamaniasad/HeadlessBrowsers | 6k+ | Chromium drivers | Low | HIGH -- exact category match |
| vinta/awesome-python | 230k+ | Web Crawling | Medium | VERY HIGH -- massive exposure |
| BruceDone/awesome-crawler | 6k+ | Python | Low | MEDIUM -- crawler audience |
| sbilly/awesome-security | 12k+ | Web > Development | Medium | MEDIUM -- security audience |

### 3.2 HeadlessBrowsers PR [AGENT-AUTO]

**Target table:** Chromium drivers (since Conduit uses Patchright/Chromium)

**Entry format** (matches existing table):
| Name | About | Supported Languages | License |
|------|-------|---------------------|---------|
| [Conduit](https://github.com/bkauto3/Conduit) | Headless browser with SHA-256 hash-chained audit trails and Ed25519 signed sessions. Stealth via Patchright. Self-verifiable proof bundles. | Python | MIT |

**PR process:**
1. Fork `dhamaniasad/HeadlessBrowsers`
2. Add row to Chromium drivers table
3. PR title: `Add Conduit - audited headless browser with cryptographic proof`

### 3.3 awesome-python PR [AGENT-AUTO]

**Target category:** Web Crawling

**Entry format:**
```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash-chained audit trails, Ed25519 signing, and self-verifiable proof bundles. Built on Patchright (stealth Playwright).
```

**Risk:** awesome-python has high curation standards. A 0-star repo may be rejected. Recommend waiting until the repo has 25+ stars from organic discovery via MCP directories.

### 3.4 awesome-crawler PR [AGENT-AUTO]

**Target category:** Python

**Entry format:**
```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with cryptographic audit trails. BFS crawling, page fingerprinting, signed change detection. Stealth mode via Patchright.
```

### 3.5 awesome-security PR [AGENT-AUTO]

**Target category:** Web > Development

**Entry format:**
```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with tamper-evident SHA-256 hash chain and Ed25519 signed session proofs. Full JS source captured in audit trail. Self-verifiable proof bundles.
```

---

## 4. PyPI Package

### 4.1 Should Conduit Be Published? YES.

**Reasons:**
- `pip install conduit-browser` is the single most impactful discoverability action
- PyPI is searched by developers before GitHub
- It enables `pip install` in README (currently impossible)
- MCP servers are commonly distributed as pip packages

### 4.2 Package Name [AGENT-AUTO to prepare, HUMAN-NEEDED to publish]

| Candidate | Available on PyPI? | Recommendation |
|-----------|-------------------|----------------|
| `conduit` | TAKEN (v1.1) | No |
| `conduit-mcp` | TAKEN (v0.0.1) | No |
| `conduit-browser` | AVAILABLE | RECOMMENDED |
| `conduit-headless` | AVAILABLE | Backup option |
| `conduit-browser-audit` | AVAILABLE | Too long |
| `conduit-audit` | AVAILABLE | Ambiguous (could be generic audit tool) |

**Recommended name:** `conduit-browser`

### 4.3 Package Description

**Short (PyPI summary, 1 line):**
```
Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents.
```

**Long (PyPI description):** Use the existing README.md (rendered as Markdown on PyPI).

### 4.4 PyPI Classifiers

```python
classifiers=[
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet :: WWW/HTTP :: Browsers",
    "Topic :: Security :: Cryptography",
    "Topic :: Software Development :: Testing",
    "Framework :: AsyncIO",
]
```

### 4.5 pyproject.toml Skeleton [AGENT-AUTO to create]

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[project]
name = "conduit-browser"
version = "0.1.0"
description = "Headless browser with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents."
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "bkauto3"}
]
keywords = [
    "headless-browser", "audit-trail", "mcp", "mcp-server",
    "browser-automation", "cryptography", "ed25519", "sha256",
    "web-scraping", "stealth-browser", "playwright", "ai-agents"
]
dependencies = [
    "patchright",
]

[project.urls]
Homepage = "https://github.com/bkauto3/Conduit"
Repository = "https://github.com/bkauto3/Conduit"
Issues = "https://github.com/bkauto3/Conduit/issues"
```

**Note:** Dependencies need verification against actual imports in the codebase. The above lists only `patchright` as a known dependency; a full audit of imports is needed.

### 4.6 Publishing Steps [HUMAN-NEEDED for PyPI credentials]

1. Agent creates `pyproject.toml` and `LICENSE`
2. Agent verifies `python -m build` succeeds
3. Human creates PyPI account and API token (or has existing one)
4. Human runs `python -m twine upload dist/*` (or agent runs with provided token)

---

## 5. README Evaluation (Detailed)

### 5.1 Current README Strengths

- Excellent comparison table vs. Playwright/Puppeteer/Selenium
- Clear architecture diagram
- Working code examples
- Complete action reference organized by "Waves"
- Good proof bundle explanation

### 5.2 Current README Weaknesses

| Issue | Severity | Fix |
|-------|----------|-----|
| No installation instructions at all | CRITICAL | Add git clone + pip install section |
| No MCP configuration example | HIGH | Add JSON config for Claude Desktop |
| No LICENSE file referenced (links to nonexistent file) | HIGH | Create LICENSE, update link |
| No badges (Python version, license, tests) | MEDIUM | Add badge row |
| "Use Cases" section is shallow | MEDIUM | Expand with audience-specific sections |
| No "Getting Started in 30 seconds" | MEDIUM | Add minimal quickstart before deep dive |
| No requirements.txt or dependency list visible | HIGH | Create or reference pyproject.toml |
| References "cato" extensively in paths/commands | LOW | Acceptable (Conduit is part of Cato ecosystem) |

### 5.3 Audience-Specific Analysis

**Audience A: Agent Developers (Primary)**
- README quality: 8/10
- Serves well: action reference, async Python examples, MCP skill file
- Missing: `pip install` command, MCP server config JSON, "works with Claude Desktop" callout

**Audience B: Security Researchers**
- README quality: 5/10
- Serves well: proof bundle section, hash chain explanation
- Missing: forensic replay walkthrough, "how to use this for incident investigation", comparison to existing forensic browser tools (there are none -- this should be stated)

**Audience C: Compliance Officers / GRC Teams**
- README quality: 3/10
- Serves well: mentions compliance in Use Cases
- Missing: mapping to specific standards (SOC 2 CC7.2 change monitoring, HIPAA audit trail requirements, PCI DSS 10.x logging requirements), sample compliance report from proof bundle, ROI language ("replaces manual screenshot evidence collection")

**Audience D: DevOps / QA Engineers**
- README quality: 6/10
- Serves well: test commands, architecture
- Missing: CI/CD integration example, Docker setup, GitHub Actions workflow for running Conduit tests

### 5.4 Recommended README Structure (Reordered)

```
# Conduit
[badges]

One-sentence pitch.

## Install (3 lines)
## Quick Start (10 lines of code)
## Why Conduit? (comparison table -- already exists)
## Core Differentiator (hash chain explanation -- already exists)
## For Agent Developers (MCP config, Claude Desktop setup)
## For Security & Compliance (standards mapping, proof bundle as evidence)
## Architecture (already exists)
## Action Reference (already exists, keep Waves structure)
## API Reference (link to full docs if they exist)
## Running Tests
## License
## Contributing
```

---

## 6. Regulated Industry Channels

### 6.1 Where Compliance/Legal/Healthcare/Finance Teams Discover Tools

| Channel | Type | Audience | How to Get Listed | Automation Level |
|---------|------|----------|-------------------|-----------------|
| G2 | Review platform | Enterprise buyers | Create vendor profile, request reviews | [HUMAN-NEEDED] requires vendor account creation |
| Product Hunt | Launch platform | Tech-forward teams | Schedule launch, prepare assets | [HUMAN-NEEDED] requires account + human engagement |
| OWASP Tool Inventory | Security tools list | AppSec teams | Submit via OWASP project process | [HUMAN-NEEDED] requires OWASP membership |
| NIST Cybersecurity Tool Registry | Government/enterprise | Federal agencies, large enterprise | Application process | [HUMAN-NEEDED] formal process |
| r/netsec (Reddit) | Community | Security researchers | Post with [Tool] tag | [AGENT-ASSIST] agent drafts, human posts |
| r/Python (Reddit) | Community | Python developers | Post as Show HN style | [AGENT-ASSIST] agent drafts, human posts |
| Hacker News (Show HN) | Community | Developers, security | "Show HN" post | [HUMAN-NEEDED] requires HN account |
| ISACA Community | Professional org | Auditors, compliance | Community forum posts | [HUMAN-NEEDED] requires membership |
| CSA STAR Registry | Cloud compliance | Cloud security teams | Self-assessment | [HUMAN-NEEDED] heavy documentation |
| InfoSec conferences (BSides, DEF CON) | Events | Security community | CFP submissions, tool demos | [HUMAN-NEEDED] months of lead time |

### 6.2 Realistic First-Wave Channels for Regulated Industries

Most regulated-industry channels require human credentials, organizational membership, or formal application processes. The practical approach:

**Wave 1 (Agent-executable, do now):**
- GitHub optimization (topics, description, badges)
- MCP directory listings (awesome-mcp-servers PR, mcp.so, mcpservers.org)
- awesome-list PRs (HeadlessBrowsers, awesome-crawler)

**Wave 2 (Agent-assisted, needs human click):**
- PyPI publication
- Reddit posts (r/Python, r/netsec, r/selfhosted)
- awesome-python PR (after 25+ stars)

**Wave 3 (Human-driven, longer timeline):**
- Hacker News Show HN
- Product Hunt launch
- Security conference demos
- Professional organization listings (ISACA, OWASP)
- Enterprise review platforms (G2)

---

## 7. Execution Plan (Prioritized)

### Phase 1: Foundation (Day 1) -- All [AGENT-AUTO]

| # | Task | Command/Action | Prereq |
|---|------|----------------|--------|
| 1 | Add LICENSE (MIT) | Create file, commit, push | None |
| 2 | Set repo topics | `gh api repos/bkauto3/Conduit/topics -X PUT ...` | None |
| 3 | Set repo description | `gh repo edit --description ...` | None |
| 4 | Add badges to README | Edit README.md | LICENSE exists |
| 5 | Add installation section to README | Edit README.md | None |
| 6 | Add MCP config snippet to README | Edit README.md | None |

### Phase 2: Directory Listings (Days 2-3) -- Mix

| # | Task | Automation | Prereq |
|---|------|-----------|--------|
| 7 | PR to awesome-mcp-servers | [AGENT-AUTO] fork, branch, edit, PR | Phase 1 done |
| 8 | PR to HeadlessBrowsers | [AGENT-AUTO] fork, branch, edit, PR | LICENSE exists |
| 9 | PR to awesome-crawler | [AGENT-AUTO] fork, branch, edit, PR | LICENSE exists |
| 10 | Submit to mcp.so | [AGENT-ASSIST] agent prepares form data | Phase 1 done |
| 11 | Submit to mcpservers.org | [AGENT-ASSIST] agent prepares form data | Owner email |
| 12 | Submit to Glama.ai | [AGENT-ASSIST] agent navigates to form | Phase 1 done |

### Phase 3: PyPI (Days 3-5) -- [AGENT-AUTO] prep, [HUMAN-NEEDED] publish

| # | Task | Automation | Prereq |
|---|------|-----------|--------|
| 13 | Audit all Python imports for dependencies | [AGENT-AUTO] | None |
| 14 | Create pyproject.toml | [AGENT-AUTO] | Import audit |
| 15 | Test `python -m build` | [AGENT-AUTO] | pyproject.toml |
| 16 | Publish to PyPI | [HUMAN-NEEDED] PyPI token | Build succeeds |

### Phase 4: Content & Community (Week 2) -- [AGENT-ASSIST]

| # | Task | Automation | Prereq |
|---|------|-----------|--------|
| 17 | Draft r/Python post | [AGENT-ASSIST] | Phase 1 done |
| 18 | Draft r/netsec post | [AGENT-ASSIST] | Phase 1 done |
| 19 | Add compliance-focused README section | [AGENT-AUTO] | None |
| 20 | PR to awesome-security | [AGENT-AUTO] | LICENSE exists |

### Phase 5: High-Visibility (Week 3+) -- [HUMAN-NEEDED]

| # | Task | Automation | Prereq |
|---|------|-----------|--------|
| 21 | Show HN post | [HUMAN-NEEDED] | Stars > 10 |
| 22 | PR to awesome-python | [AGENT-AUTO] | Stars > 25 |
| 23 | Product Hunt launch | [HUMAN-NEEDED] | README polished, PyPI live |

---

## 8. Success Metrics

| Metric | Baseline (Today) | Target (30 days) | Target (90 days) |
|--------|-------------------|-------------------|-------------------|
| GitHub stars | 0 | 25 | 150 |
| PyPI weekly downloads | N/A | 50 | 200 |
| MCP directory listings | 0 | 4 | 6 |
| Awesome-list inclusions | 0 | 3 | 5 |
| GitHub topics set | 0 | 13 | 13 |
| Inbound issues/PRs | 0 | 3 | 10 |

---

## 9. Decisions Log

| Decision | Chosen | Alternatives Considered | Rationale |
|----------|--------|------------------------|-----------|
| License | MIT | Apache-2.0, ISC | Maximizes adoption; matches ecosystem norms |
| PyPI name | conduit-browser | conduit-headless, conduit-audit | Clear, available, descriptive |
| First PR target | awesome-mcp-servers | awesome-python | Primary audience is MCP/agent devs; no star requirement |
| README restructure | Add sections, keep existing | Full rewrite | Existing content is strong; additive changes only |
| Regulated channels | Defer to Phase 5 | Pursue immediately | Require human credentials; premature with 0 stars |

---

## 10. Open Questions (Require Human Input)

1. **License choice:** MIT recommended. Owner must confirm.
2. **PyPI credentials:** Does the owner have a PyPI account?
3. **Contact email for mcpservers.org:** Required for submission.
4. **Smithery.ai:** Rate-limited during research. Manual investigation needed.
5. **Official MCP Registry:** Submission process unclear. May require formal application.
6. **Conduit as standalone vs. Cato subsystem:** The README references `~/.cato/` paths and `cato` commands extensively. Is Conduit intended to be usable independently? This affects whether PyPI packaging makes sense as `conduit-browser` standalone or as part of a larger `cato` package.
7. **requirements.txt / dependencies:** No requirements.txt exists in the repo. A dependency audit is needed before PyPI packaging.

---

## Appendix A: Exact PR Bodies

### awesome-mcp-servers PR Body
```markdown
## Add Conduit - Headless browser with cryptographic audit trails

**What:** Conduit is a headless browser (Patchright/Chromium) where every action is
logged to a tamper-evident SHA-256 hash chain, signed with Ed25519 keys, and exportable
as self-verifiable proof bundles.

**Category:** Browser Automation

**Why it belongs:** Conduit is purpose-built as an MCP server for AI agents. It adds
cryptographic auditability to browser automation -- something no other browser tool provides.

**Entry added:** Alphabetically in Browser Automation section.
```

### HeadlessBrowsers PR Body
```markdown
## Add Conduit - Audited headless browser

Conduit is a Python headless browser built on Patchright (stealth Playwright fork)
that adds SHA-256 hash-chained audit trails and Ed25519 signed session proofs.
Every browser action is logged to a tamper-evident chain. Sessions can be exported
as self-verifiable proof bundles (zero-dependency Python verifier included).

Repo: https://github.com/bkauto3/Conduit
License: MIT
Language: Python
```

---

## Appendix B: Reddit Post Drafts

### r/Python Draft
```
Title: Conduit -- headless browser with cryptographic audit trails (SHA-256 + Ed25519)

I built a headless browser in Python where every action is written to a tamper-evident
hash chain and signed with Ed25519 keys. It exports self-verifiable proof bundles that
anyone can verify with Python's stdlib (zero dependencies).

Built on Patchright (stealth Playwright fork), designed as an MCP server for AI agents.

Use cases:
- Compliance automation (prove what was submitted, when)
- Security research (forensic session replay)
- AI agent browser control with full audit trail

GitHub: https://github.com/bkauto3/Conduit

Happy to answer questions about the architecture or cryptographic design.
```

### r/netsec Draft
```
Title: Conduit: Tamper-evident headless browser with Ed25519 signed session proofs

Every browser action (navigate, click, JS execution) is logged to a SHA-256 hash chain
where each row's hash depends on the previous row. The eval action stores the full
JavaScript source in the chain -- cryptographic proof of exactly what code ran.

Sessions export as self-verifiable .tar.gz bundles containing:
- audit_log.jsonl (hash-chained log)
- Ed25519 signature over final chain hash
- verify.py (stdlib-only, zero-dep verifier)

Built for AI agent browser control but the audit layer has obvious applications
in forensics and compliance.

https://github.com/bkauto3/Conduit
```
