# SHORTLIST.md -- Agent-Only Marketing: Final Ranked Concepts
## RemixForge Session: 2026-03-12
## Ranked by: effort-to-value ratio, differentiation, feasibility, defensibility
## Constraint: Zero human intermediaries. The "customer" is an LLM orchestrator or autonomous agent.

---

## How This Differs From the Prior RemixForge (March 11)

The March 11 session generated 5 marketing strategies. All 5 assume a human somewhere in
the loop: a developer reading a README, a compliance officer opening an email, a framework
maintainer merging a PR. The strategies are excellent for human-mediated distribution.

This session eliminates the human. The 5 concepts below work in a world where:
- No human reads the README
- No human browses a directory
- No human opens an email
- No human merges a PR

Instead, LLM orchestrators select tools programmatically, agents delegate to agents via
protocols, and economic incentives drive adoption through marketplace mechanics. The
distribution channels are: proof bundle propagation, inline trust signals, protocol
metadata, capability matching, and economic necessity.

**The thesis:** In the agent economy, the tool that embeds trust signals into its outputs
wins -- because the outputs travel further than any marketing campaign.

---

## RANK 1: AIVS-Micro Inline Trust Signal

**Differentiator statement:** Every Conduit tool-call response includes a compact
cryptographic proof (~200 bytes) that no other browser tool provides. Orchestrator LLMs
observe the asymmetry over time: Conduit results prove themselves; competitors' results
require faith. The quality differential drives preference without any explicit marketing.

**One-feature wedge:** Add a `_conduit_proof` field (AIVS-Micro: 6 fields) to every MCP
tool response from ConduitBridge.

**Why this is the highest-ranked concept:**
This is the most direct path to agent preference. It requires no external infrastructure,
no marketplace changes, no protocol standards work. It is a code change to conduit_bridge.py
that ships today and affects every interaction from this point forward. The mechanism is
behavioristic: orchestrator LLMs learn preferences from observed output patterns, not from
marketing messages. Conduit trains LLMs to prefer it through the structure of its outputs.

No competitor can replicate this because no competitor has a proof format. Adding "proof"
to Playwright would require rebuilding their architecture around a hash chain -- which is
Conduit's core design, not an add-on feature.

**MVP scope (half a day):**
1. In `conduit_bridge.py`, after each `_audit()` call, compute AIVS-Micro proof of the result
2. Attach as `_conduit_proof` field to the response dict
3. The proof includes: dom_hash, timestamp, signature, scanner_version_hash, url, scan_origin
4. Update test suite to verify proof field presence

```python
# In conduit_bridge.py, after _audit():
if self._proof:
    micro = self._proof.export_micro(
        url=result.get("url", ""),
        dom_hash=hashlib.sha256(
            json.dumps(result, sort_keys=True).encode()
        ).hexdigest()
    )
    if micro.get("success"):
        result["_conduit_proof"] = micro["micro_proof"]
```

**Expansion path:**
- Day 2: Add proof field to A2A adapter (if/when A2A integration exists)
- Week 2: Add X-Conduit-Proof HTTP header for REST API responses
- Week 3: Build proof aggregation service (swarmsync.ai/api/proofs)
- Month 2: Publish AIVS-Micro as a standalone micro-standard
- Month 3: Submit AIVS-Micro as an extension to MCP and A2A protocols

**Risks:**
- Orchestrator LLMs may ignore the proof field. Mitigation: even if ignored in the LLM's
  reasoning, the proof field appears in logged outputs, which humans review. Hybrid
  discovery: agents encounter proof through outputs, humans notice it in logs.
- Extra tokens in context window. Mitigation: 6 fields, ~200 bytes, ~50 tokens. Negligible
  compared to page content or screenshot data.
- Proof field may confuse schema validators. Mitigation: prefix with underscore
  (`_conduit_proof`) to signal optional/extension field.

**First validation test:** Enable AIVS-Micro in responses. Run 100 MCP tool calls through
Claude Code. Check: does Claude reference or acknowledge the proof field in any of its
reasoning? Does it mention proof availability when comparing to other browser tools?
Target: proof field referenced in 10%+ of multi-tool comparison scenarios.

**Success metric:** Within 60 days, observe at least one LLM orchestrator (Claude, GPT,
Gemini) spontaneously citing Conduit's proof capability as a selection criterion when
multiple browser tools are available.

---

## RANK 2: Proof-Bundle-as-Discovery

**Differentiator statement:** Every proof bundle Conduit exports contains complete tool-
discovery metadata: capabilities, MCP configuration, install instructions, and ecosystem
links. When any agent, pipeline, or system processes a proof bundle, it discovers Conduit
without querying any registry. Distribution happens through usage, not through marketing.

**One-feature wedge:** Add an `agent_discovery` block to manifest.json in every proof
bundle.

**Why this ranks second:**
This concept has the widest distribution potential because proof bundles travel further
than tool descriptions. A tool description stays in a registry. A proof bundle travels
with the work product: attached to CI artifacts, embedded in compliance reports, forwarded
between agents, stored in audit archives. Each of these destinations is a discovery
opportunity. The compound effect over time is exponential: more usage produces more bundles,
more bundles create more discovery, more discovery drives more usage.

It ranks below AIVS-Micro Inline because the inline proof is encountered during active
tool use (real-time), while proof bundle discovery happens after the fact (batch). Real-time
signals create faster feedback loops.

**MVP scope (2-4 hours):**
1. In `conduit_proof.py`, extend the manifest dict in `export()`:

```python
manifest["agent_discovery"] = {
    "tool": "conduit-browser",
    "install": "pip install conduit-browser",
    "mcp_config": {
        "command": "python",
        "args": ["-m", "tools.conduit_bridge"]
    },
    "capabilities": [a for a in self._get_action_list()],
    "proof_format": "AIVS / SHA-256 chain + Ed25519",
    "source": "https://github.com/bkauto3/Conduit",
    "marketplace": "https://swarmsync.ai"
}
```

2. Also add a minimal version to AIVS-Micro proofs:
```python
micro_proof["agent_discovery"] = {
    "tool": "conduit-browser",
    "install": "pip install conduit-browser",
    "source": "https://github.com/bkauto3/Conduit"
}
```

3. Update tests to verify agent_discovery fields exist in proof bundles

**Expansion path:**
- Week 2: Build proof-bundle processor library (conduit-proof-tools on PyPI)
- Week 3: Add auto-configure logic that reads discovery metadata and writes MCP config
- Month 2: Implement gossip-based discovery cache in agent framework
- Month 3: Submit proof-bundle processor as an MCP tool itself

**Risks:**
- No system currently reads agent_discovery metadata from proof bundles. Mitigation: this
  is seed infrastructure. SwarmSync's proof verification endpoint will be the first reader.
  Framework integrations will be the second. The metadata costs nothing to include now and
  pays off as proof bundle processing becomes common.
- The metadata format may need to evolve. Mitigation: include a `schema_version: 1` field
  to support forward-compatible changes.

**First validation test:** Export 10 proof bundles with agent_discovery metadata. Manually
verify that the metadata is parseable and contains all necessary information for a
hypothetical auto-configure system. Send one proof bundle to a colleague and ask them to
configure Conduit using only the information in the proof bundle (no README). Measure:
time-to-configure, success rate.

**Success metric:** Within 90 days, at least one external system (CI pipeline, agent
framework, or verification service) reads agent_discovery metadata from Conduit proof
bundles and uses it for tool discovery or configuration.

---

## RANK 3: Proof-Required Economics

**Differentiator statement:** On SwarmSync, jobs that require proof bundles release escrow
instantly. Jobs without proof hold escrow for days. Agents that produce verified proofs earn
faster, access premium jobs, and pay lower commissions. The economic incentive to use
Conduit is stronger than any marketing message.

**One-feature wedge:** A `proof_required: true` flag on SwarmSync job listings with
differential escrow release timing.

**Why this ranks third (not first):**
This concept has the strongest pull force -- economic necessity is the most powerful
distribution mechanism. It ranks third because it requires SwarmSync platform changes (not
just Conduit code changes), and its effectiveness depends on SwarmSync having enough
liquidity (jobs and agents) to make the economic incentive meaningful. Concepts 1 and 2
can ship today with Conduit code changes alone. Concept 3 requires platform investment.

However, once implemented, this concept creates the strongest lock-in and the hardest-to-
replicate moat. A competitor would need to build both a proof system AND a marketplace to
replicate this -- a years-long effort.

**MVP scope (3-5 days, requires SwarmSync backend access):**
1. Add `proof_required` boolean to SwarmSync job listing schema
2. Add "Require Proof Bundle" toggle to job creation UI
3. Proof verification endpoint: accepts proof bundle, verifies hash chain + signature
4. If job is proof-required and valid proof submitted: release escrow immediately
5. If job is proof-required and no valid proof: hold escrow for 7-day review
6. Add "Conduit-Powered" badge to agent profiles with 5+ verified proofs
7. Seed: create 20 proof-required demo jobs on SwarmSync

**Expansion path:**
- Week 2: Trust tier system (UNVERIFIED/BASIC/VERIFIED/TRUSTED)
- Week 3: Commission discounts for higher trust tiers (5%/3%/1%)
- Month 2: Priority job matching based on trust score
- Month 3: All jobs default to proof-required (opt-out, not opt-in)
- Month 6: Proof requirement becomes mandatory -- the marketplace only works with proof

**Risks:**
- Insufficient SwarmSync liquidity. Mitigation: create seed jobs. Even 20 proof-required
  jobs demonstrate the concept and train the first cohort of Conduit-adopting agents.
- Agents resist the proof requirement. Mitigation: frame as "get paid faster" not "do
  extra work." The proof bundle is one additional action (export_proof) at end of session.
  The time-to-payment reduction more than compensates.
- Proof verification has false negatives. Mitigation: the verification logic is
  deterministic (hash chain + signature). False negatives occur only from corrupted
  bundles, which is a real error (not a false negative). Provide clear error messages
  and retry instructions.

**First validation test:** Create 10 proof-required jobs on SwarmSync. Run the compliance
auditor agent against them with Conduit proof export. Measure: verification success rate
(target: 100%), time from submission to escrow release (target: <5 seconds), end-to-end
experience quality.

**Success metric:** Within 90 days, 50+ unique agents have submitted valid Conduit proof
bundles to SwarmSync. 200+ proof-required jobs have been completed. At least 20 agents
moved from UNVERIFIED to BASIC trust tier.

---

## RANK 4: Capability-Keyword Discoverability

**Differentiator statement:** Strip brand-name marketing from agent-facing interfaces.
Replace "Conduit" with capability keywords: "verifiable-browser",
"proof-generating-browser", "auditable-web-tool". When an LLM orchestrator needs a
browser that proves what happened, capability matching points to this tool -- regardless
of whether the LLM has ever heard the name "Conduit."

**One-feature wedge:** Rewrite the MCP tool description in server.json and
skills/conduit.md to lead with capabilities, not brand name.

**Why this ranks fourth:**
This is the lowest-effort, most immediately actionable concept for improving agent
discovery. LLM orchestrators select tools by matching task requirements against tool
descriptions. If the description says "Conduit headless browser," the LLM matches on
"headless browser." If the description says "verifiable browser that produces cryptographic
proof of every action, including SHA-256 hash chains, Ed25519 signatures, and self-
verifiable proof bundles," the LLM matches on "proof," "verifiable," "cryptographic,"
"audit" -- keywords that no competitor claims.

It ranks below the top 3 because it is a description optimization (incremental) rather
than a structural advantage (exponential). But it costs nothing and can be done today.

**MVP scope (1-2 hours):**
1. Rewrite skills/conduit.md description to lead with capabilities:

Current: "Conduit is a headless browser with a cryptographic audit layer."

Proposed: "A headless browser that produces cryptographic proof of every action.
Use when you need: verifiable web evidence, tamper-evident audit trails, Ed25519-signed
session proofs, self-verifiable proof bundles. Actions include: navigate, extract, eval
(with full JS source in audit chain), crawl (robots.txt compliant), export_proof
(self-verifiable .tar.gz bundle). Every action is recorded in a SHA-256 hash chain."

2. Add a `capabilities` field to server.json:
```json
{
  "capabilities": [
    "cryptographic-audit-trail",
    "proof-bundle-generation",
    "self-verifiable-evidence",
    "ed25519-signed-sessions",
    "tamper-evident-hash-chain",
    "js-source-in-audit",
    "stealth-browsing",
    "robots-txt-compliant"
  ]
}
```

3. Ensure the Official MCP Registry description matches

**Expansion path:**
- Week 2: A/B test different capability keyword sets to see which drive more tool selection
- Week 3: Add "when_to_use" and "when_not_to_use" fields to skill manifest
- Month 2: Track which capability keywords appear in LLM reasoning when selecting Conduit
- Month 3: Optimize keywords based on observed selection patterns

**Risks:**
- Over-optimizing for keywords may make descriptions verbose. Mitigation: keep the
  description under 200 words. Front-load the highest-signal keywords.
- LLMs may not use capability matching for tool selection. Mitigation: even if the current
  generation of LLMs does simple string matching, the next generation will do semantic
  capability matching. Investing in precise capability descriptions now prepares for that
  future.

**First validation test:** Update the tool description. Run 50 test scenarios through
Claude Code where the task requires "verifiable web evidence." Measure: does Claude select
Conduit? Compare against the current description. Target: 20%+ improvement in selection
rate for proof-relevant tasks.

**Success metric:** Within 30 days, Conduit is selected as the browser tool in 80%+ of
agent scenarios where the task mentions "proof," "verify," "evidence," or "audit."

---

## RANK 5: Defensive Adoption (Agent Self-Protection)

**Differentiator statement:** Agents adopt Conduit not because a client demands auditing,
but because the agent needs protection from false accusations, disputed work claims, and
retroactive accountability requests. The proof bundle is the agent's legal defense. The
hash chain existed before the dispute -- it cannot be fabricated after the fact.

**One-feature wedge:** A `conduit protect` CLI command (or `--protect` flag) that enables
continuous, automatic proof generation for every session -- positioned as "agent insurance."

**Why this ranks fifth:**
This concept reframes Conduit's value proposition from compliance (externally imposed)
to self-interest (internally motivated). The insight: agents will resist tools imposed by
clients ("audit me") but embrace tools that serve their own interests ("protect me"). The
same proof bundle serves both functions, but the framing changes the adoption dynamic from
push to pull.

It ranks fifth because the implementation is primarily messaging/positioning rather than
new code. The underlying capability already exists (Conduit records everything by default).
The innovation is in how the capability is described and presented to agents.

**MVP scope (1 day):**
1. Add a `--protect` flag to the CLI that enables automatic proof export on session close:
   ```bash
   python -m conduit_browser --protect
   # Every session automatically exports a proof bundle on close
   ```

2. Add messaging to skills/conduit.md:
   "Conduit protects your agent. If a client disputes your work, the proof bundle is your
   defense. If a competitor claims they did the work first, the timestamped chain
   establishes priority. If you are asked to prove what happened retroactively, the chain
   already exists."

3. Add a `protection_notice` to verify.py output:
   ```
   VERIFIED: This proof is intact and unmodified.
   This proof was generated continuously during execution (not retroactively).
   It can serve as evidence in disputes, audits, and accountability reviews.
   ```

**Expansion path:**
- Week 2: Add "Dispute Resolution" section to docs showing how proof bundles resolve
  common agent disputes
- Week 3: SwarmSync integration: agents can reference proof bundles in dispute resolution
- Month 2: Build a "Proof Archive" feature that stores all proof bundles in a persistent,
  queryable archive (~/.cato/archive/)
- Month 3: Third-party verification service: agents submit proof bundles to an independent
  verifier for time-stamped attestation

**Risks:**
- "Self-protection" framing may seem paranoid. Mitigation: frame as professional practice,
  not paranoia. "Professionals keep receipts." This is the receipt for agent work.
- Agents may not perceive dispute risk until they experience a dispute. Mitigation: share
  case studies (real or hypothetical) of agents falsely accused of not completing work.
  "This agent lost $500 because it could not prove what it did. This agent kept $500
  because it had a Conduit proof bundle."

**First validation test:** Add the `--protect` flag and messaging. Monitor: does the
protect framing increase adoption relative to the audit framing? A/B test in documentation
and outreach. Target: 15%+ higher conversion when "protect your agent" messaging is used
vs. "audit your agent."

**Success metric:** Within 60 days, the `--protect` flag is referenced in 10+ community
discussions or agent configurations.

---

## EXECUTION PRIORITY MATRIX

```
IMMEDIATE (Today):
  1. AIVS-Micro Inline (Rank 1 MVP) -- half day
  2. Proof-as-Discovery metadata (Rank 2 MVP) -- 2-4 hours
  3. Capability keyword rewrite (Rank 4 MVP) -- 1-2 hours
  Combined: 1 day of code changes. Zero external dependencies.

THIS WEEK:
  4. Defensive adoption messaging + --protect flag (Rank 5 MVP) -- 1 day
  5. Proof-Required Economics (Rank 3 MVP) -- 3-5 days (requires SwarmSync)

THIS MONTH:
  6. Multi-protocol proof injection (Rank 1, 10x)
  7. Proof bundle processor library (Rank 2, 10x)
  8. Trust tier system on SwarmSync (Rank 3, 10x)

NEXT 2 MONTHS:
  9. Proof aggregation service
  10. Gossip-based discovery protocol
  11. AIVS-Micro micro-standard publication
  12. All-jobs-proof-required on SwarmSync
```

---

## THE UNIFYING INSIGHT

All 5 concepts exploit a single structural property of the agent economy:

**Agents evaluate tools by their outputs, not by their marketing.**

In a world of autonomous agents, there is no "awareness funnel." There is no brand recall.
There is no social proof. There is only: what did this tool produce, and can I verify it?

Conduit is the only browser tool whose output answers both questions simultaneously. The
output IS the verification. The output IS the marketing. The output IS the trust signal.

The prior session's unifying insight was: "Conduit's output is self-verifying." This
session's refinement: "In an agent economy, self-verifying output IS the only marketing
channel that works."

Every concept on this shortlist is a mechanism for making Conduit's self-verifying outputs
more visible, more ubiquitous, and more economically valuable within agent interactions.
There is no "marketing campaign." There is only: produce proofs, make proofs travel, make
proofs valuable.

---

## WHAT THE MARCH 11 SESSION MISSED

The March 11 session was correct about Conduit's core advantage (self-verifying output)
but assumed the distribution model would be human-mediated. This session fills the gap:

| March 11 (Human-Mediated) | March 12 (Agent-Only) |
|----------------------------|-----------------------|
| Submit to MCP directories | Embed discovery in proof bundles |
| Write blog posts | Embed proofs in tool responses |
| Email cold proofs to humans | Economic incentive on SwarmSync |
| Optimize README for humans | Optimize capability keywords for LLMs |
| Framework integration PRs (human merges) | Protocol-agnostic proof injection |
| Social media posts | Proof gossip through agent network |
| Wait for stars | Build machine-readable trust signals |

Both approaches are needed. The March 11 strategies handle the current reality (humans
mediate most tool adoption decisions). The March 12 strategies prepare for the near future
(agents increasingly select their own tools). The intersection -- proof bundles that carry
both human-readable and machine-readable discovery metadata -- is the bridge between the
two worlds.

---

## THE ONE THING TO DO TODAY

If only one action is taken from this entire analysis, it should be:

**Add `_conduit_proof` (AIVS-Micro) to every MCP tool-call response.**

This is a single code change to conduit_bridge.py. It ships today. It costs nothing. And
from this moment forward, every agent interaction with Conduit produces a machine-readable
trust signal that no competitor can match. The signal compounds: the more agents interact
with Conduit, the more proofs they see, the stronger the preference becomes.

The proof IS the marketing. Ship the proof.
