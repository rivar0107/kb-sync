"""知识库初始化模块：负责发现已有知识库或创建新的知识库结构。"""

import copy
import json
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from scripts.state import DEFAULT_STATE

# 扫描特征：用于自动发现已有知识库
KB_INDICATOR_DIRS = ["知识库", "wiki", "notes", "KB", "知识库"]
RAW_INDICATORS = ["01-Raw", "Inbox", "raw", "00-Inbox", "clips"]
WIKI_INDICATORS = ["02-Wiki", "Wiki", "wiki", "01-Wiki"]


class KnowledgeBaseInitializer:
    """管理知识库的首次发现和自动创建。"""

    def __init__(self, kb_sync_dir: str):
        self.kb_sync_dir = Path(kb_sync_dir)

    def discover_existing_kb(self, search_root: str) -> Optional[str]:
        """扫描目录，尝试发现已有的知识库。"""
        root = Path(search_root)
        candidates = []

        for item in root.iterdir():
            if not item.is_dir():
                continue
            if item.name in KB_INDICATOR_DIRS:
                # 进一步验证：是否包含 Raw 或 Wiki 子目录
                has_raw = any(
                    (item / d).exists() for d in RAW_INDICATORS
                )
                has_wiki = any(
                    (item / d).exists() for d in WIKI_INDICATORS
                )
                has_obsidian = (item / ".obsidian").exists()
                if has_raw or has_wiki or has_obsidian:
                    candidates.append(str(item))

        if len(candidates) == 1:
            return candidates[0]
        # 多个候选时返回 None，让用户选择
        return None

    def create_default_structure(self, kb_path: str) -> None:
        """创建默认的 Karpathy 风格知识库结构。"""
        config = {
            "paths": {
                "knowledge_base": os.path.relpath(kb_path, self.kb_sync_dir.parent),
                "clips_dir": "01-Raw",
                "wiki_dir": "02-Wiki",
                "concepts_dir": "概念",
                "figures_dir": "人物",
                "projects_dir": "项目",
                "tools_dir": "工具",
                "staging_dir": "待整理",
            }
        }
        self.create_structure(str(self.kb_sync_dir.parent), config)

    def create_structure(self, project_root: str, config: Dict[str, Any]) -> None:
        """根据配置创建知识库目录结构。"""
        paths = config.get("paths", {})
        kb_base = Path(project_root) / paths.get("knowledge_base", "知识库")

        dirs_to_create = [
            paths.get("clips_dir", "01-Raw"),
            paths.get("wiki_dir", "02-Wiki"),
            f"{paths.get('wiki_dir', '02-Wiki')}/{paths.get('concepts_dir', '概念')}",
            f"{paths.get('wiki_dir', '02-Wiki')}/{paths.get('figures_dir', '人物')}",
            f"{paths.get('wiki_dir', '02-Wiki')}/{paths.get('projects_dir', '项目')}",
            f"{paths.get('wiki_dir', '02-Wiki')}/{paths.get('tools_dir', '工具')}",
        ]

        for d in dirs_to_create:
            (kb_base / d).mkdir(parents=True, exist_ok=True)


def _create_default_templates(templates_dir: Path) -> None:
    """在 templates_dir 下创建默认模板文件。"""
    concept = templates_dir / "concept.md"
    if not concept.exists():
        concept.write_text(
            '---\n'
            'type: 概念\n'
            'created: {{date}}\n'
            'sources: []\n'
            'tags: []\n'
            '---\n\n'
            '# {{concept_name}}\n\n'
            '## 定义\n\n'
            '## 核心要点\n\n'
            '## 相关来源\n'
            '- [文章标题](链接) — 核心观点摘要\n\n'
            '## 相关概念\n'
            '- [[...]]\n\n'
            '## 待探索问题\n',
            encoding="utf-8",
        )

    figure = templates_dir / "figure.md"
    if not figure.exists():
        figure.write_text(
            '---\n'
            'type: 人物\n'
            'created: {{date}}\n'
            'roles: []\n'
            'tags: []\n'
            '---\n\n'
            '# {{figure_name}}\n\n'
            '## 身份与背景\n\n'
            '## 核心观点\n\n'
            '## 相关文章/来源\n'
            '- [文章标题](链接) — 观点摘要\n\n'
            '## 相关概念\n'
            '- [[...]]\n\n'
            '## 待追踪动态\n',
            encoding="utf-8",
        )


def setup_kb_sync(
    kb_sync_dir: str,
    knowledge_base_path: str,
    mode: str = "project",
) -> Dict[str, Any]:
    """初始化 .kb-sync/ 目录，写入 config.json、state.json 和默认模板。

    Args:
        kb_sync_dir: .kb-sync/ 目录路径（项目级或全局）
        knowledge_base_path: 知识库根目录的绝对路径
        mode: "project" 使用相对路径存储知识库位置；"global" 使用绝对路径

    Returns:
        创建的配置字典
    """
    kb_sync = Path(kb_sync_dir)
    kb_sync.mkdir(parents=True, exist_ok=True)

    kb_path = Path(knowledge_base_path).resolve()
    if mode == "global":
        kb_config_path = str(kb_path)
    else:
        project_root = kb_sync.parent
        try:
            kb_config_path = os.path.relpath(kb_path, project_root)
        except ValueError:
            kb_config_path = str(kb_path)

    config = {
        "paths": {
            "knowledge_base": kb_config_path,
            "clips_dir": "01-Raw",
            "wiki_dir": "02-Wiki",
            "concepts_dir": "概念",
            "figures_dir": "人物",
            "projects_dir": "项目",
            "tools_dir": "工具",
            "staging_dir": "待整理",
            "templates_dir": "templates",
        },
        "triggers": {
            "pre_exit": True,
            "keywords": [
                "结束对话", "bye", "quit", "先这样", "今天就到这", "记一下"
            ],
            "manual_command": True,
        },
        "filters": {
            "min_confidence": 0.7,
            "max_entries_per_session": 10,
            "skip_code_only_sessions": True,
        },
        "output": {
            "default_category": "staging",
            "date_in_filename": True,
            "include_raw_context": True,
        },
        "remedy": {
            "check_on_startup": True,
            "preview_before_sync": False,
        },
    }

    # 写入 config.json
    (kb_sync / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 state.json
    (kb_sync / "state.json").write_text(
        json.dumps(copy.deepcopy(DEFAULT_STATE), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 创建模板
    templates_dir = kb_sync / "templates"
    templates_dir.mkdir(exist_ok=True)
    _create_default_templates(templates_dir)

    # 创建知识库目录结构
    initializer = KnowledgeBaseInitializer(str(kb_sync))
    initializer.create_structure(str(kb_sync.parent if mode == "project" else kb_path), config)

    # 在 Wiki 子目录下放置模板副本，方便 Obsidian 中直接复制使用
    wiki_dir = kb_path / config["paths"]["wiki_dir"]
    for subdir, template_name in [
        (config["paths"]["concepts_dir"], "concept.md"),
        (config["paths"]["figures_dir"], "figure.md"),
    ]:
        target = wiki_dir / subdir / "_template.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        src = templates_dir / template_name
        if src.exists() and not target.exists():
            shutil.copy(str(src), str(target))

    return config


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="kb-sync 初始化工具")
    parser.add_argument("--kb-sync-dir", required=True, help=".kb-sync/ 目录路径")
    parser.add_argument("--kb-path", required=True, help="知识库根目录路径")
    parser.add_argument(
        "--mode",
        choices=["project", "global"],
        default="project",
        help="配置模式：project=项目级，global=全局共享",
    )
    args = parser.parse_args()

    setup_kb_sync(args.kb_sync_dir, args.kb_path, args.mode)
    print(f"kb-sync 已以 {args.mode} 模式初始化于 {args.kb_sync_dir}")
