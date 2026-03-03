"""SQLAlchemy model for Supabase public.ai_customer_reply."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class AiCustomerReply(Base):
    """Row in public.ai_customer_reply (customer behavior + summary)."""

    __tablename__ = "ai_customer_reply"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    conversation_id = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    urgency = Column(String, nullable=True)  # DB default 'Medium'
    category = Column(String, nullable=True)
    next_action = Column(Text, nullable=True)
    model = Column(String, nullable=True)  # DB default 'gpt-4'
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    thread_id = Column(String, nullable=True)
    cost = Column(Float, nullable=True)
    emotion = Column(String, nullable=True)
    emotion_intensity = Column(SmallInteger, nullable=True)
    expectation_gap = Column(String, nullable=True)
    revenue_risk = Column(String, nullable=True)
    blame_target = Column(String, nullable=True)
    strategic_signal = Column(Text, nullable=True)
    effort_level = Column(SmallInteger, nullable=True)
    refund_intent = Column(Boolean, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AiCustomerReply(id={self.id}, conversation_id={self.conversation_id}, "
            f"thread_id={self.thread_id}, revenue_risk={self.revenue_risk})>"
        )

