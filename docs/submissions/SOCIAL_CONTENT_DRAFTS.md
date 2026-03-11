# Conduit Social Content Drafts

**Ready-to-post content for all distribution channels.**

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: `pip install conduit-browser`
- SwarmSync: https://swarmsync.ai
- Conduit page: https://swarmsync.ai/conduit
- License: MIT

---

## 1. HackerNews "Show HN" Post

**Title:** Show HN: Conduit -- Headless browser with SHA-256 hash chain and Ed25519 audit trails

**Body:**

I've been building AI agent tooling and kept running into the same problem: agents browse the web, take actions, fill out forms, scrape data -- and there's zero proof of what actually happened. Screenshots can be faked. Logs can be edited. If something goes wrong, you're left pointing fingers at a black box.

So I built Conduit. It's a headless browser (Playwright under the hood) that records every action into a SHA-256 hash chain and signs the result with Ed25519. Each action gets hashed with the previous hash, forming a tamper-evident chain. At the end of a session, you get a "proof bundle" -- a JSON file containing the full action log, the hash chain, the signature, and the public key. Anyone can independently verify the bundle without trusting the party that produced it.

The main use cases I'm targeting:

- **AI agent auditing** -- You hand an agent a browser. Later you need to prove what it did. Conduit gives you cryptographic receipts.
- **Compliance automation** -- SOC 2, GDPR data subject access workflows, anything where you need evidence that a process ran correctly.
- **Web scraping provenance** -- Prove that the data you collected actually came from where you say it did, at the time you say it did.
- **Litigation support** -- Capture web content with a verifiable chain of custody.

It also ships as an MCP (Model Context Protocol) server, so Claude, GPT, and other LLM-based agents can use the browser natively through tool calls. The agent gets browse, click, fill, screenshot, and the proof bundle builds itself in the background.

Free, MIT-licensed, pure Python. No accounts, no API keys, no telemetry.

GitHub: https://github.com/bkauto3/Conduit

Install: `pip install conduit-browser`

Would love feedback on the proof bundle format and the MCP integration. Happy to answer questions about the cryptographic design.

---

## 2. Reddit Posts

### r/Python

**Title:** I built a headless browser with cryptographic audit trails in Python

**Body:**

Hey r/Python. I just open-sourced Conduit, a headless browser library that builds SHA-256 hash chains and Ed25519 digital signatures around every browser action.

The idea is simple: every time the browser navigates, clicks, fills a form, or takes a screenshot, that action gets recorded and hashed. Each hash includes the previous hash, forming a chain. At the end, the whole thing gets signed with Ed25519. You get a "proof bundle" JSON file that anyone can verify independently.

Why? I work on AI agent tooling and needed a way to prove what agents did during browser sessions. Existing tools (Playwright, Selenium, Puppeteer) are great at automation but give you nothing for accountability. Conduit wraps Playwright and adds the trust layer on top.

Tech details:

- Pure Python, async-first (built on `asyncio` + Playwright)
- SHA-256 for the hash chain, Ed25519 for signing (via `cryptography` library)
- Proof bundles are self-contained JSON -- action log, hash chain, signature, public key
- Also ships as an MCP server so LLM-based agents can call it via tool use
- Stealth mode with common fingerprint evasion built in
- MIT licensed

Install:

```bash
pip install conduit-browser
```

Basic usage:

```python
from conduit import ConduitBrowser

async with ConduitBrowser() as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
    await page.click("#submit")
    proof = await browser.get_proof_bundle()
    # proof contains hash chain + Ed25519 signature
```

The proof bundle verification is one function call:

```python
from conduit import verify_proof_bundle

is_valid = verify_proof_bundle(proof)
# Returns True if chain is intact and signature is valid
```

GitHub: https://github.com/bkauto3/Conduit

Looking for feedback on the API design and the proof bundle schema. Also curious if anyone has thoughts on adding Merkle tree support for batched proofs.

---

### r/webscraping

**Title:** Open source headless browser with built-in proof of what your scraper did

**Body:**

I built Conduit, an open-source headless browser that creates cryptographic proof of every action during a scraping session. Thought this community might find it useful.

The problem: you scrape data, deliver it to a client or use it internally, and later someone asks "where did this data actually come from?" or "when exactly was this captured?" You've got logs, maybe screenshots, but none of it is tamper-evident. Anyone could have edited those logs.

Conduit fixes this by building a SHA-256 hash chain during the browser session. Every navigation, click, form fill, and screenshot gets hashed, and each hash includes the previous one. At the end, the whole chain gets signed with an Ed25519 key. You get a "proof bundle" -- a JSON file that proves exactly what happened, in what order, and that nothing was modified after the fact.

For scraping specifically:

- **Data provenance** -- Prove your scraped data came from a specific URL at a specific time
- **Client deliverables** -- Hand clients the proof bundle alongside the data
- **Legal defensibility** -- If a site claims you accessed something you didn't, the hash chain is your alibi
- **Change monitoring** -- Capture page state with verifiable timestamps

It also has stealth mode baked in -- common fingerprint evasion, realistic viewport/user-agent rotation. So you get anti-detection and auditability in one package.

Built on Playwright, so anything Playwright can do, Conduit can do with a proof trail on top. Pure Python, MIT licensed.

```bash
pip install conduit-browser
```

GitHub: https://github.com/bkauto3/Conduit

Would love to hear from people doing scraping at scale. Is provenance something your clients ask about? Would a batch proof mode (Merkle trees over multiple sessions) be useful?

---

### r/artificial

**Title:** Giving AI agents a browser they can prove they used

**Body:**

One of the harder problems with autonomous AI agents is accountability. When you give an agent access to a browser and tell it to go fill out a form, book a flight, or research a topic, how do you know what it actually did?

I built Conduit to solve this. It's a headless browser that records every action into a SHA-256 hash chain and signs the session with Ed25519. The output is a "proof bundle" -- a self-contained JSON file that cryptographically proves what the agent did, in what order, and that the record hasn't been tampered with.

The key insight: agents need browsers, and the people deploying agents need proof. Right now those are two separate problems solved by two separate tools. Conduit combines them.

It ships as an MCP (Model Context Protocol) server, which means Claude, GPT-based agents, and any MCP-compatible system can use it natively. The agent calls tools like `browse`, `click`, `fill`, `screenshot` -- and Conduit silently builds the cryptographic proof in the background. The agent doesn't need to know or care about the audit trail.

Use cases I'm seeing:

- **Agent oversight** -- Review exactly what your agent did during a task, with tamper-proof evidence
- **Regulatory compliance** -- When agents handle sensitive workflows (financial, healthcare, legal), you need auditable records
- **Multi-agent systems** -- When agents delegate to other agents, proof bundles become receipts between parties
- **Agent marketplaces** -- Buyers can verify that a hired agent actually performed the work it claims

Free, MIT licensed, pure Python. No API keys, no accounts.

GitHub: https://github.com/bkauto3/Conduit

Install: `pip install conduit-browser`

Curious what this community thinks about the accountability gap in agent tooling. Is cryptographic proof overkill, or is it the baseline we should expect?

---

## 3. Twitter/X Thread

**Tweet 1:**
Every headless browser automates. Only one proves it.

Introducing Conduit -- a headless browser with SHA-256 hash chains and Ed25519 audit trails.

Free. MIT licensed. Built for AI agents.

Thread on why this matters:

**Tweet 2:**
The problem: you give an AI agent a browser. It navigates, clicks, fills forms, scrapes data.

Then someone asks: "What did it actually do?"

You have logs. Maybe screenshots. But none of it is tamper-evident. Anyone could have edited those after the fact.

**Tweet 3:**
Conduit fixes this with a hash chain.

Every browser action gets recorded and hashed with SHA-256. Each hash includes the previous hash. Modify any action and every subsequent hash breaks.

At the end, the chain gets signed with Ed25519.

The result: a cryptographic proof bundle.

**Tweet 4:**
A proof bundle is a self-contained JSON file:

- Full action log (navigate, click, fill, screenshot)
- SHA-256 hash chain linking every action
- Ed25519 signature over the chain
- Public key for independent verification

Anyone can verify it. No trust required.

**Tweet 5:**
It ships as an MCP server.

Claude, GPT-based agents, any MCP-compatible system can use Conduit natively through tool calls.

The agent browses. The proof builds itself in the background. Zero overhead for the agent developer.

**Tweet 6:**
Use cases:

- AI agent auditing (prove what your agent did)
- Compliance automation (SOC 2, GDPR evidence)
- Web scraping provenance (prove where data came from)
- Litigation support (chain-of-custody for web content)
- Multi-agent receipts (agents proving work to each other)

**Tweet 7:**
Install in one line:

```
pip install conduit-browser
```

Five lines to get a proof bundle:

```python
async with ConduitBrowser() as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
    proof = await browser.get_proof_bundle()
```

**Tweet 8:**
Stealth mode is built in. Fingerprint evasion, realistic viewports, user-agent rotation.

Because an auditable browser that gets blocked isn't useful.

**Tweet 9:**
It's free. MIT licensed. No API keys. No accounts. No telemetry.

GitHub: https://github.com/bkauto3/Conduit
PyPI: pip install conduit-browser
Docs: https://swarmsync.ai/conduit

Star it if you think AI agents should come with receipts.

**Tweet 10:**
Conduit is part of the SwarmSync ecosystem -- tools for building, deploying, and trusting AI agents.

More at https://swarmsync.ai

If you're building agents that touch the real world, auditability isn't optional. It's the foundation.

---

## 4. dev.to Article

**Title:** Building Auditable AI Agents with Conduit

**Tags:** python, ai, automation, security

**Body:**

### The Accountability Gap in AI Agent Tooling

AI agents are getting good at browsing the web. They can navigate pages, fill out forms, extract data, and complete multi-step workflows. But there's a gap that most agent frameworks ignore: accountability.

When an agent uses a browser, what evidence exists of what it actually did? Typically, you get logs -- plaintext files that anyone can edit after the fact. Maybe screenshots, which can be fabricated. There's no cryptographic guarantee that the record of an agent's browser session is authentic and unmodified.

This matters more than most people realize. If you're deploying agents in regulated industries (finance, healthcare, legal), you need auditable records. If you're running an agent marketplace, buyers need proof that agents performed the work they claim. If an agent makes a mistake, you need a tamper-evident trail to understand what happened.

### What Conduit Does

Conduit is a headless browser library for Python that builds a SHA-256 hash chain around every browser action and signs the result with Ed25519. It's built on top of Playwright, so it inherits all of Playwright's automation capabilities and adds a cryptographic trust layer on top.

Here's the core idea: every time the browser does something -- navigates, clicks, fills a form, takes a screenshot -- that action gets recorded as a structured event and hashed with SHA-256. Critically, each hash includes the previous hash, forming a chain. If any action in the chain is modified, every subsequent hash breaks. This is the same principle behind blockchain, applied to browser sessions.

At the end of a session, the entire hash chain is signed with an Ed25519 private key. The output is a "proof bundle" -- a self-contained JSON file that includes the action log, the hash chain, the signature, and the public key needed to verify it.

### Getting Started

Install from PyPI:

```bash
pip install conduit-browser
```

Basic usage:

```python
import asyncio
from conduit import ConduitBrowser

async def main():
    async with ConduitBrowser() as browser:
        page = await browser.new_page()

        # Every action is recorded and hashed
        await page.goto("https://example.com")
        await page.click("a[href='/about']")
        await page.screenshot(path="about.png")

        # Get the proof bundle
        proof = await browser.get_proof_bundle()

        # Save it
        with open("session_proof.json", "w") as f:
            json.dump(proof, f, indent=2)

asyncio.run(main())
```

The proof bundle looks like this:

```json
{
  "session_id": "c3f8a...",
  "actions": [
    {
      "type": "navigate",
      "url": "https://example.com",
      "timestamp": "2026-03-11T14:30:00Z",
      "hash": "a1b2c3..."
    },
    {
      "type": "click",
      "selector": "a[href='/about']",
      "timestamp": "2026-03-11T14:30:01Z",
      "previous_hash": "a1b2c3...",
      "hash": "d4e5f6..."
    }
  ],
  "chain_root": "d4e5f6...",
  "signature": "ed25519_sig_...",
  "public_key": "ed25519_pub_..."
}
```

### Verifying a Proof Bundle

Verification is independent -- anyone can verify a proof bundle without trusting the party that created it:

```python
from conduit import verify_proof_bundle
import json

with open("session_proof.json") as f:
    proof = json.load(f)

result = verify_proof_bundle(proof)

if result.valid:
    print("Chain intact, signature valid")
    print(f"Actions: {result.action_count}")
    print(f"Session duration: {result.duration}")
else:
    print(f"Verification failed: {result.reason}")
```

The verifier checks two things:
1. **Hash chain integrity** -- Recomputes every hash and confirms the chain is unbroken
2. **Signature validity** -- Verifies the Ed25519 signature over the chain root using the embedded public key

### MCP Server for AI Agents

Conduit ships as an MCP (Model Context Protocol) server. This means LLM-based agents -- Claude, GPT, or any MCP-compatible system -- can use Conduit natively through tool calls.

```json
{
  "mcpServers": {
    "conduit": {
      "command": "conduit-mcp",
      "args": ["--stealth"]
    }
  }
}
```

Once configured, the agent gets access to tools like `browse`, `click`, `fill`, `screenshot`, and `get_proof_bundle`. The hash chain builds itself in the background. The agent doesn't need to manage the audit trail -- it just uses the browser and the proof is automatic.

### Stealth Mode

An auditable browser that gets blocked isn't useful. Conduit includes stealth mode with common fingerprint evasion techniques: realistic viewport sizes, user-agent rotation, WebDriver flag masking, and other standard anti-detection measures. It's not a silver bullet against sophisticated bot detection, but it handles the common checks.

```python
async with ConduitBrowser(stealth=True) as browser:
    # Fingerprint evasion is active
    page = await browser.new_page()
    await page.goto("https://target-site.com")
```

### Real-World Use Cases

**Compliance automation:** An agent processes GDPR data subject access requests. Each request involves logging into a portal, locating records, and exporting data. Conduit provides a proof bundle for each request that auditors can independently verify.

**Web scraping provenance:** A data provider scrapes pricing data for clients. Each scraping session produces a proof bundle proving exactly which pages were visited, when, and that the collected data matches what was on the page.

**Agent marketplaces:** A buyer hires an agent to perform research. The agent returns results plus a proof bundle. The buyer verifies the agent actually visited the claimed sources.

**Litigation support:** A law firm needs to capture the current state of a web page as evidence. Conduit provides a cryptographic chain of custody for the capture.

### Open Source, No Strings

Conduit is MIT licensed. No API keys, no accounts, no telemetry. The cryptographic keys are generated locally. Proof bundles are self-contained -- verification requires no external service.

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: `pip install conduit-browser`
- Docs: https://swarmsync.ai/conduit

Conduit is part of the SwarmSync ecosystem -- a set of open-source and commercial tools for building trustworthy AI agent systems. If you're building agents that interact with the real world, auditable tooling isn't a luxury. It's infrastructure.

Star the repo, try it out, and let me know what you build with it.

---

## 5. LinkedIn Post

**Building AI Agents? Your Audit Trail Has a Gap.**

The adoption of AI agents in enterprise workflows is accelerating. Agents are filling out forms, processing documents, navigating portals, and executing multi-step tasks that used to require human operators. This creates a new category of compliance risk that most organizations haven't addressed: browser session accountability.

When a human employee completes a web-based workflow, there's an implicit audit trail -- access logs, session recordings, the human's own memory. When an AI agent does the same task, what evidence exists? Application logs are plaintext and editable. Screenshots can be fabricated. There's no tamper-evident record of what the agent actually did inside a browser.

This gap matters for anyone dealing with SOC 2 compliance, GDPR data processing records, financial regulations, or litigation holds. Auditors don't accept "we ran a script and here are the logs" as evidence. They need a chain of custody.

I've been working on this problem and built Conduit -- a headless browser that records every action into a SHA-256 hash chain and signs the session with Ed25519 digital signatures. The output is a self-contained "proof bundle" that any third party can independently verify.

**How it works:**

Each browser action (navigate, click, form fill, screenshot) is recorded as a structured event and hashed. Each hash incorporates the previous hash, forming a tamper-evident chain. Modifying any single action invalidates every subsequent hash. At session end, the chain is signed with Ed25519, producing a cryptographic proof that the session record is authentic and unmodified.

**What this means for compliance and legal teams:**

- **SOC 2 audits:** Proof bundles provide verifiable evidence that automated controls executed as described. Auditors can independently verify the hash chain and signature without trusting the organization that produced them.
- **GDPR Article 30 records:** When agents process data subject requests, each session generates a tamper-evident record of exactly what data was accessed and how it was handled.
- **Litigation support:** Web content captured through Conduit includes a cryptographic chain of custody. The proof bundle demonstrates that the content was captured at a specific time and hasn't been altered since.
- **Regulatory examinations:** Financial services firms using agents for research or compliance workflows can provide examiners with verifiable evidence of agent activities.

**The proof bundle is the key artifact.** It's a JSON file containing the full action log, the SHA-256 hash chain, the Ed25519 signature, and the public key needed for verification. It requires no external service to verify -- any party with the bundle can confirm its integrity using standard cryptographic libraries.

Conduit also ships as an MCP (Model Context Protocol) server, which means it integrates directly with AI agent frameworks. The agent uses the browser through standard tool calls, and the proof bundle builds automatically in the background.

The tool is open source (MIT license) and free to use. No API keys, no vendor lock-in.

If you're deploying AI agents in workflows where accountability matters -- and if you're in a regulated industry, it always matters -- I'd welcome your perspective on what a production-grade audit trail needs to look like.

GitHub: https://github.com/bkauto3/Conduit
Documentation: https://swarmsync.ai/conduit

#AIAgents #Compliance #CyberSecurity #LegalTech #SOC2 #GDPR #OpenSource #Automation

---

## 6. GitHub Discussions Announcement

**Title:** Conduit v0.2.0 -- MCP Server, Proof Bundles, and SwarmSync Ecosystem Integration

**Category:** Announcements

**Body:**

Conduit v0.2.0 is out. Here's what's new.

### MCP Server Support

Conduit now ships as a Model Context Protocol (MCP) server. Any MCP-compatible agent (Claude, GPT, custom agents) can use Conduit as a browser tool with built-in audit trails.

Configuration:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "conduit-mcp",
      "args": ["--stealth"]
    }
  }
}
```

Available tools: `browse`, `click`, `fill`, `screenshot`, `get_proof_bundle`, `verify_proof_bundle`

The proof bundle builds automatically in the background. Agents don't need to manage the audit trail -- they just use the browser.

### Proof Bundles

Proof bundles are the core output format. A proof bundle is a self-contained JSON file that includes:

- **Action log** -- Every browser action with timestamps
- **SHA-256 hash chain** -- Each action hashed with the previous hash, forming a tamper-evident chain
- **Ed25519 signature** -- Digital signature over the chain root
- **Public key** -- For independent verification

Generate a proof bundle:

```python
async with ConduitBrowser() as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
    proof = await browser.get_proof_bundle()
```

Verify one:

```python
from conduit import verify_proof_bundle

result = verify_proof_bundle(proof)
assert result.valid
```

### Stealth Mode Improvements

- Improved fingerprint evasion defaults
- Realistic viewport and user-agent rotation
- WebDriver flag masking

### SwarmSync Ecosystem

Conduit is now part of the SwarmSync agent ecosystem at https://swarmsync.ai. SwarmSync is a marketplace for AI agents, and Conduit provides the trust layer -- agents that use Conduit can prove what they did to buyers, auditors, and other agents.

Learn more: https://swarmsync.ai/conduit

### Install / Upgrade

```bash
pip install --upgrade conduit-browser
```

### What's Next

- Merkle tree support for batched proofs across multiple sessions
- Timestamp attestation via third-party timestamping authorities (RFC 3161)
- Video recording with hash-chained frames
- Proof bundle viewer web UI

### Links

- PyPI: https://pypi.org/project/conduit-browser/
- Docs: https://swarmsync.ai/conduit
- Issues: https://github.com/bkauto3/Conduit/issues

Feedback welcome. File issues for bugs, start discussions for feature ideas.

---

## 7. Blog Post for swarmsync.ai/blog

**Title:** Introducing Conduit: The Trust Layer for AI Agent Browsers

**Subtitle:** Why auditable browsing is the missing piece in autonomous AI agent infrastructure

---

AI agents are getting access to the real world. They browse websites, fill out forms, extract data, submit applications, and execute multi-step workflows that cross organizational boundaries. This is genuinely useful. It's also genuinely unaccountable.

When you give an agent a browser, you're giving it the ability to act on your behalf across the open web. The agent navigates pages, clicks buttons, enters information, and retrieves results. But when the session ends, what evidence exists of what actually happened?

Typically: logs. Plaintext, mutable, trivially editable logs. Maybe screenshots that anyone with image editing skills could fabricate. There's no cryptographic proof. No chain of custody. No way for a third party to independently verify that a browser session happened the way the log claims it did.

This is the problem Conduit solves.

### What Conduit Is

Conduit is a headless browser for Python that builds a SHA-256 hash chain around every browser action and signs the result with Ed25519 digital signatures. It's open source (MIT license), free to use, and designed specifically for AI agent workflows.

Under the hood, Conduit wraps Playwright -- so it inherits all of Playwright's automation power. What it adds is a trust layer: a cryptographic audit trail that proves what the browser did, when it did it, and that the record hasn't been tampered with.

### How the Hash Chain Works

The concept is straightforward. Every browser action -- navigate, click, fill, screenshot -- generates a structured event record. That record gets hashed with SHA-256. The critical part: each hash incorporates the previous action's hash, forming a chain.

```
Action 1: navigate("https://example.com")
  Hash: SHA-256(action_data)
  → a1b2c3...

Action 2: click("#submit")
  Hash: SHA-256(action_data + previous_hash)
  → d4e5f6...

Action 3: screenshot("result.png")
  Hash: SHA-256(action_data + previous_hash)
  → g7h8i9...
```

If someone modifies Action 1 after the fact, its hash changes. That breaks Action 2's hash (which included Action 1's hash), which breaks Action 3's hash, and so on. Tampering with any point in the chain is immediately detectable by recomputing the hashes.

At the end of the session, the final hash (the chain root) is signed with an Ed25519 private key. This produces a digital signature that binds the entire chain to a specific identity.

### Proof Bundles: The Key Artifact

The output of a Conduit browser session is a proof bundle -- a self-contained JSON file that includes everything needed for independent verification:

- The full action log with timestamps
- The SHA-256 hash chain
- The Ed25519 signature
- The public key

Anyone with this file can verify it. Recompute the hashes, check the chain, validate the signature. No external service required. No trust in the producing party required.

```python
from conduit import ConduitBrowser, verify_proof_bundle

# Create a session with a proof trail
async with ConduitBrowser() as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
    await page.click("button#accept-terms")
    await page.fill("input#email", "user@example.com")
    await page.screenshot(path="confirmation.png")

    proof = await browser.get_proof_bundle()

# Later, anyone can verify
result = verify_proof_bundle(proof)
assert result.valid  # Chain intact, signature valid
```

### Why AI Agents Need This

The current generation of AI agents operates on trust. You trust that the agent did what it says it did. You trust that the logs are accurate. You trust that nothing was omitted or modified.

That's fine for casual use. It's not fine for:

**Regulated industries.** Financial services, healthcare, and legal workflows have audit requirements. "The AI agent did it" is not an acceptable response to a compliance examiner. You need verifiable evidence.

**Agent marketplaces.** When you hire an agent from a marketplace to perform a task, how do you know it actually did the work? A proof bundle is a receipt -- cryptographic evidence that the agent performed the claimed actions.

**Multi-agent systems.** When Agent A delegates a browsing task to Agent B, Agent A needs to verify what Agent B actually did. Proof bundles become the trust protocol between agents.

**High-stakes decisions.** If an agent's browsing session informs a decision with significant consequences -- a financial trade, a legal filing, a medical referral -- the decision-makers need an auditable trail back to the source data.

### MCP Server: Native Agent Integration

Conduit ships as an MCP (Model Context Protocol) server. MCP is becoming the standard interface for connecting AI agents to tools, and Conduit supports it natively.

Configure it in your agent's MCP settings:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "conduit-mcp",
      "args": ["--stealth"]
    }
  }
}
```

The agent gets tools: `browse`, `click`, `fill`, `screenshot`, `get_proof_bundle`. It uses the browser normally. The hash chain and signature happen automatically. The agent developer writes zero audit code.

This is intentional. Auditability should be infrastructure, not application logic. The agent shouldn't need to think about proof -- it should just use the browser, and the proof should exist.

### Stealth When You Need It

An auditable browser that gets blocked by every website isn't practical. Conduit includes a stealth mode with standard anti-detection measures: realistic fingerprints, viewport variation, user-agent rotation, and WebDriver flag masking. It handles the common bot detection checks so you can focus on the automation logic.

### Part of the SwarmSync Ecosystem

Conduit is the trust layer for the SwarmSync agent ecosystem. SwarmSync (https://swarmsync.ai) is a marketplace where AI agents are built, deployed, and hired to perform real-world tasks. In a marketplace, trust is everything. Buyers need to know that agents performed the work they claim. Sellers need to prove their agents are reliable.

Proof bundles are the mechanism. An agent listed on SwarmSync can use Conduit to produce verifiable evidence of its work. Buyers can independently verify that evidence. The marketplace becomes a trust network, not just a listing service.

Conduit is free and open source regardless of whether you use SwarmSync. It's MIT licensed, with no API keys, accounts, or telemetry. The cryptographic keys are generated locally. Proof bundles are verified locally. There's no dependency on any external service.

### Get Started

Install from PyPI:

```bash
pip install conduit-browser
```

Check out the source:

https://github.com/bkauto3/Conduit

Read the docs:

https://swarmsync.ai/conduit

If you're building AI agents that interact with the web, give Conduit a try. Star the repo on GitHub, file issues, start discussions. The trust layer for AI agents is open source, and it's ready to use today.
