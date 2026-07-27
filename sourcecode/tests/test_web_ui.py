from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from note_analysis.models.models import BBox, Exam, QuestionBox, UncertainRegion
from note_analysis.models.serializer import Serializer
from note_analysis.web.server import _create_app, _find_free_port


def _make_test_image(path: Path) -> None:
    img = np.ones((200, 300, 3), dtype=np.uint8) * 255
    img[50:150, 50:250] = (200, 200, 200)
    for row in range(60, 140, 10):
        img[row, 60:240] = (30, 30, 30)
    cv2.imwrite(str(path), img)


def test_find_free_port():
    port = _find_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535


class TestApp:
    def test_create_app_returns_html(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "框选微调" in response.text

    def test_get_exam_data(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/api/exam")
        assert response.status_code == 200
        data = response.json()
        assert data["examId"] == exam.examId
        assert data["photos"] == exam.photos

    def test_get_photo(self, tmp_path: Path) -> None:
        _make_test_image(tmp_path / "test.jpg")
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/api/photo/0")
        assert response.status_code == 200
        assert response.headers["content-type"] in ("image/jpeg", "image/png")

    def test_get_photo_out_of_range(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/api/photo/99")
        assert response.status_code == 404

    def test_update_boxes(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)

        new_boxes = [
            {"id": 1, "bbox": {"x": 10, "y": 20, "w": 100, "h": 200}},
            {"id": 2, "bbox": {"x": 50, "y": 60, "w": 150, "h": 80}, "photoIndex": 0},
        ]
        response = client.put("/api/exam/boxes", json={"boxes": new_boxes})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        json_files = Serializer.find_exam_files(tmp_path)
        loaded = Serializer.load(json_files[0])
        assert len(loaded.boxes) == 2
        assert loaded.boxes[0].bbox.x == 10
        assert loaded.boxes[0].bbox.y == 20
        assert loaded.boxes[0].bbox.w == 100
        assert loaded.boxes[0].bbox.h == 200

    def test_update_boxes_missing_field(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)

        response = client.put("/api/exam/boxes", json={"boxes": [{"id": 1}]})
        assert response.status_code == 422

    def test_done_endpoint(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.post("/api/exam/done")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_done_persists_boxes(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        exam.boxes = [QuestionBox(id=1, bbox=BBox(x=0, y=0, w=100, h=100), questionText="test")]
        app = _create_app(exam, tmp_path)
        client = TestClient(app)

        client.post("/api/exam/done")

        json_files = Serializer.find_exam_files(tmp_path)
        loaded = Serializer.load(json_files[0])
        assert len(loaded.boxes) == 1
        assert loaded.boxes[0].questionText == "test"

    def test_html_contains_photo_count(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "p1.jpg"), str(tmp_path / "p2.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "2" in response.text

    def test_boxes_included_in_html_data(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        exam.boxes = [QuestionBox(id=42, bbox=BBox(x=10, y=20, w=100, h=200))]
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/")
        assert "42" in response.text
        assert "10" in response.text
        assert "200" in response.text


class TestUncertainPage:
    def test_uncertain_page_loads(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/uncertain")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "不确定区域确认" in response.text

    def test_uncertain_page_shows_regions(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        ur = UncertainRegion(bbox=BBox(x=10, y=10, w=60, h=25), llmGuess="sin(x)", llmConfidence=0.65)
        exam.boxes = [
            QuestionBox(id=1, bbox=BBox(x=0, y=0, w=400, h=300), uncertainRegions=[ur], questionText="求 f(x)")
        ]
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/uncertain")
        assert "sin(x)" in response.text
        assert "求 f(x)" in response.text
        assert "65%" in response.text or "65" in response.text

    def test_uncertain_page_all_confirmed(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        ur = UncertainRegion(
            bbox=BBox(x=10, y=10, w=60, h=25), llmGuess="sin(x)", llmConfidence=0.65, userConfirmed="sin(x)"
        )
        exam.boxes = [
            QuestionBox(id=1, bbox=BBox(x=0, y=0, w=400, h=300), uncertainRegions=[ur])
        ]
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/uncertain")
        assert "全部已确认" in response.text or "100" in response.text or "已确认" in response.text

    def test_uncertain_region_image_not_found(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/api/uncertain-region-image/999/0")
        assert response.status_code == 404

    def test_uncertain_region_image_bad_index(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.get("/api/uncertain-region-image/1/99")
        assert response.status_code == 404

    def test_confirm_uncertain_regions(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        ur = UncertainRegion(bbox=BBox(x=10, y=10, w=60, h=25), llmGuess="sin(x)", llmConfidence=0.65)
        exam.boxes = [
            QuestionBox(id=1, bbox=BBox(x=0, y=0, w=400, h=300), uncertainRegions=[ur])
        ]
        Serializer.save(exam, tmp_path)

        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        response = client.post(
            "/api/exam/uncertain-regions/confirm",
            json={"confirmations": [{"boxId": 1, "urIndex": 0, "userConfirmed": "cos(x)"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_confirm_persists_to_json(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        ur = UncertainRegion(bbox=BBox(x=10, y=10, w=60, h=25), llmGuess="sin(x)", llmConfidence=0.65)
        exam.boxes = [
            QuestionBox(id=1, bbox=BBox(x=0, y=0, w=400, h=300), uncertainRegions=[ur])
        ]
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        client.post(
            "/api/exam/uncertain-regions/confirm",
            json={"confirmations": [{"boxId": 1, "urIndex": 0, "userConfirmed": "sin(x)"}]},
        )

        json_files = Serializer.find_exam_files(tmp_path)
        loaded = Serializer.load(json_files[0])
        assert loaded.boxes[0].uncertainRegions[0].userConfirmed == "sin(x)"

    def test_confirm_multiple_regions(self, tmp_path: Path) -> None:
        exam = Exam.create([str(tmp_path / "test.jpg")])
        ur1 = UncertainRegion(bbox=BBox(x=10, y=10, w=60, h=25), llmGuess="guess1", llmConfidence=0.6)
        ur2 = UncertainRegion(bbox=BBox(x=80, y=10, w=40, h=20), llmGuess="guess2", llmConfidence=0.7)
        exam.boxes = [
            QuestionBox(id=1, bbox=BBox(x=0, y=0, w=400, h=300), uncertainRegions=[ur1, ur2])
        ]
        app = _create_app(exam, tmp_path)
        client = TestClient(app)
        client.post(
            "/api/exam/uncertain-regions/confirm",
            json={
                "confirmations": [
                    {"boxId": 1, "urIndex": 0, "userConfirmed": "confirmed1"},
                    {"boxId": 1, "urIndex": 1, "userConfirmed": "__IGNORED__"},
                ]
            },
        )

        json_files = Serializer.find_exam_files(tmp_path)
        loaded = Serializer.load(json_files[0])
        assert loaded.boxes[0].uncertainRegions[0].userConfirmed == "confirmed1"
        assert loaded.boxes[0].uncertainRegions[1].userConfirmed == "__IGNORED__"


class TestCliServe:
    @patch("note_analysis.web.server.run_server")
    def test_serve_command_calls_run_server(self, mock_run, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from note_analysis.cli import cli

        exam = Exam.create([str(tmp_path / "test.jpg")])
        Serializer.save(exam, tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["serve", str(tmp_path)])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_serve_no_json(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from note_analysis.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["serve", str(tmp_path)])
        assert result.exit_code != 0
