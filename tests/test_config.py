import os
import pytest
from scripts.config import ConfigManager

class TestConfigManager:
    def test_load_default_config(self, tmp_path):
        """测试：首次运行时自动生成默认配置"""
        kb_dir = tmp_path / ".kb-sync"
        cm = ConfigManager(str(kb_dir))
        config = cm.load_or_create()
        assert config["paths"]["knowledge_base"] == "./知识库"
        assert config["paths"]["clips_dir"] == "01-Raw"
        assert config["filters"]["min_confidence"] == 0.7

    def test_resolve_paths(self, tmp_path):
        """测试：路径解析是否正确拼接"""
        kb_dir = tmp_path / ".kb-sync"
        cm = ConfigManager(str(kb_dir))
        config = cm.load_or_create()
        paths = cm.resolve_paths()
        assert paths["clips"] == os.path.join(tmp_path, "知识库", "01-Raw")
        assert paths["wiki"] == os.path.join(tmp_path, "知识库", "02-Wiki")
        assert paths["concepts"] == os.path.join(tmp_path, "知识库", "02-Wiki", "概念")

    def test_custom_paths(self, tmp_path):
        """测试：自定义路径配置生效"""
        kb_dir = tmp_path / ".kb-sync"
        kb_dir.mkdir()
        config_file = kb_dir / "config.json"
        config_file.write_text(
            '{"paths": {"knowledge_base": "./my-notes", "clips_dir": "Inbox", "wiki_dir": "Wiki"}}'
        )
        cm = ConfigManager(str(kb_dir))
        config = cm.load_or_create()
        assert config["paths"]["knowledge_base"] == "./my-notes"
        paths = cm.resolve_paths()
        assert "my-notes" in paths["clips"]
