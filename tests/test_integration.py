import json
import pytest
from pathlib import Path

from scripts.config import ConfigManager
from scripts.state import StateManager
from scripts.init_kb import KnowledgeBaseInitializer
from scripts.templates import TemplateManager
from scripts.sync_engine import SyncEngine

class TestIntegration:
    def test_full_flow_kb_init_and_sync(self, tmp_path):
        """集成测试：初始化知识库 → 同步笔记 → 验证状态"""
        kb_sync = tmp_path / ".kb-sync"
        kb_sync.mkdir()

        # 1. 初始化知识库
        init = KnowledgeBaseInitializer(str(kb_sync))
        init.create_default_structure(str(tmp_path / "知识库"))
        assert (tmp_path / "知识库" / "02-Wiki" / "概念").exists()

        # 2. 初始化配置和状态
        config = ConfigManager(str(kb_sync))
        config.load_or_create()
        state = StateManager(str(kb_sync))
        state.load_or_create()

        # 3. 生成模板
        tm = TemplateManager(str(kb_sync))
        tm.ensure_default_templates()

        # 4. 模拟同步笔记
        engine = SyncEngine(str(kb_sync))
        file_path = engine.write_note(
            title="测试概念",
            category="概念",
            body="这是一个测试知识点。",
            session_id="test-session-123",
        )

        # 5. 验证文件写入
        assert Path(file_path).exists()
        content = Path(file_path).read_text(encoding="utf-8")
        assert "# 测试概念" in content
        assert "测试知识点" in content

        # 6. 验证状态更新
        state.load_or_create()
        assert state.is_session_synced("test-session-123")
        assert len(state.get_synced_files()) == 1
