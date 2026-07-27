from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NOTE_PREFIX = "笔记_"


class BBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class UncertainRegion(BaseModel):
    bbox: BBox
    llmGuess: str
    llmConfidence: float
    userConfirmed: str | None = None


class QuestionBox(BaseModel):
    id: int
    bbox: BBox
    questionText: str = ""
    annotations: str = ""
    images: list[str] = []
    uncertainRegions: list[UncertainRegion] = []
    reviewStatus: Literal["pending", "consistent", "inconsistent"] = "pending"
    reviewNotes: str = ""


class Exam(BaseModel):
    examId: str
    photos: list[str] = []
    boxes: list[QuestionBox] = []
    createdAt: str = ""
    weakPoints: list[WeakPoint] = []

    @classmethod
    def create(cls, photos: list[str]) -> "Exam":
        now = datetime.now()
        created_at = now.strftime("%Y%m%d_%H%M")
        return cls(examId=created_at, photos=photos, createdAt=created_at)

    @property
    def json_filename(self) -> str:
        return f"{NOTE_PREFIX}{self.createdAt}.json"

    @property
    def html_filename(self) -> str:
        return f"{NOTE_PREFIX}{self.createdAt}.html"


class WeakPoint(BaseModel):
    knowledgePoint: str
    errorCount: int
    llmAdvice: str
