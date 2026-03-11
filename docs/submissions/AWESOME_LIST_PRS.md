# Awesome-List PR Submissions for Conduit

> Ready-to-submit PR content for every targeted awesome-list on GitHub.
>
> **Project:** Conduit -- Free, MIT-licensed headless browser with SHA-256 hash chain + Ed25519 audit trails.
> **GitHub:** https://github.com/bkauto3/Conduit
> **PyPI:** `pip install conduit-browser`
> **Homepage:** https://swarmsync.ai/conduit

---

## Table of Contents

1. [dhamaniasad/HeadlessBrowsers](#1-dhamaniasadheadlessbrowsers)
2. [sbilly/awesome-security](#2-sbillyawesome-security)
3. [e2b-dev/awesome-ai-agents](#3-e2b-devawesome-ai-agents)
4. [mxschmitt/awesome-playwright](#4-mxschmittawesome-playwright)
5. [lorien/awesome-web-scraping](#5-lorienawesome-web-scraping)
6. [vinta/awesome-python](#6-vintaawesome-python)
7. [awesome-selfhosted/awesome-selfhosted](#7-awesome-selfhostedawesome-selfhosted)
8. [wong2/awesome-mcp-servers](#8-wong2awesome-mcp-servers)
9. [e2b-dev/awesome-ai-agents (Agent Tools)](#9-e2b-devawesome-ai-agents-agent-tools)
10. [Product Hunt](#10-product-hunt)

---

## 1. dhamaniasad/HeadlessBrowsers

The canonical list of headless browsers on GitHub (~7k stars). Entries are organized in markdown tables by engine type.

- **Repo:** `dhamaniasad/HeadlessBrowsers`
- **PR Title:** `Add Conduit - headless browser with cryptographic audit trails`
- **Commit Message:** `Add Conduit to Chromium Drivers section`
- **Target Section:** `Chromium Drivers` (table)

### Markdown Line to Add

Add this row to the **Chromium Drivers** table (alphabetical placement after "Chrome Remote Interface"):

```markdown
| [Conduit](https://github.com/bkauto3/Conduit) | Headless browser with SHA-256 hash chain + Ed25519 audit trails. Self-verifiable proof bundles. Built on Patchright (stealth Playwright fork). MCP server for AI agents. | Python | MIT |
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Chromium Drivers section.

Conduit is a free, MIT-licensed headless browser built on [Patchright](https://github.com/AuriAI/patchright) (stealth Playwright fork). It adds cryptographic audit trails to every browser session:

- **SHA-256 hash chain** linking every action into a tamper-evident log
- **Ed25519 digital signatures** for cryptographic proof of session integrity
- **Self-verifiable proof bundles** (JSON export) that anyone can independently verify
- **MCP server** for integration with AI agents (Claude, GPT, etc.)
- **BFS crawler** with robots.txt compliance and budget enforcement

Available on PyPI: `pip install conduit-browser`

Part of the [SwarmSync.ai](https://swarmsync.ai) agent ecosystem.
```

---

## 2. sbilly/awesome-security

Large security-focused awesome-list (~12k stars). Entries follow the format: `- [Name](URL) - Description.`

- **Repo:** `sbilly/awesome-security`
- **PR Title:** `Add Conduit - headless browser with tamper-evident audit trails`
- **Commit Message:** `Add Conduit to Web > Scanning / Pentesting section`
- **Target Section:** `Web` > `Scanning / Pentesting`

### Markdown Line to Add

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with tamper-evident audit trails. SHA-256 hash chain, Ed25519 signatures, self-verifiable proof bundles for browser forensics and compliance.
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Web > Scanning / Pentesting section.

Conduit is a free, MIT-licensed headless browser purpose-built for security and forensics use cases:

- **Tamper-evident audit trails:** Every browser action is linked into a SHA-256 hash chain. Modifying any entry invalidates the entire chain.
- **Ed25519 digital signatures:** Sessions are cryptographically signed, providing non-repudiation and proof of origin.
- **Self-verifiable proof bundles:** Export session logs as JSON bundles that anyone can independently verify without trusting the tool or operator.
- **Browser forensics:** Capture and prove exactly what a browser session did -- useful for compliance, incident response, and legal evidence.
- **Built on Patchright** (stealth Playwright fork) for reliable automation of modern web applications.

Install: `pip install conduit-browser`

## Why this fits awesome-security

Conduit addresses a gap in the security tooling ecosystem: the ability to cryptographically prove what happened during browser-based operations. This is relevant for:
- Penetration testing evidence collection
- Compliance auditing of automated browser workflows
- Digital forensics involving web-based activity
- Chain-of-custody for browser-captured evidence
```

---

## 3. e2b-dev/awesome-ai-agents

The most popular AI agents awesome-list on GitHub (~26k stars). Uses a structured format with H2 heading, one-line description, and collapsible `<details>` block containing category, bullet-point description, and links.

- **Repo:** `e2b-dev/awesome-ai-agents`
- **PR Title:** `Add Conduit - headless browser with cryptographic audit trails for AI agents`
- **Commit Message:** `Add Conduit to awesome-ai-agents list`
- **Target Section:** Alphabetical placement in the main list (between "Cody" and "Continue")

### Markdown Lines to Add

```markdown
## [Conduit](https://github.com/bkauto3/Conduit)
The only headless browser with cryptographic audit trails, designed for autonomous AI agents
<details>

### Category
Agent Tools, Browser Automation, Security

### Description
- A free, MIT-licensed headless browser that creates tamper-evident audit trails for every session.
- Every browser action is linked into a SHA-256 hash chain, making any modification detectable.
- Sessions are signed with Ed25519 digital signatures for cryptographic proof of integrity.
- Self-verifiable proof bundles let anyone independently verify what an AI agent did in the browser.
- Built-in MCP server allows direct integration with Claude, GPT, and other AI agent frameworks.
- Budget enforcement prevents runaway autonomous agents from exceeding defined resource limits.
- Built on Patchright (stealth Playwright fork) for reliable automation of modern web applications.
- BFS crawler with robots.txt compliance for responsible web scraping.

### Links
- [PyPI](https://pypi.org/project/conduit-browser/)
- [Homepage](https://swarmsync.ai/conduit)
- [SwarmSync.ai Ecosystem](https://swarmsync.ai)

</details>
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the awesome-ai-agents list.

Conduit is the only headless browser that provides cryptographic audit trails for AI agent browser sessions. It solves a critical trust problem: how do you prove what an autonomous agent actually did in the browser?

**Key differentiators for AI agents:**
- SHA-256 hash chain + Ed25519 signatures create tamper-evident session logs
- Self-verifiable proof bundles for accountability and compliance
- Built-in MCP server for native Claude/GPT integration
- Budget enforcement to prevent runaway autonomous operations
- Stealth capabilities via Patchright (Playwright fork) to avoid bot detection

Free, MIT-licensed, available on PyPI: `pip install conduit-browser`
```

---

## 4. mxschmitt/awesome-playwright

The official Playwright community awesome-list. Entries follow the format: `[Name](URL) - Description.` Sections include Integrations, Language Support, Utils, Reporters, Showcases, and Guides. There is no dedicated "Forks" section.

- **Repo:** `mxschmitt/awesome-playwright`
- **PR Title:** `Add Conduit - Patchright-based headless browser with audit trails`
- **Commit Message:** `Add Conduit to Integrations section`
- **Target Section:** `Integrations`

### Markdown Line to Add

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser built on Patchright (stealth Playwright fork) with SHA-256 hash chain + Ed25519 audit trails. MCP server for AI agents.
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Integrations section.

Conduit is a headless browser built on top of the Playwright ecosystem (specifically [Patchright](https://github.com/AuriAI/patchright), a stealth fork). It extends Playwright's browser automation capabilities with:

- **SHA-256 hash chain** -- every browser action is linked into a tamper-evident log
- **Ed25519 digital signatures** -- cryptographic proof of session integrity
- **Self-verifiable proof bundles** -- export and independently verify session history
- **MCP server** -- integrates with AI agents (Claude, GPT, etc.)
- **Budget enforcement** -- prevents runaway automated sessions

Conduit uses Playwright's core APIs under the hood, making it relevant to the Playwright ecosystem. It demonstrates a novel use case: adding cryptographic accountability to Playwright-based browser automation.

Free, MIT-licensed, available on PyPI: `pip install conduit-browser`
```

---

## 5. lorien/awesome-web-scraping

Web scraping resources organized by language. Entries use `* [Name](URL) - description` format (note: asterisk, not dash). The Python file (`python.md`) has sections including "Browser Automation :: Drivers" and "Browser Automation :: Frameworks."

- **Repo:** `lorien/awesome-web-scraping`
- **File to Edit:** `python.md`
- **PR Title:** `Add Conduit to Browser Automation :: Drivers`
- **Commit Message:** `Add Conduit to Python browser automation drivers`
- **Target Section:** `Browser Automation :: Drivers`

### Markdown Line to Add

```markdown
* [Conduit](https://github.com/bkauto3/Conduit) - headless browser with SHA-256 hash chain and Ed25519 audit trails, built on Patchright (stealth Playwright fork), MCP server for AI agents
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Python > Browser Automation :: Drivers section.

Conduit is a Python headless browser built on Patchright (stealth Playwright fork) that adds cryptographic audit trails to browser automation:

- **SHA-256 hash chain** for tamper-evident session logs
- **Ed25519 signatures** for proof of session integrity
- **Self-verifiable proof bundles** for independent verification
- **BFS crawler** with robots.txt compliance
- **MCP server** for AI agent integration

Install: `pip install conduit-browser`

MIT-licensed. Part of the [SwarmSync.ai](https://swarmsync.ai) ecosystem.
```

---

## 6. vinta/awesome-python

The largest Python awesome-list on GitHub (~230k stars). Entries follow: `- [name](URL) - Description.` The relevant section is "Web Crawling" which includes browser-use, scrapy, mechanicalsoup, etc.

- **Repo:** `vinta/awesome-python`
- **PR Title:** `Add Conduit to Web Crawling section`
- **Commit Message:** `Add Conduit - headless browser with cryptographic audit trails`
- **Target Section:** `Web Crawling`

### Markdown Line to Add

```markdown
- [Conduit](https://github.com/bkauto3/Conduit) - Headless browser with SHA-256 hash-chained audit log and Ed25519 signatures. Self-verifiable proof bundles. MCP server for AI agents.
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Web Crawling section.

Conduit is a free, MIT-licensed headless browser for Python that adds cryptographic audit trails to browser automation and web crawling:

- **SHA-256 hash chain** linking every action into a tamper-evident log
- **Ed25519 digital signatures** for proof of session integrity
- **Self-verifiable proof bundles** exportable as JSON for independent verification
- **BFS crawler** with robots.txt compliance and budget enforcement
- **MCP server** for AI agent integration (Claude, GPT, etc.)
- Built on **Patchright** (stealth Playwright fork) for reliable modern web automation

Install: `pip install conduit-browser`

**Note:** This list already includes [browser-use](https://github.com/browser-use/browser-use) for AI browser automation. Conduit serves a different purpose -- it focuses on cryptographic accountability and tamper-evident proof for browser sessions, rather than making websites accessible for AI agents.
```

---

## 7. awesome-selfhosted/awesome-selfhosted

One of the largest awesome-lists (~210k stars). Entries use a specific format with description, optional Demo/Source Code links in parentheses, followed by backtick-enclosed license identifier and language/platform.

Format: `- [Name](URL) - Description. ([Demo](URL), [Source Code](URL)) \`LICENSE\` \`Language\``

- **Repo:** `awesome-selfhosted/awesome-selfhosted`
- **PR Title:** `Add Conduit - headless browser with cryptographic audit trails`
- **Commit Message:** `Add Conduit to Automation section`
- **Target Section:** `Automation`

### Markdown Line to Add

```markdown
- [Conduit](https://swarmsync.ai/conduit) - Headless browser with SHA-256 hash chain and Ed25519 audit trails. Self-verifiable proof bundles, BFS crawler with robots.txt compliance, and MCP server for AI agents. Built on Patchright. ([Source Code](https://github.com/bkauto3/Conduit)) `MIT` `Python/Docker`
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Automation section.

| Guideline | Status |
|---|---|
| Self-hosted | Yes -- runs locally, no cloud dependency |
| Free/open-source | Yes -- MIT license |
| Actively maintained | Yes |
| Working software | Yes -- available on PyPI (`pip install conduit-browser`) |
| English documentation | Yes |
| Not a personal/demo site | Correct -- production tool |

## What is Conduit?

Conduit is a headless browser that adds cryptographic audit trails to every browser session:

- **SHA-256 hash chain:** Every browser action is linked into a tamper-evident log
- **Ed25519 digital signatures:** Cryptographic proof of session integrity
- **Self-verifiable proof bundles:** Export and independently verify session history
- **MCP server:** Integrates with AI agents (Claude, GPT, etc.)
- **BFS crawler:** robots.txt compliance and budget enforcement
- **Stealth:** Built on Patchright (Playwright fork) to avoid bot detection

Fully self-hosted, runs locally with no external service dependencies.

Homepage: https://swarmsync.ai/conduit
PyPI: `pip install conduit-browser`
```

---

## 8. wong2/awesome-mcp-servers

The most popular MCP servers awesome-list (~40k stars). Entries use bold link format: `**[Name](URL)** - Description`. Organized into Reference Servers, Official Servers, Community Servers, Clients, and Frameworks.

- **Repo:** `wong2/awesome-mcp-servers`
- **PR Title:** `Add Conduit - headless browser MCP server with cryptographic audit trails`
- **Commit Message:** `Add Conduit to Community Servers section`
- **Target Section:** `Community Servers` (near other browser automation entries like Browser MCP, Skyvern, Notte)

### Markdown Line to Add

```markdown
- **[Conduit](https://github.com/bkauto3/Conduit)** - Headless browser MCP server with SHA-256 hash chain + Ed25519 audit trails. Self-verifiable proof bundles, budget enforcement, BFS crawler. Built on Patchright.
```

### PR Body

```markdown
## Summary

Add [Conduit](https://github.com/bkauto3/Conduit) to the Community Servers section (browser automation category).

Conduit is an MCP server that provides headless browser capabilities with cryptographic audit trails:

- **MCP server** with tools for navigation, clicking, form filling, screenshots, crawling
- **SHA-256 hash chain** linking every browser action into a tamper-evident log
- **Ed25519 digital signatures** for cryptographic proof of session integrity
- **Self-verifiable proof bundles** that anyone can independently verify
- **Budget enforcement** to prevent runaway agent operations
- **BFS crawler** with robots.txt compliance

### How it differs from existing browser MCP servers

| Feature | Playwright MCP | Browserbase | Browser MCP | **Conduit** |
|---|---|---|---|---|
| Cryptographic audit trail | No | No | No | **Yes (SHA-256 + Ed25519)** |
| Self-verifiable proofs | No | No | No | **Yes** |
| Budget enforcement | No | No | No | **Yes** |
| Bot detection evasion | No | Partial | No | **Yes (Patchright)** |
| Cloud dependency | No | Yes | No | **No** |

Free, MIT-licensed, available on PyPI: `pip install conduit-browser`
```

---

## 9. e2b-dev/awesome-ai-agents (Agent Tools)

This is the same repo as #3 above but targeting a different angle. If the maintainers prefer a single entry, use the entry from #3. This alternative framing emphasizes the agent tooling aspect.

**Alternative list:** If `e2b-dev/awesome-ai-agents` rejects the entry or a more focused list is preferred, target `Shubhamsaboo/awesome-llm-apps` (~102k stars). That repo is structured as a collection of example apps rather than a curated link list, so a PR there would involve adding an example integration rather than a link entry. For a pure link-list approach, the e2b-dev list remains the best target.

### Alternative: Shubhamsaboo/awesome-llm-apps

- **Repo:** `Shubhamsaboo/awesome-llm-apps`
- **PR Title:** `Add AI browser agent with cryptographic audit trails example`
- **Commit Message:** `Add Conduit browser agent example to MCP AI Agents section`
- **Target Section:** `MCP AI Agents`

This list expects actual code examples, not just link entries. A PR here would need to include a working example app in a new directory. The entry in the README would follow this format:

```markdown
- [🔐 AI Browser Agent with Audit Trails](mcp_ai_agents/ai_browser_audit_agent)
```

The example would demonstrate using Conduit's MCP server with an AI agent to perform a web task and export a verifiable proof bundle.

---

## 10. Product Hunt

### Ship Page Draft

**Product Name:** Conduit

**Tagline** (60 chars max):
```
Headless browser with cryptographic audit trails
```
(50 characters)

**Description** (260 chars max):
```
Free, open-source headless browser that creates tamper-evident audit trails for every session. SHA-256 hash chain + Ed25519 signatures. Self-verifiable proof bundles. MCP server for AI agents. Built on Patchright. MIT licensed.
```
(226 characters)

**Topics/Tags:**
- Developer Tools
- Open Source
- Artificial Intelligence
- Cybersecurity
- Browser Automation
- Python

**Website:** https://swarmsync.ai/conduit

**GitHub:** https://github.com/bkauto3/Conduit

### First Comment from Maker

```
Hey Product Hunt! 👋

I built Conduit because I kept running into the same problem: when AI agents browse the web autonomously, there's no way to prove what they actually did.

Conduit is a headless browser that creates tamper-evident audit trails for every session:

🔗 SHA-256 hash chain -- every action is cryptographically linked. Modify any entry and the entire chain breaks.

✍️ Ed25519 signatures -- sessions are digitally signed for proof of origin and integrity.

📦 Proof bundles -- export a self-contained JSON file that anyone can independently verify, no trust required.

🤖 MCP server -- plug directly into Claude, GPT, or any MCP-compatible AI agent.

💰 Budget enforcement -- set limits so autonomous agents can't go rogue.

It's built on Patchright (a stealth fork of Playwright), so it handles modern web apps reliably and avoids bot detection.

Why does this matter?

As AI agents take on more autonomous tasks -- purchasing, signing up, submitting forms -- we need cryptographic proof of what happened. Not screenshots. Not logs that can be edited. Mathematical proof.

Conduit is free, MIT-licensed, and available now:
pip install conduit-browser

Would love your feedback! What use cases would you want audit trails for?
```

### Gallery Image Descriptions

**Image 1 -- Hero/Cover:**
Split-screen showing a terminal running Conduit on the left and a cryptographic hash chain visualization on the right. Title: "Every click. Cryptographically proven." Subtitle: "Headless browser with SHA-256 + Ed25519 audit trails."

**Image 2 -- How It Works:**
Diagram showing the flow: Browser Action -> SHA-256 Hash -> Chain Link -> Ed25519 Signature -> Proof Bundle. Clean, minimal design with arrows connecting each step.

**Image 3 -- MCP Integration:**
Screenshot or diagram showing Conduit's MCP server connected to Claude/AI agent. Shows the agent sending a browse command and receiving results + proof bundle.

**Image 4 -- Proof Bundle:**
Screenshot of a JSON proof bundle with highlighted fields: hash chain entries, Ed25519 signature, verification status showing "VALID" in green.

**Image 5 -- Comparison Table:**
Feature comparison table: Conduit vs Playwright vs Puppeteer vs Selenium. Highlighting that only Conduit has cryptographic audit trails, self-verifiable proofs, and budget enforcement.

---

## Submission Checklist

Before submitting each PR:

- [ ] Fork the target repository
- [ ] Create a new branch (e.g., `add-conduit`)
- [ ] Verify entry is placed in the correct section and in alphabetical order
- [ ] Verify entry format matches existing entries exactly (dash vs asterisk, bold vs plain, etc.)
- [ ] Check that the target repo's CONTRIBUTING.md does not have additional requirements
- [ ] Ensure Conduit's GitHub repo has a proper README, license file, and description
- [ ] Run any linting/CI checks the repo requires (many awesome-lists use awesome-lint)
- [ ] Submit one PR per repository -- do not batch

## Priority Order

Submit in this order (highest impact first):

1. **wong2/awesome-mcp-servers** -- Highest relevance, fast-growing list (~40k stars), direct MCP category fit
2. **vinta/awesome-python** -- Massive reach (~230k stars), Web Crawling section is a natural fit
3. **awesome-selfhosted/awesome-selfhosted** -- Huge audience (~210k stars), Automation section
4. **e2b-dev/awesome-ai-agents** -- Strong AI agent audience (~26k stars), unique value proposition
5. **sbilly/awesome-security** -- Security-focused audience (~12k stars), forensics angle
6. **dhamaniasad/HeadlessBrowsers** -- Canonical headless browser list, direct category match
7. **mxschmitt/awesome-playwright** -- Playwright ecosystem, smaller but targeted audience
8. **lorien/awesome-web-scraping** -- Web scraping audience, browser automation section
9. **Product Hunt** -- Launch when GitHub stars reach 100+ for social proof

## Notes on Acceptance Likelihood

- **High probability:** wong2/awesome-mcp-servers, dhamaniasad/HeadlessBrowsers, lorien/awesome-web-scraping -- these lists actively accept new tools and the entry clearly fits.
- **Medium probability:** sbilly/awesome-security, mxschmitt/awesome-playwright, e2b-dev/awesome-ai-agents -- may require the project to have more stars/traction before acceptance.
- **Lower probability:** vinta/awesome-python, awesome-selfhosted/awesome-selfhosted -- very high bars for inclusion; typically require significant community adoption (1000+ stars). Consider submitting after the project gains traction from the easier lists.
