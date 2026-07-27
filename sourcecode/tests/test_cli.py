from pathlib import Path

from click.testing import CliRunner

from note_analysis.cli import cli


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


def test_init_unreadable_directory():
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "/nonexistent/path"])
    assert result.exit_code != 0


def test_help_subcommands():
    runner = CliRunner()
    for cmd in ["box", "serve", "recognize", "review", "render", "analyze"]:
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0
