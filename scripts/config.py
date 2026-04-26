"""配置管理模块：负责读取/写入 config.json，解析知识库路径。"""

import json
import os
from pathlib import Path
from typing import Dict, Any

# ─── 默认配置 ───
DEFAULT_CONFIG = {
    "paths": {
        "knowledge_base": "./知识库",
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
        "keywords": ["结束对话", "bye", "quit", "先这样", "今天就到这"],
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


class ConfigManager:
    """管理 .kb-sync/config.json 的读取、写入和路径解析。"""

    def __init__(self, kb_sync_dir: str):
        self.kb_sync_dir = Path(kb_sync_dir)
        self.config_file = self.kb_sync_dir / "config.json"
        self._config: Dict[str, Any] = {}

    def load_or_create(self) -> Dict[str, Any]:
        """加载配置；如果不存在则创建默认配置并保存。"""
        if self.config_file.exists():
            self._config = json.loads(self.config_file.read_text(encoding="utf-8"))
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()
        return self._config

    def save(self) -> None:
        """将当前配置写入磁盘。"""
        self.kb_sync_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(self._config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default=None):
        """获取配置项，支持点号分隔的嵌套键（如 'paths.knowledge_base'）。"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置项，支持点号分隔的嵌套键。"""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def resolve_paths(self) -> Dict[str, str]:
        """将相对路径配置解析为绝对路径。"""
        base = self.get("paths.knowledge_base", "./知识库")
        # 如果 knowledge_base 是相对路径，基于项目根目录解析
        # 项目根目录定义为 .kb-sync 的上级目录
        project_root = self.kb_sync_dir.parent
        base_abs = project_root / base

        paths = {
            "base": str(base_abs),
            "clips": str(base_abs / self.get("paths.clips_dir", "01-Raw")),
            "wiki": str(base_abs / self.get("paths.wiki_dir", "02-Wiki")),
            "concepts": str(base_abs / self.get("paths.wiki_dir", "02-Wiki") / self.get("paths.concepts_dir", "概念")),
            "figures": str(base_abs / self.get("paths.wiki_dir", "02-Wiki") / self.get("paths.figures_dir", "人物")),
            "projects": str(base_abs / self.get("paths.wiki_dir", "02-Wiki") / self.get("paths.projects_dir", "项目")),
            "tools": str(base_abs / self.get("paths.wiki_dir", "02-Wiki") / self.get("paths.tools_dir", "工具")),
            "staging": str(base_abs / self.get("paths.clips_dir", "01-Raw") / self.get("paths.staging_dir", "待整理")),
            "templates": str(self.kb_sync_dir / self.get("paths.templates_dir", "templates")),
        }
        return paths
