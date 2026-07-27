from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from note_analysis.agent.core import Agent
from note_analysis.models.models import Exam
from note_analysis.models.serializer import Serializer

SYSTEM_PROMPT = (
    "你是一位试卷笔记一致性审查助手。"
    "你将收到每道大题的：(1) 原题文字（黑色印刷文字）(2) 红字笔记（学生批注）。"
    "请判断两者在逻辑上是否自洽。\n\n"
    "要求：\n"
    "1. consistent：笔记与原题在逻辑上一致，笔记补充内容合理\n"
    "2. inconsistent：笔记与原题存在矛盾（如题目条件为 x=5 但笔记写 x=3 且无解释）\n"
    "3. uncertain：无法确定一致性\n\n"
    "对于不确定区域，检查 userConfirmed 内容与周围上下文是否一致。\n"
    "只返回 JSON，不包含其他文字。"
)


class Reviewer:
    def __init__(
        self,
        exam_dir: str | Path,
        agent: Agent | None = None,
    ):
        self.exam_dir = Path(exam_dir)
        self.agent = agent or Agent()

    def review(self) -> Exam:
        exam = self._load_exam()
        prompt = self._build_prompt(exam)
        response = self._call_llm(prompt)
        results = self._parse_response(response)
        self._update_exam(exam, results)
        Serializer.save(exam, self.exam_dir)
        return exam

    def _load_exam(self) -> Exam:
        files = Serializer.find_exam_files(self.exam_dir)
        if not files:
            msg = f"未找到 JSON 文件: {self.exam_dir}"
            raise FileNotFoundError(msg)
        return Serializer.load(files[0])

    def _build_prompt(self, exam: Exam) -> str:
        parts: list[str] = ["请审查以下试卷中各题目的逻辑一致性：\n"]
        for box in exam.boxes:
            parts.append(f"--- 题目 {box.id} ---")
            parts.append(f"原题：{box.questionText or '(空)'}")
            parts.append(f"笔记：{box.annotations or '(无笔记批注)'}")
            if box.uncertainRegions:
                parts.append("不确定区域：")
                for idx, ur in enumerate(box.uncertainRegions):
                    ur_info = f"  [{idx}] 猜测: {ur.llmGuess}"
                    if ur.userConfirmed is not None:
                        ur_info += f", 用户确认: {ur.userConfirmed}"
                    parts.append(ur_info)
            parts.append("")
        parts.append(
            '\n请按以下 JSON 格式返回：\n'
            '{"reviews": [{"box_id": <int>, "reviewStatus": "consistent"|"inconsistent"|"uncertain", '
            '"reviewNotes": "<str>"}]}'
        )
        return "\n".join(parts)

    def _call_llm(self, prompt: str) -> str:
        self.agent.add_message("user", prompt)
        result = self.agent.call(system_prompt=SYSTEM_PROMPT)
        self.agent.pop_message()
        return result

    @staticmethod
    def _parse_response(response: str) -> list[dict[str, Any]]:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if not json_match:
            msg = "无法从 LLM 响应中解析 JSON"
            raise ValueError(msg)
        try:
            data: dict[str, Any] = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            msg = f"LLM 响应 JSON 解析失败: {e}"
            raise ValueError(msg) from e
        reviews: list[dict[str, Any]] = data.get("reviews", [])
        if not reviews:
            msg = "LLM 响应中未找到 reviews 字段或 reviews 为空"
            raise ValueError(msg)
        return reviews

    @staticmethod
    def _update_exam(exam: Exam, results: list[dict[str, Any]]) -> None:
        for result in results:
            box_id: int | None = result.get("box_id")
            if box_id is None:
                continue
            for box in exam.boxes:
                if box.id != box_id:
                    continue
                box.reviewStatus = result.get("reviewStatus", "pending")
                box.reviewNotes = result.get("reviewNotes", "")
