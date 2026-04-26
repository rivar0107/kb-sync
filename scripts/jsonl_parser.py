"""JSONL 对话解析器：从 Claude Code 的 jsonl 文件中提取可读的对话文本。"""

import json
from pathlib import Path
from typing import List, Optional


def extract_text_from_content(content) -> str:
    """从 message.content 字段提取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "thinking":
                    # 跳过 thinking 内容，不纳入对话文本
                    continue
                elif item.get("type") == "tool_use":
                    # 跳过 tool_use，但保留其名称作为上下文提示
                    name = item.get("name", "")
                    if name:
                        texts.append(f"[调用工具: {name}]")
                elif item.get("type") == "tool_result":
                    # 工具结果通常很长，只保留简短提示
                    texts.append("[工具执行结果]")
        return "\n".join(texts)
    return ""


def parse_jsonl_file(file_path: str, max_chars: int = 120000) -> str:
    """解析 jsonl 文件，提取用户和助手的对话文本。

    Args:
        file_path: jsonl 文件路径
        max_chars: 最大字符数，超过则截断（保留开头的系统上下文 + 末尾的对话）

    Returns:
        格式化的对话文本，如 "USER: ...\n\nASSISTANT: ..."
    """
    path = Path(file_path)
    if not path.exists():
        return ""

    messages: List[str] = []
    total_chars = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")
            if msg_type == "user":
                content = extract_text_from_content(obj.get("message", {}).get("content", ""))
                if content:
                    text = f"USER: {content}"
                    messages.append(text)
                    total_chars += len(text)
            elif msg_type == "assistant":
                content = extract_text_from_content(obj.get("message", {}).get("content", []))
                if content:
                    text = f"ASSISTANT: {content}"
                    messages.append(text)
                    total_chars += len(text)
            # 忽略 attachment、permission-mode、file-history-snapshot 等非对话事件

    full_text = "\n\n".join(messages)

    if len(full_text) > max_chars:
        # 截断策略：保留开头 20%（通常是上下文设置）和末尾 80%（实际对话）
        head_len = int(max_chars * 0.2)
        tail_len = max_chars - head_len
        full_text = full_text[:head_len] + "\n\n...[内容截断]...\n\n" + full_text[-tail_len:]

    return full_text


def get_dialogue_summary(file_path: str, max_turns: int = 20) -> str:
    """获取对话摘要（仅最近 N 轮），用于快速预览。"""
    path = Path(file_path)
    if not path.exists():
        return ""

    messages: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")
            if msg_type == "user":
                content = extract_text_from_content(obj.get("message", {}).get("content", ""))
                if content:
                    messages.append(f"USER: {content}")
            elif msg_type == "assistant":
                content = extract_text_from_content(obj.get("message", {}).get("content", []))
                if content:
                    messages.append(f"ASSISTANT: {content}")

    # 只保留最近 N 轮
    recent = messages[-max_turns * 2:]
    return "\n\n".join(recent)
