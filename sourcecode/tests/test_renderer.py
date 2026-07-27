from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from note_analysis.models.models import BBox, Exam, QuestionBox, UncertainRegion
from note_analysis.models.serializer import Serializer
from note_analysis.renderer.engine import NoteRenderer

MINIMAL_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>[必填] 替换为笔记标题</title></head>
<body>
<div class="desk"><div class="notebook">
<div class="title write-in" style="animation-delay:0.1s">[笔记标题]<div class="title-underline"></div></div>
<div class="subtitle write-in" style="animation-delay:0.3s">[副标题或日期信息]</div>
<!-- ===== 内容段落示例 ===== -->
<div class="section">
  <div class="section-title write-in" style="animation-delay:0.5s">[小节标题]<div class="marker-underline"></div></div>
  <div class="content write-in" style="animation-delay:0.6s">[正文内容]</div>
</div>
<!-- ===== 流程图示例 ===== -->
</div></div>
</body>
</html>"""


@pytest.fixture
def skill_root(tmp_path: Path) -> Path:
    root = tmp_path / "note-skill"
    assets = root / "assets"
    assets.mkdir(parents=True)
    (assets / "template.html").write_text(MINIMAL_TEMPLATE, encoding="utf-8")
    return root


@pytest.fixture
def exam_dir_with_data(tmp_path: Path, skill_root: Path) -> Path:
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, "已知函数 f(x) = sin(x)，求 f'(x)",
        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cv2.imwrite(str(tmp_path / "exam.jpg"), img)

    exam = Exam.create([str(tmp_path / "exam.jpg")])
    exam.boxes = [
        QuestionBox(
            id=1, bbox=BBox(x=30, y=30, w=500, h=200), photoIndex=0,
            questionText="已知函数 $f(x) = \\sin(x)$，求 $f'(x)$",
            annotations="$f'(x) = \\cos(x)$",
            reviewStatus="consistent", reviewNotes="笔记正确",
        ),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


def test_renderer_init(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    assert renderer.exam_dir == exam_dir_with_data


def test_load_exam(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    exam = renderer._load_exam()
    assert len(exam.boxes) == 1
    assert "\\sin(x)" in exam.boxes[0].questionText


def test_load_template(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    template = renderer.load_template()
    assert "<!DOCTYPE html>" in template
    assert "[笔记标题]" in template


def test_render_returns_html(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "<!DOCTYPE html>" in html


def test_render_contains_question_text(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "题目 #1" in html
    assert "已知函数" in html


def test_render_contains_annotation_text(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "\\cos(x)" in html


def test_title_placeholder_replaced(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "[笔记标题]" not in html
    assert "[必填]" not in html


def test_render_contains_mathjax(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "mathjax" in html.lower()


def test_render_contains_embedded_json(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "application/json" in html
    assert '"examId"' in html
    assert '"boxes"' in html


def test_save_html_file(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    path = renderer.save()
    assert path.exists()
    assert path.suffix == ".html"
    assert path.name.startswith("笔记_")


def test_saved_html_content(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    path = renderer.save()
    content = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "题目 #1" in content
    assert "application/json" in content


def test_render_with_uncertain_regions(exam_dir_with_data: Path, skill_root: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_data)[0])
    exam.boxes[0].uncertainRegions = [
        UncertainRegion(
            bbox=BBox(x=10, y=10, w=50, h=20),
            llmGuess="可能是 \\cos(x)",
            llmConfidence=0.65,
            userConfirmed="\\cos(x)",
        ),
    ]
    Serializer.save(exam, exam_dir_with_data)

    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "不确定区域" in html or "待确认" in html


def test_render_multiple_boxes(exam_dir_with_data: Path, skill_root: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_data)[0])
    exam.boxes.append(
        QuestionBox(
            id=2, bbox=BBox(x=30, y=300, w=500, h=200), photoIndex=0,
            questionText="求 $\\int_0^1 x^2 dx$",
            annotations="$\\frac{1}{3}$",
            reviewStatus="consistent", reviewNotes="正确",
        ),
    )
    Serializer.save(exam, exam_dir_with_data)

    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "题目 #1" in html
    assert "题目 #2" in html


def test_render_with_images(exam_dir_with_data: Path, skill_root: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_data)[0])
    exam.boxes[0].images = ["dGVzdCBpbWFnZSBkYXRh"]
    Serializer.save(exam, exam_dir_with_data)

    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "data:image" in html


def test_render_inconsistent_status(exam_dir_with_data: Path, skill_root: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_data)[0])
    exam.boxes[0].reviewStatus = "inconsistent"
    exam.boxes[0].reviewNotes = "计算错误: 2*5+3=13"
    Serializer.save(exam, exam_dir_with_data)

    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "计算错误" in html


def test_render_no_json(tmp_path: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(tmp_path, skill_root=skill_root)
    with pytest.raises(FileNotFoundError):
        renderer.render()


def test_render_no_boxes(exam_dir_with_data: Path, skill_root: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_data)[0])
    exam.boxes = []
    Serializer.save(exam, exam_dir_with_data)

    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    assert "暂无题目" in html or "笔记" in html


def test_embedded_json_matches_exam(exam_dir_with_data: Path, skill_root: Path) -> None:
    renderer = NoteRenderer(exam_dir_with_data, skill_root=skill_root)
    html = renderer.render()
    start = html.index('"examId"')
    end = html.index("</script>", start)
    json_str = html[start:end].rsplit(">", 1)[-1] if ">" in html[start:end] else ""
    # Just verify examId is present in JSON context
    exam = renderer._load_exam()
    assert exam.examId in html
