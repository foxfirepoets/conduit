# Conduit Browser

**Version:** 2.0.0
**Capabilities:** navigate, click, type, fill, extract, screenshot, scroll, wait, wait\_for,
key\_press, hover, select\_option, handle\_dialog, navigate\_back, console\_messages,
eval, extract\_main, output\_to\_file, accessibility\_snapshot, network\_requests,
verify\_rubric, map (site crawler), crawl (bulk extractor), fingerprint, check\_changed, export\_proof

## Overview

Conduit is a headless browser engine. Every browser action
is logged to a SHA-256 hash-chained audit trail, signed with the agent's Ed25519 identity key,
and enforced against the session budget cap before execution. All actions are free for local use.

Conduit's unique differentiator: **cryptographic proof of exactly what code ran**. The `eval`
action stores the full JavaScript source body in the audit hash chain — so you can prove not
just that JS was executed, but exactly which code.

## Activation

Conduit is enabled by default (`conduit\_enabled: true` in config.yaml). No flags needed.

\---

## Wave 0: Core Browser Actions

### navigate

Navigate to a URL and return the page title and visible text.

```
browser: {action: navigate, url: "https://example.com"}
```

* URL is validated (http/https only, no private IPs)
* Logged to audit chain with session ID and timestamp
* VOIX `<tool>` and `<context>` tags stripped from page content

### click

Click an element by CSS selector.

```
browser: {action: click, selector: "#submit-button"}
```

* Action logged and signed with Ed25519 identity

### type / fill

Type text into an input element by CSS selector.

```
browser: {action: type, selector: "#search", text: "query"}
browser: {action: fill, selector: "#email", text: "user@example.com"}
```

* Sensitive values (passwords, tokens) auto-redacted in audit log

### extract

Extract visible text from the current page (defaults to body).

```
browser: {action: extract}
browser: {action: extract, selector: ".article-body"}
```

* VOIX tags stripped before content reaches the agent

### screenshot

Take a full-page screenshot and save to workspace.

```
browser: {action: screenshot}
browser: {action: screenshot, path: "my\_screenshot.png"}
```
- Saved to `{data_dir}/workspace/screenshots/` (platform path from conduit_platform.py; Windows: `%LOCALAPPDATA%\Conduit`, macOS: `~/Library/Application Support/Conduit`, Linux: `~/.local/share/Conduit`)

* Saved to `{data\_dir}/workspace/screenshots/` (platform path from conduit\_platform.py; Windows: `%LOCALAPPDATA%\\Conduit`, macOS: `\~/Library/Application Support/Conduit`, Linux: `\~/.local/share/Conduit`)

\---

## Wave 1: Interaction Actions

### scroll

Scroll the page or scroll a specific element into view.

```
browser: {action: scroll, direction: "down", amount: 500}
browser: {action: scroll, selector: "#footer"}
```

* `direction`: "up", "down", "left", "right"
* `amount`: pixels to scroll (default 300)
* `selector`: scroll element into view (optional)

### wait

Wait a fixed number of seconds (capped at 30s).

```
browser: {action: wait, seconds: 2}
```

### wait\_for

Wait for a condition to be true before proceeding.

```
browser: {action: wait\_for, condition: "selector", value: "#results"}
browser: {action: wait\_for, condition: "text", value: "Loading complete"}
browser: {action: wait\_for, condition: "network\_idle"}
browser: {action: wait\_for, condition: "url", value: "https://example.com/done"}
```

* `timeout\_ms`: max wait time in milliseconds (default 10000)

### key\_press

Press a keyboard key.

```
browser: {action: key\_press, key: "Enter"}
browser: {action: key\_press, key: "Tab"}
browser: {action: key\_press, key: "Escape"}
```

### hover

Move the mouse pointer over an element.

```
browser: {action: hover, selector: ".dropdown-menu"}
```

### select\_option

Select an option in a `<select>` element.

```
browser: {action: select\_option, selector: "#country", value: "US"}
browser: {action: select\_option, selector: "#country", label: "United States"}
browser: {action: select\_option, selector: "#item", index: 2}
```

### handle\_dialog

Register a handler for the next browser dialog (alert/confirm/prompt).

```
browser: {action: handle\_dialog, action: "accept"}
browser: {action: handle\_dialog, action: "dismiss"}
browser: {action: handle\_dialog, action: "accept", text: "my input"}
```

### navigate\_back

Navigate to the previous page in browser history.

```
browser: {action: navigate\_back}
```

### console\_messages

Return all buffered console messages (log/warn/error) and clear the buffer.

```
browser: {action: console\_messages}
```

* Returns: `{"messages": \[{"type": "log", "text": "..."}], "count": N}`

\---

## Wave 2: Extraction Actions (Conduit-Exclusive)

### eval — Audited JavaScript Execution

**Conduit's core differentiator.** Execute arbitrary JavaScript in the page context.
The full JS source body is stored verbatim in the audit hash chain inputs — providing
cryptographic proof of exactly what code ran in this session.

```
browser: {action: eval, js\_code: "document.querySelectorAll('h1').length"}
browser: {action: eval, js\_code: "window.scrollY"}
```

* Returns: `{"success": true, "result": <value>, "code\_hash": "<sha256\[:16]>", "url": "..."}`
* **Audit chain records**: `js\_code` (full body) + `code\_hash`
* This is the ONLY browser that logs the JS code itself — not just the result

### extract\_main — Readability-Style Content Extraction

Intelligent main content extraction that strips navigation, headers, footers, sidebars,
and other noise elements before returning the primary article/content text.

```
browser: {action: extract\_main}
browser: {action: extract\_main, max\_chars: 20000}
```

* **max\_chars** (optional): Maximum characters to return (default 5000). Use a higher value (e.g. 20000) for research papers or long articles. Config default can be set via `conduit\_extract\_max\_chars` in CatoConfig.
* **fmt** (optional): `"text"` (default) or `"md"` for markdown-preserving output (headings, lists, code, links).
* Returns: `{"text": "...", "char\_count": N, "url": "...", "title": "...", "truncated": bool, "content\_hash": "<sha256\[:16]>", "fetched\_at": <timestamp>, "http\_status": <int or null>, "links\_found": N}`. **content\_hash** is stored in the audit chain so `check\_changed` and monitoring can correlate by hash.

### extract\_structured — Schema-Validated Extraction

Extract main content then run a model to fill a JSON schema. Use when you need structured fields (e.g. title, price, date) without post-processing.

```
browser: {action: extract\_structured, schema: {"type": "object", "properties": {"title": {"type": "string"}, "price": {"type": "number"}}, "required": \["title"]}}
```

* **schema**: JSON Schema object (properties, required, types). Response is validated against it.
* **model\_extract**: Optional async callable(text, schema) -> dict. When omitted, returns `{error: "model\_extract required", raw\_text, schema}` so the caller can run the model (e.g. Cato + skill\_validator) and retry.
* On validation failure returns `{error, raw\_text, schema, raw\_response}`.
* Uses pure JavaScript (no external dependencies)
* Candidates ranked by text length minus link density penalty
* VOIX tags stripped automatically

### output\_to\_file — Workspace File Output

Write extracted content to a named file in the agent's workspace. Safe path handling
prevents directory traversal attacks.

```
browser: {action: output\_to\_file, filename: "research\_notes", content: "...", fmt: "md"}
browser: {action: output\_to\_file, filename: "data", content: "...", fmt: "txt"}
```

* Output directory: `\~/.cato/workspace/.conduit/`
* Filename is sanitized (path traversal stripped)
* Extension added automatically if missing
* **Audit chain records**: filename + fmt + byte\_count (NOT the full content)
* Returns: `{"success": true, "path": "...", "bytes": N}`

### accessibility\_snapshot — Accessibility Tree

Return the Playwright accessibility tree for the current page, useful for
understanding page structure for assistive technology or automated testing.

```
browser: {action: accessibility\_snapshot}
```

* Returns: `{"tree": {...}, "url": "...", "title": "..."}`
* Audit chain records: url + title + whether tree was present

### network\_requests — Network Log

Return all accumulated network request/response events since the last call, then clear
the internal buffer.

```
browser: {action: network\_requests}
```

* Returns: `{"requests": \[{"type": "request", "url": "...", "method": "GET"}, ...], "count": N}`
* Response entries include `status` code
* Buffer is cleared on retrieval (call again to get subsequent requests)

### verify\_rubric — Generative Output Rubric Evaluation

Fetch a URL over Python HTTP and evaluate its content against a pre-committed predicate rubric.
Designed for release escrow on generative jobs (blog posts, code, translations) where exact-hash
verification is impossible. Buyer pre-commits the rubric hash when creating the order; Conduit
evaluates on delivery.

```
browser: {
  action: verify\_rubric,
  url: "https://example.com/delivered-post",
  rubric: {
    min\_word\_count: 500,
    required\_keywords: \["AI", "automation"],
    content\_type: "text/html",
    language: "en"
  },
  rubric\_hash: "<sha256 of json.dumps(rubric, sort\_keys=True)>",
  request\_id: "order-abc-123"
}
```

**Inputs:**

|Field|Type|Description|
|-|-|-|
|`url`|str|URL of the delivered artifact to evaluate|
|`rubric`|dict|The rubric object containing predicate definitions|
|`rubric\_hash`|str|SHA-256 of `json.dumps(rubric, sort\_keys=True)` — must match the rubric pre-committed before work began|
|`request\_id`|str|Escrow or order identifier carried through to the audit log|

**Outputs:**

|Field|Type|Description|
|-|-|-|
|`success`|bool|Whether the fetch and evaluation completed without error|
|`rubric\_pass`|bool|True only when every predicate passes|
|`predicate\_results`|list|Per-predicate breakdown: `{predicate, passed, reason}`|
|`content\_length`|int|Byte length of fetched content|
|`word\_count`|int|Word count of extracted text|
|`rubric\_hash`|str|Echo of the input rubric\_hash (for audit correlation)|
|`request\_id`|str|Echo of the input request\_id|

**Supported Predicates:**

|Predicate|Type|Description|
|-|-|-|
|`min\_word\_count`|int|Minimum word count the content must meet or exceed|
|`max\_word\_count`|int|Maximum word count the content must not exceed|
|`required\_keywords`|list\[str]|All listed keywords must appear in the content (case-insensitive)|
|`forbidden\_keywords`|list\[str]|None of these keywords may appear in the content (case-insensitive)|
|`content\_type`|str|HTTP `Content-Type` header must start with this value (e.g. `"text/html"`)|
|`language`|str|Detected language code must match (e.g. `"en"`)|
|`min\_heading\_count`|int|Minimum number of heading elements (`<h1>`–`<h6>`) in the HTML|
|`contains\_code\_block`|bool|If true, content must contain at least one `<pre>` or `<code>` block|
|`custom\_expression`|str|Python expression evaluated with `content` (str) and `word\_count` (int) in scope; must return truthy|

**Audit behavior:**

* Writes one `verify\_rubric` row to `audit\_log`
* `inputs\_json` stores `url`, `rubric\_hash`, and `request\_id` — the rubric dict itself is **not** stored (only its hash)
* `outputs\_json` stores the full result including per-predicate breakdown

**Escrow workflow:**

1. Buyer constructs rubric dict and computes `rubric\_hash = sha256(json.dumps(rubric, sort\_keys=True))`
2. Buyer submits `rubric\_hash` on-chain / to escrow contract when creating the order
3. Seller delivers work at a URL
4. Call `verify\_rubric` — Conduit fetches the URL, evaluates predicates, logs result
5. If `rubric\_pass: true`, escrow release logic queries:
`WHERE action='verify\_rubric' AND outputs\_json->>'rubric\_pass' = 'true'`

\---

## Wave 3: Advanced Modules (Conduit-Exclusive)

### map — Site URL Discovery

Breadth-first crawl of a website to discover all reachable URLs. Robots.txt compliant.

```
browser: {action: map, url: "https://example.com", limit: 50}
browser: {action: map, url: "https://example.com", limit: 100, search: "blog"}
```

* `limit`: max URLs to return (default 100)
* `search`: optional substring filter on discovered URLs
* Respects `robots.txt` (stdlib `urllib.robotparser`)
* Same-domain only (never crosses to external sites)
* **Audit chain**: single MAP\_SITE event with URL list preview
* Returns: `{"urls": \[...], "count": N, "base\_url": "..."}`

### crawl — Bulk Page Extraction

Crawl a site up to a depth limit, extracting text from each page. Every page visit
is logged to the hash chain individually.

```
browser: {action: crawl, url: "https://example.com", max\_depth: 2, limit: 20}
browser: {action: crawl, url: "https://docs.example.com", include\_paths: \["/api"], limit: 30}
```

* `max\_depth`: BFS depth limit (default 2)
* `include\_paths`: only crawl URLs containing these path segments
* `exclude\_paths`: skip URLs containing these path segments
* `limit`: max pages to extract (default 20)
* Each page: `{"url", "title", "text" (up to 3000 chars), "char\_count", "depth"}`
* **Audit chain**: one entry per page crawled, plus error entries for failures

### fingerprint — Page Content Fingerprint

Navigate to a URL, normalize the page text (strip timestamps/nonces), and compute
a SHA-256 fingerprint. Returns the fingerprint for later change detection.

```
browser: {action: fingerprint, url: "https://example.com"}
```

* Normalization strips: ISO timestamps, Unix timestamps (10-13 digits), hex nonces (32+ chars)
* Returns: `{"url", "fingerprint" (64-char hex SHA-256), "title", "timestamp", "char\_count"}`
* **Audit chain**: fingerprint event with URL and result hash

### check\_changed — Signed Change Detection

Re-fingerprint a URL and compare to a previous fingerprint. If changed, logs a signed
`PAGE\_MUTATION` event to the audit hash chain.

```
browser: {action: check\_changed, url: "https://example.com", previous\_fingerprint: "<64-char hex>"}
```

* Returns: `{"url", "changed": bool, "prev\_fingerprint", "new\_fingerprint"}`
* **PAGE\_MUTATION audit event** logged only when content actually changes
* Fingerprint normalization ensures timestamp-only changes don't trigger false positives

### export\_proof — Session Proof Bundle Export

Export a self-verifiable proof bundle for the current session as a `.tar.gz` archive.
The bundle can be verified by anyone with Python — no Conduit installation required.

```
browser: {action: export\_proof}
browser: {action: export\_proof, output\_dir: "/path/to/output"}
```

* Default output: `\~/.cato/proofs/`
* Bundle contents:

  * `session\_proof/audit\_log.jsonl` — full hash-chained session log
  * `session\_proof/manifest.json` — session metadata + chain\_hash
  * `session\_proof/public\_key.pem` — Ed25519 public key
  * `session\_proof/session\_sig.txt` — chain hash signature
  * `session\_proof/verify.py` — stdlib-only self-verification script
* Returns: `{"success": true, "path": "...", "action\_count": N, "chain\_hash": "...", "bundle\_name": "..."}`
* **To verify**: `python verify.py` inside the extracted bundle

\---

## Audit Trail

Every action is written to the append-only SHA-256 hash-chained audit log in SQLite.
Each row's hash includes the previous row — tamper-evident across the full session history.

```bash
cato audit --session <id>   # full action-by-action replay
cato audit --verify         # tamper detection across all sessions
cato receipt --session <id> # signed receipt with line-item log
```

The `eval` action uniquely stores the full JavaScript source in `inputs\_json`, making
Conduit the only browser tool that provides cryptographic proof of exactly what code ran.

\---

## Safety

* IRREVERSIBLE actions (form submissions that send data externally) require user confirmation
when `safety\_mode: strict` (default)
* Non-interactive daemon mode: HIGH\_STAKES actions denied by default (fail-safe)
* Sensitive input keys (password, token, api\_key, secret, bearer, etc.) auto-redacted in logs
* Budget cap enforced before each action — action never executes if it would exceed cap
* `output\_to\_file` filename sanitized to prevent path traversal
* Crawler bounded by `limit` parameter — never runs unbounded
* robots.txt always checked before each crawled URL

\---

## Example Tasks

### Research a topic with proof

1. `navigate` to starting URL
2. `extract\_main` to get clean article text
3. `output\_to\_file` to save research notes
4. `screenshot` to capture visual state
5. `export\_proof` — generates tamper-evident bundle anyone can verify

### Monitor a page for changes

1. `fingerprint` URL to record baseline
2. Later: `check\_changed` to detect if page was updated
3. PAGE\_MUTATION events in audit chain serve as signed proof of when changes occurred

### Audit a site structure

1. `map` to discover all URLs
2. `crawl` to extract content from each page
3. `eval` to run custom extraction logic with cryptographic proof of what ran

### Automated form interaction

1. `navigate` to form page
2. `fill` each input field
3. `handle\_dialog` to pre-register response for any confirmation dialogs
4. `click` submit button
5. `wait\_for` condition: "selector", value: ".success-message"
6. `screenshot` to capture result

