#!/usr/bin/env python3
"""Hook runner for kb-sync. Called by Claude Code hooks.

职责：参数解析 + 路由分发。具体业务逻辑在 session_hooks.py 和 cli_commands.py 中。
"""

import argparse
import sys
from pathlib import Path

# Add skill root to path so 'scripts.xxx' imports work
SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from scripts.cli_commands import handle_rollback_last, handle_status, handle_sync
from scripts.session_hooks import (
    get_prompt_text,
    handle_prompt_submit,
    handle_session_end,
    handle_session_start,
)
from scripts.utils import get_kb_sync_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="kb-sync hook runner")
    parser.add_argument(
        "--session-end", action="store_true", help="SessionEnd hook"
    )
    parser.add_argument(
        "--prompt-submit", action="store_true", help="UserPromptSubmit hook"
    )
    parser.add_argument(
        "--prompt-text", type=str, default="", help="Submitted prompt text"
    )
    parser.add_argument(
        "--session-start", action="store_true", help="SessionStart hook"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show sync status"
    )
    parser.add_argument(
        "--rollback-last", action="store_true", help="Rollback last sync"
    )
    parser.add_argument(
        "--sync", action="store_true", help="Sync pending session to KB"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Preview sync without writing"
    )
    parser.add_argument(
        "--session-id", type=str, default="", help="Target session ID"
    )
    args = parser.parse_args()

    # 查找 kb-sync 配置目录（项目级优先，全局回退）
    kb_sync_dir = get_kb_sync_dir()
    if not kb_sync_dir.exists():
        # 静默退出，不干扰未初始化的项目
        return 0

    if args.session_end:
        return handle_session_end(kb_sync_dir)

    if args.prompt_submit:
        prompt_text = args.prompt_text or get_prompt_text()
        return handle_prompt_submit(kb_sync_dir, prompt_text)

    if args.session_start:
        return handle_session_start(kb_sync_dir)

    if args.status:
        return handle_status(kb_sync_dir)

    if args.rollback_last:
        return handle_rollback_last(kb_sync_dir)

    if args.sync or args.preview:
        return handle_sync(kb_sync_dir, session_id=args.session_id, preview_only=args.preview)

    return 0


if __name__ == "__main__":
    sys.exit(main())
