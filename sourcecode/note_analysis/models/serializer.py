import json
from pathlib import Path

from note_analysis.models.models import NOTE_PREFIX, Exam


class Serializer:
    @staticmethod
    def save(exam: Exam, directory: Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        filepath = directory / exam.json_filename
        data = exam.model_dump()
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return filepath

    @staticmethod
    def load(filepath: Path) -> Exam:
        filepath = Path(filepath)
        data = json.loads(filepath.read_text(encoding="utf-8"))
        exam: Exam = Exam.model_validate(data)
        return exam

    @staticmethod
    def find_exam_files(directory: Path) -> list[Path]:
        directory = Path(directory)
        if not directory.exists():
            return []
        return sorted(directory.glob(f"{NOTE_PREFIX}*.json"))
