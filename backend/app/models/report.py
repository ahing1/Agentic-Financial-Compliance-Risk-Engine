import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    
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

    risk_score = Column(Numeric(3, 1))
    
    summary = Column(Text, nullable=False)
    
    created_at = Column(DateTime, server_default=text("NOW()"), default=datetime.utcnow)
    
    filing = relationship("Filing", back_populates="reports")
    
    risk_factors = relationship(
        "RiskFactor",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    def __repr__(self):
        return f"<AnalysisReport(id={self.id}, filing_id={self.filing_id}, score={self.risk_score})>"