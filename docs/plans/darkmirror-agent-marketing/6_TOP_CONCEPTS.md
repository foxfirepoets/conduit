# TOP_CONCEPTS.md -- 5 Best Agent-Only Marketing Concepts for Conduit
# DarkMirror Session 2 | 2026-03-12

---

## Preamble

The first DarkMirror session (2026-03-11) generated human-facing
distribution concepts: Cold Proof Outbound, Self-Evidencing Launch,
Proof-Backed Ecosystem, CPBS Standard, Trust Accelerator.

This session generates AGENT-FACING distribution concepts. The question
is not "how do humans discover Conduit?" but "how do AGENTS discover,
evaluate, and adopt Conduit?" These are strategies for a world where
the primary customer is software that reads registries, evaluates
capabilities, and makes tool selection decisions programmatically.

The five concepts below are ordered by execution difficulty (easiest
first). Each names the concept, describes the mechanism, explains why
only Conduit can do it, and estimates impact.

---

## CONCEPT 1: AIVS-Micro Viral Signatures

### One-Liner
Every agent output carries a 200-byte cryptographic micro-proof that
other agents can verify, and verification leads to Conduit discovery.

### Mechanism (The Transfer)
Email signature virality. Every email from a Hotmail user in the 1990s
contained "Get your free email at Hotmail." Every output from a
Conduit-backed agent contains a verifiable AIVS-Micro signature.
But unlike a text footer, this signature is cryptographically useful --
it proves the work was done.

### How It Works
1. Agent uses Conduit (directly or via audit proxy) to do browser work.
2. Conduit appends an AIVS-Micro proof to the agent's output:
   ```json
   {
     "aivs_micro": {
       "url": "https://example.com",
       "content_hash": "a3f9...",
       "timestamp": 1741564800,
       "session_id": "sess-abc123",
       "action_count": 47,
       "signature": "base64..."
     }
   }
   ```
3. When Agent B receives this output, it sees the micro-proof.
4. Agent B (or its operator) can verify the proof in microseconds
   using the CPBS verifier.
5. Agent B's framework documentation explains AIVS-Micro. The
   documentation links to Conduit.
6. Agent B adopts Conduit. Its outputs now carry micro-proofs.
   The cycle repeats.

### Why Only Conduit Can Do This
No other headless browser generates cryptographic attestations at
the per-action level. Playwright cannot append a verifiable signature
to its output because it does not have a signing identity, a hash
chain, or a proof format. The AIVS-Micro signature is a capability
unique to Conduit's architecture.

### Impact Estimate
**HIGH.** Every agent-to-agent interaction where output carries a
micro-proof is a Conduit touchpoint. If 100 agents use Conduit and
each produces 10 outputs/day, that is 1,000 micro-proof impressions
daily. Each impression is a verifiable product demonstration. The
growth is proportional to transaction volume in agent economies.

### MVP in 1 Week
1. AIVS-Micro already exists in conduit_proof.py.
2. Build a simple wrapper: `conduit.sign_output(result)` that appends
   an AIVS-Micro block to any dictionary.
3. Build `cpbs-verifier` standalone package (Python only for MVP).
4. Document the micro-proof format in a machine-readable spec.
5. Test: Agent A produces micro-signed output. Agent B verifies it
   using cpbs-verifier without Conduit installed.

### First Validation Test
Generate 50 micro-signed outputs from a Conduit agent. Send them to
5 different agent frameworks (LangChain, CrewAI, AutoGen, custom).
Measure: can the receiving agent verify the proof? Does verification
work without Conduit installed? If yes for 4/5 frameworks, the viral
mechanism is viable.

---

## CONCEPT 2: Conduit Audit Proxy (The Cloudflare Play)

### One-Liner
An MCP middleware that adds Conduit's audit trail to ANY existing
browser tool -- zero migration, zero code changes.

### Mechanism (The Transfer)
Cloudflare sits in front of web servers and adds security, caching,
and analytics without replacing the server. The Conduit Audit Proxy
sits in front of browser MCP servers and adds audit trails without
replacing the browser.

### How It Works
1. Agent operator installs `conduit-audit-proxy` via pip.
2. In MCP config, instead of pointing directly to Playwright's MCP
   server, they point to the audit proxy, which forwards to Playwright:
   ```json
   {
     "mcpServers": {
       "browser": {
         "command": "conduit-audit-proxy",
         "args": ["--backend", "playwright-mcp"]
       }
     }
   }
   ```
3. Every browser action flows through the proxy. The proxy:
   - Forwards the command to the backend browser tool
   - Writes the action + result to Conduit's audit chain
   - Optionally generates AIVS-Micro proofs per action
   - Returns the result to the agent unchanged
4. The agent gets its preferred browser. It also gets audit trails.
5. At any point, the operator can run `conduit export-proof` to get
   a full proof bundle of everything the browser did.

### Why Only Conduit Can Do This
Conduit's two-layer write path (billing + audit chain) is designed
to record actions atomically. The audit proxy is a natural extension
of this architecture. No competitor has the signing infrastructure,
the hash chain, or the proof export capability to offer this as a
transparent middleware.

### Impact Estimate
**VERY HIGH.** This removes the primary adoption barrier: "I would
have to switch from Playwright." With the audit proxy, agents do not
switch. They add. This is the wedge that gets Conduit into
environments that have already standardized on another browser tool.
Once the audit proxy is installed, the path to full Conduit adoption
is short because the operator is already seeing proof bundles.

### MVP in 1 Week
1. Build `conduit-audit-proxy` as a Python MCP server that accepts
   browser commands and forwards them via subprocess to a configurable
   backend MCP server.
2. Intercept responses and write to Conduit's audit chain.
3. Support `export_proof` action on the proxy itself.
4. Test with Playwright's MCP server as the backend.
5. Publish to PyPI.

### First Validation Test
Set up Claude Code with the audit proxy in front of Playwright's
MCP server. Run 10 browser tasks. Verify: (a) all tasks succeed
with identical results to direct Playwright, (b) the audit chain
captures all 10 actions, (c) the proof bundle exports and verifies.
If all three pass, the proxy is viable.

---

## CONCEPT 3: Specialized Sub-Tool MCP Listings (Surface Area Expansion)

### One-Liner
Instead of one "conduit-browser" listing, expose 5-7 task-specific
MCP tools that agents can discover independently based on their need.

### Mechanism (The Transfer)
AWS does not sell "cloud computing." It sells S3 (storage), Lambda
(functions), RDS (databases), SQS (queues). Each service is
discoverable independently. Each solves a specific problem. The
surface area of discovery is proportional to the number of services.

### How It Works
Conduit registers multiple MCP tool endpoints:

1. **conduit/browse-and-prove** -- Navigate, interact, export proof.
   Discovered by agents searching for "browser with audit trail."

2. **conduit/compliance-audit** -- Automated checks (HTTPS, cookies,
   privacy policy, accessibility). Export proof of findings.
   Discovered by agents searching for "compliance" or "audit."

3. **conduit/change-monitor** -- Fingerprint pages, detect mutations,
   alert with proof. Discovered by agents searching for "monitoring."

4. **conduit/site-mapper** -- BFS crawl with Merkle proof tree.
   Discovered by agents searching for "crawl" or "site map."

5. **conduit/js-delta** -- Static vs rendered DOM diff with proof.
   Discovered by agents searching for "javascript rendering" or
   "DOM analysis."

6. **conduit/evidence-capture** -- Screenshot + content + proof
   bundle for legal/insurance use. Discovered by agents searching
   for "evidence" or "forensic."

Each tool has its own MCP schema, its own description optimized for
that use case, and its own examples. They all share the same
underlying Conduit engine.

### Why Only Conduit Can Do This
Playwright could theoretically register multiple tool endpoints, but
it has nothing unique to differentiate them. Each Conduit sub-tool
offers something no other browser tool can: cryptographic proof of
the specific task performed. The sub-tools are not just marketing
surface area -- they are genuinely differentiated capabilities.

### Impact Estimate
**HIGH.** This multiplies Conduit's discoverability by 5-7x. An
agent searching for "compliance audit tool" would never find a
generic "headless browser." It WILL find "conduit/compliance-audit."
The specialized listings match agent queries more precisely.

### MVP in 1 Week
1. Define 5 sub-tool schemas (JSON Schema for inputs/outputs).
2. Register them as separate tools in Conduit's MCP server.
3. Write specialized descriptions for each (Stripe-style: what,
   why-different, example, output, verify).
4. Test: search the MCP registry for "compliance", "monitoring",
   "crawl", "evidence", "DOM diff". Verify Conduit sub-tools
   appear in results.
5. Update the Official MCP Registry listing.

### First Validation Test
After registering sub-tools, monitor MCP registry analytics (if
available) for 30 days. Measure: which sub-tool gets the most
discovery hits? If "compliance-audit" or "change-monitor" gets
more discovery than the generic "conduit-browser" listing, the
surface area expansion strategy works.

---

## CONCEPT 4: Recipe Packages as Dependency-Graph Distribution

### One-Liner
Build 3 standalone pip packages that solve real agent problems and
pull conduit-browser as a transitive dependency.

### Mechanism (The Transfer)
Express.js does not market itself to every Node developer. It gets
installed because 50,000 packages depend on it. The dependency
graph IS the distribution channel.

### How It Works
Build and publish three recipe packages:

**Package 1: conduit-compliance-checker**
- `pip install conduit-compliance-checker`
- Input: URL
- Output: Compliance report (HTTPS, cookies, privacy, accessibility)
  with proof bundle
- Depends on: conduit-browser
- Target: compliance teams, GRC agents, audit workflows

**Package 2: conduit-price-monitor**
- `pip install conduit-price-monitor`
- Input: URL + CSS selector for price element
- Output: Price change alerts with cryptographic proof of the change
- Depends on: conduit-browser
- Target: e-commerce agents, competitive intelligence, procurement

**Package 3: conduit-evidence-collector**
- `pip install conduit-evidence-collector`
- Input: URL + capture parameters
- Output: Evidence package (screenshot, DOM, content, proof bundle)
  suitable for legal/insurance submission
- Depends on: conduit-browser
- Target: legal tech agents, insurance agents, IP monitoring

Each package solves a problem INDEPENDENTLY. An agent searching for
"price monitoring" finds conduit-price-monitor. It installs. It gets
conduit-browser as a dependency. Now the agent produces proof bundles.
The problem-solving layer pulls the infrastructure layer into the
environment.

### Why Only Conduit Can Do This
These recipe packages are not just wrappers around a browser. They
produce PROOF-BACKED RESULTS. A price monitor that can prove the
price changed is fundamentally more valuable than one that just
claims it. The proof is the differentiator that makes these recipes
better than alternatives -- and the proof requires Conduit.

### Impact Estimate
**VERY HIGH over time.** Each recipe package has its own discovery
surface on PyPI. Each targets a different audience. The compound
effect: 3 audiences discovering Conduit through 3 entry points,
each pulling conduit-browser via dependency resolution. As recipes
grow, Conduit's install base grows proportionally.

### MVP in 1 Week
1. Build conduit-compliance-checker (the simplest recipe):
   - Navigate to URL
   - Check HTTPS, cookie banner, privacy policy link, meta tags
   - Generate compliance report + proof bundle
   - Return structured JSON results
2. Publish to PyPI.
3. Write a one-paragraph description targeting "website compliance
   audit with cryptographic proof."
4. Test: `pip install conduit-compliance-checker` in a clean venv.
   Run on 5 URLs. Verify results are useful and proof bundles verify.
5. Share in compliance and agent forums.

### First Validation Test
Track PyPI download counts for conduit-compliance-checker over 30
days. If it gets >100 installs (each pulling conduit-browser as
a dependency), the transitive distribution model works. If <10,
the recipe does not solve a compelling enough problem.

---

## CONCEPT 5: Trust-Aware Capability Protocol (The Standard Play)

### One-Liner
Propose a machine-readable schema for agent tool capability
advertisement that includes trust properties -- and make Conduit
the only tool that can fully populate it.

### Mechanism (The Transfer)
Schema.org became the standard vocabulary for web content because
Google used it for rich search results. Tools that adopted Schema.org
got better search rankings. The incentive drove adoption. The
adoption made Schema.org the standard.

Conduit proposes a "trust properties" extension to MCP tool
capability descriptions. Tools that populate trust properties get
preferred by agents doing trust-sensitive work. The incentive drives
adoption. Conduit is the only tool that can fully populate the schema
today.

### How It Works
1. Define `trust_properties` schema for MCP tool descriptions:
   ```json
   {
     "trust_properties": {
       "audit_chain": {
         "algorithm": "SHA-256",
         "tamper_evident": true
       },
       "signing": {
         "algorithm": "Ed25519",
         "identity_bound": true
       },
       "proof_export": {
         "format": "CPBS-v1",
         "self_verifiable": true,
         "zero_dependency_verify": true
       },
       "micro_attestation": {
         "format": "AIVS-Micro",
         "bytes_per_proof": 200
       }
     }
   }
   ```
2. Publish as a proposed extension to the MCP specification.
3. Implement in Conduit's MCP server registration.
4. Propose to MCP protocol maintainers for inclusion.
5. Build agent-side logic: "for trust-sensitive tasks, prefer tools
   with populated trust_properties."

### Why Only Conduit Can Do This
Conduit is the only browser tool with audit chains, signing, proof
export, and micro-attestations. Competitors would populate the
`trust_properties` schema with `null` for every field. The schema
makes Conduit's advantage MACHINE-READABLE. An agent that checks
trust_properties will see Conduit as the only viable option for
audited browser work. The schema does not just describe capabilities
-- it creates a competitive dimension where Conduit has no competitors.

### Impact Estimate
**VERY HIGH but long-horizon.** If the MCP protocol adopts trust
properties, every tool in the ecosystem is compared on trust
dimensions where Conduit wins. This is the Let's Encrypt endgame:
the standard carries the brand. The adoption timeline is 6-12
months for protocol acceptance, but the payoff is ecosystem-level
competitive advantage.

### MVP in 1 Week
1. Write the trust_properties JSON Schema spec (1 page).
2. Implement in Conduit's MCP server: populate trust_properties
   in the tool registration response.
3. Write a proof-of-concept agent that reads trust_properties
   from two MCP servers (Conduit and Playwright) and routes
   a compliance task to the tool with audit capabilities.
4. Document the behavior: "Agent automatically chose Conduit for
   the compliance task because it has trust_properties.audit_chain."
5. Publish spec + demo as a GitHub Discussion or RFC.

### First Validation Test
Share the trust_properties spec with 3 MCP ecosystem stakeholders
(registry maintainers, framework developers, tool authors). Measure:
does at least 1 express interest in supporting or adopting the
schema? If yes, the standard has traction. If zero engagement, the
ecosystem is not ready for trust-layer differentiation yet.

---

## Summary Table

| # | Concept | Transfer Source | MVP Effort | Impact | Timeline |
|---|---------|---------------|------------|--------|----------|
| 1 | AIVS-Micro Viral Signatures | Hotmail email footers | LOW | HIGH | Immediate |
| 2 | Conduit Audit Proxy | Cloudflare CDN | MEDIUM | VERY HIGH | 1-2 weeks |
| 3 | Specialized Sub-Tool Listings | AWS service catalog | LOW | HIGH | 1 week |
| 4 | Recipe Package Distribution | npm dependency graph | MEDIUM | VERY HIGH | 2-4 weeks |
| 5 | Trust-Aware Capability Protocol | Schema.org | HIGH | VERY HIGH | 6-12 months |

---

## Execution Order (Agent-Only Marketing)

**WEEK 1:** Concepts 1 + 3 (AIVS-Micro signatures + Sub-tool listings)
- Lowest effort, highest immediate visibility
- Sub-tools multiply registry discoverability NOW
- AIVS-Micro starts the viral signature mechanism
- Both build on existing code (conduit_proof.py already has AIVS-Micro)

**WEEK 2:** Concept 2 (Audit Proxy)
- Removes the biggest adoption barrier ("I use Playwright")
- Requires the sub-tools to be registered first (Week 1)
- The proxy can advertise itself as each sub-tool capability

**WEEK 3-4:** Concept 4 (Recipe Packages)
- Requires stable Conduit core (Weeks 1-2 solidify it)
- Each recipe package = new PyPI surface area
- compliance-checker first (strongest product-market fit)

**WEEK 5+:** Concept 5 (Trust Protocol)
- Requires proof of traction (Weeks 1-4 generate adoption data)
- Spec proposal is more credible with real usage numbers
- Long-horizon play that compounds all previous work

---

## The Architecture of Agent-Only Marketing

Human marketing: attention --> interest --> trial --> conversion
Agent marketing: discovery --> capability match --> integration --> dependency

Conduit's agent marketing strategy addresses each stage:

1. **Discovery:** Sub-tool listings (Concept 3) multiply the surface
   area where agents find Conduit in registries.

2. **Capability match:** Trust-aware protocol (Concept 5) makes
   Conduit's unique capabilities machine-readable, so agents
   searching for audit/trust features find an exact match.

3. **Integration:** Audit proxy (Concept 2) makes integration
   frictionless -- zero migration from existing tools.

4. **Dependency:** Recipe packages (Concept 4) make Conduit a
   transitive dependency pulled in by problem-solving packages.

5. **Viral distribution:** AIVS-Micro signatures (Concept 1) make
   every agent output a Conduit touchpoint that propagates through
   agent-to-agent interactions.

The five concepts are not five independent ideas. They are five
layers of a single distribution architecture for agent-only marketing.

---

## The One Sentence (Agent Edition)

In a world where agents choose tools by reading structured metadata,
the tool with the richest, most verifiable, most widely-distributed
metadata wins -- and Conduit is the only tool whose output IS
verifiable metadata.

---
