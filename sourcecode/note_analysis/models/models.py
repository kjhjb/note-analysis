from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NOTE_PREFIX = "笔记_"


class BBox(BaseModel):
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class UncertainRegion(BaseModel):
    bbox: BBox
    llmGuess: str
    llmConfidence: float = Field(ge=0, le=1)
    userConfirmed: str | None = None


class QuestionBox(BaseModel):
    id: int
    bbox: BBox
    photoIndex: int = 0
    questionText: str = ""
    annotations: str = ""
    images: list[str] = []
    uncertainRegions: list[UncertainRegion] = []
    reviewStatus: Literal["pending", "consistent", "inconsistent", "uncertain"] = "pending"
    reviewNotes: str = ""
    isError: bool = False
    errorMarks: list[str] = []
    circledKeyPoints: str = ""
    circledRegions: list[BBox] = []
    correction: str = ""


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
    errorCount: int = Field(ge=0)
    llmAdvice: str
