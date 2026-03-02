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
    response_accuracy: float = Field(..., ge=0.0, le=10.0, description="Score for response accuracy (0-10)")
    tone_empathy: float = Field(..., ge=0.0, le=10.0, description="Score for tone & empathy (0-10)")
    clarity_structure: float = Field(..., ge=0.0, le=10.0, description="Score for clarity & structure (0-10)")
    relevance_to_thread: float = Field(..., ge=0.0, le=10.0, description="Score for relevance to thread (0-10)")
    completeness: float = Field(..., ge=0.0, le=10.0, description="Score for completeness (0-10)")
    proactive_detail: float = Field(..., ge=0.0, le=10.0, description="Score for proactive detail (0-10)")
    personalization: float = Field(..., ge=0.0, le=10.0, description="Score for personalization (0-10)")
    policy_process_adherence: float = Field(..., ge=0.0, le=10.0, description="Score for policy & process adherence (0-10)")
    action_clarity: float = Field(..., ge=0.0, le=10.0, description="Score for action clarity (0-10)")
    grammar_professionalism: float = Field(..., ge=0.0, le=10.0, description="Score for grammar & professionalism (0-10)")
    average_score: float = Field(..., ge=0.0, le=10.0, description="Average score (0-10)")

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "evaluation_message": "The agent provided a clear and helpful response...",
                "improvement": "Consider providing more specific examples to help the customer better understand the solution.",
                "response_accuracy": 8.5,
                "tone_empathy": 9.0,
                "clarity_structure": 8.0,
                "relevance_to_thread": 8.5,
                "completeness": 8.0,
                "proactive_detail": 7.0,
                "personalization": 7.5,
                "policy_process_adherence": 9.0,
                "action_clarity": 8.5,
                "grammar_professionalism": 9.0,
                "average_score": 8.4,
            }
        }

