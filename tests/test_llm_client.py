import pytest
from scripts.llm_client import LLMClient


class TestExtractJson:
    def test_json_code_block(self):
        text = 'some text\n```json\n{"a": 1}\n```\nmore text'
        assert LLMClient._extract_json(text) == '{"a": 1}'

    def test_plain_code_block(self):
        text = 'here\n```\n{"b": 2}\n```'
        assert LLMClient._extract_json(text) == '{"b": 2}'

    def test_bare_json(self):
        text = 'prefix {"c": 3} suffix'
        assert LLMClient._extract_json(text) == '{"c": 3}'

    def test_no_json(self):
        assert LLMClient._extract_json("no json here") is None

    def test_nested_braces(self):
        text = '```json\n{"entries": [{"title": "x"}]}\n```'
        assert LLMClient._extract_json(text) == '{"entries": [{"title": "x"}]}'


class TestResolveApiKey:
    def test_no_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        assert LLMClient._resolve_api_key() is None

    def test_prefers_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key1")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "key2")
        assert LLMClient._resolve_api_key() == "key1"

    def test_fallback_auth_token(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token")
        assert LLMClient._resolve_api_key() == "token"
