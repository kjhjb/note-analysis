import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from click.testing import CliRunner

from note_analysis.cli import cli


def _make_test_image(path: Path, height: int = 600, width: int = 800) -> None:
    """创建真实 JPEG 测试图片：白底 + 模拟文字区域"""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    regions = [(80, 160), (240, 320), (400, 480)]
    for y1, y2 in regions:
        img[y1:y2, 40:760] = (200, 200, 200)
        for row in range(y1 + 8, y2 - 8, 12):
            img[row, 50:750] = (30, 30, 30)
    cv2.imwrite(str(path), img)


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "笔记分析工具" in result.output


def test_init_no_images(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_path)])
    assert result.exit_code == 1


def test_init_with_images(tmp_path: Path) -> None:
    (tmp_path / "photo1.jpg").write_text("fake-image-data")
    (tmp_path / "photo2.png").write_text("fake-image-data")

    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "已扫描 2 张图片" in result.output
    assert "JSON 骨架已生成" in result.output

    json_files = list(tmp_path.glob("笔记_*.json"))
    assert len(json_files) == 1


def test_init_skips_non_images(tmp_path: Path) -> None:
    (tmp_path / "photo1.jpg").write_text("data")
    (tmp_path / "notes.txt").write_text("text")
    (tmp_path / "data.csv").write_text("csv")

    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "已扫描 1 张图片" in result.output


def test_init_generates_valid_json(tmp_path: Path) -> None:
    (tmp_path / "exam.jpg").write_text("data")

    runner = CliRunner()
    runner.invoke(cli, ["init", str(tmp_path)])
    json_files = list(tmp_path.glob("笔记_*.json"))
    assert len(json_files) == 1

    import json
    data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert "examId" in data
    assert "photos" in data
    assert "boxes" in data
    assert "createdAt" in data
    assert len(data["photos"]) == 1


def test_box_no_json(tmp_path: Path) -> None:
    """无 JSON 文件时应报错"""
    runner = CliRunner()
    result = runner.invoke(cli, ["box", str(tmp_path)])
    assert result.exit_code != 0


def test_box_with_no_boxes(tmp_path: Path) -> None:
    """纯白图像应检测出 0 个框，JSON 中 boxes 为空列表"""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    cv2.imwrite(str(tmp_path / "blank.jpg"), img)

    runner = CliRunner()
    runner.invoke(cli, ["init", str(tmp_path)])
    result = runner.invoke(cli, ["box", str(tmp_path)])
    assert result.exit_code == 0
    assert "框选完成" in result.output

    json_files = list(tmp_path.glob("笔记_*.json"))
    data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert len(data["boxes"]) == 0


def test_box_with_synthetic_exam(tmp_path: Path) -> None:
    """合成试卷应检测出正确的 bbox 数量"""
    _make_test_image(tmp_path / "page1.jpg")

    runner = CliRunner()
    runner.invoke(cli, ["init", str(tmp_path)])
    result = runner.invoke(cli, ["box", str(tmp_path)])
    assert result.exit_code == 0
    assert "框选完成" in result.output

    json_files = list(tmp_path.glob("笔记_*.json"))
    data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert len(data["boxes"]) == 3
    for box in data["boxes"]:
        assert "x" in box["bbox"] and "y" in box["bbox"] and "w" in box["bbox"] and "h" in box["bbox"]


def test_box_generates_preview(tmp_path: Path) -> None:
    """box 命令应生成预览图"""
    _make_test_image(tmp_path / "page1.jpg")

    runner = CliRunner()
    runner.invoke(cli, ["init", str(tmp_path)])
    runner.invoke(cli, ["box", str(tmp_path)])

    previews = list(tmp_path.glob("*_bbox_preview.jpg"))
    assert len(previews) >= 1


def test_init_unreadable_directory():
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "/nonexistent/path"])
    assert result.exit_code != 0


@patch("note_analysis.agent.uncertainty.UncertaintyResolver.resolve")
def test_uncertain_command(mock_resolve, tmp_path: Path) -> None:
    """uncertain 命令基本流程"""
    from note_analysis.models.models import Exam
    from note_analysis.models.serializer import Serializer

    exam = Exam.create([str(tmp_path / "test.jpg")])
    Serializer.save(exam, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["uncertain", str(tmp_path)])
    assert result.exit_code == 0


def test_uncertain_no_json(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["uncertain", str(tmp_path)])
    assert result.exit_code != 0


@patch("note_analysis.agent.uncertainty.UncertaintyResolver.all_confirmed")
def test_review_blocks_unconfirmed(mock_all_confirmed, tmp_path: Path) -> None:
    """review 命令在未确认不确定区域时应报错"""
    from note_analysis.models.models import Exam
    from note_analysis.models.serializer import Serializer

    mock_all_confirmed.return_value = False
    exam = Exam.create([str(tmp_path / "test.jpg")])
    Serializer.save(exam, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["review", str(tmp_path)])
    assert result.exit_code != 0
    assert "未确认" in result.output


def test_help_subcommands():
    runner = CliRunner()
    for cmd in ["box", "serve", "recognize", "uncertain", "review", "render", "analyze"]:
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0
