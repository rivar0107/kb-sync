import pytest
from scripts.init_kb import KnowledgeBaseInitializer

class TestKnowledgeBaseInitializer:
    def test_discover_existing_kb(self, tmp_path):
        """测试：发现已有知识库"""
        kb = tmp_path / "知识库"
        raw = kb / "01-Raw"
        raw.mkdir(parents=True)
        (tmp_path / ".kb-sync").mkdir()
        init = KnowledgeBaseInitializer(str(tmp_path / ".kb-sync"))
        found = init.discover_existing_kb(str(tmp_path))
        assert found == str(kb)

    def test_no_kb_found(self, tmp_path):
        """测试：未检测到知识库"""
        (tmp_path / ".kb-sync").mkdir()
        init = KnowledgeBaseInitializer(str(tmp_path / ".kb-sync"))
        found = init.discover_existing_kb(str(tmp_path))
        assert found is None

    def test_create_default_structure(self, tmp_path):
        """测试：创建默认知识库结构"""
        (tmp_path / ".kb-sync").mkdir()
        init = KnowledgeBaseInitializer(str(tmp_path / ".kb-sync"))
        init.create_default_structure(str(tmp_path / "知识库"))
        assert (tmp_path / "知识库" / "01-Raw").exists()
        assert (tmp_path / "知识库" / "02-Wiki" / "概念").exists()
        assert (tmp_path / "知识库" / "02-Wiki" / "人物").exists()
        assert (tmp_path / "知识库" / "02-Wiki" / "项目").exists()
        assert (tmp_path / "知识库" / "02-Wiki" / "工具").exists()

    def test_create_kb_with_custom_config(self, tmp_path):
        """测试：按自定义配置创建知识库"""
        config = {
            "paths": {
                "knowledge_base": "./my-kb",
                "clips_dir": "Inbox",
                "wiki_dir": "Wiki",
                "concepts_dir": "concepts",
                "figures_dir": "people",
                "projects_dir": "projects",
                "tools_dir": "tools",
            }
        }
        (tmp_path / ".kb-sync").mkdir()
        init = KnowledgeBaseInitializer(str(tmp_path / ".kb-sync"))
        init.create_structure(str(tmp_path), config)
        assert (tmp_path / "my-kb" / "Inbox").exists()
        assert (tmp_path / "my-kb" / "Wiki" / "concepts").exists()
