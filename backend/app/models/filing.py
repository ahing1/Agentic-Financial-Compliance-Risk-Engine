import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class Filing(Base):
    __tablename__ = "filings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4
    )

    company = Column(String(255), nullable=False)
    ticker = Column(String(10), nullable=False, index=True)
    filing_type = Column(String(10), nullable=False)
    filing_date = Column(Date, nullable=False)
    source_url = Column(Text, nullable=False)
    raw_text = Column(Text)
    status = Column(String(20), server_default=text("NOW()"), default=datetime.utcnow)

    chunks = relationship(
        "FilingChunk", 
        back_populates="filing",
        cascade="all, delete-orphan",
        lazy = "select"
    )

    reports = relationship(
        "AnalysisReport",
        back_populates="filing",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    jobs = relationship(
        "Job", 
        back_populates = "filing",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self):
        return f"Filing(id={self.id}, ticker={self.ticker}, type={self.filing_type}, date={self.filing_date})"