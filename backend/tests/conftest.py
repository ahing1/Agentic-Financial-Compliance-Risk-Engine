import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Override the database URL BEFORE importing app modules.
# This ensures all app code uses the test database, not your real one.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/compliance_engine_test"
)
os.environ["REDIS_URL"] = os.getenv(
    "TEST_REDIS_URL",
    "redis://localhost:6379/1"  # Use Redis DB 1 for tests (DB 0 is your real app)
)

from app.db.session import Base, get_engine
from app.models import *  # noqa: F401, F403 — registers all models


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Create all tables once at the start of the test session.

    scope="session" means this runs once for the entire pytest run,
    not once per test. autouse=True means it runs automatically
    without tests needing to request it.
    """
    engine = get_engine()
    # Create pgvector extension if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield

    # Cleanup: drop all tables after all tests finish
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    """
    Provide a database session that rolls back after each test.

    Every test gets a clean slate:
    1. Open a transaction
    2. Test runs and creates/modifies data
    3. Rollback — all changes disappear

    This is faster than truncating tables and guarantees
    no test data leaks between tests.
    """
    engine = get_engine()
    connection = engine.connect()
    transaction = connection.begin()

    # Create a session bound to this specific connection/transaction
    session = sessionmaker(bind=connection)()

    yield session

    # Cleanup: rollback everything the test did
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_filing_data():
    """
    Reusable sample filing data for tests that need filing metadata.
    
    Using a fixture instead of hardcoding in each test means:
    - One place to update if the data shape changes
    - Tests are shorter and more focused on what they're testing
    """
    return {
        "ticker": "AAPL",
        "company": "Apple Inc.",
        "filing_type": "10-K",
        "filing_date": "2024-11-01",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/test.htm",
        "raw_html": "<html><body><h1>Item 1A: Risk Factors</h1><p>The company faces significant supply chain risks due to concentration in Asia-Pacific manufacturing partners.</p></body></html>",
    }