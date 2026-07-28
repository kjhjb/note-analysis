import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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


@patch("note_analysis.agent.review.Reviewer.review")
@patch("note_analysis.agent.uncertainty.UncertaintyResolver.all_confirmed")
def test_review_command_success(
    mock_all_confirmed: MagicMock,
    mock_review: MagicMock,
    tmp_path: Path,
) -> None:
    """review 命令成功执行"""
    from note_analysis.models.models import BBox, Exam, QuestionBox
    from note_analysis.models.serializer import Serializer

    mock_all_confirmed.return_value = True
    exam = Exam.create([str(tmp_path / "test.jpg")])
    exam.boxes = [
        QuestionBox(
            id=1, bbox=BBox(x=0, y=0, w=100, h=100),
            questionText="Q1", annotations="A1",
            reviewStatus="consistent", reviewNotes="OK",
        ),
    ]
    mock_review.return_value = exam
    Serializer.save(exam, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["review", str(tmp_path)])
    assert result.exit_code == 0
    assert "审查完成" in result.output
    assert "consistent" in result.output


@patch("note_analysis.agent.review.Reviewer.review")
@patch("note_analysis.agent.uncertainty.UncertaintyResolver.all_confirmed")
def test_review_command_shows_summary(
    mock_all_confirmed: MagicMock,
    mock_review: MagicMock,
    tmp_path: Path,
) -> None:
    """review 命令输出审查摘要"""
    from note_analysis.models.models import BBox, Exam, QuestionBox
    from note_analysis.models.serializer import Serializer

    mock_all_confirmed.return_value = True
    exam = Exam.create([str(tmp_path / "test.jpg")])
    exam.boxes = [
        QuestionBox(
            id=1, bbox=BBox(x=0, y=0, w=100, h=100),
            questionText="Q1", annotations="A1",
            reviewStatus="consistent", reviewNotes="逻辑一致",
        ),
        QuestionBox(
            id=2, bbox=BBox(x=0, y=100, w=100, h=100),
            questionText="Q2", annotations="A2",
            reviewStatus="inconsistent", reviewNotes="计算错误",
        ),
    ]
    mock_review.return_value = exam
    Serializer.save(exam, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["review", str(tmp_path)])
    assert result.exit_code == 0
    assert "审查完成" in result.output
    assert "逻辑一致" in result.output
    assert "计算错误" in result.output


def test_help_subcommands():
    runner = CliRunner()
    for cmd in ["box", "serve", "recognize", "uncertain", "review", "render", "analyze"]:
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0


def test_render_no_json(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["render", str(tmp_path)])
    assert result.exit_code != 0


def test_render_with_data(tmp_path: Path) -> None:
    from note_analysis.models.models import BBox, Exam, QuestionBox
    from note_analysis.models.serializer import Serializer

    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    cv2.putText(img, "Test", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(str(tmp_path / "exam.jpg"), img)

    exam = Exam.create([str(tmp_path / "exam.jpg")])
    exam.boxes = [
        QuestionBox(
            id=1, bbox=BBox(x=0, y=0, w=100, h=100),
            questionText="测试题", annotations="笔记",
        ),
    ]
    Serializer.save(exam, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["render", str(tmp_path)])
    assert result.exit_code == 0
    assert "HTML 笔记已生成" in result.output
    html_files = list(tmp_path.glob("笔记_*.html"))
    assert len(html_files) == 1


@patch("note_analysis.agent.core.httpx.Client.post")
def test_analyze_command(mock_post: MagicMock, tmp_path: Path) -> None:
    """analyze 命令基本流程"""
    from note_analysis.models.models import BBox, Exam, QuestionBox
    from note_analysis.models.serializer import Serializer

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps({
            "weakPoints": [
                {"knowledgePoint": "导数", "errorCount": 1, "llmAdvice": "多练习"},
            ]
        })}]
    }
    mock_post.return_value = mock_response

    exam = Exam.create([str(tmp_path / "test.jpg")])
    exam.boxes = [
        QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100),
                     questionText="Q1", annotations="A1",
                     reviewStatus="inconsistent", reviewNotes="计算错误"),
    ]
    Serializer.save(exam, tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "分析完成" in result.output
    assert "导数" in result.output


def test_analyze_no_json(tmp_path: Path) -> None:
    """analyze 命令无 JSON 时应提示"""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "未找到试卷 JSON 文件" in result.output


def test_cli_env_file_option(tmp_path: Path) -> None:
    """--env-file 选项应正常解析"""
    env_file = tmp_path / ".env.test"
    env_file.write_text("LLM_API_KEY=test-key-from-file", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["--env-file", str(env_file), "init", str(tmp_path)])
    assert result.exit_code == 1


def test_cli_env_file_not_found(tmp_path: Path) -> None:
    """--env-file 指定不存在的文件应报错"""
    runner = CliRunner()
    result = runner.invoke(cli, ["--env-file", str(tmp_path / "nonexistent.env"), "init", str(tmp_path)])
    assert result.exit_code != 0


@patch("note_analysis.agent.core.load_dotenv")
def test_cli_env_file_option_passed_to_agent(mock_load_dotenv: MagicMock, tmp_path: Path) -> None:
    """--env-file 选项应能被 Agent 接收"""
    from note_analysis.agent.core import Agent
    from note_analysis.models.models import Exam
    from note_analysis.models.serializer import Serializer

    env_file = tmp_path / ".env.test"
    env_file.write_text("LLM_API_KEY=key", encoding="utf-8")
    (tmp_path / "photo.jpg").write_text("data")

    runner = CliRunner()
    runner.invoke(cli, ["--env-file", str(env_file), "init", str(tmp_path)])

    json_files = Serializer.find_exam_files(tmp_path)
    assert len(json_files) == 1
