from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from note_analysis.agent.recognizer import Recognizer, crop_bbox_from_image, image_to_base64
from note_analysis.models.models import BBox, Exam, QuestionBox
from note_analysis.models.serializer import Serializer


@pytest.fixture
def exam_dir(tmp_path: Path) -> Path:
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (50, 100), (550, 300), (0, 0, 0), 2)
    cv2.putText(
        img, "求解方程 x^2 + 2x + 1 = 0",
        (60, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cv2.putText(
        img, "x = -1  (红笔批注)",
        (60, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
    )
    photo_path = tmp_path / "exam_photo.jpg"
    cv2.imwrite(str(photo_path), img)

    exam = Exam.create([str(photo_path)])
    exam.boxes = [
        QuestionBox(id=1, bbox=BBox(x=40, y=80, w=520, h=240), photoIndex=0),
        QuestionBox(id=2, bbox=BBox(x=40, y=340, w=520, h=200), photoIndex=0),
    ]

    Serializer.save(exam, tmp_path)
    return tmp_path


def test_crop_bbox_from_image(exam_dir: Path) -> None:
    photo = str(exam_dir / "exam_photo.jpg")
    bbox = BBox(x=40, y=80, w=520, h=240)

    cropped = crop_bbox_from_image(photo, bbox)

    assert cropped.shape[0] == 240
    assert cropped.shape[1] == 520
    assert cropped.shape[2] == 3


def test_crop_bbox_from_image_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        crop_bbox_from_image("/nonexistent.jpg", BBox(x=0, y=0, w=100, h=100))


def test_image_to_base64() -> None:
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    encoded = image_to_base64(img)
    assert isinstance(encoded, str)
    assert len(encoded) > 0
    import base64
    decoded = base64.b64decode(encoded)
    assert len(decoded) > 0


def test_recognizer_init_defaults(exam_dir: Path) -> None:
    r = Recognizer(exam_dir)
    assert r.exam_dir == exam_dir
    assert r.threshold == 0.8


def test_recognizer_init_custom_threshold(exam_dir: Path) -> None:
    r = Recognizer(exam_dir, threshold=0.5)
    assert r.threshold == 0.5


def test_recognizer_load_exam(exam_dir: Path) -> None:
    r = Recognizer(exam_dir)
    exam = r._load_exam()
    assert len(exam.photos) == 1
    assert len(exam.boxes) == 2


def test_recognizer_load_exam_not_found(tmp_path: Path) -> None:
    r = Recognizer(tmp_path)
    with pytest.raises(FileNotFoundError):
        r._load_exam()


def test_recognizer_prepare_boxes_data(exam_dir: Path) -> None:
    r = Recognizer(exam_dir)
    exam = r._load_exam()
    boxes_data = r._prepare_boxes_data(exam)

    assert len(boxes_data) == 2
    assert boxes_data[0]["id"] == 1
    assert "image_base64" in boxes_data[0]
    assert "bbox" in boxes_data[0]
    assert boxes_data[0]["photoIndex"] == 0


def test_recognizer_parse_response_valid() -> None:
    r = Recognizer(".")
    response = json.dumps({
            "boxes": [
                {
                    "id": 1,
                    "questionText": "求解方程 $x^2 + 2x + 1 = 0$",
                    "annotations": "使用公式法 $x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$",
                    "isError": False,
                    "errorMarks": [],
                    "circledKeyPoints": "",
                    "circledRegions": [],
                    "uncertainRegions": [
                        {
                            "bbox": {"x": 10, "y": 20, "w": 100, "h": 30},
                            "llmGuess": "可能文字",
                            "llmConfidence": 0.65,
                        }
                    ],
                }
            ]
    })

    results = r._parse_response(response)
    assert len(results) == 1
    assert results[0]["id"] == 1
    assert "$x^2" in results[0]["questionText"]


def test_recognizer_parse_response_markdown_wrapped() -> None:
    r = Recognizer(".")
    response = "```json\n{\"boxes\": [{\"id\": 1, \"questionText\": \"test\", \"isError\": false, \"errorMarks\": [], \"circledKeyPoints\": \"\", \"circledRegions\": [], \"uncertainRegions\": []}]}\n```"

    results = r._parse_response(response)
    assert len(results) == 1
    assert results[0]["id"] == 1


def test_recognizer_parse_response_empty() -> None:
    r = Recognizer(".")
    with pytest.raises(ValueError, match="未找到 boxes"):
        r._parse_response('{"boxes": []}')


def test_recognizer_parse_response_no_json() -> None:
    r = Recognizer(".")
    with pytest.raises(ValueError, match="无法.*解析 JSON"):
        r._parse_response("完全无法解析的内容")


def test_recognizer_update_exam(exam_dir: Path) -> None:
    r = Recognizer(exam_dir)
    exam = r._load_exam()

    results = [
        {
            "id": 1,
            "questionText": "Question 1 content",
            "annotations": "Note 1 content",
            "isError": False,
            "errorMarks": [],
            "circledKeyPoints": "重点公式",
            "circledRegions": [{"x": 5, "y": 5, "w": 30, "h": 15}],
            "uncertainRegions": [],
        },
        {
            "id": 2,
            "questionText": "Question 2 content",
            "annotations": "Note 2 content",
            "isError": True,
            "errorMarks": ["cross"],
            "circledKeyPoints": "",
            "circledRegions": [],
            "uncertainRegions": [
                {
                    "bbox": {"x": 0, "y": 0, "w": 100, "h": 50},
                    "llmGuess": "模糊文字",
                    "llmConfidence": 0.6,
                }
            ],
        },
    ]

    r._update_exam(exam, results, [])

    assert exam.boxes[0].questionText == "Question 1 content"
    assert exam.boxes[0].annotations == "Note 1 content"
    assert exam.boxes[0].isError is False
    assert exam.boxes[0].errorMarks == []
    assert exam.boxes[0].circledKeyPoints == "重点公式"
    assert len(exam.boxes[0].circledRegions) == 1
    assert len(exam.boxes[0].uncertainRegions) == 0
    assert exam.boxes[1].questionText == "Question 2 content"
    assert exam.boxes[1].isError is True
    assert exam.boxes[1].errorMarks == ["cross"]
    assert len(exam.boxes[1].uncertainRegions) == 1
    assert exam.boxes[1].uncertainRegions[0].llmGuess == "模糊文字"
    assert exam.boxes[1].uncertainRegions[0].llmConfidence == 0.6


def test_recognizer_update_exam_stores_images(exam_dir: Path) -> None:
    r = Recognizer(exam_dir)
    exam = r._load_exam()

    results = [{"id": 1, "questionText": "Q1", "annotations": "", "isError": False, "errorMarks": [], "circledKeyPoints": "", "circledRegions": [], "uncertainRegions": []}]

    boxes_data = [{"id": 1, "image_base64": "dGVzdA=="}]
    r._update_exam(exam, results, boxes_data)

    assert len(exam.boxes[0].images) == 1
    assert exam.boxes[0].images[0] == "dGVzdA=="


def test_recognizer_update_exam_high_confidence_not_uncertain() -> None:
    r = Recognizer(".", threshold=0.8)
    exam = Exam.create(["test.jpg"])
    exam.boxes = [QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100))]

    results = [
        {
            "id": 1,
            "questionText": "text",
            "annotations": "",
            "isError": False,
            "errorMarks": [],
            "circledKeyPoints": "",
            "circledRegions": [],
            "uncertainRegions": [
                {
                    "bbox": {"x": 0, "y": 0, "w": 10, "h": 10},
                    "llmGuess": "maybe",
                    "llmConfidence": 0.95,
                }
            ],
        }
    ]

    r._update_exam(exam, results, [])
    assert len(exam.boxes[0].uncertainRegions) == 0


def test_recognizer_update_exam_skips_unknown_boxes(exam_dir: Path) -> None:
    r = Recognizer(exam_dir)
    exam = r._load_exam()

    results = [{"id": 999, "questionText": "ghost", "annotations": "", "isError": False, "errorMarks": [], "circledKeyPoints": "", "circledRegions": [], "uncertainRegions": []}]

    r._update_exam(exam, results, [])

    assert exam.boxes[0].questionText == ""


@patch("note_analysis.agent.core.httpx.Client.post")
def test_recognizer_recognize(mock_post: MagicMock, exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "boxes": [
                        {
                            "id": 1,
                            "questionText": "求解方程 $x^2=4$",
                            "annotations": "$x=\\pm 2$",
                            "isError": False,
                            "errorMarks": [],
                            "circledKeyPoints": "平方根性质",
                            "circledRegions": [{"x": 10, "y": 10, "w": 50, "h": 20}],
                            "uncertainRegions": [],
                        },
                        {
                            "id": 2,
                            "questionText": "三角函数",
                            "annotations": "",
                            "isError": True,
                            "errorMarks": ["cross"],
                            "circledKeyPoints": "",
                            "circledRegions": [],
                            "uncertainRegions": [],
                        },
                    ]
                }),
            }
        ]
    }
    mock_post.return_value = mock_response

    r = Recognizer(exam_dir)
    exam = r.recognize()

    assert exam.boxes[0].questionText == "求解方程 $x^2=4$"
    assert exam.boxes[0].annotations == "$x=\\pm 2$"
    assert exam.boxes[1].questionText == "三角函数"
    assert exam.boxes[0].isError is False
    assert exam.boxes[1].isError is True
    assert exam.boxes[1].errorMarks == ["cross"]
    assert exam.boxes[0].circledKeyPoints == "平方根性质"
    assert len(exam.boxes[0].circledRegions) == 1


@patch("note_analysis.agent.core.httpx.Client.post")
def test_recognizer_recognize_low_confidence(mock_post: MagicMock, exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "boxes": [
                        {
                            "id": 1,
                            "questionText": "已知函数 $f(x)$",
                            "annotations": "",
                            "isError": False,
                            "errorMarks": [],
                            "circledKeyPoints": "",
                            "circledRegions": [],
                            "uncertainRegions": [
                                {
                                    "bbox": {"x": 10, "y": 20, "w": 80, "h": 30},
                                    "llmGuess": "可能是导数",
                                    "llmConfidence": 0.55,
                                }
                            ],
                        }
                    ]
                }),
            }
        ]
    }
    mock_post.return_value = mock_response

    r = Recognizer(exam_dir, threshold=0.8)
    exam = r.recognize()

    assert len(exam.boxes[0].uncertainRegions) == 1
    assert exam.boxes[0].uncertainRegions[0].llmGuess == "可能是导数"
    assert exam.boxes[0].uncertainRegions[0].llmConfidence == 0.55


@patch("note_analysis.agent.core.httpx.Client.post")
def test_recognizer_recognize_saves_json(mock_post: MagicMock, exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "boxes": [
                        {
                            "id": 1,
                            "questionText": "Q1",
                            "annotations": "A1",
                            "isError": False,
                            "errorMarks": [],
                            "circledKeyPoints": "",
                            "circledRegions": [],
                            "uncertainRegions": [],
                        }
                    ]
                }),
            }
        ]
    }
    mock_post.return_value = mock_response

    r = Recognizer(exam_dir)
    r.recognize()

    json_files = Serializer.find_exam_files(exam_dir)
    assert len(json_files) == 1

    reloaded = Serializer.load(json_files[0])
    assert reloaded.boxes[0].questionText == "Q1"


def test_recognizer_no_json_files(tmp_path: Path) -> None:
    r = Recognizer(tmp_path)
    with pytest.raises(FileNotFoundError):
        r.recognize()
