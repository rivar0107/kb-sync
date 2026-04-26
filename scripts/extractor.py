"""LLM 提炼流程编排：读取 jsonl → 调用 LLM → 写入知识库。"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.config import ConfigManager
from scripts.jsonl_parser import parse_jsonl_file
from scripts.llm_client import LLMClient
from scripts.state import StateManager
from scripts.sync_engine import SyncEngine


class Extractor:
    """负责从 pending session 提取知识点并写入知识库。"""

    def __init__(self, kb_sync_dir: str):
        self.kb_sync_dir = Path(kb_sync_dir)
        self.config = ConfigManager(str(kb_sync_dir))
        self.config.load_or_create()
        self.state = StateManager(str(kb_sync_dir))
        self.state.load_or_create()
        self.engine = SyncEngine(str(kb_sync_dir))
        self.llm: Optional[LLMClient] = None

    def _init_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """根据 session_id 查找 jsonl 文件。"""
        projects_dir = Path.home() / ".claude" / "projects"
        if not projects_dir.exists():
            return None
        for jsonl in projects_dir.rglob("*.jsonl"):
            if jsonl.stem == session_id:
                return jsonl
        return None

    def _truncate_for_llm(self, text: str, max_chars: int = 120000) -> str:
        """截断文本到 LLM 可处理长度。"""
        if len(text) <= max_chars:
            return text
        head = int(max_chars * 0.2)
        tail = max_chars - head
        return text[:head] + "\n\n...[内容截断]...\n\n" + text[-tail:]

    def _validate_entry(self, entry: Dict[str, Any]) -> bool:
        """验证 entry 是否满足写入条件。"""
        min_confidence = self.config.get("filters.min_confidence", 0.7)
        confidence = entry.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)) or confidence < min_confidence:
            return False
        title = entry.get("title", "").strip()
        body = entry.get("body", "").strip()
        if not title or not body:
            return False
        return True

    def extract_and_sync(self, session_id: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """执行完整提炼和同步流程。

        Args:
            session_id: 要同步的会话 ID；为 None 时使用 pending_session
            dry_run: 如果为 True，只返回预览结果，不写入知识库

        Returns:
            结果字典，包含 synced_count, skipped_count, entries, errors
        """
        result = {
            "session_id": session_id or self.state.get_pending_session(),
            "synced_count": 0,
            "skipped_count": 0,
            "entries": [],
            "errors": [],
        }

        target_session = session_id or self.state.get_pending_session()
        if not target_session:
            result["errors"].append("没有待同步的会话（session_id 为空）")
            return result

        session_file = self._find_session_file(target_session)
        if not session_file or not session_file.exists():
            result["errors"].append(f"找不到会话文件: {target_session}")
            return result

        # 1. 解析 jsonl
        dialogue_text = parse_jsonl_file(str(session_file))
        if not dialogue_text:
            result["errors"].append("对话内容为空，无需同步")
            self.state.mark_session_synced(target_session)
            return result

        dialogue_text = self._truncate_for_llm(dialogue_text)

        # 2. 调用 LLM 提炼
        try:
            llm = self._init_llm()
            entries = llm.extract_dialogue(dialogue_text)
        except RuntimeError as exc:
            result["errors"].append(f"LLM 客户端初始化失败: {exc}")
            return result
        except Exception as exc:
            result["errors"].append(f"LLM 提炼失败: {exc}")
            return result

        if not entries:
            result["errors"].append("LLM 未返回任何有效知识点")
            self.state.mark_session_synced(target_session)
            return result

        # 3. 过滤和写入
        max_entries = self.config.get("filters.max_entries_per_session", 10)
        entries = entries[:max_entries]

        for entry in entries:
            if not self._validate_entry(entry):
                result["skipped_count"] += 1
                continue

            result["entries"].append(entry)

            if dry_run:
                continue

            category = entry.get("category", "未确定")
            # 标准化分类名称
            category_map = {
                "concept": "概念",
                "figure": "人物",
                "project": "项目",
                "tool": "工具",
                "unknown": "未确定",
                "staging": "未确定",
            }
            category = category_map.get(category.lower(), category)

            # 如果分类不在标准列表中，设为未确定
            if category not in ("概念", "人物", "项目", "工具"):
                category = "未确定"

            try:
                self.engine.write_note(
                    title=entry["title"],
                    category=category,
                    body=entry["body"],
                    session_id=target_session,
                )
                result["synced_count"] += 1
            except Exception as exc:
                result["errors"].append(f"写入笔记失败 ({entry.get('title', '?')}): {exc}")

        # 4. 标记为已同步（即使写入失败也标记，避免反复重试同一内容）
        if not dry_run:
            self.state.mark_session_synced(target_session)

        return result

    def preview(self, session_id: Optional[str] = None) -> str:
        """生成同步预览文本（供用户在交互式流程中查看）。"""
        result = self.extract_and_sync(session_id=session_id, dry_run=True)
        lines = ["kb-sync 提炼预览", "-" * 40]
        lines.append(f"会话: {result['session_id'][:8]}...")
        lines.append(f"有效条目: {len(result['entries'])}")
        lines.append(f"跳过条目: {result['skipped_count']}")

        if result["errors"]:
            lines.append(f"错误: {len(result['errors'])}")
            for err in result["errors"][:3]:
                lines.append(f"  ⚠️ {err}")

        for i, entry in enumerate(result["entries"][:5], 1):
            title = entry.get("title", "无标题")
            category = entry.get("category", "未确定")
            confidence = entry.get("confidence", 0.0)
            body = entry.get("body", "")[:80].replace("\n", " ")
            lines.append(f"\n{i}. [{category}] {title} (置信度: {confidence:.2f})")
            lines.append(f"   {body}...")

        if len(result["entries"]) > 5:
            lines.append(f"\n... 还有 {len(result['entries']) - 5} 个条目")

        return "\n".join(lines)
