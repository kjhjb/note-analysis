import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from note_analysis.models.exam import BBox, UncertainRegion, QuestionBox, Exam, WeakPoint


class TestBBox:
    def test_construct_with_float_coords(self):
        b = BBox(x=10.5, y=20.3, w=100.0, h=200.7)
        assert b.x == 10.5
        assert b.y == 20.3
        assert b.w == 100.0
        assert b.h == 200.7

    def test_construct_with_int_coords(self):
        b = BBox(x=10, y=20, w=100, h=200)
        assert b.x == 10.0
        assert b.y == 20.0
        assert b.w == 100.0
        assert b.h == 200.0

    def test_negative_dimensions_raises(self):
        with pytest.raises(ValidationError):
            BBox(x=0, y=0, w=-100, h=200)

    def test_serialize_to_dict(self):
        b = BBox(x=10.5, y=20.3, w=100.0, h=200.7)
        d = b.model_dump()
        assert d == {"x": 10.5, "y": 20.3, "w": 100.0, "h": 200.7}


class TestUncertainRegion:
    def test_construct_minimal(self):
        u = UncertainRegion(bbox=BBox(x=0, y=0, w=50, h=50), llmGuess="maybe 42", llmConfidence=0.65)
        assert u.llmGuess == "maybe 42"
        assert u.llmConfidence == 0.65
        assert u.userConfirmed is None

    def test_construct_with_user_confirmed(self):
        u = UncertainRegion(
            bbox=BBox(x=0, y=0, w=50, h=50),
            llmGuess="maybe 42",
            llmConfidence=0.65,
            userConfirmed="42",
        )
        assert u.userConfirmed == "42"

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            UncertainRegion(bbox=BBox(x=0, y=0, w=50, h=50), llmGuess="x", llmConfidence=1.5)


class TestQuestionBox:
    def test_construct_minimal(self):
        q = QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=200))
        assert q.id == 1
        assert q.questionText == ""
        assert q.annotations == ""
        assert q.images == []
        assert q.uncertainRegions == []
        assert q.reviewStatus == "pending"
        assert q.reviewNotes == ""

    def test_with_full_data(self):
        u = UncertainRegion(bbox=BBox(x=10, y=10, w=20, h=20), llmGuess="?", llmConfidence=0.5)
        q = QuestionBox(
            id=2,
            bbox=BBox(x=0, y=0, w=100, h=200),
            questionText="Solve $x^2$",
            annotations="answer is 4",
            images=["img1.png"],
            uncertainRegions=[u],
            reviewStatus="consistent",
            reviewNotes="looks good",
        )
        assert q.questionText == "Solve $x^2$"
        assert len(q.uncertainRegions) == 1
        assert q.reviewStatus == "consistent"

    def test_invalid_review_status_raises(self):
        with pytest.raises(ValidationError):
            QuestionBox(
                id=3,
                bbox=BBox(x=0, y=0, w=100, h=200),
                reviewStatus="invalid_status",
            )


class TestWeakPoint:
    def test_construct(self):
        w = WeakPoint(knowledgePoint="二次函数", errorCount=3, llmAdvice="多练习求根公式")
        assert w.knowledgePoint == "二次函数"
        assert w.errorCount == 3
        assert w.llmAdvice == "多练习求根公式"

    def test_negative_error_count_raises(self):
        with pytest.raises(ValidationError):
            WeakPoint(knowledgePoint="x", errorCount=-1, llmAdvice="none")


class TestExam:
    def test_construct_minimal(self):
        exam = Exam(examId="test-001", photos=["photo1.jpg"], createdAt="20260727_1614")
        assert exam.examId == "test-001"
        assert exam.photos == ["photo1.jpg"]
        assert exam.boxes == []
        assert exam.weakPoints == []

    def test_with_boxes(self):
        q = QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=200))
        exam = Exam(
            examId="test-002",
            photos=["p1.jpg", "p2.jpg"],
            boxes=[q],
            createdAt="20260727_1614",
        )
        assert len(exam.boxes) == 1

    def test_serialize_deserialize_roundtrip(self):
        q = QuestionBox(id=1, bbox=BBox(x=10, y=20, w=300, h=400))
        exam = Exam(
            examId="roundtrip-test",
            photos=["photo.jpg"],
            boxes=[q],
            createdAt="20260727_1614",
        )
        data = exam.model_dump(mode="json")
        restored = Exam.model_validate(data)
        assert restored.examId == exam.examId
        assert restored.boxes[0].bbox.x == 10.0

    def test_json_file_name_format(self, tmp_path):
        """JSON 文件按 笔记_YYYYMMDD_HHmm.json 格式命名"""
        exam = Exam(
            examId="test",
            photos=[],
            createdAt="20260727_1614",
        )
        fpath = tmp_path / f"笔记_{exam.createdAt}.json"
        fpath.write_text(exam.model_dump_json(indent=2, ensure_ascii=False))
        assert fpath.exists()
        assert fpath.name == "笔记_20260727_1614.json"
        loaded = Exam.model_validate_json(fpath.read_text(encoding="utf-8"))
        assert loaded.examId == "test"
