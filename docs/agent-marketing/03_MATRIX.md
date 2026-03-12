# Morphological Matrix -- Agent-Only Marketing Channels for Conduit

## Matrix: 4 Dimensions x 6 Options Each

```
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
| Opt | D1: Discovery Surface     | D2: Marketing Artifact    | D3: Distribution Mech     | D4: Uniqueness Lever      |
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
|  A  | MCP tool registries       | Full proof bundle         | Registry API submission   | Cryptographic audit trail |
|     | (Official, Smithery,      | (.tar.gz, self-verifying, | (automated POST to each   | (SHA-256 chain + Ed25519  |
|     | Glama, PulseMCP, mcp.so)  | embeds verify.py+attrib)  | registry's submission EP) | -- zero competitors)      |
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
|  B  | Package managers          | AIVS-Micro token          | Package publication       | Self-verifiable proofs    |
|     | (PyPI, npm -- agents      | (200-byte cryptographic   | (PyPI release, version    | (zero-dep verification,   |
|     | can pip install)           | proof snippet)            | bumps trigger discovery)  | verify.py ships inside)   |
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
|  C  | GitHub API search         | server.json / MCP         | Proof-embedded attrib     | JS source in chain        |
|     | (agents search by topic,  | manifest (machine-        | (every export carries     | (forensic proof of what   |
|     | stars, language, keyword)  | readable tool declaration)| Conduit URL in manifest)  | code ran, not just result)|
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
|  D  | .well-known/ai.txt +      | CSPF spec document        | Agent-to-agent            | Stealth + proof paradox   |
|     | A2A protocol registries   | (standard positioning     | recommendation (agent     | (Patchright invisible to  |
|     | (website self-declaration) | Conduit as ref impl)      | says "use Conduit" in     | sites, but provable to    |
|     |                           |                           | its outputs/system prompt)| verifiers)                |
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
|  E  | Semantic search indices   | README/docs (structured,  | Dependency chain          | AIVS-Micro (lightweight   |
|     | (RAG, LLM knowledge,      | agent-parseable sections  | (other packages list      | 200-byte proof for any    |
|     | "auditable browser" query)| with keywords and schema) | conduit-browser as dep)   | context -- API, DNS, etc) |
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
|  F  | Agent marketplace         | API response headers      | PR to curated lists       | CSPF standard (positions  |
|     | listings (SwarmSync,      | (X-Verified-By: Conduit,  | (awesome-mcp, awesome-    | Conduit as canonical ref  |
|     | LangChain Hub, AgentHub)  | proof hash in HTTP resp)  | headless-browser, etc.)   | implementation of proof)  |
+-----+---------------------------+---------------------------+---------------------------+---------------------------+
```

## Constraints and Data Access Notes

### D1: Discovery Surface
- MCP registries: Conduit already on 8+ directories. Official MCP Registry listing confirmed.
- PyPI: conduit-browser v0.2.1 is LIVE. Agents can `pip install conduit-browser` today.
- GitHub: repo is public. Topics need audit (are headless-browser, mcp-server, audit-trail set?).
- .well-known/ai.txt: requires a hosted docs site or swarmsync.ai integration.
- Semantic search: depends on README quality and LLM training data inclusion.
- Marketplace: SwarmSync.ai is live. Other marketplaces require manual submission.

### D2: Marketing Artifact
- Proof bundle: LIVE in conduit_proof.py. Every export already has manifest.json with generator_url.
- AIVS-Micro: LIVE in conduit_proof.py. export_micro() produces 200-byte proofs.
- server.json: LIVE at repo root. Registered with Official MCP Registry.
- CSPF spec: LIVE at spec/CONDUIT_SESSION_PROOF_FORMAT.md. Not yet submitted anywhere external.
- README: LIVE and detailed. Could benefit from more machine-parseable structured data.
- API headers: NOT IMPLEMENTED. Would require changes to bridge output format.

### D3: Distribution Mechanism
- Registry submission: partially done (8+ registries). Can be expanded.
- Package publication: PyPI is live. npm not yet published.
- Proof-embedded attribution: LIVE. manifest.json has generator_url, verify.py has "Powered by Conduit" line.
- Agent-to-agent rec: requires agents that USE Conduit to recommend it in their outputs. Not yet systematic.
- Dependency chain: no known packages depend on conduit-browser yet.
- Curated list PRs: not yet submitted to awesome-* lists.

### D4: Uniqueness Lever
- All uniqueness levers are REAL and IMPLEMENTED -- this is not vaporware.
- Cryptographic audit: LIVE (audit.py, SHA-256 + Ed25519).
- Self-verifiable proofs: LIVE (verify.py embedded in every bundle).
- JS source in chain: LIVE (eval action stores full JS body).
- Stealth + proof: LIVE (Patchright fork).
- AIVS-Micro: LIVE (export_micro in conduit_proof.py).
- CSPF spec: LIVE (spec/ directory, formal RFC-style document).
