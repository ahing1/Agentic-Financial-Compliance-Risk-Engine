import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    
    filing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    
    status = Column(
        String(20),
        server_default=text("'pending'"),
        default="pending",
        index=True,
    )
    
    current_step = Column(String(50))
    
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    error = Column(Text)
    
    created_at = Column(DateTime, server_default=text("NOW()"), default=datetime.utcnow)
    
    filing = relationship("Filing", back_populates="jobs")
    user = relationship("User", back_populates="jobs")
    
    def __repr__(self):
        return f"<Job(id={self.id}, status={self.status}, step={self.current_step})>"