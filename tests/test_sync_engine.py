import json
import pytest
from scripts.sync_engine import SyncEngine

class TestSyncEngine:
    def test_get_latest_session_uuid(self, tmp_path):
        """测试：从 .claude/projects/ 中获取最新会话 UUID"""
        projects = tmp_path / ".claude" / "projects" / "test-project"
        projects.mkdir(parents=True)
        (projects / "aaa.jsonl").write_text("")
        (projects / "bbb.jsonl").write_text("")
        import time
        time.sleep(0.01)
        (projects / "bbb.jsonl").touch()

        engine = SyncEngine(str(tmp_path / ".kb-sync"))
        latest = engine._get_latest_session_file(str(projects))
        assert "bbb.jsonl" in latest

    def test_markdown_output_format(self, tmp_path):
        """测试：生成 Markdown 笔记的格式是否正确"""
        engine = SyncEngine(str(tmp_path / ".kb-sync"))
        content = engine._format_note(
            title="测试概念",
            category="概念",
            body="核心要点",
            source="Claude Code 对话",
            session_id="test-123",
            date="2026-04-26",
            tags=["AI"],
            confidence=0.85,
        )
        assert "# 测试概念" in content
        assert 'source: "Claude Code 对话"' in content
        assert "confidence: 0.85" in content
        assert "---" in content
