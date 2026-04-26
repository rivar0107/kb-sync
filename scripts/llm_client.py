"""LLM 客户端：封装 Anthropic API 调用，用于对话提炼和分类。"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── 尝试导入 anthropic SDK ───
try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore
    ANTHROPIC_AVAILABLE = False


class LLMClient:
    """轻量级 LLM 客户端，支持提取对话知识点和内容分类。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or self._resolve_api_key()
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        self.model = os.environ.get("ANTHROPIC_REASONING_MODEL", "claude-sonnet-4-6")
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "anthropic SDK 未安装。请运行: python3 -m pip install anthropic"
            )
        if not self.api_key:
            raise RuntimeError(
                "未找到 API key。请设置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN 环境变量。"
            )

        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = anthropic.Anthropic(**kwargs)

    # ─── 内部工具 ───

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        """按优先级解析 API key。"""
        for key in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]:
            value = os.environ.get(key, "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _load_prompt(prompt_name: str) -> str:
        """从 prompts/ 目录加载 prompt 文本。"""
        skill_root = Path(__file__).parent.parent
        prompt_path = skill_root / "prompts" / f"{prompt_name}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """从 Markdown 代码块或纯文本中提取 JSON 字符串。"""
        # 优先匹配 ```json ... ```
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 其次匹配 ``` ... ```
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 最后尝试直接找 { 开头的 JSON
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return None

    def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        """底层 API 调用。"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # 聚合所有 text 块
        texts = []
        for block in response.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "".join(texts)

    # ─── 公开 API ───

    def extract_dialogue(self, dialogue_text: str) -> List[Dict[str, Any]]:
        """从对话文本中提取知识点。

        Returns:
            entries 列表，每个 entry 包含 title, category, body, tags, confidence, reason
        """
        system_prompt = self._load_prompt("extract_dialogue")
        user_prompt = f"## 对话记录\n\n{dialogue_text}"

        raw = self._call(system_prompt, user_prompt, max_tokens=4096, temperature=0.2)
        json_str = self._extract_json(raw)
        if not json_str:
            raise ValueError(f"无法从 LLM 输出中提取 JSON:\n{raw[:500]}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM 输出不是合法 JSON:\n{json_str[:500]}") from exc

        entries = data.get("entries", [])
        if not isinstance(entries, list):
            raise ValueError(f"JSON 中 entries 字段不是列表: {type(entries)}")
        return entries

    def classify(self, text: str) -> str:
        """对文本进行分类。

        Returns:
            分类名称：概念 / 项目 / 人物 / 工具 / 未确定
        """
        system_prompt = self._load_prompt("classify")
        user_prompt = f"## 待分类文本\n\n{text}"

        raw = self._call(system_prompt, user_prompt, max_tokens=50, temperature=0.1)
        # 取第一行非空内容
        for line in raw.split("\n"):
            line = line.strip()
            if line:
                return line
        return "未确定"
