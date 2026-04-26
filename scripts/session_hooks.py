#!/usr/bin/env python3
"""Session hook handlers for kb-sync. Called by Claude Code hooks."""

import os
import sys
from pathlib import Path

from scripts.config import ConfigManager
from scripts.state import StateManager
from scripts.utils import get_latest_session_file


def get_prompt_text() -> str:
    """尝试从多种来源获取用户提交的 prompt 文本。"""
    # 来源1: 环境变量（Claude Code 可能通过此传递）
    for env_var in ["CLAUDE_USER_PROMPT", "USER_PROMPT", "PROMPT_TEXT"]:
        text = os.environ.get(env_var, "").strip()
        if text:
            return text

    # 来源2: stdin
    if not sys.stdin.isatty():
        try:
            text = sys.stdin.read().strip()
            if text:
                return text
        except OSError:
            pass

    return ""


def handle_session_end(kb_sync_dir: Path) -> int:
    """处理 SessionEnd 事件：自动同步当前会话内容到知识库。"""
    try:
        config = ConfigManager(str(kb_sync_dir))
        config.load_or_create()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 读取配置失败: {exc}")
        return 1

    triggers = config.get("triggers", {})
    if not triggers.get("pre_exit", True):
        print("kb-sync: pre_exit trigger disabled in config.")
        return 0

    try:
        state = StateManager(str(kb_sync_dir))
        state.load_or_create()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 读取状态失败: {exc}")
        return 1

    # 定位 .claude/projects/ 目录
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        print("kb-sync: No .claude/projects directory found.")
        return 0

    try:
        latest = get_latest_session_file(projects_dir)
    except OSError as exc:
        print(f"kb-sync: 扫描会话文件失败: {exc}")
        return 1

    if not latest.exists():
        print("kb-sync: No session file found.")
        return 0

    session_id = latest.stem

    # 检查是否已同步
    if state.is_session_synced(session_id):
        print(f"kb-sync: Session {session_id} already synced.")
        return 0

    # 当前仅标记为待处理，完整的 LLM 提炼将在后续版本实现
    state.set_pending_session(session_id)
    print(f"kb-sync: Marked session {session_id} as pending for sync.")
    print("  (Full auto-sync with LLM extraction coming in next iteration)")
    print("  You can manually run '/kb-sync' to sync now.")
    return 0


def handle_session_start(kb_sync_dir: Path) -> int:
    """处理 SessionStart 事件：检查未同步会话和未处理文章。"""
    try:
        config = ConfigManager(str(kb_sync_dir))
        config.load_or_create()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 读取配置失败: {exc}")
        return 1

    try:
        state = StateManager(str(kb_sync_dir))
        state.load_or_create()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 读取状态失败: {exc}")
        return 1

    messages = []

    # 检查未同步会话（优先检查 pending_session）
    pending_session = state.get_pending_session()

    if pending_session:
        messages.append(f"  - 待同步会话: {pending_session[:8]}...")
    else:
        projects_dir = Path.home() / ".claude" / "projects"
        if projects_dir.exists():
            try:
                latest = get_latest_session_file(projects_dir)
                if latest.exists():
                    session_id = latest.stem
                    if not state.is_session_synced(session_id):
                        messages.append(f"  - 待同步会话: {session_id[:8]}...")
            except OSError as exc:
                print(f"kb-sync: 扫描会话文件失败: {exc}")

    # 检查未处理文章
    try:
        paths = config.resolve_paths()
        raw_dir = Path(paths["clips"])
        if raw_dir.exists():
            processed = set(state.get_processed_clips())
            unprocessed = []
            for md_file in raw_dir.rglob("*.md"):
                rel_path = str(md_file.relative_to(Path(paths["base"])))
                if rel_path not in processed:
                    unprocessed.append(md_file.name)

            if unprocessed:
                messages.append(f"  - 未处理文章: {len(unprocessed)} 篇")
                for name in unprocessed[:3]:
                    messages.append(f"    - {name}")
                if len(unprocessed) > 3:
                    messages.append(f"    ... 还有 {len(unprocessed) - 3} 篇")
    except (OSError, ValueError):
        pass

    if messages:
        print("kb-sync: 检测到待处理内容")
        for msg in messages:
            print(msg)
        print("  提示: 输入 /kb-sync 可选择同步或跳过，或 /process-clips 处理文章")
    else:
        print("kb-sync: 所有内容已同步，无待处理项。")

    return 0


def handle_prompt_submit(kb_sync_dir: Path, prompt_text: str) -> int:
    """处理 UserPromptSubmit 事件：检测关键词并提示同步。"""
    if not prompt_text:
        return 0

    try:
        config = ConfigManager(str(kb_sync_dir))
        config.load_or_create()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 读取配置失败: {exc}")
        return 1

    keywords = config.get("triggers.keywords", [])
    if not keywords:
        return 0

    prompt_lower = prompt_text.lower()
    matched = [kw for kw in keywords if kw.lower() in prompt_lower]

    if matched:
        print(f"kb-sync: Detected trigger keyword(s): {', '.join(matched)}")
        print("  Tip: The conversation will be auto-synced when you exit.")
        # 不立即同步，避免打断当前对话流
        # 仅在退出时通过 SessionEnd 处理
    return 0
