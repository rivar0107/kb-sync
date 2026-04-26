"""状态管理模块：负责读取/写入 state.json，追踪已同步内容。"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

DEFAULT_STATE = {
    "last_synced_session": None,
    "last_synced_at": None,
    "pending_session": None,
    "processed_clips": [],
    "synced_files": [],
}


class StateManager:
    """管理 .kb-sync/state.json 的读取、写入和状态查询。"""

    def __init__(self, kb_sync_dir: str):
        self.kb_sync_dir = Path(kb_sync_dir)
        self.state_file = self.kb_sync_dir / "state.json"
        self._state: Dict[str, Any] = {}

    def load_or_create(self) -> Dict[str, Any]:
        if self.state_file.exists():
            self._state = json.loads(self.state_file.read_text(encoding="utf-8"))
        else:
            self._state = copy.deepcopy(DEFAULT_STATE)
            self.save()
        return self._state

    def save(self) -> None:
        self.kb_sync_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def mark_session_synced(self, session_id: str) -> None:
        self._state["last_synced_session"] = session_id
        self._state["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        self._state["pending_session"] = None
        self.save()

    def clear_pending_session(self) -> None:
        self._state["pending_session"] = None
        self.save()

    def set_pending_session(self, session_id: str) -> None:
        self._state["pending_session"] = session_id
        self.save()

    def is_session_synced(self, session_id: str) -> bool:
        return self._state.get("last_synced_session") == session_id

    def add_synced_file(self, file_path: str) -> None:
        files = self._state.setdefault("synced_files", [])
        if file_path not in files:
            files.append(file_path)
        self.save()

    def add_processed_clip(self, clip_path: str) -> None:
        clips = self._state.setdefault("processed_clips", [])
        if clip_path not in clips:
            clips.append(clip_path)
        self.save()

    def is_clip_processed(self, clip_path: str) -> bool:
        return clip_path in self._state.get("processed_clips", [])

    def get_last_synced_files(self) -> List[str]:
        """获取上次同步的文件列表（不修改状态）。"""
        return self._state.get("synced_files", []).copy()

    def clear_synced_files(self) -> None:
        """清空已同步文件记录。"""
        self._state["synced_files"] = []
        self.save()

    def rollback_last(self, dry_run: bool = False) -> List[str]:
        """撤销上次同步。

        Args:
            dry_run: 如果为 True，只返回待删除文件列表，不执行任何操作。

        Returns:
            上次同步的文件列表。
        """
        removed = self._state.get("synced_files", []).copy()
        if not dry_run:
            self._state["synced_files"] = []
            self.save()
        return removed

    def get_pending_session(self) -> Optional[str]:
        return self._state.get("pending_session")

    def get_last_synced_at(self) -> Optional[str]:
        return self._state.get("last_synced_at")

    def get_synced_files_count(self) -> int:
        return len(self._state.get("synced_files", []))

    def get_processed_clips(self) -> List[str]:
        return self._state.get("processed_clips", []).copy()

    def get_synced_files(self) -> List[str]:
        return self._state.get("synced_files", [])
