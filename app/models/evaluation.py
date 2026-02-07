"""Evaluation model for storing AI evaluations of support conversations."""

from sqlalchemy import Column, String, Text, Float, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Evaluation(Base):
    """Model for storing evaluation results."""

    __tablename__ = "evaluations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    conversation_id = Column(String(255), nullable=False, index=True)
    thread_id = Column(String(255), nullable=False, index=True)
    conversation_data = Column(JSON, nullable=True)  # Store raw Help Scout data
    evaluation_message = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        """String representation of the model."""
        return (
            f"<Evaluation(id={self.id}, conversation_id={self.conversation_id}, "
            f"thread_id={self.thread_id}, score={self.score})>"
        )

