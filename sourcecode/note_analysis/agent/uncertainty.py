from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from note_analysis.agent.core import Agent
from note_analysis.agent.recognizer import crop_bbox_from_image, image_to_base64
from note_analysis.models.models import BBox, Exam
from note_analysis.models.serializer import Serializer

SYSTEM_PROMPT = (
    "你是一位专业的试卷文字识别助手。"
    "你将收到一些从试卷中裁剪出的不确定文字区域的图片。"
    "每张图片对应一个需要精确识别的小区域。\n\n"
    "对于每个区域，请仔细查看并给出：\n"
    "1. refined_guess: 你最确定的文字内容识别结果\n"
    "2. confidence: 你的置信度评分（0.0~1.0）\n\n"
    "要求：\n"
    "- 数学和物理公式用 LaTeX 语法标记（$...$ 行内，$$...$$ 独立）\n"
    "- 结合上下文（提供的原题文字）辅助判断\n"
    "- 如果完全无法识别，confidence 设为 0.0\n\n"
    "只返回 JSON，不包含其他文字。\n"
    '格式：{"regions": [{"box_id": <int>, "ur_index": <int>, '
    '"refined_guess": "<str>", "confidence": <float>}]}'
)


class UncertaintyResolver:
    def __init__(
        self,
        exam_dir: str | Path,
        agent: Agent | None = None,
    ):
        self.exam_dir = Path(exam_dir)
        self.agent = agent or Agent()

    def resolve(self) -> Exam:
        exam = self._load_exam()
        data = self._extract_uncertain_data(exam)
        if not data:
            return exam
        self._crop_uncertain_regions(data, exam)
        content = self._build_multimodal_content(data)
        response = self._call_llm(content)
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

    def _extract_uncertain_data(self, exam: Exam) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = []
        for box in exam.boxes:
            for idx, ur in enumerate(box.uncertainRegions):
                if ur.userConfirmed is not None:
                    continue
                data.append({
                    "box_id": box.id,
                    "ur_index": idx,
                    "llmGuess": ur.llmGuess,
                    "llmConfidence": ur.llmConfidence,
                    "orig_bbox": {
                        "x": box.bbox.x + ur.bbox.x,
                        "y": box.bbox.y + ur.bbox.y,
                        "w": ur.bbox.w,
                        "h": ur.bbox.h,
                    },
                    "photo_path": exam.photos[box.photoIndex],
                    "context": box.questionText,
                })
        return data

    def _crop_uncertain_regions(
        self, data: list[dict[str, Any]], exam: Exam
    ) -> None:
        for item in data:
            orig_bbox_dict = item["orig_bbox"]
            orig_bbox = BBox(
                x=orig_bbox_dict["x"],
                y=orig_bbox_dict["y"],
                w=orig_bbox_dict["w"],
                h=orig_bbox_dict["h"],
            )
            cropped = crop_bbox_from_image(item["photo_path"], orig_bbox)
            item["image_base64"] = image_to_base64(cropped)

    def _build_multimodal_content(
        self, data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"以下是 {len(data)} 个不确定文字区域的裁剪图片，"
                    "请仔细识别每个区域的文字内容。"
                ),
            }
        ]
        for item in data:
            content.append({
                "type": "text",
                "text": (
                    f"\n区域 box_id={item['box_id']}, ur_index={item['ur_index']}:\n"
                    f"原题上下文：{item['context']}\n"
                    f"原始猜测：{item['llmGuess']}（置信度：{item['llmConfidence']}）"
                ),
            })
            if "image_base64" in item:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": item["image_base64"],
                    },
                })
        content.append({
            "type": "text",
            "text": (
                '\n请按以下 JSON 格式返回：\n'
                '{"regions": [{"box_id": <int>, "ur_index": <int>, '
                '"refined_guess": "<str>", "confidence": <float>}]}'
            ),
        })
        return content

    def _call_llm(self, content: list[dict[str, Any]]) -> str:
        self.agent.add_message_blocks("user", content)
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
        regions: list[dict[str, Any]] = data.get("regions", [])
        if not regions:
            msg = "LLM 响应中未找到 regions 字段或 regions 为空"
            raise ValueError(msg)
        return regions

    @staticmethod
    def _update_exam(exam: Exam, results: list[dict[str, Any]]) -> None:
        for result in results:
            box_id: int | None = result.get("box_id")
            ur_index: int | None = result.get("ur_index")
            if box_id is None or ur_index is None:
                continue
            for box in exam.boxes:
                if box.id != box_id:
                    continue
                if 0 <= ur_index < len(box.uncertainRegions):
                    box.uncertainRegions[ur_index].llmGuess = result.get("refined_guess", "")
                    box.uncertainRegions[ur_index].llmConfidence = result.get("confidence", 0.0)

    @staticmethod
    def all_confirmed(exam: Exam) -> bool:
        for box in exam.boxes:
            for ur in box.uncertainRegions:
                if ur.userConfirmed is None:
                    return False
        return True
