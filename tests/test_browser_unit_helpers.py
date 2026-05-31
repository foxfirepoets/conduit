from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cato.tools.browser import BrowserTool, ProxyConfig, _html_to_markdown, _parse_vtt


class TestHtmlToMarkdown:
    def test_html_to_markdown_strips_unsafe_tags_and_converts_structure(self):
        html = """
        <html>
          <head>
            <style>.hidden { display: none; }</style>
            <script>alert('x')</script>
          </head>
          <body>
            <h1>Title</h1>
            <p>Hello <a href="https://example.com">world</a></p>
            <ul><li>First</li><li>Second</li></ul>
            <pre>code sample</pre>
          </body>
        </html>
        """

        result = _html_to_markdown(html)

        assert "<script" not in result.lower(), f"script tags should be removed, got: {result!r}"
        assert "alert('x')" not in result, f"script contents should be removed, got: {result!r}"
        assert "# Title" in result, f"heading should be converted to markdown, got: {result!r}"
        assert "[world](https://example.com)" in result, f"links should be converted, got: {result!r}"
        assert "- First" in result and "- Second" in result, f"list items should become markdown bullets, got: {result!r}"
        assert "```" in result and "code sample" in result, f"pre blocks should become fenced code, got: {result!r}"

    def test_html_to_markdown_decodes_entities_and_strips_remaining_tags(self):
        html = "<p>Fish &amp; Chips&nbsp;&lt;fresh&gt;</p><div><span>done</span></div>"

        result = _html_to_markdown(html)

        assert "Fish & Chips <fresh>" in result, f"HTML entities should be decoded, got: {result!r}"
        assert "<div>" not in result and "<span>" not in result, f"remaining HTML tags should be stripped, got: {result!r}"


class TestProxyConfigHelpers:
    def test_proxy_config_from_mapping_and_to_public_dict(self):
        cfg = ProxyConfig.from_mapping(
            {
                "host": "proxy.example.com",
                "port": "3128",
                "username": "alice",
                "password": "secret",
                "protocol": "socks5",
            }
        )

        assert cfg.host == "proxy.example.com", f"host should be copied from payload, got: {cfg.host!r}"
        assert cfg.port == 3128, f"port should be coerced to int, got: {cfg.port!r}"
        assert cfg.server_url == "socks5://proxy.example.com:3128", f"server_url should include protocol, host, and port, got: {cfg.server_url!r}"
        assert cfg.to_public_dict() == {
            "host": "proxy.example.com",
            "port": 3128,
            "protocol": "socks5",
            "has_auth": True,
        }, f"public dict should omit secrets and expose auth presence, got: {cfg.to_public_dict()!r}"

    def test_coerce_proxy_config_preserves_instance_and_handles_none(self):
        cfg = ProxyConfig(host="proxy.example.com", port=8080)

        assert BrowserTool._coerce_proxy_config(cfg) is cfg, "existing ProxyConfig instances should be returned unchanged"
        assert BrowserTool._coerce_proxy_config(None) is None, "None proxy config should remain None"


class TestPrivateIpGuards:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("file:///tmp/test.html", "Blocked URL scheme: file"),
            ("http://127.0.0.1/admin", "Blocked internal IP: 127.0.0.1"),
        ],
    )
    def test_block_private_ip_rejects_unsafe_literals_and_schemes(self, url, expected):
        with pytest.raises(ValueError, match=expected):
            BrowserTool._block_private_ip(url)

    def test_block_private_ip_rejects_hostname_that_resolves_to_private_ip(self, monkeypatch):
        def fake_getaddrinfo(host, port):
            return [(None, None, None, None, ("10.0.0.7", 0))]

        monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)

        with pytest.raises(ValueError, match=r"Blocked internal IP resolved from hostname: example\.test -> 10\.0\.0\.7"):
            BrowserTool._block_private_ip("https://example.test/path")

    def test_block_private_ip_allows_public_ip_and_ignores_dns_failures(self, monkeypatch):
        def failing_getaddrinfo(host, port):
            raise OSError("dns unavailable")

        monkeypatch.setattr("socket.getaddrinfo", failing_getaddrinfo)

        BrowserTool._block_private_ip("https://8.8.8.8/")
        BrowserTool._block_private_ip("https://public.example/")

    def test_block_private_ip_by_hostname_rejects_dns_rebinding(self, monkeypatch, tmp_path):
        tool = BrowserTool(data_dir=tmp_path)

        def fake_getaddrinfo(host, port):
            return [(None, None, None, None, ("192.168.1.20", 0))]

        monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)

        with pytest.raises(ValueError, match=r"DNS rebinding detected: rebinding\.test resolved to internal IP 192\.168\.1\.20"):
            tool._block_private_ip_by_hostname("rebinding.test")

    def test_block_private_ip_by_hostname_ignores_dns_failures(self, monkeypatch, tmp_path):
        tool = BrowserTool(data_dir=tmp_path)

        def failing_getaddrinfo(host, port):
            raise OSError("dns unavailable")

        monkeypatch.setattr("socket.getaddrinfo", failing_getaddrinfo)

        tool._block_private_ip_by_hostname("public.example")


class TestElementReferenceHelpers:
    def test_build_ref_selector_prefers_role_specific_selectors(self):
        selector = BrowserTool._build_ref_selector({"role": "button", "name": "Submit"})

        assert selector == "button:has-text('Submit')", f"button roles should map to button selectors, got: {selector!r}"

    def test_build_ref_selector_falls_back_to_role_and_label(self):
        selector = BrowserTool._build_ref_selector({"role": "dialog", "name": "Settings"})

        assert selector == "[role='dialog'][aria-label='Settings']", f"unknown roles should fall back to role+aria-label selectors, got: {selector!r}"

    def test_build_ref_selector_returns_none_without_role_or_name(self):
        assert BrowserTool._build_ref_selector({"role": "button"}) is None, "missing node name should prevent selector generation"
        assert BrowserTool._build_ref_selector({"name": "Submit"}) is None, "missing role should prevent selector generation"

    def test_walk_and_assign_refs_recurses_and_skips_non_interactable_nodes(self, tmp_path):
        tool = BrowserTool(data_dir=tmp_path)
        tree = {
            "role": "document",
            "name": "Page",
            "children": [
                {"role": "button", "name": "Submit"},
                {"role": "text", "name": "Body copy"},
                {
                    "role": "group",
                    "name": "Nested",
                    "children": [{"role": "link", "name": "Details"}],
                },
            ],
        }

        tool._walk_and_assign_refs(tree)

        assert tree["children"][0]["ref"] == "e1", f"first interactable node should get e1, got: {tree['children'][0]!r}"
        assert "ref" not in tree["children"][1], f"non-interactable nodes should not get refs, got: {tree['children'][1]!r}"
        assert tree["children"][2]["children"][0]["ref"] == "e2", f"nested interactable nodes should get subsequent refs, got: {tree['children'][2]['children'][0]!r}"
        assert tool._resolve_ref("e2") == "a:has-text('Details')", f"resolve_ref should return mapped selector, got: {tool._resolve_ref('e2')!r}"
        assert tool._resolve_ref("button.primary") == "button.primary", "unknown refs should be returned unchanged"


class TestOutputToFile:
    def test_output_to_file_uses_instance_data_dir_and_falls_back_for_empty_filename(self, tmp_path):
        tool = BrowserTool(data_dir=tmp_path)

        result = asyncio.run(tool._output_to_file("", "hello", fmt="txt"))
        path = Path(result["path"])

        assert result["success"] is True, f"output_to_file should succeed for empty filenames, got: {result!r}"
        assert path == tmp_path / "workspace" / ".conduit" / "output.txt", f"output path should stay under the instance data dir, got: {path!s}"
        assert path.read_text(encoding="utf-8") == "hello", f"written file should contain the provided content, got: {path.read_text(encoding='utf-8')!r}"

    def test_output_to_file_sanitizes_dot_only_names_and_returns_hash(self, tmp_path):
        tool = BrowserTool(data_dir=tmp_path)

        result = asyncio.run(tool._output_to_file(".", "payload", fmt="md"))
        path = Path(result["path"])

        assert path.name == "output.md", f"dot-only filenames should fall back to output.md, got: {path.name!r}"
        assert len(result["content_hash"]) == 64, f"content_hash should be a SHA-256 hex digest, got: {result['content_hash']!r}"


class TestParseVtt:
    def test_parse_vtt_strips_metadata_tags_and_duplicate_lines(self):
        raw = """WEBVTT

NOTE this is ignored

00:00.000 --> 00:01.000
<c.colorE5E5E5>Hello</c>

00:01.000 --> 00:02.000
Hello

00:02.000 --> 00:03.000
World
"""

        result = _parse_vtt(raw)

        assert result == "Hello World", f"VTT parsing should remove metadata, tags, and duplicates, got: {result!r}"
