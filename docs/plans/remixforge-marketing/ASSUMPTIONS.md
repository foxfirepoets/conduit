# ASSUMPTIONS.md -- Conduit Marketing Assumption Smash
## RemixForge Session: 2026-03-11
## Focus: Marketing strategy assumptions, not product assumptions

---

## The 15 Assumptions Baked Into Conduit's Current Marketing Approach

1. **"We need to market to developers."** Developers are the primary audience. All channels, language, and positioning target them.

2. **"MCP directories are where agents discover tools."** The submission plan targets 10+ MCP directories as the primary discovery channel.

3. **"The README is our main marketing asset."** Weeks of effort restructuring, adding badges, rewriting sections. The README must convince.

4. **"Agents cannot do their own marketing."** A human must write, submit, post, and manage every marketing action.

5. **"Cryptographic proofs are a technical feature."** SHA-256 hash chains and Ed25519 signatures are positioned as engineering details in a "Core Differentiator" section.

6. **"GitHub stars are a proxy for credibility."** Multiple plans gate actions on star count ("wait for 25+ stars before awesome-python PR").

7. **"More directory listings = more discovery."** The plan maximizes listings across 140+ platforms.

8. **"Social media posts drive developer adoption."** Reddit, HN, Twitter, dev.to posts are planned for Week 3.

9. **"Open-source distribution follows a launch curve."** There is a "Phase 0 foundation, Phase 1 listings, Phase 3 launch" sequence.

10. **"The comparison table against Playwright/Puppeteer wins developers."** The competitive comparison is positioned as a key conversion tool.

11. **"Free + open-source is enough to drive adoption."** MIT license + free tool should attract developers naturally.

12. **"The funnel is: developer discovers Conduit -> builds agent -> discovers SwarmSync."** The conversion path flows from tool to marketplace.

13. **"We need a polished README before marketing."** Foundation work (badges, sections, install instructions) must precede distribution.

14. **"Proof bundles are a product output."** They are artifacts generated at the end of sessions, separate from marketing.

15. **"Our competitors are Playwright, Puppeteer, and other browser tools."** Marketing positions Conduit in the headless browser category.

---

## 7 Smashed Assumptions and What Survives

---

### SMASH 1: "We need to market to developers"
**Flipped:** The most valuable audience has never heard of MCP, does not read awesome-lists, and does not use GitHub.

**Implication:** Compliance officers, e-discovery lawyers, investigative journalists, insurance adjusters, and competitive intelligence professionals all need what Conduit produces -- but none of them will ever find an MCP directory. They search for "evidence preservation," "audit trail," "tamper-proof web capture," and "verified website monitoring." These are Google searches, not GitHub searches.

**Concepts that survive in the flipped world:**

**Concept A -- Legal/Compliance Content Marketing**
Write 5 articles targeting non-developer audiences:
1. "How to Preserve Web Evidence for Litigation" (targets: lawyers, paralegals)
2. "Cryptographic Proof of Website Content for Insurance Claims" (targets: adjusters)
3. "SOC 2 Compliant Browser Automation for Regulated Industries" (targets: GRC teams)
4. "Evidence-Grade Web Capture for OSINT Investigations" (targets: Bellingcat community)
5. "Automated Regulatory Filing Monitoring with Tamper-Proof Audit Trails" (targets: fintech compliance)

Publish on: legal tech blogs, ISACA community, SCIP newsletter, IRE (Investigative Reporters and Editors). NOT on dev.to or r/Python.

**Concept B -- Industry-Specific Landing Pages**
Create swarmsync.ai/conduit/legal, swarmsync.ai/conduit/compliance, swarmsync.ai/conduit/journalism. Each page speaks the audience's language: "evidence preservation" not "hash chain," "audit-ready proof" not "Ed25519 signature," "verified capture" not "proof bundle." Same product. Different words. Different Google rankings.

---

### SMASH 2: "MCP directories are where agents discover tools"
**Flipped:** Agents discover tools by encountering them in the wild -- in framework defaults, in proof bundles, in job requirements.

**Implication:** An agent that encounters a Conduit proof bundle while executing a SwarmSync job will discover Conduit through the manifest.json. An agent framework that ships with Conduit as a dependency will expose Conduit to every framework user. A SwarmSync job listing that requires a proof bundle will drive agents to adopt Conduit. None of these discovery paths involve a directory.

**Concepts that survive in the flipped world:**

**Concept C -- Proof Bundle as Discovery Event**
Every proof bundle contains `generator_url` in its manifest. When any system (SwarmSync, a CI pipeline, a compliance tool) ingests a proof bundle, it discovers Conduit. The proof bundle is a Trojan horse for product discovery. Scale: if 1,000 proof bundles are generated daily, that is 1,000 discovery events per day without a single directory listing.

**Concept D -- Framework Default Strategy**
Submit integration PRs to the top 5 agent frameworks (LangChain, CrewAI, AutoGen, OpenHands, BabyAGI). Each PR adds Conduit as the default or recommended auditable browser. When a framework user needs browser automation, the framework documentation points them to Conduit. Discovery happens through the framework's existing distribution, not through Conduit's marketing.

---

### SMASH 3: "The README is our main marketing asset"
**Flipped:** Nobody reads the README until after they have already decided to evaluate the product. The README is a reference doc, not a conversion tool.

**Implication:** The conversion happens BEFORE the README: in a proof bundle someone verified, in a framework that embedded Conduit, in a colleague's recommendation, in a compliance requirement, in a SwarmSync job listing. By the time someone opens the README, they are looking for install instructions and API docs, not persuasion.

**Concepts that survive in the flipped world:**

**Concept E -- Proof Bundle as the Primary Conversion Asset**
Replace the README's first CTA from "Install" to "Verify." Provide a downloadable proof bundle at the top of the README. The visitor runs `python verify.py`, sees the hash chain validate, reads the attribution footer, and experiences the product. THEN they scroll down to install instructions. The proof bundle converts. The README documents.

**Concept F -- "Don't Trust Us. Verify." as Core Messaging**
The tagline is not "headless browser with audit trails." The tagline is "Don't trust us. Verify." This directly addresses the trust paradox (0 stars, no social proof) by replacing social proof with mathematical proof. The message works regardless of star count, community size, or marketing budget. A zero-star repo with a verifiable proof is more trustworthy than a 50K-star repo without one.

---

### SMASH 4: "Agents cannot do their own marketing"
**Flipped:** An agent running on Conduit can discover, evaluate, and submit to any web-based directory, and produce cryptographic proof that it did so.

**Implication:** The META loop is not just clever -- it is structurally necessary. A solo founder with zero marketing budget and a product that automates web interactions should use the product to automate its own marketing. The proof bundles generated by the marketing agent become the demos that market the product. The loop is self-sustaining.

**Concepts that survive in the flipped world:**

**Concept G -- The Self-Marketing Agent**
Build `marketing_agent.py` (or extend compliance_auditor.py as a template):
1. Crawl a list of directory submission URLs
2. For each: extract submission requirements, fill forms, submit
3. Export a proof bundle of each submission
4. Post the proof bundle to the GitHub Proof Gallery
5. Run daily on a cron, discovering new directories via web search

Human effort after initial setup: zero. Marketing output: continuous. And every proof bundle is a product demo.

**Concept H -- Agent Testimonials (Agents Review Conduit Using Conduit)**
Build an agent that uses Conduit to browse the Conduit README, extract the feature claims, then uses Conduit to verify each claim (e.g., "stealth mode" -> visit a bot detection site, produce proof). The agent generates a "Verified Feature Report" -- a proof bundle that cryptographically verifies Conduit's own marketing claims. No competitor can produce a self-verifying product review.

---

### SMASH 5: "Cryptographic proofs are a technical feature"
**Flipped:** Cryptographic proofs are the ENTIRE VALUE PROPOSITION. They are not a feature -- they are the product.

**Implication:** Every marketing message should lead with trust, not with browser automation. "We prove what happened" is more compelling than "we automate browsers." The comparison is not Conduit vs Playwright. The comparison is Conduit (verifiable) vs everything else (trust me). This reframes the competitive landscape: Conduit is not in the browser category. It is in the trust category.

**Concepts that survive in the flipped world:**

**Concept I -- "Proof" as the Brand, Not "Browser"**
Rename the positioning from "headless browser with audit trails" to "verifiable agent execution engine." Every marketing message leads with: "Prove what your agent did." The browser is the implementation. The proof is the product. This attracts everyone who needs trust (compliance officers, lawyers, enterprise buyers) not just everyone who needs a browser (developers).

**Concept J -- Proof-as-a-Service for Non-Technical Users**
Non-developers cannot run `pip install`. But they can receive a proof bundle, click verify.py, and see "VERIFIED." Build a web-based verifier at swarmsync.ai/verify that accepts a proof bundle upload and displays the verification result. Now compliance officers, lawyers, and executives can verify proofs without Python. The verification page IS the marketing -- it puts SwarmSync.ai in the flow.

---

### SMASH 6: "GitHub stars are a proxy for credibility"
**Flipped:** Mathematical proof is a proxy for credibility. Stars are vanity. Verification is trust.

**Implication:** Stop waiting for stars. A proof bundle that verifies is infinitely more credible than 10,000 stars. The trust paradox ("we build trust tools but have zero social proof") is resolved by demonstrating, not by accumulating. Every interaction should demonstrate, not claim.

**Concepts that survive in the flipped world:**

**Concept K -- "Zero Stars, Full Proof" Campaign**
Lean into the zero-star status. Marketing message: "This repo has [N] stars and [M] independently verifiable proof bundles. Which one matters?" This is contrarian, memorable, and structurally true. It positions the star obsession of the open-source community as a weakness -- social proof is gamed, mathematical proof is not.

**Concept L -- Proof Counter Instead of Star Counter**
Add a badge to the README: "Proof Bundles Verified: [N]" instead of (or alongside) the star count badge. Every verified proof bundle increments the counter. This creates a new metric -- one that only Conduit can measure, one that directly correlates with real usage. Over time, the proof count becomes the credibility signal.

---

### SMASH 7: "Our competitors are Playwright, Puppeteer, and other browser tools"
**Flipped:** Our competitors are screenshots, manual evidence collection, unverified claims, and blind trust.

**Implication:** Conduit is not competing with browser tools. It is competing with the absence of verification. Every time someone takes a screenshot as "evidence," that is a lost Conduit user. Every time someone trusts an agent's log without proof, that is a lost Conduit user. The addressable market is not "people who use headless browsers." It is "anyone who needs to trust what happened on the web."

**Concepts that survive in the flipped world:**

**Concept M -- Position Against "Trust Me" Culture**
Marketing message: "Your agent's work is only as trustworthy as your evidence. Screenshots are not evidence. Logs are not evidence. Proof bundles are evidence." This positions the real competitor (unverified claims) and makes every existing tool inadequate by omission. It is not "Conduit vs Playwright." It is "Proof vs No Proof."

**Concept N -- The "Screenshot Graveyard" Demo**
Build a demo that takes a screenshot of a web page, then modifies the screenshot (changes a number, alters text), and shows both side by side -- asking "which one is real?" Then produce a Conduit proof bundle of the same page and run verify.py. The demo makes the weakness of screenshots visceral. Use this as a conference talk opener, a blog post hook, or a video intro. The visual is impossible to ignore.

---

## Summary: Concepts Generated from Smashed Assumptions

| Concept | Assumption Smashed | Core Innovation |
|---------|-------------------|-----------------|
| A -- Legal/Compliance Content | "Market to developers" | Non-developer audiences with unmet needs |
| B -- Industry Landing Pages | "Market to developers" | Same product, different vocabulary per audience |
| C -- Proof Bundle as Discovery | "MCP directories" | Product output IS discovery channel |
| D -- Framework Default | "MCP directories" | Infrastructure embedding replaces directory listings |
| E -- Proof as Primary Conversion | "README is marketing" | Verify before you read |
| F -- "Don't Trust Us. Verify." | "README is marketing" | Mathematical proof replaces social proof |
| G -- Self-Marketing Agent | "Agents can't market" | Product markets itself using itself |
| H -- Agent Verified Features | "Agents can't market" | Product reviews its own claims with proof |
| I -- "Proof" as the Brand | "Proofs are technical" | Trust is the product, browser is implementation |
| J -- Web Proof Verifier | "Proofs are technical" | Non-technical users verify at swarmsync.ai |
| K -- "Zero Stars, Full Proof" | "Stars = credibility" | Contrarian positioning that is structurally true |
| L -- Proof Counter Badge | "Stars = credibility" | New metric only Conduit can measure |
| M -- Anti "Trust Me" Culture | "Competitors are browsers" | Real competitor is unverified claims |
| N -- Screenshot Graveyard Demo | "Competitors are browsers" | Visceral demonstration of evidence gap |
