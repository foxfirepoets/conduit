# Conduit + CrewAI Integration

**Give your CrewAI agents auditable browser access with cryptographic proof of every action.**

Conduit is a headless browser with a SHA-256 hash-chained audit log and Ed25519-signed proof bundles. Every navigate, click, extract, and JavaScript execution your CrewAI agent performs is written to a tamper-evident chain that anyone can verify — using only Python's standard library, with no external dependencies.

---

## Why Conduit for CrewAI?

CrewAI agents doing web research, monitoring, or compliance work need more than automation — they need **proof**. When Agent A hands off work to Agent B, or when a crew produces a research report, how do you know what the agents actually did?

Conduit answers that question with a cryptographic record:

- Every URL navigated, every element clicked, every JS expression evaluated — all chained and signed
- Export a proof bundle at the end of any task: the receiving agent, a compliance team, or a counterparty can verify it without trusting you
- The `eval` action stores the full JavaScript source in the hash chain — not just the result, but the exact code that ran

No other CrewAI browser tool provides this.

---

## Installation

```bash
pip install conduit-browser crewai crewai-tools
```

Install Chromium:

```bash
python -m patchright install chromium
```

Or from source:

```bash
git clone https://github.com/bkauto3/Conduit.git
cd Conduit
pip install -r requirements.txt
python -m patchright install chromium
```

---

## Tool Classes

CrewAI uses a `BaseTool` subclass pattern. Each Conduit action becomes its own tool class.

### Core Tools

```python
from crewai_tools import BaseTool
from tools.conduit_bridge import ConduitBridge
import asyncio

# Use a module-level bridge so all tools in a crew share one audit session.
_bridge = ConduitBridge()


class ConduitNavigateTool(BaseTool):
    name: str = "Conduit Navigate"
    description: str = (
        "Navigate to a URL with a cryptographic audit trail. "
        "Every action is SHA-256 hash-chained and Ed25519-signed. "
        "Input: a full URL (http:// or https:// only). "
        "Returns the page title."
    )

    def _run(self, url: str) -> str:
        result = asyncio.run(_bridge.execute({"action": "navigate", "url": url}))
        return f"Navigated to: {result.get('title', url)}"


class ConduitExtractMainTool(BaseTool):
    name: str = "Conduit Extract Main Content"
    description: str = (
        "Extract the main article content from the current page. "
        "Strips navigation, ads, headers, and footers. "
        "Returns clean Markdown. No input required — pass any string."
    )

    def _run(self, _: str = "") -> str:
        result = asyncio.run(
            _bridge.execute({"action": "extract_main", "fmt": "md"})
        )
        return result.get("text", "No content extracted.")


class ConduitScreenshotTool(BaseTool):
    name: str = "Conduit Screenshot"
    description: str = (
        "Take a full-page screenshot and save it to the workspace. "
        "No input required — pass any string. "
        "Returns the path to the saved screenshot."
    )

    def _run(self, _: str = "") -> str:
        result = asyncio.run(_bridge.execute({"action": "screenshot"}))
        return f"Screenshot saved: {result.get('path', 'screenshot captured')}"


class ConduitEvalTool(BaseTool):
    name: str = "Conduit JavaScript Eval"
    description: str = (
        "Execute JavaScript in the current page context. "
        "The full JS source is stored verbatim in the audit hash chain — "
        "cryptographic proof of exactly what code ran. "
        "Input: a JavaScript expression or statement."
    )

    def _run(self, js_code: str) -> str:
        result = asyncio.run(
            _bridge.execute({"action": "eval", "js_code": js_code})
        )
        return str(result.get("result", ""))


class ConduitExportProofTool(BaseTool):
    name: str = "Conduit Export Proof"
    description: str = (
        "Export a self-verifiable proof bundle of all browser actions taken "
        "in this session. The bundle is a .tar.gz file containing the full "
        "hash-chained log, Ed25519 signature, and a zero-dependency verify.py. "
        "Call this at the end of any research or compliance task. "
        "No input required — pass any string."
    )

    def _run(self, _: str = "") -> str:
        result = asyncio.run(_bridge.execute({"action": "export_proof"}))
        return (
            f"Proof bundle exported to: {result.get('path', 'unknown')}\n"
            f"Actions recorded: {result.get('action_count', '?')}\n"
            f"Chain hash: {result.get('chain_hash', '?')}\n"
            f"Verify: tar xf <bundle> && cd session_proof && python verify.py"
        )
```

### Crawl and Monitor Tools

```python
class ConduitMapTool(BaseTool):
    name: str = "Conduit Site Map"
    description: str = (
        "Discover all reachable URLs on a website via BFS crawl. "
        "Respects robots.txt. Input: base URL string. "
        "Returns list of discovered URLs."
    )

    def _run(self, url: str) -> str:
        result = asyncio.run(
            _bridge.execute({"action": "map", "url": url, "limit": 100})
        )
        urls = result.get("urls", [])
        return f"Found {len(urls)} URLs:\n" + "\n".join(urls[:50])


class ConduitCrawlTool(BaseTool):
    name: str = "Conduit Site Crawl"
    description: str = (
        "BFS-crawl a site and extract text from each page. "
        "Respects robots.txt. Each page visit is logged to the hash chain. "
        "Input: base URL string. Returns extracted text from up to 20 pages."
    )

    def _run(self, url: str) -> str:
        result = asyncio.run(
            _bridge.execute({"action": "crawl", "url": url, "max_depth": 2, "limit": 20})
        )
        pages = result.get("pages", [])
        output = []
        for page in pages:
            output.append(f"## {page.get('title', page.get('url', ''))}")
            output.append(page.get("text", "")[:1500])
            output.append("")
        return "\n".join(output) if output else "No pages crawled."


class ConduitFingerprintTool(BaseTool):
    name: str = "Conduit Page Fingerprint"
    description: str = (
        "Compute a SHA-256 fingerprint of a page's content for change detection. "
        "Normalizes timestamps and nonces to avoid false positives. "
        "Input: URL string. Returns 64-char hex fingerprint."
    )

    def _run(self, url: str) -> str:
        result = asyncio.run(
            _bridge.execute({"action": "fingerprint", "url": url})
        )
        fp = result.get("fingerprint", "")
        return f"Fingerprint for {url}:\n{fp}"


class ConduitCheckChangedTool(BaseTool):
    name: str = "Conduit Check Page Changed"
    description: str = (
        "Re-fingerprint a URL and compare to a previous fingerprint. "
        "Logs a signed PAGE_MUTATION event to the audit chain if content changed. "
        "Input format: 'URL|||previous_fingerprint' (64-char hex)."
    )

    def _run(self, input_str: str) -> str:
        parts = input_str.split("|||")
        if len(parts) != 2:
            return "Error: input must be 'URL|||fingerprint'"
        url, prev_fp = parts[0].strip(), parts[1].strip()
        result = asyncio.run(
            _bridge.execute({
                "action": "check_changed",
                "url": url,
                "previous_fingerprint": prev_fp
            })
        )
        changed = result.get("changed", False)
        status = "CHANGED" if changed else "unchanged"
        return f"Page {url} is {status}.\nNew fingerprint: {result.get('new_fingerprint', '')}"


class ConduitWebSearchTool(BaseTool):
    name: str = "Conduit Web Search"
    description: str = (
        "Multi-engine web search using DuckDuckGo, Brave, Exa, and Tavily. "
        "Automatically routes queries: code/technical queries use Exa+Brave, "
        "news queries use Tavily+Brave, general queries use Brave+DuckDuckGo. "
        "Input: search query string."
    )

    def _run(self, query: str) -> str:
        result = asyncio.run(
            _bridge.execute({"action": "web_search", "query": query})
        )
        results = result.get("results", [])
        if not results:
            return "No results found."
        output = []
        for r in results[:10]:
            output.append(f"- [{r.get('title', 'No title')}]({r.get('url', '')})")
            if r.get("snippet"):
                output.append(f"  {r['snippet']}")
        return "\n".join(output)
```

---

## Complete Crew Example: Web Research with Proof Bundles

This example builds a two-agent crew: a researcher that gathers information about a topic, and a writer that synthesizes it into a report. Both agents use Conduit, so the full session is audited and a proof bundle is exported at the end.

```python
import asyncio
from crewai import Agent, Task, Crew
from tools.conduit_bridge import ConduitBridge

# Shared bridge — one audit session across the entire crew
_bridge = ConduitBridge()

# --- Tool instances ---

navigate_tool = ConduitNavigateTool()
extract_tool = ConduitExtractMainTool()
search_tool = ConduitWebSearchTool()
crawl_tool = ConduitCrawlTool()
screenshot_tool = ConduitScreenshotTool()
proof_tool = ConduitExportProofTool()

# --- Agents ---

researcher = Agent(
    role="Web Research Specialist",
    goal=(
        "Research a topic thoroughly using auditable browser sessions. "
        "Every source you visit and every piece of content you extract "
        "is recorded in a tamper-evident hash chain."
    ),
    backstory=(
        "You are a meticulous researcher who values source verification. "
        "You use Conduit's cryptographic audit trail to prove exactly "
        "which pages you visited and what you read."
    ),
    tools=[search_tool, navigate_tool, extract_tool, crawl_tool, screenshot_tool],
    verbose=True
)

writer = Agent(
    role="Research Report Writer",
    goal=(
        "Synthesize research findings into a clear, structured report. "
        "At the end of every report, export a proof bundle so readers "
        "can verify the sources independently."
    ),
    backstory=(
        "You write research reports that include cryptographic citations — "
        "not just URLs, but proof bundles that anyone can verify."
    ),
    tools=[proof_tool],
    verbose=True
)

# --- Tasks ---

research_task = Task(
    description=(
        "Research the topic: '{topic}'. "
        "1. Use web_search to find 3-5 relevant sources. "
        "2. Navigate to each source and extract the main content. "
        "3. Take a screenshot of each key page. "
        "4. Summarize the key findings from each source. "
        "Every action is automatically recorded in the audit chain."
    ),
    expected_output=(
        "A structured summary of findings from 3-5 verified sources, "
        "including the URL of each source and a 2-3 sentence summary "
        "of what was found there."
    ),
    agent=researcher
)

report_task = Task(
    description=(
        "Using the research findings provided, write a comprehensive report on '{topic}'. "
        "Structure the report with an executive summary, key findings, and conclusion. "
        "At the end, call conduit_export_proof to export a self-verifiable proof bundle "
        "of all browser actions taken during this research session."
    ),
    expected_output=(
        "A complete research report in Markdown format, ending with "
        "the path to the exported proof bundle and instructions for verification."
    ),
    agent=writer,
    context=[research_task]
)

# --- Crew ---

research_crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, report_task],
    verbose=True
)

result = research_crew.kickoff(inputs={"topic": "cryptographic audit trails in AI agents"})
print(result)
```

After the crew finishes, verify the proof:

```bash
tar xf ~/.cato/proofs/conduit_proof_sess-*.tar.gz
cd session_proof
python verify.py
# Chain OK (18 actions verified)
# Signature OK
```

---

## Compliance Audit Crew Example

For compliance use cases — SOC 2, GDPR, HIPAA — where you need to prove exactly what your automated systems did:

```python
from crewai import Agent, Task, Crew
from tools.conduit_bridge import ConduitBridge

_bridge = ConduitBridge()

auditor = Agent(
    role="Compliance Auditor",
    goal=(
        "Verify compliance requirements on target systems by navigating to "
        "the relevant pages, documenting what was observed, and producing "
        "a cryptographically verifiable evidence bundle."
    ),
    backstory=(
        "You are a compliance auditor who uses Conduit to capture tamper-evident "
        "evidence of system states. Your proof bundles serve as chain-of-custody "
        "documentation for SOC 2, GDPR, and HIPAA audits."
    ),
    tools=[
        ConduitNavigateTool(),
        ConduitExtractMainTool(),
        ConduitScreenshotTool(),
        ConduitEvalTool(),
        ConduitFingerprintTool(),
        ConduitExportProofTool()
    ],
    verbose=True
)

audit_task = Task(
    description=(
        "Perform a compliance check on '{target_url}'. "
        "1. Navigate to the URL. "
        "2. Extract the main content and record what is displayed. "
        "3. Take a screenshot as visual evidence. "
        "4. Use JavaScript eval to check for specific compliance indicators: "
        "   document.cookie, document.title, meta tags (privacy policy link, consent banner). "
        "5. Fingerprint the page for baseline change detection. "
        "6. Export a proof bundle. "
        "The proof bundle is your evidence artifact — it proves what the page showed "
        "at this specific time without requiring trust in your report."
    ),
    expected_output=(
        "A compliance evidence report including: page content summary, "
        "screenshot path, JavaScript evaluation results, page fingerprint, "
        "and proof bundle path with verification instructions."
    ),
    agent=auditor
)

crew = Crew(agents=[auditor], tasks=[audit_task], verbose=True)
result = crew.kickoff(inputs={"target_url": "https://example.com"})
```

---

## Proof Bundle Verification

The proof bundle exports from any Conduit session are self-verifiable:

```bash
# Extract the bundle
tar xf ~/.cato/proofs/conduit_proof_sess-abc123_20260311.tar.gz

# Verify with no dependencies beyond Python stdlib
cd session_proof
python verify.py
```

```
Chain OK (18 actions verified)
Signature OK
```

Bundle contents:

```
session_proof/
├── audit_log.jsonl      # Full hash-chained log (one JSON record per line)
├── manifest.json        # Session metadata + final chain hash
├── public_key.pem       # Ed25519 public key
├── session_sig.txt      # Ed25519 signature over the final chain hash
└── verify.py            # Self-contained verifier — stdlib only, zero dependencies
```

Each record in `audit_log.jsonl` links to the previous one via `prev_hash`. Altering any field — any input, output, or timestamp — breaks the chain. `verify.py` detects it deterministically.

---

## Tool Reference Summary

| Tool Class | Action Wave | Purpose |
|---|---|---|
| `ConduitNavigateTool` | Wave 0 | Navigate to URL, return title |
| `ConduitExtractMainTool` | Wave 2 | Clean Markdown extraction |
| `ConduitScreenshotTool` | Wave 0 | Full-page PNG screenshot |
| `ConduitEvalTool` | Wave 2 | Audited JavaScript execution |
| `ConduitExportProofTool` | Wave 3 | Export signed proof bundle |
| `ConduitMapTool` | Wave 3 | BFS site URL discovery |
| `ConduitCrawlTool` | Wave 3 | Bulk BFS page extraction |
| `ConduitFingerprintTool` | Wave 3 | SHA-256 page fingerprint |
| `ConduitCheckChangedTool` | Wave 3 | Signed change detection |
| `ConduitWebSearchTool` | Wave 6 | Multi-engine search |

---

## Security Notes

- Navigation is restricted to HTTP/HTTPS. No `file://`, `data://`, or `javascript://` schemes.
- RFC-1918 and loopback IPs are blocked — no SSRF via browser automation.
- Sensitive input keys (`password`, `token`, `api_key`, `secret`, `bearer`, and others) are auto-redacted before writing to the audit log.
- BFS crawlers always check `robots.txt` before visiting any URL.

---

## Links

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: https://pypi.org/project/conduit-browser/
- Full action reference: [skills/conduit.md](../../skills/conduit.md)
- Agent marketplace: https://swarmsync.ai
