"""模板管理模块：负责默认模板的生成和渲染。"""

from pathlib import Path
from typing import Dict

DEFAULT_CONCEPT_TEMPLATE = """---
type: 概念
created: {{date}}
sources: []
tags: []
---

# {{concept_name}}

## 定义

## 核心要点

## 相关来源
- [文章标题](链接) — 核心观点摘要

## 相关概念
- [[...]]

## 待探索问题
"""

DEFAULT_FIGURE_TEMPLATE = """---
type: 人物
created: {{date}}
roles: []
tags: []
---

# {{figure_name}}

## 身份与背景

## 核心观点

## 相关文章/来源
- [文章标题](链接) — 观点摘要

## 相关概念
- [[...]]

## 待追踪动态
"""


class TemplateManager:
    """管理 .kb-sync/templates/ 下的模板文件。"""

    def __init__(self, kb_sync_dir: str):
        self.templates_dir = Path(kb_sync_dir) / "templates"

    def ensure_default_templates(self) -> None:
        """确保默认模板文件存在，不存在则自动生成。"""
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        concept_file = self.templates_dir / "concept.md"
        if not concept_file.exists():
            concept_file.write_text(DEFAULT_CONCEPT_TEMPLATE, encoding="utf-8")

        figure_file = self.templates_dir / "figure.md"
        if not figure_file.exists():
            figure_file.write_text(DEFAULT_FIGURE_TEMPLATE, encoding="utf-8")

    def render_concept(self, concept_name: str, date: str) -> str:
        self.ensure_default_templates()
        template = (self.templates_dir / "concept.md").read_text(encoding="utf-8")
        return template.replace("{{concept_name}}", concept_name).replace("{{date}}", date)

    def render_figure(self, figure_name: str, date: str) -> str:
        self.ensure_default_templates()
        template = (self.templates_dir / "figure.md").read_text(encoding="utf-8")
        return template.replace("{{figure_name}}", figure_name).replace("{{date}}", date)
