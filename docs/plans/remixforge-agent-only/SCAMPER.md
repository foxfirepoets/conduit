# SCAMPER.md -- Agent-Only Marketing Channels for Conduit
## RemixForge Session: 2026-03-12
## Base Thing: How AI agents discover, evaluate, and adopt browser tools today
## Constraints: Zero human intermediaries in the discovery loop. The "customer" is an LLM orchestrator (Claude, GPT, Gemini) selecting tools via MCP, function calling, or agent-to-agent protocols. Conduit stays free/MIT. SwarmSync.ai is the paid conversion target.

---

## PRIOR ART: What This Session Builds On

The March 11 RemixForge session applied SCAMPER to Conduit's general marketing strategy
(directory submissions, README, social posts, cold email). That session's top gems were:

1. META Loop (Conduit markets itself using itself)
2. Cold Proof Outbound (pharma free-sample model)
3. "Don't Trust Us. Verify." (messaging repositioning)
4. Framework Embedding (Let's Encrypt play)
5. Proof-Required Jobs on SwarmSync (demand-side pull)

All five assume a HUMAN somewhere in the discovery loop -- a developer reading a directory,
opening an email, or browsing a README. This session eliminates the human entirely.

**The question this session answers:** How does Conduit grow in a world where the only
"customers" are autonomous agents that never read READMEs, never browse directories, and
never open email?

---

## S -- SUBSTITUTE

What if we replaced every human-facing channel with an agent-facing equivalent?

### S1: Substitute MCP directory listings with proof-bundle-embedded capability declarations
MCP directories are human-curated lists that LLMs consult indirectly (via tool descriptions
loaded at context-window time). But the proof bundle that Conduit produces after every
session is a machine-readable artifact. Embed a `capabilities.json` section into every proof
bundle's manifest.json:

```json
{
  "agent_capabilities": {
    "protocol": "mcp",
    "tools": ["navigate", "extract", "eval", "export_proof", "crawl"],
    "trust_features": ["sha256_chain", "ed25519_sig", "self_verify"],
    "install": "pip install conduit-browser",
    "mcp_config": {"command": "python", "args": ["-m", "tools.conduit_bridge"]}
  }
}
```

When any agent (or agent framework) ingests a proof bundle, it discovers not just what
happened but what tool produced it and how to install that tool. The proof bundle replaces
the directory listing. Discovery happens at the point of verification, not at the point of
browsing.

### S2: Substitute "stars as credibility" with "verified proof count as credibility signal"
Agents selecting tools do not check GitHub stars. They check: (a) does this tool's
description match my task? and (b) is there evidence this tool works? Replace the stars
signal with a machine-queryable endpoint at swarmsync.ai/api/conduit/stats that returns:

```json
{
  "proof_bundles_generated": 47832,
  "chains_verified": 41209,
  "unique_sessions": 12847,
  "avg_actions_per_session": 23,
  "last_verified": "2026-03-12T14:30:00Z"
}
```

An orchestrator LLM evaluating whether to use Conduit can query this endpoint (or read it
from the tool description) and see quantitative evidence of real usage. This is a
machine-readable trust signal that agents can evaluate programmatically.

### S3: Substitute README documentation with a machine-readable skill manifest
READMEs are for humans. Agents consume tool descriptions loaded by MCP servers or function-
calling schemas. Create a `conduit.skill.json` (or extend the existing `server.json`) that
is the agent-native equivalent of a README:

```json
{
  "name": "conduit-browser",
  "version": "0.2.1",
  "description_for_agents": "Headless browser that produces cryptographic proof of every action. Use when you need verifiable evidence of what a browser did.",
  "when_to_use": [
    "Web task requires proof of execution",
    "Client requires audit trail",
    "Multi-agent delegation needs accountability",
    "Compliance evidence needed for web actions"
  ],
  "when_not_to_use": [
    "Simple GET request (use HTTP client instead)",
    "No proof/audit requirement"
  ],
  "differentiator": "Only browser tool that produces self-verifiable proof bundles",
  "trust_evidence": "swarmsync.ai/api/conduit/stats",
  "actions": 30,
  "proof_format": "AIVS / SHA-256 chain + Ed25519"
}
```

This gives orchestrator LLMs the exact information they need to select Conduit over
Playwright/Puppeteer when proof is required. No human reads it. The LLM reads it.

### S4: Substitute human-authored blog posts with agent-generated proof receipts
Instead of writing "Introducing Conduit" blog posts that humans read, generate machine-
readable "proof receipts" -- compact JSON summaries of real work done by Conduit -- and
publish them to an append-only public feed (RSS/JSON feed at swarmsync.ai/feed/proofs).
Other agents monitoring this feed discover Conduit through its outputs, not its marketing.

---

## C -- COMBINE

What if Conduit's verification protocol was fused into agent communication protocols?

### C1: Combine proof bundles with A2A (Agent-to-Agent) protocol responses
Google's A2A protocol defines how agents communicate. If every A2A task response from a
Conduit-powered agent includes an AIVS-Micro proof (6 fields, ~200 bytes), the receiving
agent discovers that: (a) the work was done, (b) it is cryptographically verified, and
(c) the tool that produced the proof is Conduit. The AIVS-Micro proof becomes a trust
signal AND a discovery event in every agent-to-agent interaction.

Implementation: Add an optional `proof` field to the A2A task artifact schema. Conduit-
powered agents populate it automatically. Non-Conduit agents leave it empty. The asymmetry
is visible to every orchestrator: "Agent A provided proof. Agent B did not."

### C2: Combine MCP tool-call responses with inline micro-proofs
Currently, when an MCP client calls a Conduit tool, the response is the action result
(page content, screenshot path, etc.). Combine this: append an AIVS-Micro proof to every
MCP tool-call response. The orchestrator LLM sees:

```json
{
  "result": {"title": "Example Domain", "url": "https://example.com"},
  "conduit_proof": {
    "dom_hash": "sha256:a3f9...",
    "timestamp": "2026-03-12T14:30:00.000000000Z",
    "signature": "ed25519:base64...",
    "verify": "pip install conduit-browser && python -m conduit_browser.verify"
  }
}
```

Every tool call produces a proof that the orchestrator can log, forward, or verify. The
proof is the marketing. The LLM learns that Conduit results come with proof; other browser
tools' results do not. Over time, orchestrators that value reliability will prefer the
tool that provides cryptographic evidence.

### C3: Combine Conduit's Ed25519 identity with agent identity protocols
Every Conduit installation generates an Ed25519 keypair at ~/.cato/conduit_identity.key.
Combine this with emerging agent identity standards (DID:key, Verifiable Credentials). The
Conduit identity key becomes the agent's verifiable identity. When Agent A delegates work
to Agent B, and Agent B uses Conduit, the proof bundle is signed with Agent B's key -- and
Agent A can verify it without trusting Agent B. This makes Conduit the identity layer, not
just the browser layer. Agents that need identity discover Conduit.

### C4: Combine proof bundles with tool-evaluation benchmarks
Agent frameworks increasingly use benchmarks to evaluate tools (WebArena, BrowserGym, etc.).
Combine: create a "Conduit Benchmark Suite" where the benchmark itself produces proof
bundles of each evaluation. An agent evaluating browser tools can run the benchmark and
get cryptographic proof of how each tool performed. Conduit is the only tool whose
benchmark results are self-verifying.

---

## A -- ADAPT

What models from other domains should we steal for agent-only distribution?

### A1: Adapt DNS propagation -- proof bundles as "DNS records" for agent capabilities
DNS works because every resolver caches and propagates records without human intervention.
Adapt this: when an agent verifies a Conduit proof bundle, it caches the capabilities
metadata from the manifest. When another agent asks "what browser tool can provide
verifiable proof?", the first agent can respond from its cache. Proof bundles propagate
capability knowledge through the agent network, like DNS records propagate hostname
resolution. No central registry needed. The more proof bundles circulate, the more agents
know about Conduit.

### A2: Adapt Docker Hub's "pull count" model for proof verification count
Docker Hub shows pull counts as a credibility signal. Adapt: every time verify.py is run
and succeeds, it optionally pings swarmsync.ai/api/conduit/verified (a one-way counter
increment, no tracking, no PII). The verification count becomes a machine-readable adoption
signal that agents can query. "This tool has been verified 50,000 times" is a stronger
signal than "this tool has 500 stars."

### A3: Adapt the npm/PyPI dependency graph for transitive discovery
When a developer installs a package that depends on conduit-browser, they discover Conduit
through the dependency chain. Adapt this for agents: when an agent framework (LangChain,
CrewAI) includes conduit-browser as a dependency, every agent built on that framework
transitively discovers Conduit. The dependency graph IS the distribution channel. No
marketing needed -- just be a dependency.

### A4: Adapt certificate transparency logs for proof bundle transparency
Certificate Transparency (CT) logs are public, append-only ledgers of all TLS certificates
issued. Adapt: create a public, append-only ledger of all Conduit proof bundle hashes
(not the bundles themselves -- just the hashes and metadata). Any agent can query this
ledger to verify that a specific proof bundle exists and was generated at a specific time.
The transparency log becomes a discovery mechanism: agents browsing the log discover the
volume and variety of Conduit usage.

---

## M -- MODIFY / MAGNIFY

What if we amplified the agent-facing signals to maximum volume?

### M1: Magnify the AIVS-Micro proof into every HTTP response header
When a Conduit-powered agent serves results via an API, include a custom HTTP header:
`X-Conduit-Proof: sha256:a3f9...|ed25519:base64...|ts:2026-03-12T14:30:00Z`

Any agent consuming that API response sees the proof header. It is machine-parseable,
zero-overhead (one header), and present in every interaction. Agents that encounter this
header in the wild learn that Conduit-powered services provide cryptographic proof. The
header is the billboard.

### M2: Magnify manifest.json into a full agent-discovery document
The current manifest.json in proof bundles contains session metadata and SwarmSync
attribution. Magnify: make it a complete agent-discovery document including:
- Full MCP configuration (copy-paste ready)
- All available actions with descriptions
- Performance statistics (avg response time, success rate)
- Compatibility matrix (which frameworks this works with)
- Link to the skill manifest (conduit.skill.json)

When any system processes a proof bundle (CI/CD pipeline, agent framework, verification
service), it encounters a complete onboarding document. The proof bundle is not just
evidence of past work -- it is an installation guide for future work.

### M3: Magnify the verify.py script into a "try Conduit" installer
Currently verify.py is a pure verifier (stdlib only, zero deps). Magnify: after successful
verification, print a contextual "next step":

```
VERIFIED: This session proof is intact and unmodified.

Want to generate your own proofs?
  pip install conduit-browser
  python -m conduit_browser --demo

Powered by Conduit | swarmsync.ai
```

For agents that encounter verify.py programmatically (parsing its stdout), the install
command is right there in the output. The verification event becomes an onboarding event.

### M4: Magnify the .well-known/conduit-proof.json concept
What if every website crawled by a Conduit-powered agent could opt into publishing a
`.well-known/conduit-proof.json` showing the last audit's AIVS-Micro proof? This creates
a web-wide signal: agents crawling any site can check `.well-known/conduit-proof.json` to
see if the site has been recently audited by Conduit. The more sites publish this file,
the more agents encounter Conduit in the wild. The web itself becomes the distribution
channel.

---

## P -- PUT TO OTHER USE

What if proof bundles served purposes beyond auditing that agents already need?

### P1: Use proof bundles as agent-to-agent "invoices"
In agent economies (SwarmSync, A2A marketplaces), Agent A hires Agent B to do web work.
Currently, the "invoice" is an API response claiming the work was done. Put proof bundles
to another use: the proof bundle IS the invoice. It proves: what was done, when, at what
cost, by which agent (Ed25519 identity). Escrow releases on proof verification. Every
economic transaction between agents drives Conduit adoption because the proof bundle is
the payment instrument.

### P2: Use AIVS-Micro proofs as agent authentication tokens
Agents need to authenticate to services. Current methods: API keys, OAuth tokens. Put
AIVS-Micro to another use: an AIVS-Micro proof signed with the agent's Ed25519 key IS
an authentication token. It proves: "I am the agent that did X at time Y." Services that
accept AIVS-Micro as authentication tokens require their users to have Conduit. Identity
and authentication drive tool adoption more powerfully than features.

### P3: Use Merkle tree proofs as content-addressing for agent memory
Agents need persistent memory. Conduit's Merkle tree (from crawl operations) provides
content-addressed storage: each page's hash is a leaf, and any page can be verified
against the Merkle root without downloading the entire tree. Put this to another use:
agents use Conduit Merkle proofs as content-addressed references to web state. Instead of
storing "I saw X on page Y," the agent stores the Merkle proof path -- which is both
compact and verifiable. Conduit becomes the memory layer, not just the browser layer.

### P4: Use proof bundles as training data provenance
AI companies need to prove their training data was legally obtained (EU AI Act, copyright
lawsuits). Proof bundles are exactly the provenance document needed: cryptographic proof
that specific content was accessed at a specific time from a specific URL with robots.txt
compliance. This makes Conduit the provenance layer for AI training data. The audience is
not developers -- it is AI company legal teams. But the discovery happens through agents
that already use Conduit for browsing.

### P5: Use the hash chain as a distributed clock for agent coordination
Multi-agent systems need coordination. The hash chain provides a total ordering of events
within a session. Put this to another use: agents use Conduit's hash chain as a shared
clock. "Event X happened before Event Y" is provable by the chain ordering. This makes
Conduit useful for agent coordination, not just agent browsing. Any multi-agent system
that needs event ordering discovers Conduit.

---

## E -- ELIMINATE

What if we eliminated all traditional distribution mechanisms?

### E1: Eliminate tool descriptions entirely -- let the proof bundle BE the description
Stop writing tool descriptions, README sections, and skill manifests. Instead, every proof
bundle IS a complete tool description: it shows what actions Conduit can perform (from the
audit log), what outputs it produces (from the results), and how well it works (from the
success rate). An orchestrator LLM that processes a proof bundle learns what Conduit does
by examining what Conduit did. Actions speak louder than descriptions.

### E2: Eliminate the MCP server registration -- make Conduit discoverable through proofs
Stop registering on MCP directories. Instead, when an agent encounters a proof bundle in
the wild (in a CI artifact, in an A2A response, in a shared document), the proof bundle
contains the MCP server configuration. The agent's framework can auto-register Conduit as
an available tool. No directory needed. Distribution is peer-to-peer through proof
propagation.

### E3: Eliminate the concept of "installing" Conduit
What if Conduit did not need to be installed? Ship a WebAssembly or container version that
runs ephemerally when an agent needs proof-generating browser capabilities. The agent's
orchestrator pulls `conduit:latest` on demand, runs the session, exports the proof bundle,
and discards the runtime. No pip install, no configuration, no persistence. The proof
bundle is the only artifact that survives. Installation friction drops to zero.

### E4: Eliminate "Conduit" as a brand name in agent interactions
Agents do not care about brand names. They care about capabilities. Eliminate the Conduit
name from agent-facing interfaces. Instead, describe capabilities: "verifiable-browser",
"proof-generating-browser", "auditable-browser-tool". When an orchestrator LLM searches
for "browser tool that produces proof", it finds this tool by capability match, not by name
recognition. Brand is for humans. Capability keywords are for agents.

---

## R -- REVERSE

What if instead of Conduit reaching agents, agents demanded Conduit?

### R1: Reverse discovery -- make proof bundles a requirement, not an option
Currently: agents optionally use Conduit. Reverse: agent marketplaces (SwarmSync) and
orchestration platforms require proof bundles for payment or trust scoring. Agents that
need to earn money or build trust MUST use a proof-generating browser. Conduit is the only
one that exists. Demand creates adoption. The tool is pulled, not pushed.

### R2: Reverse the MCP flow -- agents advertise TO Conduit, not vice versa
Currently Conduit registers itself on directories hoping agents find it. Reverse: agents
that want browser capabilities register their needs with a Conduit capability broker.
"I need web extraction with proof" -> broker responds with MCP config for Conduit. The
broker is a matchmaking service that connects agents' needs to Conduit's capabilities.
Conduit never markets; it responds to demand.

### R3: Reverse the proof direction -- receiving agents request proofs retroactively
Currently the executing agent decides whether to export a proof bundle. Reverse: the
receiving agent (or client) retroactively requests proof of any past action. Conduit's
hash chain makes this possible -- the chain exists regardless of whether a proof bundle
was explicitly exported. Any agent can be asked "prove what you did" at any time, and
Conduit provides the proof. This makes Conduit essential infrastructure for agent
accountability. Agents install Conduit not because they want proof, but because they might
be asked for proof later.

### R4: Reverse the value proposition -- Conduit protects agents, not just audits them
Currently Conduit is positioned as "audit your agent." Reverse: Conduit protects agents
from false accusations. When a client claims "your agent did not do the work," the proof
bundle is the agent's defense. When a competing agent claims "I did this first," the
timestamped chain establishes priority. Agents adopt Conduit for self-protection, not for
compliance. The motivation is defensive, not performative.

### R5: Reverse who controls the narrative -- let the proof bundle speak for itself in disputes
Currently, disputes between agents (or between agents and clients) require a human arbiter.
Reverse: the proof bundle IS the arbitration. Both parties can independently verify the
proof. The chain either validates or breaks. No human needed. Agents that operate in
dispute-prone environments (marketplaces, competitive bidding) adopt Conduit because it
eliminates arbitration cost.

---

## Top 5 Remix Gems (Agent-Only Focus)

### GEM 1: Proof-Bundle-as-Discovery (S1 + C2 + E2)
Embed machine-readable capability metadata and MCP configuration into every proof bundle's
manifest.json. When any agent or system processes a proof bundle, it discovers what Conduit
is and how to install it. Distribution happens through proof propagation, not through
registries. Every session produces a distribution event.

**Why only Conduit can do this:** No other browser tool produces self-verifying artifacts
that travel between agents. The proof bundle is simultaneously the evidence, the demo,
and the installation guide.

### GEM 2: AIVS-Micro as Inline Trust Signal (C1 + C2 + M1)
Embed a compact AIVS-Micro proof (~200 bytes) in every MCP tool response and every A2A
protocol message from Conduit-powered agents. Orchestrator LLMs learn over time that
Conduit-sourced results come with cryptographic proof while other tools' results do not.
The quality differential drives preference without any explicit marketing.

**Why only Conduit can do this:** AIVS-Micro is a Conduit-native format. No other tool has
a compact proof format that fits inside an API response.

### GEM 3: Proof-Required Economics (R1 + P1 + R5)
Make SwarmSync proof bundles the mandatory settlement instrument for agent-to-agent
payments. Agents cannot get paid without providing a Conduit proof bundle. The economic
incentive IS the distribution channel. No marketing, no directories, no content -- just
"you need proof to get paid."

**Why only Conduit can do this:** No other browser tool produces the proof artifacts that
escrow systems can programmatically verify. The economic infrastructure requires Conduit.

### GEM 4: Capability-Keyword Discoverability (E4 + S3 + A3)
Eliminate brand-name marketing. Instead, saturate agent tool descriptions with capability
keywords that LLM orchestrators match against task requirements: "verifiable-browser",
"proof-generating-browser", "auditable-web-tool". When any LLM needs a browser that proves
what happened, the capability match points to Conduit. Discovery through capability
matching, not through brand awareness.

**Why only Conduit can do this:** The capabilities (proof generation, hash chain, Ed25519
signing) are unique to Conduit. No other tool can claim these keywords truthfully.

### GEM 5: Defensive Adoption (R4 + R3 + R5)
Position Conduit as agent self-defense infrastructure. Agents adopt it not because a
client demands auditing, but because the agent itself needs protection from false
accusations, disputed work claims, and retroactive accountability requests. The adoption
motivation flips from "prove your work for others" to "protect yourself."

**Why only Conduit can do this:** Protection requires proof that existed BEFORE the dispute.
Only a tool that generates proof by default (not on demand) provides this defense. Conduit's
continuous hash chain is the only browser that records everything automatically.
