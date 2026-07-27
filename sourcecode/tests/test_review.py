from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from note_analysis.agent.review import Reviewer
from note_analysis.models.models import BBox, Exam, QuestionBox, UncertainRegion
from note_analysis.models.serializer import Serializer


@pytest.fixture
def exam_dir_consistent(tmp_path: Path) -> Path:
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, "已知函数 f(x) = sin(x)，求 f'(x)",
        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cv2.putText(
        img, "f'(x) = cos(x)",
        (50, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
    )
    photo_path = tmp_path / "exam.jpg"
    cv2.imwrite(str(photo_path), img)

    exam = Exam.create([str(photo_path)])
    exam.boxes = [
        QuestionBox(
            id=1,
            bbox=BBox(x=30, y=80, w=540, h=120),
            photoIndex=0,
            questionText="已知函数 f(x) = sin(x)，求 f'(x)",
            annotations="f'(x) = cos(x)",
        ),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


@pytest.fixture
def exam_dir_inconsistent(tmp_path: Path) -> Path:
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, "已知 x = 5，求 2x + 3",
        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cropped = (tmp_path / "exam.jpg")
    cv2.imwrite(str(cropped), img)

    exam = Exam.create([str(cropped)])
    exam.boxes = [
        QuestionBox(
            id=1,
            bbox=BBox(x=30, y=80, w=540, h=80),
            photoIndex=0,
            questionText="已知 x = 5，求 2x + 3",
            annotations="2x + 3 = 7",  # 应该是 13
        ),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


@pytest.fixture
def exam_dir_with_ur(tmp_path: Path) -> Path:
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, "求三角形面积",
        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cropped = (tmp_path / "exam.jpg")
    cv2.imwrite(str(cropped), img)

    exam = Exam.create([str(cropped)])
    exam.boxes = [
        QuestionBox(
            id=1,
            bbox=BBox(x=30, y=80, w=540, h=80),
            photoIndex=0,
            questionText="求三角形面积，底=6，高=4",
            annotations="S = 12",
            uncertainRegions=[
                UncertainRegion(
                    bbox=BBox(x=10, y=10, w=60, h=25),
                    llmGuess="可能是 6",
                    llmConfidence=0.65,
                    userConfirmed="6",
                ),
            ],
        ),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


def test_reviewer_init(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    assert r.exam_dir == exam_dir_consistent


def test_load_exam(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    assert len(exam.boxes) == 1
    assert exam.boxes[0].questionText == "已知函数 f(x) = sin(x)，求 f'(x)"
    assert exam.boxes[0].annotations == "f'(x) = cos(x)"


def test_build_prompt_contains_question_and_annotation(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    prompt = r._build_prompt(exam)
    assert "已知函数 f(x) = sin(x)" in prompt
    assert "f'(x) = cos(x)" in prompt
    assert "题目 1" in prompt


def test_build_prompt_handles_no_annotations(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    exam.boxes[0].annotations = ""
    prompt = r._build_prompt(exam)
    assert "(无笔记批注)" in prompt


def test_build_prompt_includes_uncertain_regions(exam_dir_with_ur: Path) -> None:
    r = Reviewer(exam_dir_with_ur)
    exam = r._load_exam()
    prompt = r._build_prompt(exam)
    assert "不确定区域" in prompt
    assert "userConfirmed" in prompt or "用户确认" in prompt
    assert "6" in prompt


@pytest.mark.parametrize("response,expected_box_id,expected_status", [
    (
        '{"reviews": [{"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "笔记与原题一致"}]}',
        1, "consistent",
    ),
    (
        '{"reviews": [{"box_id": 1, "reviewStatus": "inconsistent", "reviewNotes": "计算有误"}]}',
        1, "inconsistent",
    ),
    (
        '{"reviews": [{"box_id": 1, "reviewStatus": "uncertain", "reviewNotes": "无法判断"}]}',
        1, "uncertain",
    ),
])
def test_parse_response_valid(response: str, expected_box_id: int, expected_status: str) -> None:
    r = Reviewer(".")
    results = r._parse_response(response)
    assert len(results) == 1
    assert results[0]["box_id"] == expected_box_id
    assert results[0]["reviewStatus"] == expected_status


def test_parse_response_markdown_wrapped() -> None:
    r = Reviewer(".")
    response = '```json\n{"reviews": [{"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "OK"}]}\n```'
    results = r._parse_response(response)
    assert len(results) == 1
    assert results[0]["reviewStatus"] == "consistent"


def test_parse_response_empty() -> None:
    r = Reviewer(".")
    with pytest.raises(ValueError, match="未找到 reviews"):
        r._parse_response('{"reviews": []}')


def test_parse_response_no_json() -> None:
    r = Reviewer(".")
    with pytest.raises(ValueError, match="无法.*解析 JSON"):
        r._parse_response("无法解析的内容")


def test_parse_response_multiple_boxes() -> None:
    r = Reviewer(".")
    response = json.dumps({
        "reviews": [
            {"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "正确"},
            {"box_id": 2, "reviewStatus": "inconsistent", "reviewNotes": "错误"},
        ]
    })
    results = r._parse_response(response)
    assert len(results) == 2
    assert results[0]["box_id"] == 1
    assert results[1]["box_id"] == 2


def test_update_exam_consistent(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    results = [{"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "笔记与原题一致"}]
    r._update_exam(exam, results)
    assert exam.boxes[0].reviewStatus == "consistent"
    assert exam.boxes[0].reviewNotes == "笔记与原题一致"


def test_update_exam_inconsistent(exam_dir_inconsistent: Path) -> None:
    r = Reviewer(exam_dir_inconsistent)
    exam = r._load_exam()
    results = [{"box_id": 1, "reviewStatus": "inconsistent", "reviewNotes": "计算错误：2*5+3=13，但笔记写7"}]
    r._update_exam(exam, results)
    assert exam.boxes[0].reviewStatus == "inconsistent"
    assert "13" in exam.boxes[0].reviewNotes


def test_update_exam_skips_unknown_box(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    results = [{"box_id": 999, "reviewStatus": "consistent", "reviewNotes": "无关"}]
    r._update_exam(exam, results)
    assert exam.boxes[0].reviewStatus == "pending"


def test_update_exam_only_targeted_box(exam_dir_consistent: Path) -> None:
    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    exam.boxes.append(
        QuestionBox(id=2, bbox=BBox(x=0, y=0, w=100, h=100), questionText="Q2", annotations="A2")
    )
    results = [
        {"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "OK"},
        {"box_id": 2, "reviewStatus": "inconsistent", "reviewNotes": "NOT OK"},
    ]
    r._update_exam(exam, results)
    assert exam.boxes[0].reviewStatus == "consistent"
    assert exam.boxes[1].reviewStatus == "inconsistent"


@patch("note_analysis.agent.core.httpx.Client.post")
def test_call_llm(mock_post: MagicMock, exam_dir_consistent: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": (
            '{"reviews": [{"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "\u6b63\u786e"}]}'
        )}],
    }
    mock_post.return_value = mock_response

    r = Reviewer(exam_dir_consistent)
    exam = r._load_exam()
    prompt = r._build_prompt(exam)
    response = r._call_llm(prompt)
    assert "consistent" in response
    assert "reviewStatus" in response


@patch("note_analysis.agent.core.httpx.Client.post")
def test_review_full_flow(mock_post: MagicMock, exam_dir_consistent: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "reviews": [{"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "笔记正确"}]
            }),
        }]
    }
    mock_post.return_value = mock_response

    r = Reviewer(exam_dir_consistent)
    exam = r.review()
    assert exam.boxes[0].reviewStatus == "consistent"
    assert exam.boxes[0].reviewNotes == "笔记正确"


@patch("note_analysis.agent.core.httpx.Client.post")
def test_review_saves_json(mock_post: MagicMock, exam_dir_consistent: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "reviews": [{"box_id": 1, "reviewStatus": "consistent", "reviewNotes": "OK"}]
            }),
        }]
    }
    mock_post.return_value = mock_response

    r = Reviewer(exam_dir_consistent)
    r.review()

    json_files = Serializer.find_exam_files(exam_dir_consistent)
    loaded = Serializer.load(json_files[0])
    assert loaded.boxes[0].reviewStatus == "consistent"


def test_review_no_json(tmp_path: Path) -> None:
    r = Reviewer(tmp_path)
    with pytest.raises(FileNotFoundError):
        r.review()


@pytest.mark.parametrize("status", ["consistent", "inconsistent", "uncertain"])
def test_review_status_round_trip(status: str, exam_dir_consistent: Path) -> None:
    """验证三种 reviewStatus 均可写入 JSON 并正确重新加载"""
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_consistent)[0])
    exam.boxes[0].reviewStatus = status  # type: ignore[arg-type]
    exam.boxes[0].reviewNotes = "测试"
    Serializer.save(exam, exam_dir_consistent)

    loaded = Serializer.load(Serializer.find_exam_files(exam_dir_consistent)[0])
    assert loaded.boxes[0].reviewStatus == status
    assert loaded.boxes[0].reviewNotes == "测试"
