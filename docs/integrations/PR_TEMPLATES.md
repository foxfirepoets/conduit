# PR Templates: Conduit Integrations

Copy-paste-ready PR descriptions for submitting Conduit to LangChain and CrewAI upstream repositories.

---

## 1. langchain-community — Add Conduit Browser Tool

**Target repository:** `langchain-ai/langchain`
**Target directory:** `libs/community/langchain_community/tools/`
**Branch naming suggestion:** `feat/add-conduit-browser-tool`

---

### PR Title

```
Add Conduit browser tool with cryptographic audit trails
```

---

### PR Body

```markdown
## Summary

This PR adds Conduit as a community browser tool for LangChain agents.

Conduit is an open-source headless browser (MIT license) that writes every agent browser action — every navigate, click, JavaScript eval, and extraction — to a SHA-256 hash-chained audit log signed with an Ed25519 identity key. At any point, the agent can export a self-verifiable proof bundle that anyone can verify using only Python's standard library.

**What Conduit adds that no existing LangChain browser tool provides:**

- SHA-256 hash-chained audit log — every action is tamper-evident
- Ed25519-signed session proofs — cryptographic identity for the executing agent
- Self-verifiable proof bundles — verifiable by anyone, zero dependencies, no Conduit required
- JavaScript source stored in the chain — not just that JS ran, but exactly which code
- Sensitive input auto-redaction — passwords, tokens, API keys never appear in the audit log
- Stealth browser built on Patchright (anti-bot detection resistant)
- Robots.txt compliant BFS site crawler built-in
- Signed page change detection (SHA-256 fingerprinting)

This is not a feature addition to an existing tool — it is a fundamentally different trust model for browser automation.

## Installation

```bash
pip install conduit-browser
python -m patchright install chromium
```

## Usage

```python
import asyncio
from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain import hub
from tools.conduit_bridge import ConduitBridge

bridge = ConduitBridge()

navigate_tool = Tool(
    name="conduit_navigate",
    description=(
        "Navigate to a URL with a cryptographic audit trail. "
        "Every action is SHA-256 hash-chained and Ed25519-signed. "
        "Input: a URL string (must start with http:// or https://)."
    ),
    func=lambda url: asyncio.run(
        bridge.execute({"action": "navigate", "url": url})
    ).get("title", url)
)

extract_tool = Tool(
    name="conduit_extract",
    description="Extract main article content from the current page. Strips nav/ads/footers.",
    func=lambda _: asyncio.run(
        bridge.execute({"action": "extract_main", "fmt": "md"})
    ).get("text", "")
)

proof_tool = Tool(
    name="conduit_export_proof",
    description=(
        "Export a self-verifiable proof bundle of all browser actions in this session. "
        "Bundle includes full hash-chained log, Ed25519 signature, and verify.py."
    ),
    func=lambda _: str(asyncio.run(bridge.execute({"action": "export_proof"})))
)

llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [navigate_tool, extract_tool, proof_tool]
prompt = hub.pull("hwchase17/react")
agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({
    "input": "Research https://example.com and export a proof bundle of the session."
})
```

Verify the proof without Conduit:

```bash
tar xf ~/.cato/proofs/conduit_proof_sess-*.tar.gz
cd session_proof
python verify.py
# Chain OK (3 actions verified)
# Signature OK
```

## Test Plan

- [ ] `pip install conduit-browser` succeeds on Python 3.10, 3.11, 3.12
- [ ] `python -m patchright install chromium` downloads browser successfully
- [ ] `ConduitBridge` initializes without errors
- [ ] `navigate` action returns page title
- [ ] `extract_main` returns Markdown content
- [ ] `export_proof` creates a `.tar.gz` bundle at `~/.cato/proofs/`
- [ ] `python verify.py` inside extracted bundle prints "Chain OK" and "Signature OK"
- [ ] Agent executor runs end-to-end with the three example tools
- [ ] Sensitive inputs (passwords) are redacted in `audit_log.jsonl`
- [ ] Private IP navigation is blocked (returns error, does not navigate)

## Links

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: https://pypi.org/project/conduit-browser/
- Integration guide: https://github.com/bkauto3/Conduit/blob/main/docs/integrations/langchain-integration.md
- License: MIT
```

---

## 2. crewai-tools — Add Conduit Auditable Browser Tool

**Target repository:** `joaomdmoura/crewAI-tools`
**Target directory:** `crewai_tools/tools/conduit_browser_tool/`
**Branch naming suggestion:** `feat/add-conduit-browser-tool`

---

### PR Title

```
Add Conduit: auditable browser tool with proof bundles
```

---

### PR Body

```markdown
## Summary

This PR adds Conduit as a browser tool for CrewAI agents.

Conduit is an open-source headless browser (MIT license) that provides cryptographic audit trails for every browser action an agent takes. Every navigate, extract, JavaScript evaluation, and form interaction is written to a SHA-256 hash-chained log signed with an Ed25519 key. At the end of any task, the agent can export a self-verifiable proof bundle — a `.tar.gz` file that anyone can verify using only Python's standard library, with no Conduit installation required.

**What Conduit adds that no existing CrewAI browser tool provides:**

- SHA-256 hash-chained audit log — tamper-evident record of every agent action
- Ed25519-signed session proofs — cryptographic identity tied to the executing agent
- Self-verifiable proof bundles — portable evidence anyone can verify, zero dependencies
- JavaScript source stored verbatim in the hash chain — proof of exactly what code ran
- Sensitive input auto-redaction — passwords and tokens never appear in the audit log
- Stealth browser (Patchright) — anti-bot detection resistant
- Robots.txt compliant BFS crawler built-in
- Signed page change detection with SHA-256 fingerprinting

This matters for compliance automation, AI agent accountability, research with verifiable citations, and legal evidence capture.

## Installation

```bash
pip install conduit-browser crewai crewai-tools
python -m patchright install chromium
```

## Usage

```python
from crewai_tools import BaseTool
from tools.conduit_bridge import ConduitBridge
import asyncio

_bridge = ConduitBridge()


class ConduitNavigateTool(BaseTool):
    name: str = "Conduit Navigate"
    description: str = (
        "Navigate to a URL with a cryptographic audit trail. "
        "Every action is SHA-256 hash-chained and Ed25519-signed. "
        "Input: a full URL (http:// or https:// only)."
    )

    def _run(self, url: str) -> str:
        result = asyncio.run(_bridge.execute({"action": "navigate", "url": url}))
        return f"Navigated to: {result.get('title', url)}"


class ConduitExtractMainTool(BaseTool):
    name: str = "Conduit Extract Main Content"
    description: str = (
        "Extract main article content from the current page. "
        "Strips nav, ads, headers, footers. Returns Markdown."
    )

    def _run(self, _: str = "") -> str:
        result = asyncio.run(
            _bridge.execute({"action": "extract_main", "fmt": "md"})
        )
        return result.get("text", "No content extracted.")


class ConduitExportProofTool(BaseTool):
    name: str = "Conduit Export Proof"
    description: str = (
        "Export a self-verifiable proof bundle of all browser actions in this session. "
        "Bundle includes full hash-chained log, Ed25519 signature, and verify.py. "
        "No input required."
    )

    def _run(self, _: str = "") -> str:
        result = asyncio.run(_bridge.execute({"action": "export_proof"}))
        return (
            f"Proof bundle: {result.get('path', 'unknown')}\n"
            f"Actions: {result.get('action_count', '?')}\n"
            f"Chain hash: {result.get('chain_hash', '?')}\n"
            f"Verify: tar xf <bundle> && cd session_proof && python verify.py"
        )


# Example crew using Conduit for audited web research
from crewai import Agent, Task, Crew

researcher = Agent(
    role="Research Specialist",
    goal="Research topics with cryptographically verifiable browser sessions.",
    backstory="You produce research with tamper-evident source citations.",
    tools=[ConduitNavigateTool(), ConduitExtractMainTool(), ConduitExportProofTool()],
    verbose=True
)

task = Task(
    description=(
        "Research {topic}: navigate to 2-3 sources, extract content, "
        "then export a proof bundle."
    ),
    expected_output="Research summary with proof bundle path and verification instructions.",
    agent=researcher
)

crew = Crew(agents=[researcher], tasks=[task], verbose=True)
result = crew.kickoff(inputs={"topic": "cryptographic audit trails"})
```

Verify the proof:

```bash
tar xf ~/.cato/proofs/conduit_proof_sess-*.tar.gz
cd session_proof
python verify.py
# Chain OK (6 actions verified)
# Signature OK
```

## Files Added

```
crewai_tools/tools/conduit_browser_tool/
├── __init__.py
├── conduit_navigate_tool.py
├── conduit_extract_tool.py
├── conduit_screenshot_tool.py
├── conduit_eval_tool.py
├── conduit_crawl_tool.py
├── conduit_search_tool.py
└── conduit_proof_tool.py
```

## Test Plan

- [ ] `pip install conduit-browser crewai crewai-tools` succeeds on Python 3.10+
- [ ] `ConduitBridge` initializes without errors
- [ ] `ConduitNavigateTool._run(url)` returns page title
- [ ] `ConduitExtractMainTool._run("")` returns Markdown content
- [ ] `ConduitExportProofTool._run("")` creates `.tar.gz` bundle
- [ ] `python verify.py` inside extracted bundle prints "Chain OK" and "Signature OK"
- [ ] Full crew runs end-to-end: researcher navigates, extracts, exports proof
- [ ] Sensitive inputs are auto-redacted in `audit_log.jsonl`
- [ ] RFC-1918 IP navigation is blocked

## Links

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: https://pypi.org/project/conduit-browser/
- Integration guide: https://github.com/bkauto3/Conduit/blob/main/docs/integrations/crewai-integration.md
- License: MIT
```

---

## 3. LangChain Docs — Add Conduit to Integrations Page

**Target repository:** `langchain-ai/langchain`
**Target directory:** `docs/docs/integrations/tools/`
**Branch naming suggestion:** `docs/add-conduit-browser-integration`

---

### PR Title

```
docs: Add Conduit browser integration
```

---

### PR Body

```markdown
## Summary

This PR adds Conduit to the LangChain integrations documentation.

Conduit is an open-source headless browser tool that provides SHA-256 hash-chained audit trails and Ed25519-signed proof bundles for every browser action an agent takes. It is the only LangChain browser tool that gives agents cryptographic accountability — a portable proof of exactly what they did that anyone can verify.

**New page:** `docs/docs/integrations/tools/conduit.mdx`

## What Conduit Is

Conduit wraps Patchright (stealth Playwright fork) with a two-layer write path: every action writes atomically to both a billing ledger and a SHA-256 hash-chained audit log. At any point, the agent can export a self-verifiable `.tar.gz` proof bundle containing the full log, the Ed25519 signature, and a zero-dependency `verify.py`.

**Key differentiators vs. other browser tools:**

| Feature | Conduit | playwright-mcp | browser-use |
|---|---|---|---|
| Hash-chained audit log | Yes | No | No |
| Ed25519-signed proofs | Yes | No | No |
| Self-verifiable bundles | Yes | No | No |
| JS source in audit chain | Yes | No | No |

## Documentation Added

The new page covers:
- Why use Conduit (audit trails for agent accountability)
- Installation (`pip install conduit-browser`)
- Quick start with AgentExecutor (3 tools)
- Full tool listing (all action waves)
- Proof bundle verification walkthrough
- MCP server configuration alternative

## Test Plan

- [ ] MDX renders correctly in docs site
- [ ] Code examples are syntactically valid Python
- [ ] Links to GitHub and PyPI are correct
- [ ] Page appears in the integrations index

## Links

- GitHub: https://github.com/bkauto3/Conduit
- PyPI: https://pypi.org/project/conduit-browser/
- Full integration guide: https://github.com/bkauto3/Conduit/blob/main/docs/integrations/langchain-integration.md
- License: MIT
```

---

## Submission Checklist

Before submitting any of these PRs:

- [ ] Fork the target repository
- [ ] Create a branch from `main` (not from an existing feature branch)
- [ ] Add the implementation files (not just documentation)
- [ ] Run the repository's existing test suite locally and confirm it passes
- [ ] Add tests for the new tool following the repository's existing test patterns
- [ ] Verify `pip install conduit-browser` works in a clean virtual environment
- [ ] Verify the proof bundle verify step works end-to-end
- [ ] Check that the PR title is under 70 characters
- [ ] Link this repository (https://github.com/bkauto3/Conduit) in the PR body

## Notes on Async Handling

LangChain `Tool.func` expects a synchronous callable. CrewAI `BaseTool._run` is also synchronous. Both integrations use `asyncio.run()` to bridge into Conduit's async API. This is the correct pattern for these frameworks — see the LangChain docs on [async tools](https://python.langchain.com/docs/how_to/custom_tools/) for context.

If the target repository prefers native async support, Conduit's `ConduitBridge.execute()` is a native `async def` coroutine and can be called directly with `await` in async tool implementations.
