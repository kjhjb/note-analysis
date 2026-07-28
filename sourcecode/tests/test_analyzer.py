from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from note_analysis.analyzer.engine import Analyzer
from note_analysis.models.models import BBox, Exam, QuestionBox
from note_analysis.models.serializer import Serializer

# ── fixtures ──────────────────────────────────────────────

@pytest.fixture
def single_exam_dir(tmp_path: Path) -> Path:
    exam = Exam.create([str(tmp_path / "photo1.jpg")])
    exam.boxes = [
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="已知函数 f(x)=x^2，求 f'(x)",
                     annotations="f'(x)=2x",
                     reviewStatus="consistent", reviewNotes=""),
        QuestionBox(id=2, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="求方程 2x+3=7 的解",
                     annotations="x=2",
                     reviewStatus="inconsistent", reviewNotes="计算有误",
                     isError=True, errorMarks=["cross"]),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


@pytest.fixture
def multi_exam_dir(tmp_path: Path) -> Path:
    exam1 = Exam.create([str(tmp_path / "exam1.jpg")])
    exam1.examId = "20260101_1001"
    exam1.createdAt = "20260101_1001"
    exam1.boxes = [
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="求 sin(π/2) 的值",
                     annotations="=1",
                     reviewStatus="consistent", reviewNotes=""),
        QuestionBox(id=2, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="已知 F=ma，求 a",
                     annotations="a=F/m",
                     reviewStatus="inconsistent", reviewNotes="公式写反",
                     isError=True, errorMarks=["cross"]),
    ]
    Serializer.save(exam1, tmp_path)

    exam2 = Exam.create([str(tmp_path / "exam2.jpg")])
    exam2.examId = "20260102_1002"
    exam2.createdAt = "20260102_1002"
    exam2.boxes = [
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="求函数 y=2x+1 的斜率",
                     annotations="k=2",
                     reviewStatus="inconsistent", reviewNotes="误写为 1/2",
                     isError=True, errorMarks=["cross"]),
    ]
    Serializer.save(exam2, tmp_path)

    return tmp_path


# ── _load_all_exams ───────────────────────────────────────

def test_load_all_exams_single(single_exam_dir: Path) -> None:
    a = Analyzer(single_exam_dir)
    exams = a._load_all_exams()
    assert len(exams) == 1
    assert len(exams[0].boxes) == 2


def test_load_all_exams_multi(multi_exam_dir: Path) -> None:
    a = Analyzer(multi_exam_dir)
    exams = a._load_all_exams()
    assert len(exams) == 2


def test_load_all_exams_empty(tmp_path: Path) -> None:
    a = Analyzer(tmp_path)
    exams = a._load_all_exams()
    assert exams == []


# ── _build_summary ────────────────────────────────────────

def test_build_summary_contains_exam_count(single_exam_dir: Path) -> None:
    a = Analyzer(single_exam_dir)
    exams = a._load_all_exams()
    summary = a._build_summary(exams)
    assert "1 份试卷" in summary


def test_build_summary_contains_question_text(single_exam_dir: Path) -> None:
    a = Analyzer(single_exam_dir)
    exams = a._load_all_exams()
    summary = a._build_summary(exams)
    assert "f(x)=x^2" in summary
    assert "f'(x)=2x" in summary


def test_build_summary_contains_review_status(single_exam_dir: Path) -> None:
    a = Analyzer(single_exam_dir)
    exams = a._load_all_exams()
    summary = a._build_summary(exams)
    assert "consistent" in summary
    assert "inconsistent" in summary
    assert "isError" in summary
    assert "cross" in summary


def test_build_summary_contains_isError_info(single_exam_dir: Path) -> None:
    a = Analyzer(single_exam_dir)
    exams = a._load_all_exams()
    summary = a._build_summary(exams)
    assert "isError: True" in summary
    assert "isError: False" in summary
    assert "应计入易错点统计" in summary


def test_build_summary_multi_exams(multi_exam_dir: Path) -> None:
    a = Analyzer(multi_exam_dir)
    exams = a._load_all_exams()
    summary = a._build_summary(exams)
    assert "2 份试卷" in summary
    assert "sin(π/2)" in summary
    assert "F=ma" in summary
    assert "y=2x+1" in summary


# ── _parse_response ───────────────────────────────────────

def test_parse_response_valid() -> None:
    response = json.dumps({
        "weakPoints": [
            {"knowledgePoint": "导数", "errorCount": 2, "llmAdvice": "多练习求导"},
            {"knowledgePoint": "三角函数", "errorCount": 1, "llmAdvice": "熟记特殊角"},
        ]
    })
    results = Analyzer._parse_response(response)
    assert len(results) == 2
    assert results[0]["knowledgePoint"] == "导数"
    assert results[0]["errorCount"] == 2


def test_parse_response_markdown_wrapped() -> None:
    inner = '{"weakPoints": [{"knowledgePoint": "牛顿定律", "errorCount": 3, "llmAdvice": "复习"}]}'
    response = f"```json\n{inner}\n```"
    results = Analyzer._parse_response(response)
    assert len(results) == 1
    assert results[0]["knowledgePoint"] == "牛顿定律"


def test_parse_response_single() -> None:
    response = '{"weakPoints": [{"knowledgePoint": "三角函数", "errorCount": 1, "llmAdvice": "记忆公式"}]}'
    results = Analyzer._parse_response(response)
    assert len(results) == 1


def test_parse_response_empty() -> None:
    with pytest.raises(ValueError, match="未找到 weakPoints"):
        Analyzer._parse_response('{"weakPoints": []}')


def test_parse_response_no_json() -> None:
    with pytest.raises(ValueError, match="无法.*解析 JSON"):
        Analyzer._parse_response("无法解析的内容")


def test_parse_response_no_weakpoints_key() -> None:
    with pytest.raises(ValueError, match="未找到 weakPoints"):
        Analyzer._parse_response('{"other": []}')


# ── _update_exams ─────────────────────────────────────────

def test_update_exams_sets_weak_points(single_exam_dir: Path) -> None:
    a = Analyzer(single_exam_dir)
    exams = a._load_all_exams()
    results = [
        {"knowledgePoint": "导数", "errorCount": 1, "llmAdvice": "练习求导"},
        {"knowledgePoint": "方程求解", "errorCount": 1, "llmAdvice": "检查计算"},
    ]
    Analyzer._update_exams(exams, results)
    assert len(exams[0].weakPoints) == 2
    assert exams[0].weakPoints[0].knowledgePoint == "导数"
    assert exams[0].weakPoints[1].errorCount == 1


def test_update_exams_same_data_all_exams(multi_exam_dir: Path) -> None:
    a = Analyzer(multi_exam_dir)
    exams = a._load_all_exams()
    results = [
        {"knowledgePoint": "牛顿定律", "errorCount": 2, "llmAdvice": "复习"},
    ]
    Analyzer._update_exams(exams, results)
    for exam in exams:
        assert len(exam.weakPoints) == 1
        assert exam.weakPoints[0].knowledgePoint == "牛顿定律"


def test_update_exams_empty_results(multi_exam_dir: Path) -> None:
    a = Analyzer(multi_exam_dir)
    exams = a._load_all_exams()
    Analyzer._update_exams(exams, [])
    for exam in exams:
        assert exam.weakPoints == []


def test_update_exams_round_trip(multi_exam_dir: Path) -> None:
    a = Analyzer(multi_exam_dir)
    exams = a._load_all_exams()
    results = [
        {"knowledgePoint": "三角函数", "errorCount": 3, "llmAdvice": "多做题"},
    ]
    a._update_exams(exams, results)
    a._save_exams(exams)

    # reload and verify
    reloaded = a._load_all_exams()
    for exam in reloaded:
        assert len(exam.weakPoints) == 1
        assert exam.weakPoints[0].knowledgePoint == "三角函数"
        assert exam.weakPoints[0].errorCount == 3


# ── analyze (end-to-end, mocked LLM) ──────────────────────

@patch("note_analysis.agent.core.httpx.Client.post")
def test_analyze_full_flow(mock_post: MagicMock, single_exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "weakPoints": [
                {"knowledgePoint": "导数", "errorCount": 1, "llmAdvice": "练习求导"},
                {"knowledgePoint": "方程求解", "errorCount": 1, "llmAdvice": "检查计算步骤"},
            ]
        })}]
    }
    mock_post.return_value = mock_response

    a = Analyzer(single_exam_dir)
    exams = a.analyze()
    assert len(exams) == 1
    assert len(exams[0].weakPoints) == 2
    assert exams[0].weakPoints[0].knowledgePoint == "导数"


@patch("note_analysis.agent.core.httpx.Client.post")
def test_analyze_multi_exams(mock_post: MagicMock, multi_exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "weakPoints": [
                {"knowledgePoint": "三角函数", "errorCount": 2, "llmAdvice": "记忆公式"},
                {"knowledgePoint": "牛顿定律", "errorCount": 1, "llmAdvice": "受力分析"},
            ]
        })}]
    }
    mock_post.return_value = mock_response

    a = Analyzer(multi_exam_dir)
    exams = a.analyze()
    assert len(exams) == 2
    for exam in exams:
        assert len(exam.weakPoints) == 2


@patch("note_analysis.agent.core.httpx.Client.post")
def test_analyze_saves_json(mock_post: MagicMock, single_exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "weakPoints": [{"knowledgePoint": "导数", "errorCount": 1, "llmAdvice": "练习"}]
        })}]
    }
    mock_post.return_value = mock_response

    a = Analyzer(single_exam_dir)
    a.analyze()

    json_files = Serializer.find_exam_files(single_exam_dir)
    loaded = Serializer.load(json_files[0])
    assert len(loaded.weakPoints) == 1
    assert loaded.weakPoints[0].knowledgePoint == "导数"


def test_analyze_no_json(tmp_path: Path) -> None:
    a = Analyzer(tmp_path)
    exams = a.analyze()
    assert exams == []


@patch("note_analysis.agent.core.httpx.Client.post")
def test_analyze_preserves_existing_boxes(mock_post: MagicMock, single_exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "weakPoints": [{"knowledgePoint": "导数", "errorCount": 1, "llmAdvice": "练习"}]
        })}]
    }
    mock_post.return_value = mock_response

    a = Analyzer(single_exam_dir)
    exams = a.analyze()
    assert len(exams[0].boxes) == 2
    assert exams[0].boxes[0].questionText == "已知函数 f(x)=x^2，求 f'(x)"


@patch("note_analysis.agent.core.httpx.Client.post")
def test_analyze_empty_llm_response(mock_post: MagicMock, single_exam_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "{}"}]
    }
    mock_post.return_value = mock_response

    a = Analyzer(single_exam_dir)
    with pytest.raises(ValueError, match="未找到 weakPoints"):
        a.analyze()
