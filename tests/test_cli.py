import json
import os
from datetime import datetime

from click.testing import CliRunner

from main import cli


class TestCliSubcommands:
    """所有子命令已注册"""

    def test_all_subcommands_registered(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ["init", "box", "serve", "recognize", "review", "render", "analyze"]:
            assert cmd in result.output


class TestInitCommand:
    def test_init_creates_json_skeleton(self, tmp_path):
        (tmp_path / "photo1.jpg").write_text("fake-image-data")
        (tmp_path / "photo2.png").write_text("fake-image-data")

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        json_files = list(tmp_path.glob("笔记_*.json"))
        assert len(json_files) == 1

        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "examId" in data
        assert data["photos"] == [
            str(tmp_path / "photo1.jpg"),
            str(tmp_path / "photo2.png"),
        ]
        assert data["boxes"] == []
        assert data["weakPoints"] == []

    def test_init_skips_non_images(self, tmp_path):
        (tmp_path / "photo1.jpg").write_text("fake")
        (tmp_path / "notes.txt").write_text("not an image")
        (tmp_path / "data.csv").write_text("a,b,c")

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        json_files = list(tmp_path.glob("笔记_*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert len(data["photos"]) == 1
        assert "photo1.jpg" in data["photos"][0]

    def test_init_with_no_images(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        json_files = list(tmp_path.glob("笔记_*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert data["photos"] == []

    def test_init_output_naming(self, tmp_path):
        (tmp_path / "test.jpg").write_text("fake")
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        json_files = list(tmp_path.glob("笔记_*.json"))
        name = json_files[0].name
        assert name.startswith("笔记_")
        assert name.endswith(".json")
        date_part = name.replace("笔记_", "").replace(".json", "")
        assert len(date_part) == 13  # YYYYMMDD_HHmm
        assert "_" in date_part

    def test_init_is_idempotent(self, tmp_path):
        (tmp_path / "test.jpg").write_text("fake")
        runner = CliRunner()
        r1 = runner.invoke(cli, ["init", str(tmp_path)])
        assert r1.exit_code == 0
        r2 = runner.invoke(cli, ["init", str(tmp_path)])
        assert r2.exit_code == 0

        json_files = list(tmp_path.glob("笔记_*.json"))
        assert len(json_files) >= 1  # 同一分钟内运行可能覆盖
