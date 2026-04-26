import json
import pytest
from pathlib import Path
from scripts.jsonl_parser import extract_text_from_content, parse_jsonl_file, get_dialogue_summary


class TestExtractTextFromContent:
    def test_string_content(self):
        assert extract_text_from_content("hello") == "hello"

    def test_text_blocks(self):
        content = [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_from_content(content) == "hello\nworld"

    def test_skip_thinking(self):
        content = [
            {"type": "thinking", "thinking": "secret"},
            {"type": "text", "text": "visible"},
        ]
        assert extract_text_from_content(content) == "visible"

    def test_tool_use_hint(self):
        content = [
            {"type": "tool_use", "name": "read_file"},
            {"type": "text", "text": "result"},
        ]
        assert "[调用工具: read_file]" in extract_text_from_content(content)

    def test_tool_result_hint(self):
        content = [
            {"type": "tool_result", "content": "lots of data"},
            {"type": "text", "text": "done"},
        ]
        assert "[工具执行结果]" in extract_text_from_content(content)

    def test_empty_and_unknown(self):
        assert extract_text_from_content([]) == ""
        assert extract_text_from_content(None) == ""
        assert extract_text_from_content({"foo": "bar"}) == ""


class TestParseJsonlFile:
    def test_parse_simple_conversation(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        lines = [
            json.dumps({"type": "user", "message": {"content": "hi"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}}),
        ]
        jsonl.write_text("\n".join(lines), encoding="utf-8")

        text = parse_jsonl_file(str(jsonl))
        assert "USER: hi" in text
        assert "ASSISTANT: hello" in text

    def test_skip_attachments(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        lines = [
            json.dumps({"type": "attachment", "attachment": {"type": "hook_success"}}),
            json.dumps({"type": "user", "message": {"content": "question"}}),
        ]
        jsonl.write_text("\n".join(lines), encoding="utf-8")

        text = parse_jsonl_file(str(jsonl))
        assert "hook_success" not in text
        assert "USER: question" in text

    def test_missing_file(self):
        assert parse_jsonl_file("/nonexistent/file.jsonl") == ""

    def test_truncation(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        lines = [
            json.dumps({"type": "user", "message": {"content": "A" * 50000}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "B" * 50000}]}}),
            json.dumps({"type": "user", "message": {"content": "C" * 50000}}),
        ]
        jsonl.write_text("\n".join(lines), encoding="utf-8")

        text = parse_jsonl_file(str(jsonl), max_chars=10000)
        assert "...[内容截断]..." in text
        assert len(text) <= 10000 + 50  # 允许截断标记的额外长度


class TestGetDialogueSummary:
    def test_recent_turns(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        lines = []
        for i in range(30):
            lines.append(json.dumps({"type": "user", "message": {"content": f"q{i}"}}))
            lines.append(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": f"a{i}"}]}}))
        jsonl.write_text("\n".join(lines), encoding="utf-8")

        text = get_dialogue_summary(str(jsonl), max_turns=5)
        assert "q24" not in text  # 太旧的不应出现（只保留最近 5 轮 = 10 条消息）
        assert "q25" in text or "a25" in text  # q25 及之后应该出现
        assert "q29" in text or "a29" in text
