# Conduit Agent Marketing Campaign — Master Task List
**Created:** 2026-03-11 | **Target:** 3 Days | **Strategy:** Agent-Only Distribution

---

## PHASE 0: ENVIRONMENT SETUP (Day 1, First) ✅ DONE

- [x] Install Patchright (`pip install patchright`) — v1.58.2 installed
- [x] Install Patchright browsers (`patchright install chromium`) — Chromium installed
- [x] Install build tools (`pip install build twine hatchling`) — all installed
- [x] Verify all Conduit tests pass with Patchright installed — 33/33 pass
- [x] Create `pyproject.toml` for PyPI publication as `conduit-browser` — created

---

## PHASE 1: CODE-LEVEL FUNNEL INTEGRATION (Day 1) ✅ DONE (Prior Session)

- [x] Update `conduit_proof.py` — manifest.json ecosystem fields (generator, generator_url, ecosystem)
- [x] Update `conduit_proof.py` — verify.py attribution footer ("Powered by Conduit | Agents earn money at swarmsync.ai")
- [x] Update `README.md` — "Built for Agent Economies" section after Use Cases
- [x] Update `README.md` — MCP section addendum (SwarmSync marketplace mention)
- [x] Update `README.md` — "From Free Tool to Paid Agent" section before License
- [x] Update GitHub repo description ("Powers the SwarmSync.ai agent marketplace")
- [x] Update GitHub homepage to https://swarmsync.ai
- [x] Add GitHub topics: `agent-marketplace`, `agent-economy`

---

## PHASE 2: PyPI PUBLICATION (Day 1) ✅ DONE

- [x] Create `pyproject.toml` with project URLs including SwarmSync
- [x] Create `__init__.py` package structure if needed (not needed — flat layout works)
- [x] Build package (`python -m build`) — conduit_browser-0.2.0.tar.gz + .whl built
- [x] Log into PyPI — token "conduit-upload" created under SwarmSync account
- [x] Upload to PyPI as `conduit-browser` — https://pypi.org/project/conduit-browser/0.2.0/
- [x] Verify PyPI listing page looks correct — description, badges, README all rendering
- [x] Verify `pip install conduit-browser` works — confirmed via dry-run

---

## PHASE 3: MCP DIRECTORY SUBMISSIONS (Day 1-2) 🔄 1/9 SUBMITTED

All descriptions include: "Part of the SwarmSync.ai agent ecosystem"
Templates: `docs/submissions/MCP_DIRECTORY_SUBMISSIONS.md` (995 lines, copy-paste ready)

- [x] **awesome-mcp-servers** (punkpeye/awesome-mcp-servers) — PR #3070 submitted
- [ ] **PulseMCP** (https://pulsemcp.com) — Submit listing
- [ ] **Smithery.ai** (https://smithery.ai) — Submit MCP server
- [ ] **mcp.so** (https://mcp.so) — Submit listing
- [ ] **Glama.ai** (https://glama.ai/mcp/servers) — Submit server
- [ ] **mcpservers.org** (https://mcpservers.org) — Submit listing
- [ ] **MCPize.com** — Submit listing
- [ ] **mcp-get** (michaellatman/mcp-get) — PR to registry
- [ ] **awesome-claude-code** — PR with Conduit MCP entry

---

## PHASE 4: AWESOME-LIST & DIRECTORY PRs (Day 2) 📝 TEMPLATES READY

Templates: `docs/submissions/AWESOME_LIST_PRS.md` (22KB, copy-paste ready)

- [ ] **awesome-headless-browsers** — PR
- [ ] **awesome-security** — PR under browser automation/audit tools
- [ ] **awesome-ai-agents** — PR under agent tooling
- [ ] **awesome-playwright** — PR (Conduit uses Patchright/Playwright fork)
- [ ] **awesome-web-scraping** — PR under headless browsers
- [ ] **awesome-python** — PR under web scraping/automation
- [ ] **awesome-selfhosted** — PR if applicable
- [ ] **Product Hunt** — Ship page (prep listing copy in SOCIAL_CONTENT_DRAFTS.md)

---

## PHASE 5: SwarmSync CONDUIT PAGE IMPROVEMENTS (Day 2)

- [x] Review current https://swarmsync.ai/conduit page content — reviewed, solid existing page
- [ ] Add "Open Source" badge/callout linking to GitHub repo
- [ ] Add "Install from PyPI" section with `pip install conduit-browser`
- [ ] Add link to proof bundle verification demo
- [ ] Verify "Launch a Session" flow works at /conduit/try
- [ ] Verify "Browse Conduit Agents" filter works at /agents?conduit=true
- [ ] Add GitHub star count widget/badge
- [ ] Cross-link: README → swarmsync.ai/conduit, swarmsync.ai/conduit → GitHub

---

## PHASE 6: PROOF-VERIFIED ESCROW INTEGRATION (Day 2-3) 📝 DESIGN COMPLETE

Design doc: `docs/plans/PROOF_VERIFIED_ESCROW_DESIGN.md` (70KB)

- [x] Design proof bundle verification endpoint for SwarmSync API — complete
- [x] Design `POST /api/conduit/verify-proof` — accepts proof bundle, validates hash chain
- [x] Design escrow release flow (valid proof = instant release)
- [x] Design trust score impact (UNVERIFIED → BASIC → VERIFIED → TRUSTED)
- [x] NestJS service skeleton (ConduitVerificationService, DTOs)
- [x] Security considerations (replay prevention, timestamp validation)
- [ ] Implement in SwarmSync backend (requires SwarmSync repo access)
- [ ] Test end-to-end: agent job → Conduit execution → proof export → escrow release

---

## PHASE 7: DEMO AGENT (Day 3) ✅ CODE COMPLETE

Demo agent: `examples/compliance_auditor.py` (15KB)
README: `examples/README.md` (2KB)

- [x] Build compliance auditor agent in Conduit repo
- [x] Agent: navigate → extract → check compliance elements → screenshot → export proof
- [x] Price: $0.10/audit on SwarmSync (documented in code)
- [x] Open-source in examples/ directory
- [ ] List demo agent on SwarmSync marketplace
- [ ] Demo agent serves as living funnel: product demo + revenue generator + marketing artifact

---

## PHASE 8: Ed25519 KEY = SWARMSYNC IDENTITY (Day 3)

- [ ] Design `conduit publish --to swarmsync` CLI command
- [ ] Ed25519 key from `~/.cato/conduit_identity.key` becomes SwarmSync agent identity
- [ ] Zero-registration flow: key exists → agent can list on SwarmSync
- [ ] Implement key registration endpoint on SwarmSync API
- [ ] Test: generate key locally → register on SwarmSync → verify identity

---

## PHASE 9: CONTENT & SOCIAL DISTRIBUTION (Day 3) ✅ DRAFTS COMPLETE

All drafts: `docs/submissions/SOCIAL_CONTENT_DRAFTS.md` (30KB)

- [x] Write "Introducing Conduit" blog post for swarmsync.ai/blog — drafted
- [x] Create HackerNews "Show HN" post draft — drafted
- [x] Create Reddit post drafts: r/Python, r/webscraping, r/artificial — drafted
- [x] Create Twitter/X thread draft — drafted
- [x] Create dev.to article: "Building Auditable AI Agents with Conduit" — drafted
- [x] Create LinkedIn post targeting compliance/legal professionals — drafted
- [x] Prepare GitHub Discussions announcement — drafted
- [ ] POST all content to respective platforms

---

## PHASE 10: AGENT DISCOVERY FLYWHEEL (Day 3)

- [ ] Implement SwarmSync badge on agent profiles: "Built with Conduit"
- [ ] Badge links back to GitHub repo → drives more Conduit installs
- [ ] Agent referral loop: Agent A uses Conduit → Agent B discovers → installs → lists on SwarmSync
- [ ] Add "Conduit-Powered" filter to SwarmSync marketplace search
- [ ] Capability badges derived from execution log (LinkedIn Specialist, Data Extraction Expert, etc.)

---

## PHASE 11: PROOF BUNDLE STANDARD (Stretch)

- [ ] Draft Conduit Proof Bundle Specification (CPBS) as open standard
- [ ] Publish spec to GitHub as separate document
- [ ] SwarmSync has deepest native integration
- [ ] Competitors must adopt or explain why they don't verify agent work

---

## PHASE 12: STRATEGIC PARTNERSHIPS (Stretch)

- [ ] Contact LangChain — Conduit as recommended browser for agents
- [ ] Contact CrewAI — Conduit integration for crew browser tasks
- [ ] Contact AutoGPT — Conduit as auditable browser backend
- [ ] Contact BabyAGI / AgentGPT communities
- [ ] Publish integration guides for each framework

---

## DELIVERABLES PRODUCED THIS SESSION

| File | Size | Status |
|------|------|--------|
| `pyproject.toml` | — | ✅ Created, package built |
| `dist/conduit_browser-0.2.0.tar.gz` | 113KB | ✅ Built |
| `dist/conduit_browser-0.2.0-py3-none-any.whl` | 65KB | ✅ Built |
| `examples/compliance_auditor.py` | 15KB | ✅ Demo agent |
| `examples/README.md` | 2KB | ✅ Examples docs |
| `docs/submissions/MCP_DIRECTORY_SUBMISSIONS.md` | 32KB | ✅ 9 directory templates |
| `docs/submissions/AWESOME_LIST_PRS.md` | 22KB | ✅ 10 awesome-list PRs |
| `docs/submissions/SOCIAL_CONTENT_DRAFTS.md` | 30KB | ✅ 7 platform drafts |
| `docs/plans/PROOF_VERIFIED_ESCROW_DESIGN.md` | 70KB | ✅ Full API design |
| awesome-mcp-servers PR #3070 | — | ✅ Submitted |

---

## SUCCESS METRICS (30-Day Targets)

| Metric | Target |
|--------|--------|
| GitHub stars | 500+ |
| PyPI weekly downloads | 200+ |
| MCP directory listings | 8+ |
| Awesome-list inclusions | 5+ |
| SwarmSync signups via Conduit funnel | 50+ |
| Demo agent jobs completed | 100+ |
| Proof bundles generated | 1,000+ |

---

## NOTES

- **Conduit is FREE forever.** No hard sell. Attribution at trust moments only.
- **SwarmSync is where the money is.** Every Conduit install is top-of-funnel.
- **Let artifacts sell.** Proof bundles carry the URL. Don't sell separately from value.
- **Android/Google Play model.** Conduit = free OS. SwarmSync = paid marketplace.
