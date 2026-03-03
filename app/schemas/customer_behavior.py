"""Pydantic schemas for customer behavior analysis (reply/customer)."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CustomerBehaviorResponse(BaseModel):
    """Response schema for customer behavior analysis."""

    emotion: Optional[str] = Field(
        None,
        description="angry | frustrated | confused | disappointed | neutral | positive",
    )
    emotion_intensity: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Intensity 1-5",
    )
    expectation_gap: Optional[str] = Field(
        None,
        description="feature_missing | bug | pricing_confusion | renewal_issue | ux_confusion | compatibility_issue | none",
    )
    problem_type: Optional[str] = Field(
        None,
        description="installation | search | payment | booking | forms | ui | performance | integration | subscription | other",
    )
    revenue_risk: Optional[str] = Field(
        None,
        description="high | medium | low",
    )
    blame_target: Optional[str] = Field(
        None,
        description="product | company | support | third_party | none",
    )
    effort_level: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Effort level 1-5",
    )
    refund_intent: Optional[bool] = Field(None, description="Whether refund is indicated")
    strategic_signal: Optional[str] = Field(
        None,
        description="Short summary of root cause",
    )

    @field_validator("emotion_intensity", "effort_level", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return v
