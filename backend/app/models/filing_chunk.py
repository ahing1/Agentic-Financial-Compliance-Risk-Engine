import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from pgvector.sqlalchemy import Vector

from app.db.session import Base
from app.config import settings


class FilingChunk(Base):
    __tablename__ = "filing_chunks"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )

    filing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("filing.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    chunk_text = Column(Text, nullable=False)
    
    # Position within the filing (0, 1, 2, ...) — preserves document order
    chunk_index = Column(Integer, nullable=False)
    
    # Which section this chunk belongs to (e.g., "Risk Factors")
    section = Column(String(255))

    embedding = Column(Vector(settings.embedding_dimensions), nullable=False)

    created_at = Column(DateTime, server_default=text("NOW()"), default=datetime.utcnow)
    
    # Bidirectional relationships
    filing = relationship("Filing", back_populates="chunks")
    risk_factors = relationship("RiskFactor", back_populates="source_chunk")
    
    def __repr__(self):
        return f"<FilingChunk(id={self.id}, section={self.section}, index={self.chunk_index})>"