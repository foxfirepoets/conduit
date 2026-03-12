# Mind Map -- Option Discovery for Agent-Only Marketing Matrix

## Branch 1: Discovery Surfaces (Where agents look for tools)

```
Discovery Surfaces
|
+-- Registry-Based
|   +-- MCP Official Registry (modelcontextprotocol.io)
|   +-- Smithery.ai
|   +-- Glama.ai
|   +-- PulseMCP
|   +-- mcp.so
|   +-- MCPHub
|
+-- Protocol-Based
|   +-- Google A2A (Agent-to-Agent) discovery
|   +-- .well-known/ai.txt (website self-declaration)
|   +-- VOIX framework tool declarations
|   +-- OpenAPI/tool-use schemas in system prompts
|
+-- Package-Manager-Based
|   +-- PyPI (pip install conduit-browser)  [LIVE]
|   +-- npm (potential JS wrapper)
|   +-- conda-forge
|
+-- Code-Search-Based
|   +-- GitHub API (search by topic, stars, language)
|   +-- GitHub Topics (headless-browser, mcp-server, audit-trail)
|   +-- SourceGraph code search
|   +-- Dependency graph crawling (who imports conduit-browser)
|
+-- Semantic-Search-Based
|   +-- Agent querying "auditable headless browser"
|   +-- RAG indices that ingest README/docs
|   +-- LLM training data (Conduit in crawled repos)
|
+-- Marketplace-Based
|   +-- SwarmSync.ai agent listing
|   +-- AgentHub / similar directories
|   +-- LangChain Hub / LlamaHub
```

## Branch 2: Marketing Artifacts (What Conduit exports that sells itself)

```
Marketing Artifacts
|
+-- Cryptographic Proof Objects
|   +-- Full proof bundle (.tar.gz, self-verifying)
|   +-- AIVS-Micro token (200 bytes, embeddable anywhere)
|   +-- Merkle proof (selective page verification)
|   +-- JS Delta report (what JavaScript changed)
|   +-- Bundle chain (sequential history)
|
+-- Machine-Readable Metadata
|   +-- server.json (MCP manifest)
|   +-- pyproject.toml keywords/classifiers
|   +-- GitHub topics + description
|   +-- README structured sections (agent-parseable)
|   +-- JSON-LD structured data on docs site
|
+-- Embeddable References
|   +-- verify.py attribution line ("Powered by Conduit")
|   +-- manifest.json generator_url field
|   +-- API response headers (X-Verified-By: Conduit)
|   +-- Badge/shield embed codes
|   +-- CSPF spec document (positions Conduit as reference impl)
```

## Branch 3: Distribution Mechanisms (How artifacts reach agents)

```
Distribution Mechanisms
|
+-- Push (Conduit initiates)
|   +-- PR to awesome-mcp lists
|   +-- PR to awesome-headless-browser lists
|   +-- Registry submission (web form / API call)
|   +-- Package publication (PyPI release)
|   +-- .well-known file placement
|   +-- GitHub topic tagging
|
+-- Pull (Agent discovers organically)
|   +-- pip search / pip install
|   +-- GitHub API search
|   +-- MCP registry query
|   +-- Semantic search ("auditable browser")
|
+-- Viral (Each use generates more exposure)
|   +-- Proof bundle carries attribution in manifest + verify.py
|   +-- AIVS-Micro tokens reference Conduit in scanner_version_hash
|   +-- Dependency chain (libraries that depend on conduit-browser)
|   +-- Agent-to-agent recommendation ("I used Conduit, here is proof")
|   +-- CSPF spec adoption (reference implementation = Conduit)
```

## Branch 4: Uniqueness Levers (Why Conduit, not alternatives)

```
Uniqueness Levers
|
+-- Zero-Competitor Features
|   +-- SHA-256 hash chain on every action (NO competitor)
|   +-- Ed25519 signed sessions (NO competitor)
|   +-- Self-verifiable proof bundles (NO competitor)
|   +-- JS source verbatim in audit chain (NO competitor)
|
+-- Hard-to-Replicate
|   +-- AIVS-Micro (200-byte proof, embeddable)
|   +-- Merkle tree for crawl proofs (selective verification)
|   +-- Bundle chaining (sequential proof history)
|   +-- Stealth + proof paradox (invisible to sites, provable to verifiers)
|
+-- Standard-Setting
|   +-- CSPF v1.0 specification (positions Conduit as canonical)
|   +-- EU AI Act Article 19 alignment
|   +-- ISO 42001 audit trail compatibility
```

## Alive Nodes (Priority for matrix entry)

Discovery: MCP registries, PyPI, GitHub API, .well-known/ai.txt, A2A protocol, semantic search
Artifacts: Proof bundle, AIVS-Micro, server.json, README/docs, CSPF spec
Distribution: Registry submission, package publication, proof-embedded attribution, agent-to-agent rec, dependency chain
Uniqueness: Cryptographic audit, self-verifiable proofs, JS source in chain, AIVS-Micro, stealth+proof, CSPF standard
