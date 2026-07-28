from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from note_analysis.agent.core import Agent
from note_analysis.models.models import BBox, Exam, UncertainRegion
from note_analysis.models.serializer import Serializer

DEFAULT_CONFIDENCE_THRESHOLD = 0.8

SYSTEM_PROMPT = (
    "你是一位专业的试卷笔记识别助手。"
    "你将收到一张或多张试卷大题区域的裁剪图片。\n\n"
    "对于每道大题区域，请识别：\n"
    "1. questionText: 黑色印刷文字（原题内容），包含所有题目文字和公式\n"
    "2. annotations: 红色手写笔记文字（学生的批注、解题过程）\n"
    "3. isError: 该题目是否有打叉（×）、画斜线（\\）等表示错误的标记，true 或 false\n"
    "4. errorMarks: 检测到的具体错误标记类型列表，如 [\"cross\"] 或 [\"backslash\"]，空列表表示无错误\n"
    "5. circledKeyPoints: 被圆圈、下划线、高亮等标记出来的重点内容文字（若无则为空字符串）\n"
    "6. circledRegions: 圈划区域的位置坐标列表（每个元素含 x, y, w, h），若无可为空列表\n"
    "7. uncertainRegions: 你不太确定的文字区域列表\n\n"
    "要求：\n"
    "- 数学和物理公式用 LaTeX 语法标记（$...$ 行内，$$...$$ 独立）\n"
    "- 对每个文字区域给出置信度评分（0.0~1.0）\n"
    "- 置信度低于 0.8 的区域要标记为 uncertainRegions\n"
    "- uncertainRegions 的 bbox 坐标相对于裁剪图片\n"
    "- circledRegions 的 bbox 坐标相对于裁剪图片\n\n"
    "只返回 JSON，不包含其他文字。"
)


def crop_bbox_from_image(image_path: str | Path, bbox: BBox) -> np.ndarray:
    img = cv2.imread(str(image_path))
    if img is None:
        msg = f"无法读取图片: {image_path}"
        raise FileNotFoundError(msg)
    x, y, w, h = int(bbox.x), int(bbox.y), int(bbox.w), int(bbox.h)
    return img[y : y + h, x : x + w]


def image_to_base64(image: np.ndarray) -> str:
    _, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return base64.b64encode(buffer).decode("utf-8")


class Recognizer:
    def __init__(
        self,
        exam_dir: str | Path,
        agent: Agent | None = None,
        threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        self.exam_dir = Path(exam_dir)
        self.agent = agent or Agent()
        self.threshold = threshold

    def recognize(self) -> Exam:
        exam = self._load_exam()
        boxes_data = self._prepare_boxes_data(exam)
        response = self._call_llm(boxes_data)
        results = self._parse_response(response)
        self._update_exam(exam, results, boxes_data)
        Serializer.save(exam, self.exam_dir)
        return exam

    def _load_exam(self) -> Exam:
        files = Serializer.find_exam_files(self.exam_dir)
        if not files:
            msg = f"未找到 JSON 文件: {self.exam_dir}"
            raise FileNotFoundError(msg)
        return Serializer.load(files[0])

    def _prepare_boxes_data(self, exam: Exam) -> list[dict[str, Any]]:
        boxes_data: list[dict[str, Any]] = []
        for box in exam.boxes:
            photo_path = exam.photos[box.photoIndex]
            cropped = crop_bbox_from_image(photo_path, box.bbox)
            img_b64 = image_to_base64(cropped)
            boxes_data.append({
                "id": box.id,
                "photoIndex": box.photoIndex,
                "bbox": box.bbox.model_dump(),
                "image_base64": img_b64,
            })
        return boxes_data

    def _build_multimodal_content(self, boxes_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": "请分析以下试卷中的各大题区域。"}
        ]
        for data in boxes_data:
            content.append({
                "type": "text",
                "text": (
                    f"\n题目 {data['id']}（位置: x={data['bbox']['x']:.0f}, "
                    f"y={data['bbox']['y']:.0f}, "
                    f"宽={data['bbox']['w']:.0f}, 高={data['bbox']['h']:.0f}）:"
                ),
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": data["image_base64"],
                },
            })
        content.append({
            "type": "text",
            "text": (
                '\n请按以下 JSON 格式返回：\n'
                '{"boxes": ['
                '{"id": <int>, "questionText": "<str>", '
                '"annotations": "<str>", '
                '"isError": <bool>, '
                '"errorMarks": ["<str>", ...], '
                '"circledKeyPoints": "<str>", '
                '"circledRegions": [{"x": <float>, "y": <float>, '
                '"w": <float>, "h": <float>}], '
                '"uncertainRegions": [{"bbox": {"x": <float>, "y": <float>, '
                '"w": <float>, "h": <float>}, "llmGuess": "<str>", '
                '"llmConfidence": <float>}]}]}'
            ),
        })
        return content

    def _call_llm(self, boxes_data: list[dict[str, Any]]) -> str:
        content = self._build_multimodal_content(boxes_data)
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
        boxes: list[dict[str, Any]] = data.get("boxes", [])
        if not boxes:
            msg = "LLM 响应中未找到 boxes 字段或 boxes 为空"
            raise ValueError(msg)
        return boxes

    def _update_exam(
        self,
        exam: Exam,
        results: list[dict[str, Any]],
        boxes_data: list[dict[str, Any]],
    ) -> None:
        result_map: dict[int, dict[str, Any]] = {r["id"]: r for r in results}
        image_map: dict[int, str] = {d["id"]: d.get("image_base64", "") for d in boxes_data}

        for box in exam.boxes:
            result = result_map.get(box.id)
            if result is None:
                continue

            box.questionText = result.get("questionText", "")
            box.annotations = result.get("annotations", "")

            box.isError = result.get("isError", False)
            box.errorMarks = result.get("errorMarks", [])
            box.circledKeyPoints = result.get("circledKeyPoints", "")

            circled_bboxes = result.get("circledRegions", [])
            box.circledRegions = [
                BBox(x=cb.get("x", 0), y=cb.get("y", 0), w=cb.get("w", 0), h=cb.get("h", 0))
                for cb in circled_bboxes
            ]

            img_b64 = image_map.get(box.id, "")
            if img_b64:
                box.images = [img_b64]

            box.uncertainRegions = []
            for ur in result.get("uncertainRegions", []):
                conf = ur.get("llmConfidence", 1.0)
                if conf < self.threshold:
                    bbox_data = ur.get("bbox", {})
                    box.uncertainRegions.append(
                        UncertainRegion(
                            bbox=BBox(
                                x=bbox_data.get("x", 0),
                                y=bbox_data.get("y", 0),
                                w=bbox_data.get("w", 0),
                                h=bbox_data.get("h", 0),
                            ),
                            llmGuess=ur.get("llmGuess", ""),
                            llmConfidence=conf,
                        )
                    )
