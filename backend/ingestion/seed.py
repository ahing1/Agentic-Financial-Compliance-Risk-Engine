"""
ingestion/seed.py — Historical Data Seed Script

Run this script ONCE to populate your database with historical analyses
for a few well-known companies. This enables the comparison feature.

USAGE:
    python -m ingestion.seed

WARNING:
- Makes real API calls to EDGAR and OpenAI
- Each filing takes 30-60 seconds to analyze
- 5 companies × 1 filing = ~5 minutes + API costs
- The script skips companies that already have analyses
"""

import sys
import logging
from datetime import datetime

sys.path.insert(0, ".")

from app.config import settings
from app.db.session import get_session, engine, Base
from app.models import Filing, Job
from ingestion.edgar_client import fetch_latest_filing
from agent.graph import agent_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Companies to seed — well-known, different industries
SEED_TICKERS = [
    "AAPL",   # Tech — Apple
    "JPM",    # Finance — JPMorgan
    "JNJ",    # Healthcare — Johnson & Johnson
    "XOM",    # Energy — ExxonMobil
    "AMZN",   # Retail/Cloud — Amazon
]


def create_tables():
    """Create all database tables if they don't exist."""
    import app.models  # noqa: F401 — registers models with Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")


def already_seeded(ticker: str) -> bool:
    """Check if we already have analysis data for this ticker."""
    with get_session() as session:
        count = session.query(Filing).filter_by(
            ticker=ticker.upper(),
            status="completed",
        ).count()
        return count > 0


def seed_ticker(ticker: str):
    """
    Fetch the latest filing for a ticker and run the analysis agent.
    """
    logger.info(f"=== Seeding {ticker} ===")
    
    # --- Fetch filing from EDGAR ---
    try:
        filing_data = fetch_latest_filing(ticker, "10-K")
    except Exception as e:
        logger.error(f"Failed to fetch filing for {ticker}: {e}")
        return
    
    # --- Create database records ---
    with get_session() as session:
        filing = Filing(
            company=filing_data["company"],
            ticker=filing_data["ticker"],
            filing_type=filing_data["filing_type"],
            filing_date=datetime.strptime(filing_data["filing_date"], "%Y-%m-%d").date(),
            source_url=filing_data["source_url"],
            raw_text=filing_data["html"],
            status="processing",
        )
        session.add(filing)
        session.flush()
        
        job = Job(
            filing_id=filing.id,
            status="processing",
            started_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()
        
        filing_id = str(filing.id)
        logger.info(f"Created filing record: {filing_id}")
    
    # --- Run the agent ---
    initial_state = {
        "filing_id": filing_id,
        "ticker": filing_data["ticker"],
        "raw_html": filing_data["html"],
        "company": filing_data["company"],
        "filing_type": filing_data["filing_type"],
        "retry_count": 0,
        "status_messages": [],
    }
    
    try:
        result = agent_graph.invoke(initial_state)
        
        for msg in result.get("status_messages", []):
            logger.info(f"  [{msg.get('step')}] {msg.get('message')}")
        
        if result.get("completed"):
            logger.info(f"✓ {ticker} analysis complete (report: {result.get('report_id')})")
        else:
            logger.warning(f"✗ {ticker} analysis incomplete: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Agent failed for {ticker}: {e}")
        with get_session() as session:
            job = session.query(Job).filter_by(filing_id=filing_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.utcnow()
            session.commit()


def main():
    """Run the seed process for all configured tickers."""
    logger.info("Starting historical data seed")
    logger.info(f"Tickers to seed: {SEED_TICKERS}")
    
    create_tables()
    
    for ticker in SEED_TICKERS:
        if already_seeded(ticker):
            logger.info(f"Skipping {ticker} — already has analysis data")
            continue
        
        seed_ticker(ticker)
        logger.info("")
    
    logger.info("Seed complete!")


if __name__ == "__main__":
    main()