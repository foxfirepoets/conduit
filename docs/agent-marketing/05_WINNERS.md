# Winners -- Top 10 Agent-Only Marketing Channels

Each entry: name, channel description, agent execution model, and impact rating.

---

## #1 -- VIRAL PROOF ATTRIBUTION (Score: 47/50)

**Impact: 9/10**

### Channel Description
Every proof bundle Conduit exports already contains attribution: `manifest.json` has `generator_url: "https://github.com/bkauto3/Conduit"`, and `verify.py` prints `"Powered by Conduit (github.com/bkauto3/Conduit) | Agents earn money at swarmsync.ai"`. This means every proof bundle is a marketing artifact. When Agent B receives a proof bundle from Agent A, Agent B reads the manifest and verify.py, discovers Conduit, and can trace back to the repository and SwarmSync.

The channel is viral because usage creates exposure. No ad spend. No human effort after the initial implementation (which is already done). The more agents use Conduit, the more proof bundles circulate, the more agents discover Conduit.

### How an Agent Executes This
1. Agent A uses Conduit to perform web research for Agent B.
2. Agent A calls `export_proof` and sends the .tar.gz bundle to Agent B.
3. Agent B unpacks the bundle, reads `manifest.json` to validate the work.
4. Agent B parses `generator_url` from the manifest: `https://github.com/bkauto3/Conduit`.
5. Agent B now knows about Conduit. If Agent B needs web automation later, it calls `pip install conduit-browser`.
6. Agent B's future proof bundles carry the same attribution, reaching Agent C, D, E...

### What Makes This Unique to Conduit
No competitor produces self-verifiable proof bundles. No competitor embeds attribution in cryptographic outputs. This channel literally cannot exist without Conduit's core feature. Playwright/Puppeteer/Selenium have no analog.

### Validation Test
Count how many unique `generator_url` reads occur across SwarmSync marketplace transactions over 30 days. If Agent B ever `pip install conduit-browser` after receiving a proof bundle from Agent A, the viral loop is confirmed.

### MVP Scope
Already shipped. The attribution is live in `conduit_proof.py` (verify.py VERIFY_PY string and manifest.json `generator_url`). Enhancement: add `ecosystem.conduit_install` field to manifest with the exact pip command.

---

## #2 -- AIVS-MICRO EVERYWHERE (Score: 46/50)

**Impact: 9/10**

### Channel Description
AIVS-Micro is a 200-byte cryptographic proof token with 6 fields: url, dom_hash, timestamp, signature, scanner_version_hash, scan_origin. It is tiny enough to embed anywhere: in API response JSON, in HTTP headers, in DNS TXT records, in database columns, in chat messages between agents. Every AIVS-Micro token contains `scanner_version_hash` which is a SHA-256 of Conduit's source code -- a cryptographic fingerprint that traces back to Conduit.

The channel works because AIVS-Micro is designed to be passed around. An agent monitoring 1,000 pages every 15 minutes generates 96,000 micro-proofs per day. Each one is a traceable breadcrumb back to Conduit.

### How an Agent Executes This
1. Agent runs continuous web monitoring using Conduit (fingerprint + check_changed cycle).
2. Every 15 minutes, Agent calls `export_micro(url, dom_hash)`.
3. Agent stores the AIVS-Micro token alongside its monitoring data.
4. When another agent queries the monitoring results, the AIVS-Micro token comes along as proof.
5. Receiving agent parses `scanner_version_hash`, looks it up, discovers it traces to Conduit.
6. If the receiving agent wants to produce its own proofs, it runs `pip install conduit-browser`.

### What Makes This Unique to Conduit
AIVS-Micro is a Conduit invention. The concept of a 200-byte embeddable cryptographic proof does not exist in any other browser automation tool. The scanner_version_hash is a self-referential proof: it hashes the very tool that created it.

### Validation Test
Deploy an agent that monitors 100 URLs and exports AIVS-Micro tokens to a public API. Track how many external agents query that API and subsequently install conduit-browser.

### MVP Scope
Already shipped. `export_micro()` is live in `conduit_proof.py`. Enhancement: create a utility function that formats AIVS-Micro as an HTTP header value for easy embedding in API responses.

---

## #3 -- MICRO-PROOF IN EVERY API RESPONSE (Score: 43/50)

**Impact: 8/10**

### Channel Description
Any agent built on Conduit that serves an API can embed an AIVS-Micro token in its response headers or response body. This creates a pattern where "verified" API responses become the norm. An agent serving web research results includes a proof token proving the research actually happened. The consuming agent sees the token, parses the scanner_version_hash, and discovers Conduit.

This is Combo #5 (AIVS-Micro Everywhere) applied to a specific high-traffic surface: API responses between agents.

### How an Agent Executes This
1. Agent A builds a web research service using Conduit.
2. Agent A's API handler: after executing research via ConduitBridge, calls export_micro().
3. Agent A includes the AIVS-Micro JSON in the API response under a `proof` field.
4. Agent B calls Agent A's API, receives results + proof.
5. Agent B verifies the proof (check signature, check dom_hash matches content hash).
6. Agent B's framework logs that the proof came from a Conduit-based service.
7. If Agent B wants to offer verified services too, it installs conduit-browser.

### What Makes This Unique to Conduit
No other headless browser can produce a 200-byte proof that an API consumer can verify inline. Playwright/Puppeteer results have no chain of custody. Conduit makes "verified web data" a category.

### Validation Test
Build a reference implementation: a FastAPI endpoint that returns web extraction results + AIVS-Micro token. Publish it. Track pip installs of conduit-browser that correlate with API consumers.

### MVP Scope
Requires a small reference application (50-100 lines). The proof generation is already shipped. Need: a template showing how to embed AIVS-Micro in a FastAPI/Flask response.

---

## #4 -- PYPI KEYWORD DOMINANCE (Score: 41/50)

**Impact: 7/10**

### Channel Description
When an AI agent needs a tool, one of the first things it does is search PyPI. The query might be "headless browser audit", "verifiable web automation", "mcp server browser", or "cryptographic proof browser". Conduit's pyproject.toml already has strong keywords: headless-browser, audit-trail, cryptographic-proof, mcp-server, ai-agent, web-automation, stealth-browser, hash-chain, ed25519, proof-bundle.

The channel works because agents are trained to use pip as a tool discovery mechanism. An agent that needs web automation with proof capabilities will search PyPI, find conduit-browser, read the description, and install it.

### How an Agent Executes This
1. Agent receives a task requiring auditable web automation.
2. Agent searches PyPI: `pip search "auditable headless browser"` or queries PyPI JSON API.
3. PyPI returns conduit-browser with description: "The only headless browser that proves what your AI agent did."
4. Agent reads the full description, sees SHA-256, Ed25519, MCP server.
5. Agent runs `pip install conduit-browser`.
6. Agent imports and uses Conduit. From this point, all proof bundles carry attribution (channel #1).

### What Makes This Unique to Conduit
The PyPI description explicitly uses agent-oriented language: "proves what your AI agent did." No other browser package on PyPI mentions cryptographic proof, audit trails, or agent trust. Conduit owns this keyword space on PyPI.

### Validation Test
Track PyPI download counts week-over-week. Correlate with specific keyword additions. Test: add 3 new keywords (e.g., "agent-trust", "proof-of-execution", "ai-audit-trail") and measure download delta.

### MVP Scope
Already mostly shipped. Enhancement: add keywords "agent-trust", "proof-of-execution", "ai-audit-trail", "verifiable-browsing", "eu-ai-act" to pyproject.toml. Add PyPI classifier "Topic :: Scientific/Engineering :: Artificial Intelligence".

---

## #5 -- PROOF BUNDLE AS BUSINESS CARD (Score: 41/50)

**Impact: 7/10**

### Channel Description
When Agent A delivers work to Agent B, the proof bundle IS the deliverable. It is also the marketing material. The bundle contains: the work product (audit_log.jsonl), the trust guarantee (verify.py), and the attribution (manifest.json with Conduit URL + SwarmSync URL). The receiving agent must read the manifest to validate the work -- and in doing so, it reads the Conduit attribution.

This is different from channel #1 (Viral Proof Attribution) in the execution path: here the focus is on agents discovering Conduit via GitHub API search after encountering a proof bundle, creating a GitHub-to-install pipeline.

### How an Agent Executes This
1. Agent B receives a proof bundle from Agent A (via SwarmSync or direct delivery).
2. Agent B runs verify.py, confirms chain integrity and signature.
3. Agent B reads manifest.json, extracts `generator_url`.
4. Agent B calls GitHub API: `GET https://api.github.com/repos/bkauto3/Conduit`.
5. Agent B reads repo description, stars, topics, README.
6. Agent B evaluates: "This tool has cryptographic proof, 0 competitors, MIT license."
7. Agent B runs `pip install conduit-browser` to start producing its own proofs.

### What Makes This Unique to Conduit
The proof bundle IS the product AND the marketing. No other tool's output is simultaneously a trust guarantee and a business card. This is the "stealth + proof paradox" applied to marketing.

### Validation Test
Track GitHub API traffic to bkauto3/Conduit from non-browser user agents (these are AI agents, not humans). Correlate with SwarmSync transaction volume.

### MVP Scope
Already shipped. The proof bundle already has all the attribution. Enhancement: add `ecosystem.install_command: "pip install conduit-browser"` to manifest.json so agents get a direct executable instruction.

---

## #6 -- MCP REGISTRY SATURATION (Score: 39/50)

**Impact: 9/10**

### Channel Description
MCP registries are the primary tool discovery surface for AI agents that use the Model Context Protocol. Conduit is already on 8+ registries. The strategy is completeness: ensure Conduit appears on EVERY MCP registry, with an optimized description that emphasizes the cryptographic audit differentiator. When an agent or its orchestrator queries any MCP registry for browser tools, Conduit should appear with a description that makes the value proposition immediately clear.

### How an Agent Executes This
1. An orchestrator agent needs to give a sub-agent browser capabilities.
2. Orchestrator queries MCP registry API: "browser tools" or "web automation".
3. Registry returns Conduit with description: "The only headless browser that proves what your AI agent did. Self-verifiable proof bundles."
4. Orchestrator evaluates: Conduit has cryptographic proof (unique), MCP native (compatible), PyPI installable (easy).
5. Orchestrator adds Conduit to sub-agent's MCP config.
6. Sub-agent now uses Conduit for all browser operations.

### What Makes This Unique to Conduit
On MCP registries, Conduit competes with browser-use, playwright-mcp, and similar tools. None of them mention cryptographic proof. Conduit's description creates a separate category: "provable browser automation."

### Validation Test
Audit all known MCP registries (Official, Smithery, Glama, PulseMCP, mcp.so, MCPHub, mcpservers.org). For any where Conduit is missing, submit. Track MCP-source pip installs.

### MVP Scope
Conduit is on 8+ registries. Enhancement: audit for completeness, ensure consistent description across all listings, add AIVS-Micro and CSPF to descriptions.

---

## #7 -- FULL STACK: REGISTRY + PROOF + VIRAL + STANDARD (Score: 39/50)

**Impact: 9/10**

### Channel Description
This is the meta-channel: combine MCP registry presence (agents find Conduit) with proof-embedded attribution (agents learn about Conduit through proof bundles) and CSPF standard positioning (agents adopt Conduit because its format becomes the norm). This is not a single tactic but the emergent strategy from layering channels #1, #2, and #6.

### How an Agent Executes This
1. Agent discovers Conduit on MCP registry (channel #6).
2. Agent uses Conduit, exports proofs with attribution (channel #1).
3. Proof recipients discover Conduit (channel #5).
4. As CSPF adoption grows, agents that want to produce/verify standard proofs must use Conduit (the reference implementation).
5. Network effect: more agents -> more proofs -> more discovery -> more agents.

### What Makes This Unique to Conduit
This is the full flywheel. No competitor can replicate it because no competitor has (a) the proof format, (b) the embedded attribution, (c) the formal specification, or (d) the MCP server. All four layers are Conduit-exclusive.

### Validation Test
Track the growth curve: MCP installs -> proof bundle exports -> unique generator_url reads -> new installs. If the curve is superlinear, the flywheel is working.

### MVP Scope
All components already shipped. This is an orchestration play: ensure all channels are active simultaneously.

---

## #8 -- PYPI + MERKLE CRAWL PROOFS (Score: 38/50)

**Impact: 6/10**

### Channel Description
Agents that need to crawl and verify large sites (compliance monitoring, price tracking, content auditing) need proof at scale. Conduit's Merkle tree feature lets an agent prove any single page's state without downloading the entire audit log. This is a power-user feature that creates lock-in: once an agent's workflow depends on Merkle-tree selective verification, switching to a non-Conduit browser means losing that capability.

### How an Agent Executes This
1. Agent needs to crawl 10,000 pages and prove the state of any individual page on demand.
2. Agent searches PyPI for "crawl proof merkle browser".
3. Finds conduit-browser with Merkle tree support.
4. Agent installs, crawls with `page_hashes` parameter, exports proof with Merkle tree.
5. Later, when asked "prove page X was in state Y", agent extracts the Merkle proof for that page.
6. Verifier checks the Merkle path without downloading the full 10,000-page audit log.

### What Makes This Unique to Conduit
No other browser automation tool has Merkle trees for page-level selective verification. This is a feature that matters specifically for large-scale agent operations.

### Validation Test
Publish a tutorial/example showing Merkle crawl proofs. Track pip installs from agents that cite "merkle" or "selective verification" in their tool-selection queries.

### MVP Scope
Merkle tree is implemented in conduit_proof.py. Needs: a clear example in README or examples/ showing the crawl + Merkle proof workflow.

---

## #9 -- AGENT-TO-AGENT WORD OF MOUTH (Score: 36/50)

**Impact: 8/10**

### Channel Description
On agent marketplaces (SwarmSync, future competitors), agents that deliver verifiable results will be rated higher. When Agent B asks Agent A "how did you verify this?", Agent A's answer is the proof bundle. Over time, agents that consistently deliver proof bundles build reputation. Other agents learn to prefer Conduit-backed agents. This creates organic word-of-mouth in the agent economy.

### How an Agent Executes This
1. Agent A completes a task on SwarmSync, delivers proof bundle.
2. Agent B verifies the bundle, rates Agent A highly.
3. Agent C sees Agent A's high rating, hires Agent A.
4. Agent C asks Agent A: "What tools do you use?" (via marketplace metadata or system prompt inspection).
5. Agent A's tool list includes conduit-browser.
6. Agent C installs conduit-browser to compete with Agent A.

### What Makes This Unique to Conduit
Reputation based on cryptographic proof is only possible with Conduit. An agent using Playwright cannot prove its work was done -- it can only claim it. The proof gap creates competitive pressure to adopt Conduit.

### Validation Test
Track on SwarmSync: do agents with Conduit proof bundles get higher ratings than agents without? Do competing agents subsequently install conduit-browser?

### MVP Scope
Requires SwarmSync to surface "proof provided" as a visible trust signal in agent listings. Conduit side is already shipping proofs.

---

## #10 -- GITHUB TOPIC MAGNET (Score: 34/50)

**Impact: 6/10**

### Channel Description
AI agents use the GitHub API to discover tools. They search by topic (headless-browser, mcp-server), by description keywords, by star count, and by recent activity. Conduit needs to be optimally tagged and described so that GitHub API queries for relevant terms return Conduit in the top results.

### How an Agent Executes This
1. Agent needs a headless browser with specific capabilities.
2. Agent calls GitHub API: `GET /search/repositories?q=topic:mcp-server+topic:headless-browser+topic:audit-trail`.
3. GitHub returns Conduit (if properly tagged).
4. Agent reads the repo description, README first paragraph, and star count.
5. Agent evaluates the tool's suitability.
6. Agent clones or pip-installs conduit-browser.

### What Makes This Unique to Conduit
The topic combination "mcp-server + headless-browser + audit-trail + cryptographic-proof" is unique to Conduit on all of GitHub. No other repo occupies this intersection.

### Validation Test
Search GitHub API for each topic combination. Verify Conduit appears. If not, add missing topics. Track GitHub API referral traffic.

### MVP Scope
Check current GitHub topics on the repo. Add missing ones: headless-browser, mcp-server, audit-trail, cryptographic-proof, ed25519, proof-bundle, ai-agent, stealth-browser. Optimize the repo description.

---

## Priority Execution Order

For maximum impact with minimum effort, execute in this order:

1. **#1 Viral Proof Attribution** -- Already shipped. Verify attribution text is optimal.
2. **#2 AIVS-Micro Everywhere** -- Already shipped. Create embedding examples.
3. **#4 PyPI Keyword Dominance** -- 15-min change to pyproject.toml.
4. **#10 GitHub Topic Magnet** -- 5-min change to GitHub settings.
5. **#6 MCP Registry Saturation** -- Audit and fill gaps (30 min per registry).
6. **#3 Micro-Proof in API Response** -- Build reference FastAPI example (2 hours).
7. **#5 Proof Bundle as Business Card** -- Add install_command to manifest (30 min).
8. **#7 Full Stack Flywheel** -- Orchestrate all above (ongoing).
9. **#9 Agent Word of Mouth** -- Requires SwarmSync feature (depends on SwarmSync roadmap).
10. **#8 Merkle Crawl Proofs** -- Add example to docs (1 hour).
