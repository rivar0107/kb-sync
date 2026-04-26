import pytest
from scripts.templates import TemplateManager

class TestTemplateManager:
    def test_render_concept(self, tmp_path):
        tm = TemplateManager(str(tmp_path / ".kb-sync"))
        content = tm.render_concept("测试概念", date="2026-04-26")
        assert "# 测试概念" in content
        assert "type: 概念" in content
        assert "2026-04-26" in content

    def test_render_figure(self, tmp_path):
        tm = TemplateManager(str(tmp_path / ".kb-sync"))
        content = tm.render_figure("张三", date="2026-04-26")
        assert "# 张三" in content
        assert "type: 人物" in content

    def test_ensure_defaults(self, tmp_path):
        tm = TemplateManager(str(tmp_path / ".kb-sync"))
        tm.ensure_default_templates()
        assert (tmp_path / ".kb-sync" / "templates" / "concept.md").exists()
        assert (tmp_path / ".kb-sync" / "templates" / "figure.md").exists()
