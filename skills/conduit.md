# Conduit Browser
**Version:** 2.0.0
**Capabilities:** navigate, click, type, fill, extract, screenshot, scroll, wait, wait_for,
key_press, hover, select_option, handle_dialog, navigate_back, console_messages,
eval, extract_main, output_to_file, accessibility_snapshot, network_requests,
verify_rubric, map (site crawler), crawl (bulk extractor), fingerprint, check_changed, export_proof

## Overview
Conduit is Cato's built-in headless browser engine — enabled by default. Every browser action
is logged to a SHA-256 hash-chained audit trail, signed with the agent's Ed25519 identity key,
and enforced against the session budget cap before execution. All actions are free for local use.

Conduit's unique differentiator: **cryptographic proof of exactly what code ran**. The `eval`
action stores the full JavaScript source body in the audit hash chain — so you can prove not
just that JS was executed, but exactly which code.

## Activation
Conduit is enabled by default (`conduit_enabled: true` in config.yaml). No flags needed.

---

## Wave 0: Core Browser Actions

### navigate
Navigate to a URL and return the page title and visible text.
```
browser: {action: navigate, url: "https://example.com"}
```
- URL is validated (http/https only, no private IPs)
- Logged to audit chain with session ID and timestamp
- VOIX `<tool>` and `<context>` tags stripped from page content

### click
Click an element by CSS selector.
```
browser: {action: click, selector: "#submit-button"}
```
- Action logged and signed with Ed25519 identity

### type / fill
Type text into an input element by CSS selector.
```
browser: {action: type, selector: "#search", text: "query"}
browser: {action: fill, selector: "#email", text: "user@example.com"}
```
- Sensitive values (passwords, tokens) auto-redacted in audit log

### extract
Extract visible text from the current page (defaults to body).
```
browser: {action: extract}
browser: {action: extract, selector: ".article-body"}
```
- VOIX tags stripped before content reaches the agent

### screenshot
Take a full-page screenshot and save to workspace.
```
browser: {action: screenshot}
browser: {action: screenshot, path: "my_screenshot.png"}
```
- Saved to `{data_dir}/workspace/screenshots/` (platform path from conduit_platform.py; Windows: `%LOCALAPPDATA%\Conduit`, macOS: `~/Library/Application Support/Conduit`, Linux: `~/.local/share/Conduit`)

---

## Wave 1: Interaction Actions

### scroll
Scroll the page or scroll a specific element into view.
```
browser: {action: scroll, direction: "down", amount: 500}
browser: {action: scroll, selector: "#footer"}
```
- `direction`: "up", "down", "left", "right"
- `amount`: pixels to scroll (default 300)
- `selector`: scroll element into view (optional)

### wait
Wait a fixed number of seconds (capped at 30s).
```
browser: {action: wait, seconds: 2}
```

### wait_for
Wait for a condition to be true before proceeding.
```
browser: {action: wait_for, condition: "selector", value: "#results"}
browser: {action: wait_for, condition: "text", value: "Loading complete"}
browser: {action: wait_for, condition: "network_idle"}
browser: {action: wait_for, condition: "url", value: "https://example.com/done"}
```
- `timeout_ms`: max wait time in milliseconds (default 10000)

### key_press
Press a keyboard key.
```
browser: {action: key_press, key: "Enter"}
browser: {action: key_press, key: "Tab"}
browser: {action: key_press, key: "Escape"}
```

### hover
Move the mouse pointer over an element.
```
browser: {action: hover, selector: ".dropdown-menu"}
```

### select_option
Select an option in a `<select>` element.
```
browser: {action: select_option, selector: "#country", value: "US"}
browser: {action: select_option, selector: "#country", label: "United States"}
browser: {action: select_option, selector: "#item", index: 2}
```

### handle_dialog
Register a handler for the next browser dialog (alert/confirm/prompt).
```
browser: {action: handle_dialog, action: "accept"}
browser: {action: handle_dialog, action: "dismiss"}
browser: {action: handle_dialog, action: "accept", text: "my input"}
```

### navigate_back
Navigate to the previous page in browser history.
```
browser: {action: navigate_back}
```

### console_messages
Return all buffered console messages (log/warn/error) and clear the buffer.
```
browser: {action: console_messages}
```
- Returns: `{"messages": [{"type": "log", "text": "..."}], "count": N}`

---

## Wave 2: Extraction Actions (Conduit-Exclusive)

### eval — Audited JavaScript Execution
**Conduit's core differentiator.** Execute arbitrary JavaScript in the page context.
The full JS source body is stored verbatim in the audit hash chain inputs — providing
cryptographic proof of exactly what code ran in this session.

```
browser: {action: eval, js_code: "document.querySelectorAll('h1').length"}
browser: {action: eval, js_code: "window.scrollY"}
```
- Returns: `{"success": true, "result": <value>, "code_hash": "<sha256[:16]>", "url": "..."}`
- **Audit chain records**: `js_code` (full body) + `code_hash`
- This is the ONLY browser that logs the JS code itself — not just the result

### extract_main — Readability-Style Content Extraction
Intelligent main content extraction that strips navigation, headers, footers, sidebars,
and other noise elements before returning the primary article/content text.

```
browser: {action: extract_main}
browser: {action: extract_main, max_chars: 20000}
```
- **max_chars** (optional): Maximum characters to return (default 5000). Use a higher value (e.g. 20000) for research papers or long articles. Config default can be set via `conduit_extract_max_chars` in CatoConfig.
- **fmt** (optional): `"text"` (default) or `"md"` for markdown-preserving output (headings, lists, code, links).
- Returns: `{"text": "...", "char_count": N, "url": "...", "title": "...", "truncated": bool, "content_hash": "<sha256[:16]>", "fetched_at": <timestamp>, "http_status": <int or null>, "links_found": N}`. **content_hash** is stored in the audit chain so `check_changed` and monitoring can correlate by hash.

### extract_structured — Schema-Validated Extraction
Extract main content then run a model to fill a JSON schema. Use when you need structured fields (e.g. title, price, date) without post-processing.
```
browser: {action: extract_structured, schema: {"type": "object", "properties": {"title": {"type": "string"}, "price": {"type": "number"}}, "required": ["title"]}}
```
- **schema**: JSON Schema object (properties, required, types). Response is validated against it.
- **model_extract**: Optional async callable(text, schema) -> dict. When omitted, returns `{error: "model_extract required", raw_text, schema}` so the caller can run the model (e.g. Cato + skill_validator) and retry.
- On validation failure returns `{error, raw_text, schema, raw_response}`.
- Uses pure JavaScript (no external dependencies)
- Candidates ranked by text length minus link density penalty
- VOIX tags stripped automatically

### output_to_file — Workspace File Output
Write extracted content to a named file in the agent's workspace. Safe path handling
prevents directory traversal attacks.

```
browser: {action: output_to_file, filename: "research_notes", content: "...", fmt: "md"}
browser: {action: output_to_file, filename: "data", content: "...", fmt: "txt"}
```
- Output directory: `~/.cato/workspace/.conduit/`
- Filename is sanitized (path traversal stripped)
- Extension added automatically if missing
- **Audit chain records**: filename + fmt + byte_count (NOT the full content)
- Returns: `{"success": true, "path": "...", "bytes": N}`

### accessibility_snapshot — Accessibility Tree
Return the Playwright accessibility tree for the current page, useful for
understanding page structure for assistive technology or automated testing.

```
browser: {action: accessibility_snapshot}
```
- Returns: `{"tree": {...}, "url": "...", "title": "..."}`
- Audit chain records: url + title + whether tree was present

### network_requests — Network Log
Return all accumulated network request/response events since the last call, then clear
the internal buffer.

```
browser: {action: network_requests}
```
- Returns: `{"requests": [{"type": "request", "url": "...", "method": "GET"}, ...], "count": N}`
- Response entries include `status` code
- Buffer is cleared on retrieval (call again to get subsequent requests)

### verify_rubric — Generative Output Rubric Evaluation
Fetch a URL over Python HTTP and evaluate its content against a pre-committed predicate rubric.
Designed for release escrow on generative jobs (blog posts, code, translations) where exact-hash
verification is impossible. Buyer pre-commits the rubric hash when creating the order; Conduit
evaluates on delivery.

```
browser: {
  action: verify_rubric,
  url: "https://example.com/delivered-post",
  rubric: {
    min_word_count: 500,
    required_keywords: ["AI", "automation"],
    content_type: "text/html",
    language: "en"
  },
  rubric_hash: "<sha256 of json.dumps(rubric, sort_keys=True)>",
  request_id: "order-abc-123"
}
```

**Inputs:**

| Field | Type | Description |
|-------|------|-------------|
| `url` | str | URL of the delivered artifact to evaluate |
| `rubric` | dict | The rubric object containing predicate definitions |
| `rubric_hash` | str | SHA-256 of `json.dumps(rubric, sort_keys=True)` — must match the rubric pre-committed before work began |
| `request_id` | str | Escrow or order identifier carried through to the audit log |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the fetch and evaluation completed without error |
| `rubric_pass` | bool | True only when every predicate passes |
| `predicate_results` | list | Per-predicate breakdown: `{predicate, passed, reason}` |
| `content_length` | int | Byte length of fetched content |
| `word_count` | int | Word count of extracted text |
| `rubric_hash` | str | Echo of the input rubric_hash (for audit correlation) |
| `request_id` | str | Echo of the input request_id |

**Supported Predicates:**

| Predicate | Type | Description |
|-----------|------|-------------|
| `min_word_count` | int | Minimum word count the content must meet or exceed |
| `max_word_count` | int | Maximum word count the content must not exceed |
| `required_keywords` | list[str] | All listed keywords must appear in the content (case-insensitive) |
| `forbidden_keywords` | list[str] | None of these keywords may appear in the content (case-insensitive) |
| `content_type` | str | HTTP `Content-Type` header must start with this value (e.g. `"text/html"`) |
| `language` | str | Detected language code must match (e.g. `"en"`) |
| `min_heading_count` | int | Minimum number of heading elements (`<h1>`–`<h6>`) in the HTML |
| `contains_code_block` | bool | If true, content must contain at least one `<pre>` or `<code>` block |
| `custom_expression` | str | Python expression evaluated with `content` (str) and `word_count` (int) in scope; must return truthy |

**Audit behavior:**
- Writes one `verify_rubric` row to `audit_log`
- `inputs_json` stores `url`, `rubric_hash`, and `request_id` — the rubric dict itself is **not** stored (only its hash)
- `outputs_json` stores the full result including per-predicate breakdown

**Escrow workflow:**
1. Buyer constructs rubric dict and computes `rubric_hash = sha256(json.dumps(rubric, sort_keys=True))`
2. Buyer submits `rubric_hash` on-chain / to escrow contract when creating the order
3. Seller delivers work at a URL
4. Call `verify_rubric` — Conduit fetches the URL, evaluates predicates, logs result
5. If `rubric_pass: true`, escrow release logic queries:
   `WHERE action='verify_rubric' AND outputs_json->>'rubric_pass' = 'true'`

---

## Wave 3: Advanced Modules (Conduit-Exclusive)

### map — Site URL Discovery
Breadth-first crawl of a website to discover all reachable URLs. Robots.txt compliant.

```
browser: {action: map, url: "https://example.com", limit: 50}
browser: {action: map, url: "https://example.com", limit: 100, search: "blog"}
```
- `limit`: max URLs to return (default 100)
- `search`: optional substring filter on discovered URLs
- Respects `robots.txt` (stdlib `urllib.robotparser`)
- Same-domain only (never crosses to external sites)
- **Audit chain**: single MAP_SITE event with URL list preview
- Returns: `{"urls": [...], "count": N, "base_url": "..."}`

### crawl — Bulk Page Extraction
Crawl a site up to a depth limit, extracting text from each page. Every page visit
is logged to the hash chain individually.

```
browser: {action: crawl, url: "https://example.com", max_depth: 2, limit: 20}
browser: {action: crawl, url: "https://docs.example.com", include_paths: ["/api"], limit: 30}
```
- `max_depth`: BFS depth limit (default 2)
- `include_paths`: only crawl URLs containing these path segments
- `exclude_paths`: skip URLs containing these path segments
- `limit`: max pages to extract (default 20)
- Each page: `{"url", "title", "text" (up to 3000 chars), "char_count", "depth"}`
- **Audit chain**: one entry per page crawled, plus error entries for failures

### fingerprint — Page Content Fingerprint
Navigate to a URL, normalize the page text (strip timestamps/nonces), and compute
a SHA-256 fingerprint. Returns the fingerprint for later change detection.

```
browser: {action: fingerprint, url: "https://example.com"}
```
- Normalization strips: ISO timestamps, Unix timestamps (10-13 digits), hex nonces (32+ chars)
- Returns: `{"url", "fingerprint" (64-char hex SHA-256), "title", "timestamp", "char_count"}`
- **Audit chain**: fingerprint event with URL and result hash

### check_changed — Signed Change Detection
Re-fingerprint a URL and compare to a previous fingerprint. If changed, logs a signed
`PAGE_MUTATION` event to the audit hash chain.

```
browser: {action: check_changed, url: "https://example.com", previous_fingerprint: "<64-char hex>"}
```
- Returns: `{"url", "changed": bool, "prev_fingerprint", "new_fingerprint"}`
- **PAGE_MUTATION audit event** logged only when content actually changes
- Fingerprint normalization ensures timestamp-only changes don't trigger false positives

### export_proof — Session Proof Bundle Export
Export a self-verifiable proof bundle for the current session as a `.tar.gz` archive.
The bundle can be verified by anyone with Python — no Conduit installation required.

```
browser: {action: export_proof}
browser: {action: export_proof, output_dir: "/path/to/output"}
```
- Default output: `~/.cato/proofs/`
- Bundle contents:
  - `session_proof/audit_log.jsonl` — full hash-chained session log
  - `session_proof/manifest.json` — session metadata + chain_hash
  - `session_proof/public_key.pem` — Ed25519 public key
  - `session_proof/session_sig.txt` — chain hash signature
  - `session_proof/verify.py` — stdlib-only self-verification script
- Returns: `{"success": true, "path": "...", "action_count": N, "chain_hash": "...", "bundle_name": "..."}`
- **To verify**: `python verify.py` inside the extracted bundle

---

## Audit Trail
Every action is written to the append-only SHA-256 hash-chained audit log in SQLite.
Each row's hash includes the previous row — tamper-evident across the full session history.

```bash
cato audit --session <id>   # full action-by-action replay
cato audit --verify         # tamper detection across all sessions
cato receipt --session <id> # signed receipt with line-item log
```

The `eval` action uniquely stores the full JavaScript source in `inputs_json`, making
Conduit the only browser tool that provides cryptographic proof of exactly what code ran.

---

## Safety
- IRREVERSIBLE actions (form submissions that send data externally) require user confirmation
  when `safety_mode: strict` (default)
- Non-interactive daemon mode: HIGH_STAKES actions denied by default (fail-safe)
- Sensitive input keys (password, token, api_key, secret, bearer, etc.) auto-redacted in logs
- Budget cap enforced before each action — action never executes if it would exceed cap
- `output_to_file` filename sanitized to prevent path traversal
- Crawler bounded by `limit` parameter — never runs unbounded
- robots.txt always checked before each crawled URL

---

## Example Tasks

### Research a topic with proof
1. `navigate` to starting URL
2. `extract_main` to get clean article text
3. `output_to_file` to save research notes
4. `screenshot` to capture visual state
5. `export_proof` — generates tamper-evident bundle anyone can verify

### Monitor a page for changes
1. `fingerprint` URL to record baseline
2. Later: `check_changed` to detect if page was updated
3. PAGE_MUTATION events in audit chain serve as signed proof of when changes occurred

### Audit a site structure
1. `map` to discover all URLs
2. `crawl` to extract content from each page
3. `eval` to run custom extraction logic with cryptographic proof of what ran

### Automated form interaction
1. `navigate` to form page
2. `fill` each input field
3. `handle_dialog` to pre-register response for any confirmation dialogs
4. `click` submit button
5. `wait_for` condition: "selector", value: ".success-message"
6. `screenshot` to capture result
