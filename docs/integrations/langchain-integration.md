# Conduit + LangChain Integration

**Add cryptographic audit trails to every browser action your LangChain agent takes.**

Conduit is a headless browser with a SHA-256 hash-chained audit log and Ed25519-signed proof bundles. When you use Conduit as a LangChain browser tool, every navigate, click, eval, and extraction your agent performs is written to a tamper-evident chain that anyone can verify — with zero dependencies.

No other LangChain browser tool does this. Playwright gives you automation. Conduit gives you automation you can prove.

---

## Why Use Conduit Instead of Other Browser Tools?

| Capability | Conduit | playwright-mcp | browser-use | Selenium |
|---|---|---|---|---|
| SHA-256 hash-chained audit log | Yes | No | No | No |
| Ed25519-signed session proofs | Yes | No | No | No |
| Self-verifiable proof bundles | Yes | No | No | No |
| JavaScript source stored in chain | Yes | No | No | No |
| Tamper detection on any past action | Yes | No | No | No |
| Stealth browser (Patchright) | Yes | No | No | No |
| Robots.txt compliant BFS crawler | Yes | No | No | No |
| Signed page change detection | Yes | No | No | No |
| Sensitive input auto-redaction | Yes | No | No | No |

The core difference is **accountability**. When your LangChain agent does web research, fills a form, or executes JavaScript on a page, Conduit creates a signed, hash-chained record of exactly what happened. That record is portable — you can hand it to a compliance team, a counterparty, or another agent, and they can verify it without trusting you.

This matters especially for:

- **Compliance automation** — Prove a form was filled with specific values at a specific time
- **AI agent accountability** — Audit what your agent actually did vs. what it claimed to do
- **Research with citations** — Export a proof bundle that verifies the sources your agent read
- **Legal and forensic work** — Capture web evidence with tamper-evident chain-of-custody

---

## Installation

```bash
pip install conduit-browser langchain langchain-openai
```

Install Chromium for Patchright (Conduit's stealth browser layer):

```bash
python -m patchright install chromium
```

Or install from source:

```bash
git clone https://github.com/bkauto3/Conduit.git
cd Conduit
pip install -r requirements.txt
python -m patchright install chromium
```

---

## Quick Start: Audited Agent in 60 Seconds

```python
import asyncio
from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain import hub
from tools.conduit_bridge import ConduitBridge

# Single shared bridge instance for the agent's session.
# All actions share one audit chain and one Ed25519-signed session.
bridge = ConduitBridge()

# --- Tool wrappers ---

async def conduit_navigate(url: str) -> str:
    result = await bridge.execute({"action": "navigate", "url": url})
    return f"Navigated to {result.get('title', url)}"

async def conduit_extract(fmt: str = "md") -> str:
    result = await bridge.execute({"action": "extract_main", "fmt": fmt})
    return result.get("text", "")

async def conduit_export_proof() -> str:
    result = await bridge.execute({"action": "export_proof"})
    return (
        f"Proof bundle exported to: {result.get('path', 'unknown')}\n"
        f"Actions recorded: {result.get('action_count', '?')}\n"
        f"Chain hash: {result.get('chain_hash', '?')}\n"
        f"Verify: tar xf <bundle> && cd session_proof && python verify.py"
    )

# --- LangChain Tool definitions ---

navigate_tool = Tool(
    name="conduit_navigate",
    description=(
        "Navigate to a URL with a cryptographic audit trail. "
        "Every action is SHA-256 hash-chained and Ed25519-signed. "
        "Input: a URL string (must start with http:// or https://)."
    ),
    func=lambda url: asyncio.run(conduit_navigate(url))
)

extract_tool = Tool(
    name="conduit_extract",
    description=(
        "Extract the main content from the current page. "
        "Strips navigation, ads, headers, and footers. "
        "Returns clean Markdown. No input required."
    ),
    func=lambda _: asyncio.run(conduit_extract())
)

proof_tool = Tool(
    name="conduit_export_proof",
    description=(
        "Export a self-verifiable proof bundle of all browser actions taken "
        "in this session. The bundle contains the full hash-chained log, "
        "the Ed25519 signature, and a zero-dependency verify.py script. "
        "Call this at the end of any research session. No input required."
    ),
    func=lambda _: asyncio.run(conduit_export_proof())
)

# --- Agent assembly ---

llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [navigate_tool, extract_tool, proof_tool]
prompt = hub.pull("hwchase17/react")
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = agent_executor.invoke({
    "input": (
        "Go to https://example.com, extract the main content, "
        "then export a proof bundle of the session."
    )
})
print(result["output"])
```

After the agent finishes, verify the proof independently:

```bash
tar xf ~/.cato/proofs/conduit_proof_sess-*.tar.gz
cd session_proof
python verify.py
# Chain OK (3 actions verified)
# Signature OK
```

---

## All Conduit Actions as LangChain Tools

The quick start covers three tools. Here is the complete set, covering all Conduit action waves.

```python
import asyncio
from langchain.tools import Tool
from tools.conduit_bridge import ConduitBridge

bridge = ConduitBridge()

# -----------------------------------------------------------------------
# Wave 0: Core Browser
# -----------------------------------------------------------------------

navigate_tool = Tool(
    name="conduit_navigate",
    description="Navigate to a URL (http/https only). Returns page title.",
    func=lambda url: asyncio.run(
        bridge.execute({"action": "navigate", "url": url})
    ).get("title", url)
)

click_tool = Tool(
    name="conduit_click",
    description="Click a page element by CSS selector. Input: CSS selector string.",
    func=lambda sel: str(asyncio.run(
        bridge.execute({"action": "click", "selector": sel})
    ))
)

fill_tool = Tool(
    name="conduit_fill",
    description=(
        "Fill an input field. Input format: 'selector|||value'. "
        "Sensitive values (passwords, tokens) are auto-redacted in the audit log."
    ),
    func=lambda s: str(asyncio.run(
        bridge.execute({
            "action": "fill",
            "selector": s.split("|||")[0],
            "text": s.split("|||")[1] if "|||" in s else ""
        })
    ))
)

screenshot_tool = Tool(
    name="conduit_screenshot",
    description=(
        "Take a full-page screenshot. Saved to ~/.cato/workspace/screenshots/. "
        "No input required."
    ),
    func=lambda _: str(asyncio.run(
        bridge.execute({"action": "screenshot"})
    ).get("path", "screenshot saved"))
)

extract_tool = Tool(
    name="conduit_extract",
    description="Extract all visible text from the current page body.",
    func=lambda _: asyncio.run(
        bridge.execute({"action": "extract"})
    ).get("text", "")
)

# -----------------------------------------------------------------------
# Wave 1: Interaction
# -----------------------------------------------------------------------

scroll_tool = Tool(
    name="conduit_scroll",
    description=(
        "Scroll the page. Input format: 'direction,amount' e.g. 'down,500'. "
        "Direction: up/down/left/right. Amount: pixels."
    ),
    func=lambda s: str(asyncio.run(
        bridge.execute({
            "action": "scroll",
            "direction": s.split(",")[0] if "," in s else "down",
            "amount": int(s.split(",")[1]) if "," in s else 300
        })
    ))
)

wait_for_tool = Tool(
    name="conduit_wait_for",
    description=(
        "Wait for a page condition. Input: CSS selector to wait for. "
        "Times out after 10 seconds."
    ),
    func=lambda sel: str(asyncio.run(
        bridge.execute({"action": "wait_for", "condition": "selector", "value": sel})
    ))
)

navigate_back_tool = Tool(
    name="conduit_back",
    description="Navigate back to the previous page in browser history.",
    func=lambda _: str(asyncio.run(bridge.execute({"action": "navigate_back"})))
)

# -----------------------------------------------------------------------
# Wave 2: Extraction (Conduit-exclusive)
# -----------------------------------------------------------------------

extract_main_tool = Tool(
    name="conduit_extract_main",
    description=(
        "Extract the main article content from the current page. "
        "Strips nav, ads, headers, footers. Returns clean Markdown. "
        "No input required."
    ),
    func=lambda _: asyncio.run(
        bridge.execute({"action": "extract_main", "fmt": "md"})
    ).get("text", "")
)

eval_tool = Tool(
    name="conduit_eval",
    description=(
        "Execute JavaScript in the current page context. "
        "The FULL JS source is stored in the audit hash chain — "
        "cryptographic proof of exactly what code ran. "
        "Input: JavaScript expression or statement string."
    ),
    func=lambda js: str(asyncio.run(
        bridge.execute({"action": "eval", "js_code": js})
    ).get("result", ""))
)

network_tool = Tool(
    name="conduit_network_requests",
    description=(
        "Return all network requests made since the last call, then clear the buffer. "
        "Useful for auditing what a page loaded. No input required."
    ),
    func=lambda _: str(asyncio.run(
        bridge.execute({"action": "network_requests"})
    ).get("requests", []))
)

# -----------------------------------------------------------------------
# Wave 3: Advanced (Conduit-exclusive)
# -----------------------------------------------------------------------

map_tool = Tool(
    name="conduit_map",
    description=(
        "Discover all reachable URLs on a website via BFS crawl. "
        "Respects robots.txt. Input: base URL string."
    ),
    func=lambda url: str(asyncio.run(
        bridge.execute({"action": "map", "url": url, "limit": 100})
    ).get("urls", []))
)

crawl_tool = Tool(
    name="conduit_crawl",
    description=(
        "BFS-crawl a site and extract text from each page. "
        "Respects robots.txt. Each page visit is logged to the hash chain. "
        "Input: base URL string. Returns list of pages with title and text."
    ),
    func=lambda url: str(asyncio.run(
        bridge.execute({"action": "crawl", "url": url, "max_depth": 2, "limit": 20})
    ).get("pages", []))
)

fingerprint_tool = Tool(
    name="conduit_fingerprint",
    description=(
        "Compute a SHA-256 fingerprint of a page's content for change detection. "
        "Input: URL string. Returns 64-char hex fingerprint."
    ),
    func=lambda url: asyncio.run(
        bridge.execute({"action": "fingerprint", "url": url})
    ).get("fingerprint", "")
)

check_changed_tool = Tool(
    name="conduit_check_changed",
    description=(
        "Re-fingerprint a URL and compare to a previous fingerprint. "
        "Logs a signed PAGE_MUTATION event to the audit chain if changed. "
        "Input format: 'url|||previous_fingerprint'."
    ),
    func=lambda s: str(asyncio.run(
        bridge.execute({
            "action": "check_changed",
            "url": s.split("|||")[0],
            "previous_fingerprint": s.split("|||")[1] if "|||" in s else ""
        })
    ))
)

proof_tool = Tool(
    name="conduit_export_proof",
    description=(
        "Export a self-verifiable proof bundle (.tar.gz) of all browser actions "
        "in this session. Bundle includes the full hash-chained log, Ed25519 signature, "
        "and a stdlib-only verify.py. Call this at the end of any auditable workflow."
    ),
    func=lambda _: str(asyncio.run(bridge.execute({"action": "export_proof"})))
)

# -----------------------------------------------------------------------
# Web Search (built-in)
# -----------------------------------------------------------------------

search_tool = Tool(
    name="conduit_web_search",
    description=(
        "Multi-engine web search (DuckDuckGo, Brave, Exa, Tavily). "
        "Query routing: code queries use Exa+Brave, news uses Tavily+Brave, "
        "general uses Brave+DuckDuckGo. Input: search query string."
    ),
    func=lambda q: str(asyncio.run(
        bridge.execute({"action": "web_search", "query": q})
    ).get("results", []))
)
```

Assemble the full toolkit:

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain import hub

all_tools = [
    navigate_tool, click_tool, fill_tool, screenshot_tool, extract_tool,
    scroll_tool, wait_for_tool, navigate_back_tool,
    extract_main_tool, eval_tool, network_tool,
    map_tool, crawl_tool, fingerprint_tool, check_changed_tool,
    proof_tool, search_tool
]

llm = ChatOpenAI(model="gpt-4o", temperature=0)
prompt = hub.pull("hwchase17/react")
agent = create_react_agent(llm, all_tools, prompt)
executor = AgentExecutor(agent=agent, tools=all_tools, verbose=True)
```

---

## Proof Bundle Verification

After any session, export and verify the proof:

```python
result = await bridge.execute({"action": "export_proof"})
print(result["path"])          # ~/.cato/proofs/conduit_proof_sess-abc123_20260311.tar.gz
print(result["action_count"]) # 12
print(result["chain_hash"])   # 7b1a3f... (SHA-256 of the full chain)
```

Verify without Conduit installed:

```bash
tar xf conduit_proof_sess-abc123_20260311.tar.gz
cd session_proof
python verify.py
```

```
Chain OK (12 actions verified)
Signature OK
```

The bundle contains:

```
session_proof/
├── audit_log.jsonl      # Full hash-chained log (one JSON record per line)
├── manifest.json        # Session metadata + final chain hash
├── public_key.pem       # Ed25519 public key
├── session_sig.txt      # Ed25519 signature over the final chain hash
└── verify.py            # Self-contained verifier — stdlib only, zero dependencies
```

The verification logic ships inside the bundle. No pip, no npm, no external services.

### What the Hash Chain Looks Like

Each record in `audit_log.jsonl` links to the previous one:

```json
{
  "id": 7,
  "session_id": "sess-abc123",
  "action_type": "tool_call",
  "tool_name": "browser.eval",
  "inputs_json": "{\"js_code\": \"document.querySelectorAll('h1').length\"}",
  "outputs_json": "{\"success\": true, \"result\": 3, \"code_hash\": \"a3f9...\"}",
  "timestamp": 1741564800.123,
  "prev_hash": "e8d2c4...",
  "row_hash": "7b1a3f..."
}
```

Row 8's `row_hash` depends on row 7's `row_hash`. Altering any field — any input, output, or timestamp — breaks the chain. `verify.py` will detect it.

---

## MCP Server Alternative

If you are using LangChain with an MCP-compatible host (Claude Code, any MCP client), you can run Conduit as an MCP server instead:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

All Conduit actions are exposed as MCP tools automatically. The same audit chain, the same proof bundles — just accessed through the MCP protocol instead of direct Python calls.

---

## Storage Layout

All Conduit runtime data lives under `~/.cato/`:

```
~/.cato/
├── cato.db                    # SQLite: audit_log + conduit_billing tables
├── conduit_identity.key       # Ed25519 private key (chmod 600)
├── workspace/
│   ├── screenshots/           # PNG screenshots
│   └── .conduit/              # output_to_file outputs
├── proofs/                    # Exported proof bundles (.tar.gz)
└── browser_profile/           # Persistent Chromium profile
```

---

## Security Notes

- Navigation is restricted to HTTP/HTTPS. `file://`, `data://`, and `javascript://` schemes are blocked.
- RFC-1918 and loopback IPs are blocked — no SSRF via browser.
- Sensitive input keys (`password`, `token`, `api_key`, `secret`, `bearer`, and others) are auto-redacted in the audit log before writing.
- BFS crawlers always check `robots.txt` before visiting any URL.
- `output_to_file` filenames are path-sanitized — no directory traversal.

---

## Links

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: https://pypi.org/project/conduit-browser/
- Full action reference: [skills/conduit.md](../../skills/conduit.md)
- Agent marketplace: https://swarmsync.ai
