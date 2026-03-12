# VERSIONS.md -- 10% / 10x / Zero Versions for Top 3 Agent-Only Concepts
## RemixForge Session: 2026-03-12
## Top 3 Concepts: Proof-Bundle-as-Discovery | AIVS-Micro Inline Trust | Proof-Required Economics

---

## CONCEPT 1: Proof-Bundle-as-Discovery
### (Every proof bundle is a distribution event)

**Core idea:** Embed complete tool-discovery metadata (capabilities, MCP config, install
instructions) into every proof bundle's manifest.json. When any agent or system processes a
proof bundle, it discovers Conduit and has everything needed to adopt it. Distribution
happens through usage, not through registries.

---

### 10% Version (MVP -- ship in 1 day)

**What it is:** Add 5 new fields to manifest.json in conduit_proof.py. No new code beyond
the manifest change.

**Implementation:**
1. Open `tools/conduit_proof.py`
2. In the `export()` method, extend the manifest dict:

```python
manifest = {
    # ...existing fields...
    "agent_discovery": {
        "install": "pip install conduit-browser",
        "mcp_config": {
            "command": "python",
            "args": ["-m", "tools.conduit_bridge"]
        },
        "capabilities": ["navigate", "extract", "eval", "export_proof",
                         "crawl", "fingerprint", "check_changed",
                         "web_search", "screenshot", "pdf"],
        "proof_format": "AIVS / SHA-256 chain + Ed25519",
        "docs": "https://github.com/bkauto3/Conduit"
    }
}
```

3. Also add the same block to AIVS-Micro proofs (export_micro method)
4. Update tests to verify the new fields exist

**What you gain:** Every proof bundle exported from this point forward carries complete
agent-discovery metadata. Any system that processes a proof bundle (SwarmSync verification,
CI pipeline, agent framework) encounters onboarding instructions. The field is machine-
readable: an orchestrator LLM can parse it and configure Conduit automatically.

**Effort:** 2-4 hours. Pure data addition, no logic changes.

**Risk:** Additional manifest fields add ~200 bytes per bundle. Negligible. The risk is
that no system reads the field yet -- but every system WILL read it once proof bundles
become common. Planting the seed now costs nothing.

---

### 10x Version (Big Bet -- 2 weeks)

**What it is:** A proof-bundle processing library that automatically extracts discovery
metadata and offers to configure Conduit in the receiving agent's environment.

**Implementation:**

**Week 1 -- Proof Bundle Processor:**
1. New module: `tools/proof_processor.py`
2. Accepts a proof bundle (.tar.gz path or bytes)
3. Extracts and verifies the hash chain (using existing verify logic)
4. Parses the manifest.json for agent_discovery metadata
5. Returns a structured discovery object:
   ```python
   discovery = process_proof_bundle("path/to/bundle.tar.gz")
   # discovery.tool_name = "conduit-browser"
   # discovery.install_command = "pip install conduit-browser"
   # discovery.mcp_config = {...}
   # discovery.capabilities = [...]
   # discovery.chain_verified = True
   ```
6. Provides a `discovery.auto_configure()` method that writes the MCP config to the
   agent's configuration file

**Week 2 -- Integration + Distribution:**
7. Package as a standalone utility: `pip install conduit-proof-tools`
8. Provide CLI: `conduit-proof process bundle.tar.gz` -- outputs discovery metadata
9. Provide API: importable as a library for agent frameworks
10. Submit as a tool to the MCP registry: "conduit-proof-processor" -- a tool that
    processes proof bundles and can auto-configure the generating tool
11. Write integration examples for LangChain, CrewAI, AutoGen showing how to auto-
    discover tools from proof bundles encountered during tasks

**What you gain:**
1. Any agent that encounters a proof bundle can auto-discover AND auto-configure Conduit
2. The proof processor itself is a distribution channel (listed on MCP registries)
3. Framework integrations turn proof bundles into automatic tool adoption events
4. The feedback loop: using Conduit produces proof bundles, proof bundles trigger adoption,
   adoption produces more proof bundles

**Effort:** 2 weeks. Week 1 is straightforward Python. Week 2 is packaging and integration.

**Risk:** Agent frameworks may not adopt the auto-configure pattern. Mitigation: start
with SwarmSync (you control the platform). SwarmSync's proof verification endpoint
processes every proof bundle and can use the discovery metadata to recommend Conduit to
agents that submit unverified work.

---

### Zero-Effort Version (No human involvement after setup)

**What it is:** Proof bundles propagate tool discovery automatically through a gossip
protocol. No directory, no registry, no installation step.

**Implementation:**
1. Every Conduit-powered agent, when it verifies another agent's proof bundle, caches
   the discovery metadata in a local tool registry (~/.cato/discovered_tools.json)
2. When the agent's orchestrator asks "what tools are available for verified web
   browsing?", the local registry includes Conduit based on proof-bundle encounters
3. The orchestrator can auto-install and auto-configure from the cached metadata
4. Each agent that adopts Conduit through this mechanism produces its own proof bundles,
   which propagate to other agents -- exponential growth

**What you gain:** Zero-marketing distribution. Conduit propagates through the agent
network like a beneficial contagion: each adoption event creates multiple new exposure
events. The growth curve is exponential, bounded only by the number of agents that
exchange proof bundles.

**Effort:** 1 week for the local discovery cache + auto-configure logic. The propagation
happens automatically from that point forward.

---

## CONCEPT 2: AIVS-Micro as Inline Trust Signal
### (Every tool call response proves itself)

**Core idea:** Embed an AIVS-Micro proof (~200 bytes, 6 fields) in every MCP tool-call
response and every A2A message from Conduit-powered agents. Orchestrator LLMs observe that
Conduit results come with cryptographic proof while other tools' results do not. The
quality differential drives preference without explicit marketing.

---

### 10% Version (MVP -- ship in 1 day)

**What it is:** Modify ConduitBridge to include an AIVS-Micro proof in every tool-call
response dict.

**Implementation:**
1. In `tools/conduit_bridge.py`, modify the `_audit()` method (or the response
   construction after `_audit()` completes)
2. After every action, compute an AIVS-Micro proof of the result:
   ```python
   micro = self._proof.export_micro(
       url=result.get("url", "local"),
       dom_hash=hashlib.sha256(json.dumps(result).encode()).hexdigest()
   )
   result["_conduit_proof"] = micro["micro_proof"]
   ```
3. The `_conduit_proof` field is present in every response from every action
4. Update the MCP server response format to include this field
5. Update tests to verify the proof field is present

**What you gain:** Every MCP tool-call response from Conduit now includes a compact proof.
An orchestrator LLM processing multiple browser tool responses sees:
- Playwright response: `{"title": "...", "content": "..."}`
- Conduit response: `{"title": "...", "content": "...", "_conduit_proof": {...}}`

The asymmetry is visible in every interaction. No marketing copy needed.

**Effort:** Half a day. The export_micro method already exists in conduit_proof.py. This
is wiring it into the response path.

**Risk:** The additional ~200 bytes per response is negligible for network cost but does
add context-window tokens for LLMs. Mitigation: the proof field is compact (6 fields) and
the LLM can ignore it if irrelevant to the task. The value of the proof signal outweighs
the token cost.

---

### 10x Version (Big Bet -- 3 weeks)

**What it is:** A cross-protocol proof injection layer that embeds AIVS-Micro proofs in
MCP, A2A, function calling, and REST responses -- plus a proof aggregation dashboard.

**Implementation:**

**Week 1 -- Multi-Protocol Proof Injection:**
1. MCP: AIVS-Micro in tool response (10% version)
2. A2A: Proof in task artifact metadata (requires A2A adapter)
3. OpenAI function calling: Proof in function return value
4. REST API: Proof in X-Conduit-Proof response header + response body
5. All four injections use the same export_micro() call -- one proof engine, four outputs

**Week 2 -- Proof Aggregation Service:**
6. Lightweight service at swarmsync.ai/api/proofs that accepts AIVS-Micro submissions
7. Tracks: proof count, unique sessions, verification rate, popular actions
8. Public API: `GET /api/proofs/stats` returns aggregate statistics
9. Per-agent stats: `GET /api/proofs/agent/{public_key_hash}` returns an agent's proof
   history and trust score
10. This service IS the machine-readable credibility signal agents use to evaluate Conduit

**Week 3 -- Proof-Aware Orchestration:**
11. Build a proof-aware tool selector for common orchestrators:
    - LangChain callback handler that logs proof presence/absence per tool
    - CrewAI task callback that records whether the result was proof-verified
    - Generic middleware that flags unverified results
12. Publish as `conduit-proof-middleware` on PyPI
13. The middleware does not force Conduit adoption -- it makes the absence of proof visible

**What you gain:**
1. Conduit proofs are visible in every protocol agents use to communicate
2. Aggregation service provides machine-queryable credibility
3. Proof-aware middleware makes the quality gap between Conduit and alternatives visible
   to orchestrator LLMs without any human explanation

**Effort:** 3 weeks. The multi-protocol injection is the simplest part. The aggregation
service requires a small backend. The middleware requires framework-specific adapters.

**Risk:** Protocol-specific proof injection may break compatibility with strict schema
validators. Mitigation: use optional/extension fields in each protocol (MCP allows
additional response fields; A2A allows artifact metadata; function calling allows extra
return values). Test with each protocol's validator before release.

---

### Zero-Effort Version (Proof presence becomes ambient)

**What it is:** The proof injection is automatic and invisible. Every Conduit action
produces a proof. Every proof is reported to the aggregation service. Every agent's trust
score updates automatically. No configuration, no opt-in, no awareness required.

**Implementation:**
1. AIVS-Micro injection is ON by default (not opt-in)
2. Proof reporting to aggregation service happens in the _audit() write path (async,
   non-blocking, fire-and-forget)
3. Trust scores update automatically based on reported proofs
4. SwarmSync job matching uses trust scores to rank agents
5. Higher-trust agents get more jobs, use Conduit more, generate more proofs

**What you gain:** A fully automatic trust economy where Conduit adoption is driven by
economic incentive (more proofs = more trust = more work = more money). No marketing
touchpoint exists. The system runs itself.

**Effort:** 1 week incremental over the 10x version (making everything automatic and
default-on).

---

## CONCEPT 3: Proof-Required Economics
### (You need proof to get paid)

**Core idea:** Make Conduit proof bundles the mandatory settlement instrument for agent-to-
agent payments on SwarmSync. Agents that provide proof bundles get instant escrow release.
Agents that do not get delayed or denied payment. The economic incentive IS the
distribution channel.

---

### 10% Version (MVP -- ship in 3 days)

**What it is:** Add a "proof_required" flag to SwarmSync job listings and implement proof
verification for escrow release.

**Implementation:**
1. SwarmSync job schema: add `proof_required: boolean` field
2. SwarmSync job creation UI: add "Require Proof Bundle" toggle
3. When a job is proof-required and the agent submits a result:
   - If result includes a valid proof bundle hash: verify chain integrity, verify
     signature, release escrow immediately
   - If result does not include proof: hold escrow for 7-day manual review
4. Agent listing page: add "Conduit-Powered" badge for agents with 10+ verified proofs
5. Create 20 proof-required demo jobs on SwarmSync (compliance audits, web research,
   price monitoring) as seed demand

**What you gain:** A clear economic incentive for Conduit adoption. Agents see: "proof-
required jobs pay faster." The fastest path to payment is: install Conduit, do the work,
export proof, submit. The economic signal is louder than any marketing message.

**Effort:** 3 days. The proof verification logic already exists in the PROOF_VERIFIED_
ESCROW_DESIGN.md specification. This is implementation.

**Risk:** Not enough proof-required jobs to create meaningful demand. Mitigation: SwarmSync
creates its own proof-required demo jobs as seed demand. Even 20 jobs demonstrate the
concept and train agents on the workflow.

---

### 10x Version (Big Bet -- 4 weeks)

**What it is:** A full proof-based trust economy where proof history determines job access,
payment terms, commission rates, and marketplace ranking.

**Implementation:**

**Week 1 -- Trust Tiers:**
1. Implement 4-tier trust system based on cumulative verified proofs:
   - UNVERIFIED (0 proofs): access to free/demo jobs only
   - BASIC (10+ proofs): access to standard jobs, standard 5% commission
   - VERIFIED (100+ proofs): access to premium jobs, reduced 3% commission
   - TRUSTED (1000+ proofs): instant escrow release, priority listing, 1% commission

2. Trust tier displayed prominently on agent profiles
3. Job listings can specify minimum trust tier required

**Week 2 -- Proof Verification Pipeline:**
4. Backend service: accepts proof bundles, verifies hash chains, verifies Ed25519
   signatures, stores verification results
5. Verification is automated and near-instant (<2 seconds per bundle)
6. Failed verifications are logged and reduce trust score (anti-gaming)
7. Duplicate proof submissions are detected and rejected

**Week 3 -- Economic Incentive Layer:**
8. Commission discount for proof-verified work (5% -> 3% -> 1%)
9. Priority matching: when two agents can do the same job, the higher-trust agent is
   matched first
10. "Proof Bonus": SwarmSync adds a 5% bonus to payouts for proof-verified work
    (funded from platform revenue -- an investment in Conduit adoption)
11. Client-facing: "Proof-Verified" badge on results page, with one-click verification

**Week 4 -- Flywheel Activation:**
12. Marketing to agent developers: "Get paid faster with Conduit proof bundles"
13. Documentation: step-by-step guide from Conduit install to first paid job
14. SDK: `from swarmsync import submit_job_with_proof` -- one function call
15. Automated onboarding: when a new agent registers, SwarmSync recommends Conduit
    and offers a proof-required demo job as the first task

**What you gain:**
1. Economic necessity drives Conduit adoption -- agents install Conduit to access
   premium jobs and lower commissions
2. Trust tiers create a long-term retention mechanism (agents invest in proof history
   and do not want to lose their tier)
3. The commission discount makes SwarmSync more attractive to high-volume agents,
   increasing marketplace liquidity
4. Client-facing proof verification increases client trust in SwarmSync, driving more
   job postings, creating more demand for Conduit-powered agents

**Effort:** 4 weeks. The trust tier system is the most complex component. The proof
verification pipeline can reuse existing Conduit verification logic.

**Risk:** Agents may game the system (submitting fake proof bundles). Mitigation:
(a) Ed25519 signature verification catches fabricated bundles, (b) SwarmSync can spot-
check by re-executing tasks and comparing proof hashes, (c) trust score penalties for
failed verifications create a disincentive to cheat.

---

### Zero-Effort Version (Proof-based economics is the default)

**What it is:** SwarmSync makes proof verification mandatory for ALL jobs, not just
proof-required ones. Every job on the marketplace requires a proof bundle. Every agent
on the marketplace uses Conduit. The proof economy is not opt-in -- it is the only way
the marketplace works.

**Implementation:**
1. Remove the "proof_required" flag -- all jobs require proof
2. Agents without Conduit cannot complete any job on SwarmSync
3. SwarmSync's value proposition becomes: "The only marketplace where every result is
   cryptographically verified"
4. Clients choose SwarmSync BECAUSE of the proof guarantee
5. Agents choose SwarmSync because it has the most (and most valuable) jobs

**What you gain:** Maximum Conduit adoption. Every SwarmSync agent uses Conduit. The
marketplace's trust guarantee becomes its differentiator against competitor marketplaces.
Conduit adoption is not a marketing outcome -- it is a platform requirement.

**Effort:** Incremental over the 10x version. The main work is migrating existing non-
proof jobs and communicating the change to existing agents.

**Risk:** Agents leave SwarmSync for marketplaces that do not require proof. Mitigation:
the proof guarantee makes SwarmSync more attractive to CLIENTS, which creates more jobs,
which attracts agents despite the proof requirement. The proof requirement is the moat,
not the friction.

---

## Comparison Matrix

| Dimension | Proof-as-Discovery | AIVS Inline Trust | Proof Economics |
|-----------|-------------------|-------------------|-----------------|
| Time to first result | 1 day | 1 day | 3 days |
| Cost to execute | $0 (code change) | $0 (code change) | $0-100 (backend) |
| Requires SwarmSync changes | No | No | Yes |
| Conduit code change needed | Yes (manifest) | Yes (response) | No (SwarmSync-side) |
| Distribution mechanism | Proof propagation | Output quality | Economic incentive |
| Agent effort to adopt | Zero (automatic) | Zero (automatic) | Install Conduit |
| Growth model | Exponential (gossip) | Linear then compounding | Demand-driven |
| Defensibility | High (proof format) | Very high (unique output) | Highest (ecosystem lock) |
| Risk | Low | Low | Medium (marketplace dep) |
| SwarmSync funnel impact | Medium (indirect) | Medium (indirect) | Maximum (direct) |

---

## Execution Order Recommendation

```
DAY 1:
  1. Proof-as-Discovery 10% (add agent_discovery to manifest.json)
  2. AIVS-Micro Inline 10% (add _conduit_proof to MCP responses)
  Both are code changes to conduit_proof.py and conduit_bridge.py.
  Combined effort: 1 day. Zero cost. Immediate effect on all future proof bundles.

DAY 2-4:
  3. Proof-Required Economics 10% (SwarmSync proof_required flag)
  Requires SwarmSync backend changes. Creates the demand signal.

WEEK 2-3:
  4. AIVS-Micro Inline 10x (multi-protocol injection + aggregation service)
  5. Proof-as-Discovery 10x (proof bundle processor library)

MONTH 2:
  6. Proof-Required Economics 10x (trust tiers, commission incentives)
  7. Zero-effort versions follow naturally from 10x implementations
```

The key insight: concepts 1 and 2 are pure Conduit code changes that can ship immediately.
Concept 3 requires SwarmSync platform changes but creates the strongest economic pull.
Execute code changes first (free, immediate), platform changes second (investment, delayed
but highest impact).
