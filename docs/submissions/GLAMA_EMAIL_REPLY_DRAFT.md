# Glama Email Reply Drafts

## Reply 1: To Glama Team Personal Email
**Subject:** RE: What are you trying to accomplish?

Hi,

Thanks for reaching out! We're primarily interested in **MCP** — we just published our MCP server **Conduit** (a headless browser with cryptographic audit trails) and it was approved on your directory.

Conduit gives AI agents a browser with SHA-256 hash-chained audit logs and Ed25519-signed session proofs. Every action — navigation, clicks, JavaScript execution — is cryptographically recorded and exportable as a self-verifiable proof bundle. It's designed as the trust/verification layer for agent-to-agent work.

We're using Glama to help other developers and agents discover Conduit as an MCP server they can integrate into their workflows. The main use cases are:

- **Compliance automation** — agents that need to prove what web actions they took
- **Security research** — cryptographic evidence of what a page did
- **AI agent browser control** — auditable browser for autonomous agents
- **Web monitoring** — signed change detection with proof of when pages mutated

We'd also love to claim the server under our account if there are any additional steps needed beyond the admin settings page.

Thanks for building Glama — the MCP directory is exactly what the ecosystem needs.

Best,
Bullrush Investments / BKAuto3

---

## Reply 2: Claiming the Server (Admin Steps)
**Action needed:** Log into Glama with the bkauto3 GitHub account, navigate to the Conduit server page, and use the admin settings to claim ownership. Then provide a Dockerfile for the server.

**Server URL:** https://glama.ai/mcp/servers/bkauto3/conduit

**Dockerfile note:** Conduit runs as `python -m tools.conduit_bridge` and requires Patchright (Chromium). A Dockerfile would need:
- Python 3.10+
- patchright + chromium browser
- The Conduit source code
