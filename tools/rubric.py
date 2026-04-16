"""
rubric.py — Rubric evaluation engine for generative AI output verification.

## Rubric Format

A rubric is a plain dict (matching RubricSchema) that declares one or more
predicates to check against a string of generated content.  Every predicate
that appears in the rubric is evaluated; `rubric_pass` is True only when ALL
predicates pass.

Supported predicates:

    min_word_count       int   content.split() count must be >= value
    max_word_count       int   content.split() count must be <= value
    must_contain         list  every string must appear (case-insensitive)
    must_not_contain     list  no string may appear (case-insensitive)
    min_length_chars     int   len(content) must be >= value
    max_length_chars     int   len(content) must be <= value
    language             str   ISO 639-1 code e.g. "en" (requires langdetect)
    content_type_hint    str   "text" | "json" | "html" | "markdown"
    custom_checks        list  sandboxed Python boolean expressions

## Pre-commitment with make_rubric_hash

Call `make_rubric_hash(rubric)` before generating content and store the hex
digest.  After generation, re-hash the same rubric dict and compare — this
proves the rubric was not altered between commitment and evaluation.

    hash_before = make_rubric_hash(rubric)
    content     = generate(...)
    assert make_rubric_hash(rubric) == hash_before  # rubric unchanged
    result      = evaluate_rubric(content, rubric)

## Custom Check Sandbox

Expressions in `custom_checks` run in a restricted namespace.  Available
names: content (str), len, str, int, float, bool, list, dict, re.
Dunder attribute access, imports, and dangerous builtins are blocked at the
AST level before any code executes.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import warnings
from typing import Any

try:
    from typing import TypedDict

    class RubricSchema(TypedDict, total=False):
        min_word_count: int
        max_word_count: int
        must_contain: list[str]
        must_not_contain: list[str]
        min_length_chars: int
        max_length_chars: int
        language: str
        content_type_hint: str
        custom_checks: list[str]

except ImportError:
    RubricSchema = dict  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BLOCKED_CALL_NAMES = frozenset({
    "__import__", "eval", "exec", "open", "compile",
    "getattr", "setattr", "delattr", "globals", "locals",
    "vars", "dir",
})

_SAFE_GLOBALS: dict[str, Any] = {"__builtins__": {}}
_SAFE_LOCALS: dict[str, Any] = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "re": re,
}


def _ast_is_safe(expr: str) -> tuple[bool, str]:
    """Return (True, "") if the expression passes the AST security check,
    or (False, reason) if it should be rejected."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        return False, f"syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "imports are not allowed"

        if isinstance(node, ast.Call):
            func = node.func
            name: str | None = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name in _BLOCKED_CALL_NAMES:
                return False, f"blocked function call: {name}"

        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return False, f"dunder attribute access blocked: {node.attr}"

        # Block walrus operator (:=) — NamedExpr allows rebinding names in
        # local_ns mid-expression (e.g. `(x := len)(content)`).  While the
        # sandbox is ephemeral, walrus assignments are confusing and unnecessary
        # for legitimate rubric checks.
        if isinstance(node, ast.NamedExpr):
            return False, "walrus operator (:=) is not allowed in custom_checks"

    return True, ""


def _eval_custom_check(expr: str, content: str) -> dict:
    """Evaluate a single custom_check expression. Returns a predicate result dict."""
    safe, reason = _ast_is_safe(expr)
    if not safe:
        return {
            "predicate": f"custom_check: {expr!r}",
            "passed": False,
            "reason": f"custom_check rejected: unsafe expression ({reason})",
        }

    try:
        code = compile(expr, "<rubric_check>", "eval")
        local_ns = dict(_SAFE_LOCALS)
        local_ns["content"] = content
        result = eval(code, _SAFE_GLOBALS, local_ns)  # noqa: S307
        passed = bool(result)
    except Exception as exc:
        return {
            "predicate": f"custom_check: {expr!r}",
            "passed": False,
            "reason": f"custom_check error: {exc}",
        }

    status = "PASS" if passed else "FAIL"
    return {
        "predicate": f"custom_check: {expr!r}",
        "passed": passed,
        "reason": f"expression evaluated to {result!r}: {status}",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_rubric(content: str, rubric: dict) -> dict:
    """Evaluate *content* against *rubric* and return a results dict.

    Parameters
    ----------
    content:
        The generated text to evaluate.
    rubric:
        A dict matching RubricSchema.  Unknown keys are silently ignored.

    Returns
    -------
    dict with keys:
        rubric_pass       bool   True only when every predicate passes
        predicate_results list   one entry per evaluated predicate
        content_length    int    len(content)
        word_count        int    len(content.split())
    """
    predicates: list[dict] = []
    word_count = len(content.split())
    content_length = len(content)

    # --- min_word_count ---
    if "min_word_count" in rubric:
        min_wc = int(rubric["min_word_count"])
        passed = word_count >= min_wc
        predicates.append({
            "predicate": "min_word_count",
            "passed": passed,
            "reason": f"word_count={word_count} >= min={min_wc}: {'PASS' if passed else 'FAIL'}",
        })

    # --- max_word_count ---
    if "max_word_count" in rubric:
        max_wc = int(rubric["max_word_count"])
        passed = word_count <= max_wc
        predicates.append({
            "predicate": "max_word_count",
            "passed": passed,
            "reason": f"word_count={word_count} <= max={max_wc}: {'PASS' if passed else 'FAIL'}",
        })

    # --- must_contain ---
    if "must_contain" in rubric:
        content_lower = content.lower()
        for phrase in rubric["must_contain"]:
            found = phrase.lower() in content_lower
            predicates.append({
                "predicate": "must_contain",
                "passed": found,
                "reason": f"'{phrase}' {'found' if found else 'NOT found'}: {'PASS' if found else 'FAIL'}",
            })

    # --- must_not_contain ---
    if "must_not_contain" in rubric:
        content_lower = content.lower()
        for phrase in rubric["must_not_contain"]:
            absent = phrase.lower() not in content_lower
            predicates.append({
                "predicate": "must_not_contain",
                "passed": absent,
                "reason": f"'{phrase}' {'absent' if absent else 'FOUND (not allowed)'}: {'PASS' if absent else 'FAIL'}",
            })

    # --- min_length_chars ---
    if "min_length_chars" in rubric:
        min_ch = int(rubric["min_length_chars"])
        passed = content_length >= min_ch
        predicates.append({
            "predicate": "min_length_chars",
            "passed": passed,
            "reason": f"length={content_length} >= min={min_ch}: {'PASS' if passed else 'FAIL'}",
        })

    # --- max_length_chars ---
    if "max_length_chars" in rubric:
        max_ch = int(rubric["max_length_chars"])
        passed = content_length <= max_ch
        predicates.append({
            "predicate": "max_length_chars",
            "passed": passed,
            "reason": f"length={content_length} <= max={max_ch}: {'PASS' if passed else 'FAIL'}",
        })

    # --- language ---
    if "language" in rubric:
        expected_lang = rubric["language"]
        try:
            import langdetect  # type: ignore[import]
            try:
                detected = langdetect.detect(content)
                passed = detected == expected_lang
                predicates.append({
                    "predicate": "language",
                    "passed": passed,
                    "reason": (
                        f"detected='{detected}', expected='{expected_lang}': "
                        f"{'PASS' if passed else 'FAIL'}"
                    ),
                })
            except Exception as exc:
                predicates.append({
                    "predicate": "language",
                    "passed": True,
                    "reason": f"WARNING: langdetect detection failed ({exc}); check skipped",
                })
        except ImportError:
            warnings.warn(
                "langdetect is not installed; 'language' predicate skipped. "
                "Install with: pip install langdetect",
                stacklevel=2,
            )
            predicates.append({
                "predicate": "language",
                "passed": True,
                "reason": (
                    "WARNING: langdetect not installed; language check skipped "
                    "(install langdetect to enable)"
                ),
            })

    # --- content_type_hint ---
    if "content_type_hint" in rubric:
        hint = rubric["content_type_hint"]
        if hint == "text":
            passed = True
            reason = "content_type_hint='text' always passes: PASS"
        elif hint == "json":
            try:
                json.loads(content)
                passed = True
                reason = "valid JSON: PASS"
            except json.JSONDecodeError as exc:
                passed = False
                reason = f"invalid JSON ({exc}): FAIL"
        elif hint == "html":
            cl = content.lower()
            passed = "<html" in cl or "<!doctype" in cl
            reason = (
                "found <html or <!doctype: PASS"
                if passed
                else "no <html or <!doctype found: FAIL"
            )
        elif hint == "markdown":
            pattern = r"(^#{1,6} |\*\*|__|```|\[.+\]\(.+\))"
            passed = bool(re.search(pattern, content, re.MULTILINE))
            reason = (
                "markdown pattern found: PASS"
                if passed
                else "no markdown pattern found (expected #heading, **bold**, __, ```, or [link](url)): FAIL"
            )
        else:
            passed = True
            reason = f"unknown content_type_hint='{hint}'; check skipped: PASS"

        predicates.append({
            "predicate": "content_type_hint",
            "passed": passed,
            "reason": reason,
        })

    # --- custom_checks ---
    if "custom_checks" in rubric:
        for expr in rubric["custom_checks"]:
            predicates.append(_eval_custom_check(str(expr), content))

    rubric_pass = all(p["passed"] for p in predicates)

    return {
        "rubric_pass": rubric_pass,
        "predicate_results": predicates,
        "content_length": content_length,
        "word_count": word_count,
    }


def make_rubric_hash(rubric: dict) -> str:
    """Return a SHA-256 hex digest of the rubric for pre-commitment.

    The rubric dict is serialised with sorted keys so the hash is stable
    regardless of insertion order.  Store this hash before generating
    content, then re-hash after generation to prove the rubric was not
    modified between commitment and evaluation.
    """
    return hashlib.sha256(json.dumps(rubric, sort_keys=True).encode()).hexdigest()
