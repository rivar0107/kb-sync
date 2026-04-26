"""同步引擎模块：负责对话同步的核心调度逻辑。"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from scripts.config import ConfigManager
from scripts.state import StateManager
from scripts.templates import TemplateManager
from scripts.utils import compute_similarity, safe_filename, truncate_text


class SyncEngine:
    """对话同步引擎：读取 jsonl、格式化输出、写入知识库。"""

    def __init__(self, kb_sync_dir: str):
        self.kb_sync_dir = Path(kb_sync_dir)
        self.config = ConfigManager(str(kb_sync_dir))
        self.config.load_or_create()
        self.state = StateManager(str(kb_sync_dir))
        self.state.load_or_create()
        self.template = TemplateManager(str(kb_sync_dir))
        self.paths = self.config.resolve_paths()

    def _get_latest_session_file(self, projects_dir: str) -> Optional[str]:
        """获取 .claude/projects/<project> 下最新的 jsonl 文件路径。"""
        proj = Path(projects_dir)
        if not proj.exists():
            return None
        jsonls = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not jsonls:
            return None
        return str(jsonls[0])

    def _get_session_file_by_id(self, projects_dir: str, session_id: str) -> Optional[str]:
        """根据 session_id 查找对应的 jsonl 文件路径（遍历所有项目子目录）。"""
        proj = Path(projects_dir)
        if not proj.exists():
            return None
        for jsonl in proj.rglob("*.jsonl"):
            if jsonl.stem == session_id:
                return str(jsonl)
        return None

    def _find_related_notes(self, title: str, body: str, exclude_path: Optional[Path] = None) -> List[Path]:
        """扫描已有笔记，找出与新内容语义关联的文件。

        基于 bigram Jaccard 相似度计算，阈值 0.15。
        扫描范围包括概念、人物、项目、工具四个 Wiki 目录。
        """
        new_text = f"{title}\n{body}"
        related: List[Path] = []

        wiki_dirs = [
            self.paths.get("concepts"),
            self.paths.get("figures"),
            self.paths.get("projects"),
            self.paths.get("tools"),
        ]

        for wiki_dir in wiki_dirs:
            if not wiki_dir or not Path(wiki_dir).exists():
                continue
            for md_file in Path(wiki_dir).rglob("*.md"):
                if exclude_path and md_file.resolve() == exclude_path.resolve():
                    continue
                try:
                    existing_text = md_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                sim = compute_similarity(new_text, existing_text)
                if sim >= 0.15:
                    related.append(md_file)

        # 按相似度降序排列，最多取 5 个
        related.sort(
            key=lambda p: compute_similarity(new_text, p.read_text(encoding="utf-8")),
            reverse=True,
        )
        return related[:5]

    def _insert_link_into_section(self, content: str, section_title: str, link_line: str) -> str:
        """在 Markdown 的指定 section 中插入一行链接；如 section 不存在则在末尾追加。"""
        lines = content.split("\n")
        section_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith(f"## {section_title}"):
                section_start = i
                break

        if section_start is None:
            return content + f"\n\n## {section_title}\n{link_line}\n"

        # 找到 section 结束位置（下一个 ## 开头或文件末尾）
        section_end = len(lines)
        for i in range(section_start + 1, len(lines)):
            if lines[i].strip().startswith("## "):
                section_end = i
                break

        # 检查是否已存在相同链接
        for line in lines[section_start:section_end]:
            if link_line in line:
                return content

        lines.insert(section_end, link_line)
        return "\n".join(lines)

    def _add_backlinks(self, related_paths: List[Path], new_note_path: Path) -> None:
        """在已有笔记中追加指向新笔记的反向链接。"""
        new_link = f"- [[{new_note_path.stem}]]"
        section_titles = ["关联文件", "相关概念"]

        for related_path in related_paths:
            if related_path.resolve() == new_note_path.resolve():
                continue
            try:
                content = related_path.read_text(encoding="utf-8")
            except Exception:
                continue

            inserted = False
            for section_title in section_titles:
                if f"## {section_title}" in content:
                    content = self._insert_link_into_section(content, section_title, new_link)
                    inserted = True
                    break

            if not inserted:
                content = self._insert_link_into_section(content, "关联文件", new_link)

            related_path.write_text(content, encoding="utf-8")

    def _format_note(
        self,
        title: str,
        category: str,
        body: str,
        source: str,
        session_id: str,
        date: str,
        tags: List[str],
        confidence: float,
        related_links: Optional[List[Path]] = None,
    ) -> str:
        """将提炼的知识点格式化为 Markdown 笔记。"""
        tags_str = ", ".join(f'"{t}"' for t in tags)

        if related_links:
            links_str = "\n".join(f"- [[{p.stem}]]" for p in related_links)
        else:
            links_str = "- [[相关概念]]"

        return f"""---
source: "{source}"
session_id: "{session_id}"
synced_at: "{date}"
category: "{category}"
tags: [{tags_str}]
confidence: {confidence}
---

# {title}

## 核心要点
{body}

## 原始对话上下文
> （详见对话记录）

## 关联文件
{links_str}
"""

    def write_note(self, title: str, category: str, body: str, session_id: str) -> str:
        """将笔记写入知识库对应目录，返回写入的文件路径。"""
        category_map = {
            "概念": self.paths["concepts"],
            "人物": self.paths["figures"],
            "项目": self.paths["projects"],
            "工具": self.paths["tools"],
        }
        target_dir = category_map.get(category, self.paths["staging"])
        Path(target_dir).mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{safe_filename(title)}-{date_str}.md"
        file_path = Path(target_dir) / filename

        # 如果文件已存在，追加内容
        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            note_body = f"\n\n## 补充（{date_str}）\n{body}"
            file_path.write_text(existing + note_body, encoding="utf-8")
        else:
            # 新建笔记：扫描已有文件，建立双向链接
            related = self._find_related_notes(title, body, exclude_path=file_path)
            note = self._format_note(
                title=title,
                category=category,
                body=body,
                source="Claude Code 对话",
                session_id=session_id,
                date=datetime.now().isoformat(),
                tags=[],
                confidence=0.85,
                related_links=related,
            )
            file_path.write_text(note, encoding="utf-8")
            self._add_backlinks(related, file_path)

        relative_path = str(file_path.relative_to(self.config.kb_sync_dir.parent))
        self.state.add_synced_file(relative_path)
        self.state.mark_session_synced(session_id)
        return str(file_path)
