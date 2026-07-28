from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from note_analysis.agent.correction import Corrector
from note_analysis.models.models import BBox, Exam, QuestionBox
from note_analysis.models.serializer import Serializer


@pytest.fixture
def exam_with_errors(tmp_path: Path) -> Path:
    exam = Exam.create([str(tmp_path / "photo.jpg")])
    exam.boxes = [
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="已知函数 f(x)=x^2，求 f'(x)",
                     annotations="f'(x)=x", isError=True, errorMarks=["cross"]),
        QuestionBox(id=2, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="求 2+3 的值",
                     annotations="=6", isError=True, errorMarks=["cross"]),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


@pytest.fixture
def exam_no_errors(tmp_path: Path) -> Path:
    exam = Exam.create([str(tmp_path / "photo.jpg")])
    exam.boxes = [
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="已知函数 f(x)=x^2，求 f'(x)",
                     annotations="f'(x)=2x", isError=False, errorMarks=[]),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


def test_corrector_init(exam_with_errors: Path) -> None:
    c = Corrector(exam_with_errors)
    assert c.exam_dir == exam_with_errors


def test_corrector_load_exam(exam_with_errors: Path) -> None:
    c = Corrector(exam_with_errors)
    exam = c._load_exam()
    assert len(exam.boxes) == 2
    assert exam.boxes[0].isError is True


def test_corrector_load_exam_not_found(tmp_path: Path) -> None:
    c = Corrector(tmp_path)
    with pytest.raises(FileNotFoundError):
        c._load_exam()


def test_corrector_build_prompt(exam_with_errors: Path) -> None:
    c = Corrector(exam_with_errors)
    exam = c._load_exam()
    prompt = c._build_prompt(exam)
    assert "题目 1" in prompt
    assert "题目 2" in prompt
    assert "f(x)=x^2" in prompt
    assert "cross" in prompt


def test_corrector_build_prompt_skips_non_error(exam_no_errors: Path) -> None:
    c = Corrector(exam_no_errors)
    exam = c._load_exam()
    prompt = c._build_prompt(exam)
    assert "题目 1" not in prompt


def test_corrector_parse_response_valid() -> None:
    response = json.dumps({
        "corrections": [
            {"box_id": 1, "correctAnswer": "$f'(x)=2x$", "errorAnalysis": "幂函数求导公式记错"},
            {"box_id": 2, "correctAnswer": "$5$", "errorAnalysis": "加法计算错误"},
        ]
    })
    results = Corrector._parse_response(response)
    assert len(results) == 2
    assert results[0]["box_id"] == 1
    assert "2x" in results[0]["correctAnswer"]


def test_corrector_parse_response_markdown_wrapped() -> None:
    inner = '{"corrections": [{"box_id": 1, "correctAnswer": "$x=2$", "errorAnalysis": "移项错误"}]}'
    response = f"```json\n{inner}\n```"
    results = Corrector._parse_response(response)
    assert len(results) == 1
    assert results[0]["box_id"] == 1


def test_corrector_parse_response_empty() -> None:
    with pytest.raises(ValueError, match="未找到 corrections"):
        Corrector._parse_response('{"corrections": []}')


def test_corrector_parse_response_no_json() -> None:
    with pytest.raises(ValueError, match="无法.*解析 JSON"):
        Corrector._parse_response("无法解析的内容")


def test_corrector_update_exam(exam_with_errors: Path) -> None:
    c = Corrector(exam_with_errors)
    exam = c._load_exam()
    results = [
        {"box_id": 1, "correctAnswer": "$f'(x)=2x$", "errorAnalysis": "求导公式记错"},
    ]
    Corrector._update_exam(exam, results)
    assert "2x" in exam.boxes[0].correction
    assert "求导公式记错" in exam.boxes[0].correction


def test_corrector_update_exam_skips_unknown_boxes(exam_with_errors: Path) -> None:
    c = Corrector(exam_with_errors)
    exam = c._load_exam()
    results = [{"box_id": 999, "correctAnswer": "x=5", "errorAnalysis": "计算错误"}]
    Corrector._update_exam(exam, results)
    assert exam.boxes[0].correction == ""


def test_corrector_correct_no_errors(exam_no_errors: Path) -> None:
    c = Corrector(exam_no_errors)
    exam = c.correct()
    assert exam.boxes[0].correction == ""


@patch("note_analysis.agent.core.httpx.Client.post")
def test_corrector_correct_full_flow(mock_post: MagicMock, exam_with_errors: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "corrections": [
                {"box_id": 1, "correctAnswer": "$f'(x)=2x$", "errorAnalysis": "幂函数求导记错"},
                {"box_id": 2, "correctAnswer": "$5$", "errorAnalysis": "加法计算错误"},
            ]
        })}]
    }
    mock_post.return_value = mock_response

    c = Corrector(exam_with_errors)
    exam = c.correct()
    assert "2x" in exam.boxes[0].correction
    assert "5" in exam.boxes[1].correction
    assert "幂函数" in exam.boxes[0].correction


@patch("note_analysis.agent.core.httpx.Client.post")
def test_corrector_correct_saves_json(mock_post: MagicMock, exam_with_errors: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "corrections": [
                {"box_id": 1, "correctAnswer": "$f'(x)=2x$", "errorAnalysis": "求导错误"},
            ]
        })}]
    }
    mock_post.return_value = mock_response

    c = Corrector(exam_with_errors)
    c.correct()

    json_files = Serializer.find_exam_files(exam_with_errors)
    loaded = Serializer.load(json_files[0])
    assert "2x" in loaded.boxes[0].correction
