import json
from pathlib import Path

from note_analysis.models.models import BBox, Exam, QuestionBox, UncertainRegion, WeakPoint
from note_analysis.models.serializer import Serializer


def test_bbox_creation():
    bbox = BBox(x=10.0, y=20.0, w=100.0, h=200.0)
    assert bbox.x == 10.0
    assert bbox.y == 20.0
    assert bbox.w == 100.0
    assert bbox.h == 200.0


def test_uncertain_region_creation():
    bbox = BBox(x=0, y=0, w=50, h=30)
    region = UncertainRegion(bbox=bbox, llmGuess="可能是sin(x)", llmConfidence=0.65)
    assert region.llmGuess == "可能是sin(x)"
    assert region.llmConfidence == 0.65
    assert region.userConfirmed is None


def test_uncertain_region_with_confirmation():
    bbox = BBox(x=0, y=0, w=50, h=30)
    region = UncertainRegion(
        bbox=bbox, llmGuess="sin(x)", llmConfidence=0.65, userConfirmed="cos(x)"
    )
    assert region.userConfirmed == "cos(x)"


def test_question_box_creation():
    bbox = BBox(x=0, y=0, w=400, h=300)
    qb = QuestionBox(id=1, bbox=bbox)
    assert qb.id == 1
    assert qb.questionText == ""
    assert qb.annotations == ""
    assert qb.images == []
    assert qb.uncertainRegions == []
    assert qb.reviewStatus == "pending"


def test_question_box_with_content():
    bbox = BBox(x=0, y=0, w=400, h=300)
    region = UncertainRegion(bbox=BBox(x=10, y=10, w=20, h=20), llmGuess="?", llmConfidence=0.5)
    qb = QuestionBox(
        id=2,
        bbox=bbox,
        questionText="求 $f(x)$ 的导数",
        annotations="注意链式法则",
        images=["data:image/png;base64,abc"],
        uncertainRegions=[region],
    )
    assert qb.questionText == "求 $f(x)$ 的导数"
    assert len(qb.images) == 1
    assert len(qb.uncertainRegions) == 1


def test_exam_create():
    photos = ["photo1.jpg", "photo2.png"]
    exam = Exam.create(photos)
    assert exam.photos == photos
    assert len(exam.examId) == 13
    assert len(exam.createdAt) == 13
    assert exam.boxes == []
    assert exam.weakPoints == []


def test_exam_filenames():
    exam = Exam.create(["test.jpg"])
    assert exam.json_filename.startswith("笔记_")
    assert exam.json_filename.endswith(".json")
    assert exam.html_filename.startswith("笔记_")
    assert exam.html_filename.endswith(".html")


def test_weak_point_creation():
    wp = WeakPoint(knowledgePoint="三角函数", errorCount=5, llmAdvice="多练习诱导公式")
    assert wp.knowledgePoint == "三角函数"
    assert wp.errorCount == 5
    assert wp.llmAdvice == "多练习诱导公式"


def test_serializer_save_and_load(tmp_path: Path) -> None:
    photos = [str(tmp_path / "test.jpg")]
    exam = Exam.create(photos)
    exam.boxes.append(
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100), questionText="1+1=?")
    )
    saved_path = Serializer.save(exam, tmp_path)
    assert saved_path.exists()
    assert saved_path.name.startswith("笔记_")

    loaded = Serializer.load(saved_path)
    assert loaded.examId == exam.examId
    assert len(loaded.boxes) == 1
    assert loaded.boxes[0].questionText == "1+1=?"


def test_serializer_json_content(tmp_path: Path) -> None:
    exam = Exam.create(["pic.jpg"])
    exam.boxes.append(
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100), questionText="测试题")
    )
    saved_path = Serializer.save(exam, tmp_path)
    raw = json.loads(saved_path.read_text(encoding="utf-8"))
    assert raw["examId"] == exam.examId
    assert raw["boxes"][0]["questionText"] == "测试题"


def test_serializer_find_exam_files(tmp_path: Path) -> None:
    files = Serializer.find_exam_files(tmp_path)
    assert files == []

    exam = Exam.create(["pic.jpg"])
    Serializer.save(exam, tmp_path)
    files = Serializer.find_exam_files(tmp_path)
    assert len(files) == 1
    assert files[0].suffix == ".json"
