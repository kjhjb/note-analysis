from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from note_analysis.agent.uncertainty import UncertaintyResolver
from note_analysis.models.models import BBox, Exam, QuestionBox, UncertainRegion
from note_analysis.models.serializer import Serializer


@pytest.fixture
def exam_dir_with_ur(tmp_path: Path) -> Path:
    """创建包含不确定区域的 JSON 和图片"""
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, "已知函数 f(x) = sin(x)",
        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cv2.putText(
        img, "则 f'(x) = ?",
        (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    cv2.circle(img, (300, 120), 15, (0, 0, 255), 2)
    cv2.putText(
        img, "cos(x)",
        (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1,
    )
    photo_path = tmp_path / "exam.jpg"
    cv2.imwrite(str(photo_path), img)

    exam = Exam.create([str(photo_path)])
    exam.boxes = [
        QuestionBox(
            id=1,
            bbox=BBox(x=30, y=80, w=540, h=150),
            photoIndex=0,
            questionText="已知函数 f(x) = sin(x)，则 f'(x) = ?",
            annotations="cos(x)",
            images=[""],
            uncertainRegions=[
                UncertainRegion(
                    bbox=BBox(x=170, y=90, w=60, h=25),
                    llmGuess="可能是 cos(x)",
                    llmConfidence=0.65,
                ),
                UncertainRegion(
                    bbox=BBox(x=260, y=95, w=30, h=20),
                    llmGuess="可能是 f'(x)",
                    llmConfidence=0.7,
                ),
            ],
        ),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


@pytest.fixture
def exam_dir_no_ur(tmp_path: Path) -> Path:
    """创建没有不确定区域的 JSON"""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, "1 + 1 = 2",
        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2,
    )
    photo_path = tmp_path / "simple.jpg"
    cv2.imwrite(str(photo_path), img)

    exam = Exam.create([str(photo_path)])
    exam.boxes = [
        QuestionBox(id=1, bbox=BBox(x=30, y=80, w=540, h=50), photoIndex=0),
    ]
    Serializer.save(exam, tmp_path)
    return tmp_path


def test_uncertainty_resolver_init(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    assert r.exam_dir == exam_dir_with_ur


def test_load_exam_with_uncertain_regions(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    assert len(exam.boxes) == 1
    assert len(exam.boxes[0].uncertainRegions) == 2
    assert exam.boxes[0].uncertainRegions[0].llmGuess == "可能是 cos(x)"
    assert exam.boxes[0].uncertainRegions[0].llmConfidence == 0.65


def test_load_exam_no_uncertain_regions(exam_dir_no_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_no_ur)
    exam = r._load_exam()
    assert len(exam.boxes) == 1
    assert len(exam.boxes[0].uncertainRegions) == 0


def test_extract_uncertain_data(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)

    assert len(data) == 2
    assert data[0]["box_id"] == 1
    assert data[0]["ur_index"] == 0
    assert data[0]["llmGuess"] == "可能是 cos(x)"
    assert data[0]["llmConfidence"] == 0.65

    assert data[1]["box_id"] == 1
    assert data[1]["ur_index"] == 1
    assert data[1]["llmGuess"] == "可能是 f'(x)"


def test_extract_uncertain_data_computes_correct_orig_bbox(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)

    box = exam.boxes[0]
    ur = box.uncertainRegions[0]
    expected_x = box.bbox.x + ur.bbox.x
    expected_y = box.bbox.y + ur.bbox.y
    assert data[0]["orig_bbox"]["x"] == expected_x
    assert data[0]["orig_bbox"]["y"] == expected_y
    assert data[0]["orig_bbox"]["w"] == ur.bbox.w
    assert data[0]["orig_bbox"]["h"] == ur.bbox.h


@patch("note_analysis.agent.uncertainty.crop_bbox_from_image")
@patch("note_analysis.agent.uncertainty.image_to_base64")
def test_crop_uncertain_regions(
    mock_img_b64: MagicMock,
    mock_crop: MagicMock,
    exam_dir_with_ur: Path,
) -> None:
    mock_crop.return_value = np.ones((25, 60, 3), dtype=np.uint8) * 200
    mock_img_b64.return_value = "crop_b64_data"

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)
    r._crop_uncertain_regions(data, exam)

    assert len(data) == 2
    assert data[0]["image_base64"] == "crop_b64_data"
    assert data[1]["image_base64"] == "crop_b64_data"

    assert mock_crop.call_count == 2
    call_arg = mock_crop.call_args_list[0]
    assert call_arg[0][1].x == pytest.approx(200.0)
    assert call_arg[0][1].y == pytest.approx(170.0)


@patch("note_analysis.agent.uncertainty.crop_bbox_from_image")
@patch("note_analysis.agent.uncertainty.image_to_base64")
def test_build_multimodal_content(
    mock_img_b64: MagicMock,
    mock_crop: MagicMock,
    exam_dir_with_ur: Path,
) -> None:
    mock_crop.return_value = np.ones((25, 60, 3), dtype=np.uint8) * 200
    mock_img_b64.return_value = "crop_b64_data"

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)
    r._crop_uncertain_regions(data, exam)

    content = r._build_multimodal_content(data)
    assert len(content) >= 3

    text_blocks = [c for c in content if c["type"] == "text"]
    image_blocks = [c for c in content if c["type"] == "image"]
    assert len(text_blocks) >= 1
    assert len(image_blocks) == 2

    all_text = " ".join(c["text"] for c in text_blocks)
    assert "不确定" in all_text
    assert "cos(x)" in all_text
    assert "f'(x)" in all_text
    assert "box_id" in all_text
    assert "ur_index" in all_text


@patch("note_analysis.agent.uncertainty.crop_bbox_from_image")
@patch("note_analysis.agent.uncertainty.image_to_base64")
def test_build_multimodal_content_includes_images(
    mock_img_b64: MagicMock,
    mock_crop: MagicMock,
    exam_dir_with_ur: Path,
) -> None:
    mock_crop.return_value = np.ones((25, 60, 3), dtype=np.uint8) * 200
    mock_img_b64.return_value = "mock_b64"

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)
    r._crop_uncertain_regions(data, exam)
    content = r._build_multimodal_content(data)

    image_blocks = [c for c in content if c["type"] == "image"]
    for ib in image_blocks:
        assert ib["source"]["data"] == "mock_b64"


@pytest.mark.parametrize("response,expected_count", [
    (
        '{"regions": ['
        '{"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.92}'
        "]}",
        1,
    ),
    (
        '{"regions": ['
        '{"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.92},'
        '{"box_id": 1, "ur_index": 1, "refined_guess": "f(x)", "confidence": 0.88}'
        "]}",
        2,
    ),
])
def test_parse_response_valid(response: str, expected_count: int) -> None:
    r = UncertaintyResolver(".")
    results = r._parse_response(response)
    assert len(results) == expected_count
    assert results[0]["box_id"] == 1
    assert results[0]["ur_index"] == 0


def test_parse_response_markdown_wrapped() -> None:
    r = UncertaintyResolver(".")
    response = '```json\n{"regions": [{"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.9}]}\n```'
    results = r._parse_response(response)
    assert len(results) == 1


def test_parse_response_empty() -> None:
    r = UncertaintyResolver(".")
    with pytest.raises(ValueError, match="未找到 regions"):
        r._parse_response('{"regions": []}')


def test_parse_response_no_json() -> None:
    r = UncertaintyResolver(".")
    with pytest.raises(ValueError, match="无法.*解析 JSON"):
        r._parse_response("无法解析的内容")


def test_update_exam_with_refined_guesses(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()

    results = [
        {"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.92},
        {"box_id": 1, "ur_index": 1, "refined_guess": "f'(x)", "confidence": 0.88},
    ]
    r._update_exam(exam, results)

    assert exam.boxes[0].uncertainRegions[0].llmGuess == "cos(x)"
    assert exam.boxes[0].uncertainRegions[0].llmConfidence == 0.92
    assert exam.boxes[0].uncertainRegions[1].llmGuess == "f'(x)"
    assert exam.boxes[0].uncertainRegions[1].llmConfidence == 0.88


def test_update_exam_skips_unknown_region(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    original_guess = exam.boxes[0].uncertainRegions[0].llmGuess

    results = [{"box_id": 999, "ur_index": 0, "refined_guess": "???", "confidence": 0.5}]
    r._update_exam(exam, results)
    assert exam.boxes[0].uncertainRegions[0].llmGuess == original_guess


def test_update_exam_preserves_user_confirmed(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    exam.boxes[0].uncertainRegions[0].userConfirmed = "cos(x)"

    results = [
        {"box_id": 1, "ur_index": 0, "refined_guess": "sin(x)", "confidence": 0.9},
        {"box_id": 1, "ur_index": 1, "refined_guess": "f'(x)", "confidence": 0.88},
    ]
    r._update_exam(exam, results)

    assert exam.boxes[0].uncertainRegions[0].userConfirmed == "cos(x)"
    assert exam.boxes[0].uncertainRegions[0].llmGuess == "sin(x)"
    assert exam.boxes[0].uncertainRegions[1].userConfirmed is None


@patch("note_analysis.agent.core.httpx.Client.post")
def test_call_llm(mock_post: MagicMock, exam_dir_with_ur: Path) -> None:
    mock_response = MagicMock()
    llm_response = json.dumps({
        "regions": [
            {"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.95},
        ]
    })
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": llm_response}],
    }
    mock_post.return_value = mock_response

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)
    content = r._build_multimodal_content(data)
    response = r._call_llm(content)

    assert "cos(x)" in response
    assert "95" in response or "0.95" in response


@patch("note_analysis.agent.uncertainty.UncertaintyResolver._call_llm")
def test_resolve_full_flow(mock_call_llm: MagicMock, exam_dir_with_ur: Path) -> None:
    mock_call_llm.return_value = json.dumps({
        "regions": [
            {"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.95},
            {"box_id": 1, "ur_index": 1, "refined_guess": "f'(x)", "confidence": 0.90},
        ]
    })

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r.resolve()

    assert exam.boxes[0].uncertainRegions[0].llmGuess == "cos(x)"
    assert exam.boxes[0].uncertainRegions[0].llmConfidence == 0.95
    assert exam.boxes[0].uncertainRegions[1].llmGuess == "f'(x)"


@patch("note_analysis.agent.uncertainty.UncertaintyResolver._call_llm")
def test_resolve_saves_json(mock_call_llm: MagicMock, exam_dir_with_ur: Path) -> None:
    mock_call_llm.return_value = json.dumps({
        "regions": [
            {"box_id": 1, "ur_index": 0, "refined_guess": "cos(x)", "confidence": 0.95},
        ]
    })

    r = UncertaintyResolver(exam_dir_with_ur)
    r.resolve()

    json_files = Serializer.find_exam_files(exam_dir_with_ur)
    loaded = Serializer.load(json_files[0])
    assert loaded.boxes[0].uncertainRegions[0].llmGuess == "cos(x)"


def test_resolve_no_uncertain_regions(exam_dir_no_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_no_ur)
    exam = r.resolve()
    assert len(exam.boxes) == 1
    assert len(exam.boxes[0].uncertainRegions) == 0


@patch("note_analysis.agent.uncertainty.UncertaintyResolver._call_llm")
def test_resolve_skips_already_confirmed(mock_call_llm: MagicMock, exam_dir_with_ur: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_ur)[0])
    exam.boxes[0].uncertainRegions[0].userConfirmed = "cos(x)"
    Serializer.save(exam, exam_dir_with_ur)

    mock_call_llm.return_value = json.dumps({
        "regions": [
            {"box_id": 1, "ur_index": 1, "refined_guess": "f'(x)", "confidence": 0.90},
        ]
    })

    r = UncertaintyResolver(exam_dir_with_ur)
    result = r.resolve()

    assert result.boxes[0].uncertainRegions[0].userConfirmed == "cos(x)"
    assert result.boxes[0].uncertainRegions[1].llmGuess == "f'(x)"


def test_all_confirmed_check(exam_dir_with_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    assert not r.all_confirmed(exam)

    exam.boxes[0].uncertainRegions[0].userConfirmed = "yes"
    assert not r.all_confirmed(exam)

    exam.boxes[0].uncertainRegions[1].userConfirmed = "yes"
    assert r.all_confirmed(exam)


def test_all_confirmed_no_uncertain_regions(exam_dir_no_ur: Path) -> None:
    r = UncertaintyResolver(exam_dir_no_ur)
    exam = r._load_exam()
    assert r.all_confirmed(exam)


def test_all_confirmed_empty_exam(tmp_path: Path) -> None:
    exam = Exam.create(["test.jpg"])
    Serializer.save(exam, tmp_path)
    r = UncertaintyResolver(tmp_path)
    exam = r._load_exam()
    assert r.all_confirmed(exam)


def test_extract_uncertain_data_skips_confirmed(exam_dir_with_ur: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_ur)[0])
    exam.boxes[0].uncertainRegions[0].userConfirmed = "cos(x)"
    Serializer.save(exam, exam_dir_with_ur)

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)

    assert len(data) == 1
    assert data[0]["ur_index"] == 1


def test_extract_uncertain_data_all_confirmed(exam_dir_with_ur: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_ur)[0])
    for ur in exam.boxes[0].uncertainRegions:
        ur.userConfirmed = "yes"
    Serializer.save(exam, exam_dir_with_ur)

    r = UncertaintyResolver(exam_dir_with_ur)
    exam = r._load_exam()
    data = r._extract_uncertain_data(exam)

    assert len(data) == 0


@patch("note_analysis.agent.uncertainty.UncertaintyResolver._call_llm")
def test_resolve_only_unconfirmed(mock_call_llm: MagicMock, exam_dir_with_ur: Path) -> None:
    exam = Serializer.load(Serializer.find_exam_files(exam_dir_with_ur)[0])
    exam.boxes[0].uncertainRegions[0].userConfirmed = "cos(x)"
    Serializer.save(exam, exam_dir_with_ur)

    mock_call_llm.return_value = json.dumps({
        "regions": [
            {"box_id": 1, "ur_index": 1, "refined_guess": "f'(x)", "confidence": 0.90},
        ]
    })

    r = UncertaintyResolver(exam_dir_with_ur)
    result = r.resolve()

    assert result.boxes[0].uncertainRegions[0].llmGuess == "可能是 cos(x)"
    assert result.boxes[0].uncertainRegions[0].userConfirmed == "cos(x)"
    assert result.boxes[0].uncertainRegions[1].llmGuess == "f'(x)"
