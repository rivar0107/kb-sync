import pytest
from scripts.utils import safe_filename, compute_similarity, scan_markdown_files

class TestUtils:
    def test_safe_filename(self):
        assert safe_filename("Agent Skill 设计方法论") == "Agent-Skill-设计方法论"
        assert safe_filename("test/file:name?") == "test-file-name"

    def test_compute_similarity_identical(self):
        assert compute_similarity("相同内容", "相同内容") > 0.99

    def test_compute_similarity_different(self):
        sim = compute_similarity("人工智能伦理讨论", "量子计算硬件架构")
        assert sim < 0.3

    def test_scan_markdown_files(self, tmp_path):
        (tmp_path / "a.md").write_text("# A")
        (tmp_path / "b.txt").write_text("not md")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("# C")
        files = scan_markdown_files(str(tmp_path))
        assert len(files) == 2
        assert any("a.md" in f for f in files)
        assert any("c.md" in f for f in files)
