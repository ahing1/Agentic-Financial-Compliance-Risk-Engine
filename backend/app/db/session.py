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

WHY LAZY INITIALIZATION:
The engine and session factory are created on first use, not at import time.
This is critical for Celery workers on macOS: billiard forks the worker
process during startup, and a connection pool created before the fork gets
corrupted in the child process (causing SIGSEGV). Lazy init ensures the
pool is created AFTER the fork.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass

_engine = None
_SessionLocal = None

def get_engine():
    global _engine
    if _engine is None:
        db_url = settings.database_url
        # psycopg v3 uses the "psycopg" driver name, not "psycopg2"
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif db_url.startswith("postgresql+psycopg2://"):
            db_url = db_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        _engine = create_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    return _engine

def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal

# Keep these as properties for backward compatibility with main.py's
# Base.metadata.create_all(bind=engine)
engine = None  # Set lazily; use get_engine() instead

@contextmanager
def get_session():
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
