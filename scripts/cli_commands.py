#!/usr/bin/env python3
"""CLI command handlers for kb-sync."""

from pathlib import Path

from scripts.config import ConfigManager
from scripts.extractor import Extractor
from scripts.state import StateManager


def handle_status(kb_sync_dir: Path) -> int:
    """处理 --status 命令：输出当前同步状态。"""
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

    print("kb-sync 状态报告")
    print("-" * 40)

    pending = state.get_pending_session()

    if pending:
        print(f"待同步会话: {pending[:8]}...")
    else:
        print("待同步会话: 无")

    last_synced = state.get_last_synced_at()

    if last_synced:
        print(f"上次同步时间: {last_synced}")
    else:
        print("上次同步时间: 无")

    synced_count = state.get_synced_files_count()
    print(f"已同步文件数: {synced_count}")

    # 检查未处理文章
    try:
        paths = config.resolve_paths()
        raw_dir = Path(paths["clips"])
        processed = set(state.get_processed_clips())
        unprocessed = 0
        if raw_dir.exists():
            for md_file in raw_dir.rglob("*.md"):
                rel_path = str(md_file.relative_to(Path(paths["base"])))
                if rel_path not in processed:
                    unprocessed += 1
        print(f"未处理文章数: {unprocessed}")
    except (OSError, ValueError):
        print("未处理文章数: 无法计算")

    return 0


def handle_sync(kb_sync_dir: Path, session_id: str = "", preview_only: bool = False) -> int:
    """处理同步命令：读取 jsonl，调用 LLM 提炼，写入知识库。"""
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

    target = session_id or state.get_pending_session()
    if not target:
        print("kb-sync: 没有待同步的会话。输入 /kb-sync 启动新对话后会自动检测。")
        return 0

    extractor = Extractor(str(kb_sync_dir))

    if preview_only:
        try:
            text = extractor.preview(target)
            print(text)
        except Exception as exc:
            print(f"kb-sync: 预览失败: {exc}")
            return 1
        return 0

    try:
        result = extractor.extract_and_sync(session_id=target)
    except Exception as exc:
        print(f"kb-sync: 同步失败: {exc}")
        return 1

    print(f"kb-sync: 同步完成")
    print(f"  会话: {result['session_id'][:8]}...")
    print(f"  成功写入: {result['synced_count']} 个知识点")
    print(f"  跳过: {result['skipped_count']} 个（置信度不足或内容不完整）")

    if result["errors"]:
        print(f"  错误: {len(result['errors'])}")
        for err in result["errors"][:3]:
            print(f"    ⚠️ {err}")

    return 0


def handle_rollback_last(kb_sync_dir: Path) -> int:
    """处理 --rollback-last：列出上次同步的文件并清空记录。

    注意：本命令只清空状态记录，不自动删除物理文件。
    如需物理删除，请在 /kb-sync --rollback-last 交互流程中确认。
    """
    try:
        state = StateManager(str(kb_sync_dir))
        state.load_or_create()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 读取状态失败: {exc}")
        return 1

    try:
        files = state.get_last_synced_files()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 获取同步记录失败: {exc}")
        return 1

    if not files:
        print("kb-sync: 没有可回滚的同步记录。")
        return 0

    print("kb-sync: 上次同步的文件列表（仅清空记录，不删除物理文件）：")
    for f in files:
        print(f"  - {f}")
    print(f"\n共 {len(files)} 个文件。记录已清空。")
    print("如需物理删除 Wiki 页面，请在交互式回滚流程中确认。")

    try:
        state.clear_synced_files()
    except (OSError, ValueError) as exc:
        print(f"kb-sync: 清空记录失败: {exc}")
        return 1

    return 0
