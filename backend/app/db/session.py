"""
This module sets up two things:
1. The ENGINE — a connection pool to PostgreSQL. Instead of opening a new connection
   for every query (slow), the engine maintains a pool of reusable connections.

2. The SESSION FACTORY — creates individual sessions for database operations.

WHY SESSIONS MATTER:
Without sessions, every database operation would be independent. If you
need to create a Report AND its RiskFactors together (they reference each
other via foreign keys), you need them in the same session so they either
ALL succeed or ALL fail. This is called a "transaction."
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# every database model inherits from this base class. ssqlalchemy uses base to keep track of all your models your models and their table definitions
class Base(DeclarativeBase):
    pass

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_size = 5,
    max_overflow = 10
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

