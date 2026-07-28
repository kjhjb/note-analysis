from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from note_analysis.agent.core import Agent
from note_analysis.models.models import Exam
from note_analysis.models.serializer import Serializer

SYSTEM_PROMPT = (
    "你是一位高中数学和物理的学科辅导专家。"
    "你将收到试卷中每道被标记为错误的题目信息。\n\n"
    "对于每道错题，请给出：\n"
    "1. correctAnswer: 正确的解答过程（用 LaTeX 标记公式）\n"
    "2. errorAnalysis: 简要分析学生可能出错的原因\n\n"
    "要求：\n"
    "- 数学和物理公式用 LaTeX 语法标记（$...$ 行内，$$...$$ 独立）\n"
    "- 解答过程要详细清晰，适合学生自学参考\n"
    "- 错误分析要一针见血，指出关键误区\n\n"
    "只返回 JSON，不包含其他文字。\n"
    '格式：{"corrections": [{"box_id": <int>, '
    '"correctAnswer": "<str>", "errorAnalysis": "<str>"}]}'
)


class Corrector:
    def __init__(
        self,
        exam_dir: str | Path,
        agent: Agent | None = None,
    ):
        self.exam_dir = Path(exam_dir)
        self.agent = agent or Agent()

    def correct(self) -> Exam:
        exam = self._load_exam()
        error_boxes = [b for b in exam.boxes if b.isError]
        if not error_boxes:
            return exam

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
        parts: list[str] = [
            "请为以下试卷中被标记为错误的题目生成修正解答：\n"
        ]
        for box in exam.boxes:
            if not box.isError:
                continue
            parts.append(f"--- 题目 {box.id} ---")
            parts.append(f"原题：{box.questionText or '(空)'}")
            parts.append(f"学生笔记：{box.annotations or '(无笔记批注)'}")
            marks_str = ", ".join(box.errorMarks) if box.errorMarks else "错误标记"
            parts.append(f"错误标记类型：{marks_str}")
            if box.reviewNotes:
                parts.append(f"审查备注：{box.reviewNotes}")
            parts.append("")

        parts.append(
            '\n请按以下 JSON 格式返回：\n'
            '{"corrections": [{"box_id": <int>, '
            '"correctAnswer": "<str>", "errorAnalysis": "<str>"}]}'
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
        corrections: list[dict[str, Any]] = data.get("corrections", [])
        if not corrections:
            msg = "LLM 响应中未找到 corrections 字段或 corrections 为空"
            raise ValueError(msg)
        return corrections

    @staticmethod
    def _update_exam(exam: Exam, results: list[dict[str, Any]]) -> None:
        for result in results:
            box_id: int | None = result.get("box_id")
            if box_id is None:
                continue
            for box in exam.boxes:
                if box.id != box_id:
                    continue
                correct_answer = result.get("correctAnswer", "")
                error_analysis = result.get("errorAnalysis", "")
                box.correction = (
                    f"【正确解答】{correct_answer}\n【错误分析】{error_analysis}"
                )
