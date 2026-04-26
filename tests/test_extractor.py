import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.extractor import Extractor


class TestValidateEntry:
    def test_valid_entry(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        config = {"filters": {"min_confidence": 0.7, "max_entries_per_session": 10}}
        (kb_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (kb_dir / "state.json").write_text("{}", encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        assert extractor._validate_entry({
            "title": "Test", "body": "Body", "confidence": 0.8
        })

    def test_low_confidence(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        config = {"filters": {"min_confidence": 0.7, "max_entries_per_session": 10}}
        (kb_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (kb_dir / "state.json").write_text("{}", encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        assert not extractor._validate_entry({
            "title": "Test", "body": "Body", "confidence": 0.5
        })

    def test_missing_title(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        config = {"filters": {"min_confidence": 0.7, "max_entries_per_session": 10}}
        (kb_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (kb_dir / "state.json").write_text("{}", encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        assert not extractor._validate_entry({
            "title": "", "body": "Body", "confidence": 0.9
        })


class TestTruncateForLlm:
    def test_no_truncation(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        (kb_dir / "config.json").write_text("{}", encoding="utf-8")
        (kb_dir / "state.json").write_text("{}", encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        text = "short"
        assert extractor._truncate_for_llm(text, max_chars=100) == "short"

    def test_truncation(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        (kb_dir / "config.json").write_text("{}", encoding="utf-8")
        (kb_dir / "state.json").write_text("{}", encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        text = "A" * 10000
        result = extractor._truncate_for_llm(text, max_chars=1000)
        assert "...[内容截断]..." in result
        assert len(result) < 1200  # 允许截断标记的额外长度


class TestExtractAndSync:
    @patch("scripts.extractor.LLMClient")
    @patch.object(Extractor, "_find_session_file")
    def test_successful_sync(self, mock_find, mock_llm_cls, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        config = {"filters": {"min_confidence": 0.7, "max_entries_per_session": 10}}
        (kb_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        state = {"pending_session": "sess-123"}
        (kb_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

        # 创建假的 jsonl
        session_file = tmp_path / "sess-123.jsonl"
        session_file.write_text(
            json.dumps({"type": "user", "message": {"content": "hello"}}) + "\n" +
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n",
            encoding="utf-8"
        )
        mock_find.return_value = session_file

        mock_llm = MagicMock()
        mock_llm.extract_dialogue.return_value = [
            {"title": "Test", "body": "Body", "category": "概念", "confidence": 0.9, "tags": ["t1"]}
        ]
        mock_llm_cls.return_value = mock_llm

        extractor = Extractor(str(kb_dir))
        result = extractor.extract_and_sync()

        assert result["synced_count"] == 1
        assert result["skipped_count"] == 0
        assert len(result["entries"]) == 1
        assert result["entries"][0]["title"] == "Test"

    @patch("scripts.extractor.LLMClient")
    @patch.object(Extractor, "_find_session_file")
    def test_dry_run(self, mock_find, mock_llm_cls, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        config = {"filters": {"min_confidence": 0.7, "max_entries_per_session": 10}}
        (kb_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        state = {"pending_session": "sess-456"}
        (kb_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

        session_file = tmp_path / "sess-456.jsonl"
        session_file.write_text(
            json.dumps({"type": "user", "message": {"content": "q"}}) + "\n",
            encoding="utf-8"
        )
        mock_find.return_value = session_file

        mock_llm = MagicMock()
        mock_llm.extract_dialogue.return_value = [
            {"title": "X", "body": "Y", "category": "概念", "confidence": 0.9}
        ]
        mock_llm_cls.return_value = mock_llm

        extractor = Extractor(str(kb_dir))
        result = extractor.extract_and_sync(dry_run=True)

        assert result["synced_count"] == 0  # dry_run 不写入
        assert len(result["entries"]) == 1

    def test_no_pending_session(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        (kb_dir / "config.json").write_text("{}", encoding="utf-8")
        (kb_dir / "state.json").write_text("{}", encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        result = extractor.extract_and_sync()

        assert result["synced_count"] == 0
        assert any("没有待同步" in e for e in result["errors"])

    def test_missing_session_file(self, tmp_path):
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        (kb_dir / "config.json").write_text("{}", encoding="utf-8")
        state = {"pending_session": "sess-missing"}
        (kb_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

        extractor = Extractor(str(kb_dir))
        result = extractor.extract_and_sync()

        assert result["synced_count"] == 0
        assert any("找不到会话文件" in e for e in result["errors"])
