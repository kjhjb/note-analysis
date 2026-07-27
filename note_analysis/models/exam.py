from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    id: int = Field(ge=0)
    bbox: BBox
    questionText: str = ""
    annotations: str = ""
    images: list[str] = []
    uncertainRegions: list[UncertainRegion] = []
    reviewStatus: str = "pending"
    reviewNotes: str = ""

    @field_validator("reviewStatus")
    @classmethod
    def _validate_review_status(cls, v: str) -> str:
        allowed = {"pending", "consistent", "inconsistent"}
        if v not in allowed:
            msg = f"reviewStatus must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v


class WeakPoint(BaseModel):
    knowledgePoint: str
    errorCount: int = Field(ge=0)
    llmAdvice: str


class Exam(BaseModel):
    examId: str
    photos: list[str]
    boxes: list[QuestionBox] = []
    createdAt: str
    weakPoints: list[dict] = []
