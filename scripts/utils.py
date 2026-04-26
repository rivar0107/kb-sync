"""工具函数模块：相似度计算、文件名安全处理、文件扫描等辅助函数。"""

import re
from pathlib import Path
from typing import List


def get_latest_session_file(projects_dir: Path) -> Path:
    """获取最新的会话 jsonl 文件路径。"""
    if not projects_dir.exists():
        return Path()

    jsonls = sorted(
        projects_dir.rglob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not jsonls:
        return Path()
    return jsonls[0]


def safe_filename(name: str) -> str:
    """将字符串转换为安全的文件名（空格和非法字符替换为连字符，合并连续的连字符）。"""
    # 替换空格和非法字符为连字符
    safe = re.sub(r'[\\/:*?"<>| ]', "-", name)
    # 合并连续的连字符
    safe = re.sub(r'-+', "-", safe)
    # 移除首尾的连字符
    safe = safe.strip("-")
    return safe


def compute_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的相似度（简单基于字符二元组（bigram）的 Jaccard 系数）。"""
    def get_bigrams(text):
        text = text.lower()
        return set(text[i:i+2] for i in range(len(text) - 1))

    a = get_bigrams(text_a)
    b = get_bigrams(text_b)
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def scan_markdown_files(directory: str) -> List[str]:
    """递归扫描目录下所有 .md 文件，返回相对路径列表。"""
    base = Path(directory)
    if not base.exists():
        return []
    return [
        str(p.relative_to(base))
        for p in base.rglob("*.md")
    ]


def get_kb_sync_dir() -> Path:
    """获取 kb-sync 配置目录。

    优先级：
    1. 当前项目目录下的 .kb-sync/（项目级配置）
    2. 用户主目录下的 ~/.kb-sync/（全局配置）

    Returns:
        Path: kb-sync 配置目录路径（不一定已存在）
    """
    project_level = Path.cwd() / ".kb-sync"
    if project_level.exists():
        return project_level

    return Path.home() / ".kb-sync"


def get_kb_sync_mode() -> str:
    """判断当前使用的配置模式。

    Returns:
        str: "project" 如果当前目录有 .kb-sync/，否则 "global"
    """
    if (Path.cwd() / ".kb-sync").exists():
        return "project"
    if (Path.home() / ".kb-sync").exists():
        return "global"
    return "none"


def truncate_text(text: str, max_chars: int = 200) -> str:
    """截断文本到指定长度，用于生成摘要。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
