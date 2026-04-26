import json
import pytest
from scripts.state import StateManager

class TestStateManager:
    def test_load_or_create_default(self, tmp_path):
        sm = StateManager(str(tmp_path / ".kb-sync"))
        state = sm.load_or_create()
        assert state["last_synced_session"] is None
        assert state["processed_clips"] == []
        assert state["synced_files"] == []

    def test_mark_session_synced(self, tmp_path):
        sm = StateManager(str(tmp_path / ".kb-sync"))
        sm.load_or_create()
        sm.mark_session_synced("session-abc-123")
        state = sm.load_or_create()
        assert state["last_synced_session"] == "session-abc-123"
        assert state["pending_session"] is None

    def test_add_synced_file(self, tmp_path):
        sm = StateManager(str(tmp_path / ".kb-sync"))
        sm.load_or_create()
        sm.add_synced_file("02-Wiki/概念/test.md")
        state = sm.load_or_create()
        assert "02-Wiki/概念/test.md" in state["synced_files"]

    def test_add_processed_clip(self, tmp_path):
        sm = StateManager(str(tmp_path / ".kb-sync"))
        sm.load_or_create()
        sm.add_processed_clip("01-Raw/article.md")
        state = sm.load_or_create()
        assert "01-Raw/article.md" in state["processed_clips"]

    def test_is_session_synced(self, tmp_path):
        sm = StateManager(str(tmp_path / ".kb-sync"))
        sm.load_or_create()
        assert sm.is_session_synced("session-abc") is False
        sm.mark_session_synced("session-abc")
        assert sm.is_session_synced("session-abc") is True

    def test_rollback_last(self, tmp_path):
        sm = StateManager(str(tmp_path / ".kb-sync"))
        sm.load_or_create()
        sm.add_synced_file("file1.md")
        sm.add_synced_file("file2.md")
        removed = sm.rollback_last()
        assert removed == ["file1.md", "file2.md"]
        state = sm.load_or_create()
        assert state["synced_files"] == []
