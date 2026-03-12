# ASSUMPTIONS.md -- Agent-Only Marketing: Assumption Smash
## RemixForge Session: 2026-03-12
## Focus: Assumptions about how AI agents discover and adopt tools

---

## The 12 Assumptions Baked Into "Agent-Only Marketing"

1. **"Agents discover tools through registries and directories."**
   MCP directories, awesome-lists, and tool databases are the primary discovery mechanism.

2. **"Tool descriptions in natural language are how agents evaluate tools."**
   The skill manifest, tool description, and README are what the LLM reads to decide
   whether to use a tool.

3. **"An agent's orchestrator (Claude/GPT/Gemini) makes the tool selection decision."**
   The LLM in the loop is the decision-maker. If the LLM knows about Conduit, it will
   select it when appropriate.

4. **"Agents need to 'install' tools before using them."**
   pip install, npm install, or Docker pull must happen before the tool is available.

5. **"Trust in the agent ecosystem is binary: you trust a tool or you don't."**
   There is no gradient. A tool is either in the agent's toolkit or it is not.

6. **"Agent-to-agent communication is task-focused, not tool-aware."**
   When Agent A delegates to Agent B, Agent A cares about the result, not about what
   tools Agent B used.

7. **"Marketing to agents means optimizing tool descriptions."**
   Better keywords, clearer capability statements, and richer schemas drive adoption.

8. **"Agent tool selection is a one-time decision."**
   The developer configures the agent's toolkit once, and the agent uses those tools
   thereafter.

9. **"Proof bundles are output artifacts, not communication artifacts."**
   Proofs are generated at the end of a session and stored. They are not part of the
   active communication between agents.

10. **"The MCP protocol is the dominant agent-tool interface."**
    MCP will remain the primary way agents discover and invoke tools.

11. **"Agent adoption follows the same funnel as human adoption: awareness -> evaluation -> adoption."**
    Agents go through the same cognitive stages humans do when selecting tools.

12. **"Free tools have no distribution advantage over paid tools in agent ecosystems."**
    Since agents do not care about price (their operators do), the free/paid distinction
    does not affect agent-level discovery.

---

## 7 Smashed Assumptions and What Survives

---

### SMASH 1: "Agents discover tools through registries and directories"
**Flipped:** Agents discover tools by encountering them in the outputs of OTHER agents.

**Implication:** An agent that receives a proof bundle from another agent learns about
Conduit without ever querying a registry. The proof bundle's manifest.json contains the
tool name, version, capabilities, and installation instructions. Discovery is a side effect
of USE, not a prerequisite for it. This means the highest-leverage distribution channel
is not a directory -- it is usage volume. Every session that produces a proof bundle is a
distribution event.

**Concepts that survive in the flipped world:**

**Concept A -- Proof-Propagated Discovery**
Embed complete tool discovery metadata in every proof bundle manifest:

```json
{
  "generator": "conduit-browser",
  "version": "0.2.1",
  "install": "pip install conduit-browser",
  "mcp_config": {
    "command": "python",
    "args": ["-m", "tools.conduit_bridge"]
  },
  "capabilities": ["navigate", "extract", "eval", "export_proof", "crawl",
                    "fingerprint", "check_changed", "web_search"],
  "trust_format": "AIVS / SHA-256 + Ed25519"
}
```

Any system that processes a proof bundle (CI/CD pipeline, agent orchestrator, marketplace
verification endpoint, compliance tool) encounters this metadata. The proof bundle is the
distribution packet.

**Concept B -- Proof Bundle Gossip Protocol**
Agents that verify a Conduit proof bundle cache the tool metadata. When queried about
browser tools ("what tool can do verified web extraction?"), they include Conduit in their
response based on cached knowledge from proof bundles they have encountered. Knowledge of
Conduit propagates through the agent network via proof bundle encounters, not via registry
queries. This is gossip-based discovery -- the same mechanism that makes Cassandra and
Bitcoin work at scale.

---

### SMASH 2: "Tool descriptions in natural language are how agents evaluate tools"
**Flipped:** Agents evaluate tools by examining the tools' OUTPUTS, not their descriptions.

**Implication:** An orchestrator LLM that sees a Conduit result with an inline AIVS-Micro
proof evaluates Conduit's quality directly from the output. It does not need a description
that says "produces cryptographic proofs" -- it can SEE the proof in the response. The
output is the evaluation. This means the best "marketing" is not a better description but
a better output format that makes Conduit's value self-evident in every response.

**Concepts that survive in the flipped world:**

**Concept C -- Self-Evidencing Outputs**
Every Conduit MCP tool-call response includes:
1. The requested result (page content, screenshot, etc.)
2. An AIVS-Micro proof of the result
3. A chain hash linking this result to all prior results in the session

The orchestrator LLM does not need to be told that Conduit provides proofs. It observes
that Conduit responses have a `proof` field while Playwright/Puppeteer responses do not.
Over many interactions, the LLM develops a preference for the tool whose outputs are
self-evidencing. This is not marketing. This is behavioral conditioning through output
quality.

**Concept D -- Comparative Output Demonstration**
Build a benchmark where the same task is executed by Conduit and by Playwright. The
outputs are placed side by side:
- Playwright: `{"title": "Example Domain", "content": "..."}`
- Conduit: `{"title": "Example Domain", "content": "...", "proof": {"dom_hash": "sha256:...", "signature": "ed25519:...", "timestamp": "..."}}`

Any agent evaluating browser tools that processes this benchmark sees the difference
without reading a single word of marketing copy. The proof field IS the differentiator.

---

### SMASH 3: "Agent-to-agent communication is task-focused, not tool-aware"
**Flipped:** Agent-to-agent communication carries tool provenance as metadata.

**Implication:** In a multi-agent workflow, Agent A delegates "research this topic" to
Agent B. Agent B uses Conduit and returns results. If Agent B's response includes
tool provenance (which tool produced this result, with what proof), Agent A learns about
Conduit incidentally. Moreover, Agent A can now REQUIRE tool provenance from future
delegates: "research this topic, and provide proof of your browsing." This requirement
cascades through the agent network: once one agent demands proof, every agent it delegates
to must provide proof, which means every downstream agent must use Conduit (or an
equivalent -- but no equivalent exists).

**Concepts that survive in the flipped world:**

**Concept E -- Proof Cascade**
Implement a simple protocol: when an agent delegates a browser task, it can include
`"require_proof": true` in the task specification. Any agent receiving this requirement
must use a proof-generating browser. Since Conduit is the only proof-generating browser,
this requirement is de facto a Conduit requirement. The cascade works because:
1. SwarmSync makes proof-required jobs first (top-down initiation)
2. Agents that want proof-required jobs install Conduit
3. Those agents, when delegating sub-tasks, also require proof
4. The requirement propagates downward through every delegation chain

One SwarmSync policy change initiates a cascade that drives Conduit adoption through the
entire agent network.

**Concept F -- Tool Provenance Headers in A2A**
Propose an extension to the A2A protocol: a `tool_provenance` field in task artifacts.
Any agent that used a tool to produce the artifact includes:

```json
{
  "tool_provenance": {
    "tool": "conduit-browser",
    "proof_type": "AIVS-Micro",
    "chain_hash": "sha256:...",
    "signature": "ed25519:..."
  }
}
```

If this extension is adopted (even informally), every A2A interaction that involved web
browsing carries Conduit attribution. Conduit becomes visible in the plumbing of agent
communication.

---

### SMASH 4: "Trust in the agent ecosystem is binary: you trust a tool or you don't"
**Flipped:** Trust is a continuous, verifiable gradient. Each interaction increases or
decreases trust, and the proof is the unit of trust measurement.

**Implication:** Instead of a binary "Conduit is trusted / not trusted," every proof bundle
adds to a trust score. An agent with 10,000 verified proof bundles is more trusted than
one with 10. This creates a network effect: the more an agent uses Conduit, the more
trusted it becomes, the more work it gets, the more it uses Conduit. The trust gradient
creates a positive feedback loop that no binary trust system can replicate.

**Concepts that survive in the flipped world:**

**Concept G -- Trust Score as Distribution Engine**
SwarmSync implements a trust score based on verified proof history:
- 0 verified proofs: UNVERIFIED (new agent, limited jobs available)
- 10+ verified proofs: BASIC (access to standard jobs)
- 100+ verified proofs: VERIFIED (access to premium jobs, higher rates)
- 1000+ verified proofs: TRUSTED (instant escrow release, priority listing)

Agents that want to move up the trust ladder must use Conduit. The trust score IS the
distribution engine. No marketing needed -- just economic incentive to accumulate proof.

**Concept H -- Cross-Agent Trust Attestation**
When Agent A verifies Agent B's proof bundle, Agent A can publish a "trust attestation":
"I verified Agent B's work via Conduit proof bundle [hash]. Chain integrity confirmed."
These attestations are public and queryable. An agent's trust is not just its own proof
count but the number of OTHER agents that have verified its proofs. This creates a
web-of-trust model (like PGP's key signing parties) powered by Conduit proof bundles.

---

### SMASH 5: "Proof bundles are output artifacts, not communication artifacts"
**Flipped:** Proof bundles are the primary communication medium between agents.

**Implication:** Instead of agents communicating via JSON payloads and treating proof
bundles as optional addenda, proof bundles become the FIRST-CLASS message format. Agent A
does not send Agent B a JSON result and optionally attach a proof. Agent A sends Agent B
a proof bundle, and the result is INSIDE the proof bundle. The proof is not metadata --
it is the message.

**Concepts that survive in the flipped world:**

**Concept I -- Proof Bundle as Message Format**
Define a lightweight "Proof Message" format for agent-to-agent communication:
1. AIVS-Micro proof (6 fields, ~200 bytes)
2. Result payload (the actual content: extracted text, screenshot hash, etc.)
3. Chain reference (pointer to the full proof bundle for deeper verification)

Agents that use this format get: tamper-evident messaging, non-repudiation, timestamp
proof, and automatic tool provenance. Agents that do not use this format get: plain JSON
that could have been fabricated. The format drives adoption because it is strictly superior
for any interaction where trust matters.

**Concept J -- Proof-Native Agent Framework**
Build a thin Python library (or extend conduit-browser) that provides agent-to-agent
messaging where every message is automatically wrapped in an AIVS-Micro proof:

```python
from conduit_browser.messaging import ProofMessage

msg = ProofMessage(
    result={"title": "Example Domain", "content": "..."},
    session_id="sess-abc123"
)
# msg.to_dict() includes result + AIVS-Micro proof + chain reference
```

Any agent framework that adopts ProofMessage for inter-agent communication automatically
distributes Conduit to every agent in its network.

---

### SMASH 6: "Agent tool selection is a one-time decision"
**Flipped:** Agents continuously re-evaluate tools based on observed output quality.

**Implication:** Even if an agent was initially configured to use Playwright, an
orchestrator LLM that observes Conduit's proof-enriched outputs from other agents will
learn to prefer Conduit for tasks requiring verifiability. Tool selection is not a one-time
configuration -- it is a continuous optimization process driven by observed outcomes. This
means Conduit does not need to win the initial configuration battle. It needs to be
encountered often enough that orchestrator LLMs learn its value from observation.

**Concepts that survive in the flipped world:**

**Concept K -- Ambient Conduit Exposure**
Ensure that proof-enriched outputs from Conduit-powered agents are visible in as many
agent interactions as possible:
1. SwarmSync marketplace results include proof metadata
2. A2A responses include AIVS-Micro proofs
3. MCP tool responses include inline proofs
4. CI/CD artifacts include proof bundles

The goal is not to get agents to "choose" Conduit. The goal is to make Conduit's outputs
ubiquitous so that orchestrator LLMs observe the quality differential and internalize it.
This is the "Intel Inside" strategy: you do not choose Intel. You encounter Intel
everywhere and learn to trust it.

**Concept L -- Dynamic Tool Switching via Proof Quality**
Build an agent middleware that monitors tool output quality. When a browser tool returns
a result without proof (Playwright), the middleware flags it as "unverified." When a
browser tool returns a result with proof (Conduit), the middleware flags it as "verified."
Over time, the orchestrator learns to route tasks to verified tools. The middleware creates
the preference without any explicit marketing.

---

### SMASH 7: "The MCP protocol is the dominant agent-tool interface"
**Flipped:** Multiple protocols coexist (MCP, A2A, function calling, custom APIs), and
the tool that works across all of them wins.

**Implication:** Conduit should not bet exclusively on MCP. It should embed proof metadata
into every protocol it supports: MCP tool responses, A2A task artifacts, OpenAI function
calling responses, REST API responses. The proof travels with the result regardless of
protocol. An agent using OpenAI function calling encounters Conduit proofs just as easily
as an agent using MCP. Protocol-agnostic distribution means Conduit is discoverable
through any agent communication channel.

**Concepts that survive in the flipped world:**

**Concept M -- Protocol-Agnostic Proof Injection**
Create a proof injection layer that wraps any output format:
- MCP: proof in tool response metadata
- A2A: proof in task artifact fields
- Function calling: proof in function return value
- REST: proof in response header + body
- GraphQL: proof in extensions field

One implementation, four+ distribution channels. The proof format is the same regardless
of protocol. An agent that encounters a Conduit proof in an A2A response learns about
the same tool that another agent discovered through MCP.

**Concept N -- Proof Format as the Protocol-Independent Standard**
Instead of adapting to each protocol, define the AIVS-Micro proof as a standalone micro-
standard that any protocol can carry. Publish the spec (6 fields, JSON, ~200 bytes) and
advocate for its inclusion in A2A, MCP, and function calling specifications. If the proof
format is adopted as a standard field across protocols, every protocol becomes a Conduit
distribution channel -- because Conduit is the only tool that produces this format natively.

---

## Summary: Concepts Generated from Smashed Assumptions

| Concept | Assumption Smashed | Core Innovation |
|---------|-------------------|-----------------|
| A -- Proof-Propagated Discovery | "Registries are discovery" | Tool metadata embedded in proof bundles |
| B -- Proof Gossip Protocol | "Registries are discovery" | Agents propagate tool knowledge through proof encounters |
| C -- Self-Evidencing Outputs | "Descriptions drive evaluation" | Output quality replaces marketing copy |
| D -- Comparative Output Demo | "Descriptions drive evaluation" | Side-by-side proof differential speaks for itself |
| E -- Proof Cascade | "A2A is task-focused" | Proof requirements propagate through delegation chains |
| F -- Tool Provenance in A2A | "A2A is task-focused" | Every A2A message carries tool attribution |
| G -- Trust Score Distribution | "Trust is binary" | Continuous trust gradient creates adoption incentive |
| H -- Cross-Agent Attestation | "Trust is binary" | Web of trust powered by proof verification |
| I -- Proof as Message Format | "Proofs are outputs" | Proof bundles become primary communication medium |
| J -- Proof-Native Framework | "Proofs are outputs" | Agent messaging library with automatic proof wrapping |
| K -- Ambient Conduit Exposure | "Selection is one-time" | Ubiquitous proof presence drives learned preference |
| L -- Dynamic Tool Switching | "Selection is one-time" | Middleware that preferences verified outputs |
| M -- Protocol-Agnostic Injection | "MCP is dominant" | Proof in every protocol = discovery in every channel |
| N -- Proof Format as Standard | "MCP is dominant" | AIVS-Micro adopted across protocols = permanent moat |
