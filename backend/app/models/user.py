import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class User(Base):
    __tablename__ = "users"
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4
    )

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=text("NOW()"), default=datetime.utcnow)

    jobs = relationship("Job", back_populates="user", lazy="selectin")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"



