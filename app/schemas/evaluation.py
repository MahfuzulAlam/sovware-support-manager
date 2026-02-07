"""Pydantic schemas for evaluation endpoints."""

from pydantic import BaseModel, Field
from typing import Optional


class EvaluationRequest(BaseModel):
    """Request schema for evaluation endpoint."""

    conversation_id: str = Field(..., description="Help Scout conversation ID")
    thread_id: str = Field(..., description="Help Scout thread ID")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "conversation_id": "123",
                "thread_id": "456",
            }
        }


class EvaluationCreate(BaseModel):
    """Schema for creating an evaluation in the database."""

    conversation_id: str
    thread_id: str
    conversation_data: Optional[dict] = None
    evaluation_message: str
    score: float = Field(..., ge=0.0, le=10.0, description="Score between 0 and 10")


class EvaluationResponse(BaseModel):
    """Response schema for evaluation endpoint."""

    evaluation_message: str
    improvement: str
    empathy_understanding: float = Field(..., ge=0.0, le=10.0, description="Score for empathy & understanding (0-10)")
    tone_warmth: float = Field(..., ge=0.0, le=10.0, description="Score for tone & warmth (0-10)")
    professionalism: float = Field(..., ge=0.0, le=10.0, description="Score for professionalism (0-10)")
    personalization: float = Field(..., ge=0.0, le=10.0, description="Score for personalization (0-10)")
    clarity: float = Field(..., ge=0.0, le=10.0, description="Score for clarity (0-10)")
    completeness: float = Field(..., ge=0.0, le=10.0, description="Score for completeness (0-10)")
    proactiveness: float = Field(..., ge=0.0, le=10.0, description="Score for proactiveness (0-10)")
    helpfulness_problem_solving: float = Field(..., ge=0.0, le=10.0, description="Score for helpfulness & problem-solving (0-10)")
    patience_respect: float = Field(..., ge=0.0, le=10.0, description="Score for patience & respect (0-10)")
    structure_closing: float = Field(..., ge=0.0, le=10.0, description="Score for structure & closing (0-10)")

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "evaluation_message": "The agent provided a clear and helpful response...",
                "improvement": "Consider providing more specific examples to help the customer better understand the solution.",
                "empathy_understanding": 8.5,
                "tone_warmth": 9.0,
                "professionalism": 8.0,
                "personalization": 7.5,
                "clarity": 9.5,
                "completeness": 8.0,
                "proactiveness": 7.0,
                "helpfulness_problem_solving": 8.5,
                "patience_respect": 9.0,
                "structure_closing": 8.5,
            }
        }

