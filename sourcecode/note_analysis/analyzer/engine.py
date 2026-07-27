from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from note_analysis.agent.core import Agent
from note_analysis.models.models import Exam, WeakPoint
from note_analysis.models.serializer import Serializer

SYSTEM_PROMPT = (
    "你是一位高中数学和物理的学科分析专家。"
    "你将收到多份试卷的题目内容和学生笔记批注。\n\n"
    "请分析这些试卷，完成以下任务：\n"
    "1. 提取所有涉及的知识点（使用高中数学、物理的标准专有名词，如「三角函数」「牛顿第二定律」「导数与单调性」等）\n"
    "2. 对每个知识点，统计有多少道题涉及该知识点，以及其中有多少道题可能存在理解问题\n"
    "   （判断依据：笔记中有解题过程、reviewStatus 为 inconsistent 或 uncertain、有不确定区域等）\n"
    "3. 基于错误频次为每个知识点生成针对性的提升建议\n\n"
    "只返回 JSON，不包含其他文字。\n"
    '格式：{"weakPoints": [{"knowledgePoint": "<知识点名称>", "errorCount": <整数>, '
    '"llmAdvice": "<提升建议（使用高中数理专有名词）>"}]}'
)


class Analyzer:
    """跨卷薄弱点分析引擎

    遍历多份 JSON 试卷，汇总题目和笔记数据，
    调用 LLM 提取知识点并统计错误频次，生成提升建议。
    """

    def __init__(self, exams_dir: str | Path, agent: Agent | None = None):
        self.exams_dir = Path(exams_dir)
        self.agent = agent or Agent()

    def analyze(self) -> list[Exam]:
        exams = self._load_all_exams()
        if not exams:
            return exams

        summary = self._build_summary(exams)
        response = self._call_llm(summary)
        results = self._parse_response(response)
        self._update_exams(exams, results)
        self._save_exams(exams)
        return exams

    def _load_all_exams(self) -> list[Exam]:
        json_files = Serializer.find_exam_files(self.exams_dir)
        return [Serializer.load(f) for f in json_files]

    def _build_summary(self, exams: list[Exam]) -> str:
        parts: list[str] = ["以下是多份试卷的题目内容和学生笔记，请进行分析：\n"]
        parts.append(f"共 {len(exams)} 份试卷\n")

        for exam_idx, exam in enumerate(exams):
            parts.append(f"\n{'='*60}")
            parts.append(f"试卷 {exam_idx + 1}: {exam.examId}")
            parts.append(f"创建时间: {exam.createdAt}")
            parts.append(f"题目数量: {len(exam.boxes)}")
            parts.append("")

            for box in exam.boxes:
                parts.append(f"--- 题目 {box.id} ---")
                parts.append(f"原题: {box.questionText or '(空)'}")
                parts.append(f"笔记: {box.annotations or '(无)'}")
                parts.append(f"审查状态: {box.reviewStatus}")
                if box.reviewNotes:
                    parts.append(f"审查备注: {box.reviewNotes}")
                if box.uncertainRegions:
                    parts.append(f"不确定区域数: {len(box.uncertainRegions)}")
                    for ur in box.uncertainRegions:
                        confirmed = ur.userConfirmed if ur.userConfirmed else ur.llmGuess
                        parts.append(f"  不确定区域内容: {confirmed} (置信度: {ur.llmConfidence:.2f})")
                parts.append("")

        parts.append(
            '\n请按 JSON 格式返回：\n'
            '{"weakPoints": [{"knowledgePoint": "<str>", "errorCount": <int>, '
            '"llmAdvice": "<str>"}]}'
        )
        return "\n".join(parts)

    def _call_llm(self, summary: str) -> str:
        self.agent.add_message("user", summary)
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
        weak_points: list[dict[str, Any]] = data.get("weakPoints", [])
        if not weak_points:
            msg = "LLM 响应中未找到 weakPoints 字段或 weakPoints 为空"
            raise ValueError(msg)
        return weak_points

    @staticmethod
    def _update_exams(exams: list[Exam], results: list[dict[str, Any]]) -> None:
        weak_points = [
            WeakPoint(
                knowledgePoint=r.get("knowledgePoint", ""),
                errorCount=r.get("errorCount", 0),
                llmAdvice=r.get("llmAdvice", ""),
            )
            for r in results
        ]
        for exam in exams:
            exam.weakPoints = weak_points

    def _save_exams(self, exams: list[Exam]) -> None:
        for exam in exams:
            Serializer.save(exam, self.exams_dir)
