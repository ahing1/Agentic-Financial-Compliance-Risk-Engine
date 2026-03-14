"""
1. Fetches a filing from EDGAR
2. Creates database records
3. Runs the full agent pipeline
4. Prints results

USAGE:
    python run_analysis.py AAPL
    python run_analysis.py MSFT 10-Q
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


def ensure_tables():
    """Create tables if they don't exist."""
    import app.models
    Base.metadata.create_all(bind=engine)


def run(ticker: str, filing_type: str = "10-K"):
    print(f"\n{'='*60}")
    print(f"  Analyzing {ticker} ({filing_type})")
    print(f"{'='*60}\n")
    
    ensure_tables()
    
    # --- Fetch filing ---
    print(f"[1/3] Fetching {filing_type} from SEC EDGAR...")
    try:
        filing_data = fetch_latest_filing(ticker, filing_type)
        print(f"      ✓ {filing_data['company']} dated {filing_data['filing_date']}")
        print(f"      ✓ {len(filing_data['html'])} characters of HTML")
    except Exception as e:
        print(f"      ✗ Failed: {e}")
        return
    
    # --- Create database records ---
    print(f"\n[2/3] Creating database records...")
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
        print(f"      ✓ Filing ID: {filing_id}")
    
    # --- Run agent ---
    print(f"\n[3/3] Running agent analysis...\n")
    
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
    except Exception as e:
        print(f"\n      ✗ Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # --- Print results ---
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}\n")
    
    print("Agent Timeline:")
    for msg in result.get("status_messages", []):
        step = msg.get("step", "unknown")
        message = msg.get("message", "")
        progress = msg.get("progress", 0)
        bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
        print(f"  [{bar}] {progress:3d}% | {step}: {message}")
    
    print()
    
    if result.get("completed"):
        print(f"✓ Analysis COMPLETED (Report: {result.get('report_id')})")
    else:
        print(f"✗ Analysis INCOMPLETE: {result.get('error')}")
    
    risk_factors = result.get("risk_factors", [])
    verification = result.get("verification_results", [])
    
    print(f"\nRisk Factors ({len(risk_factors)} identified):")
    for i, rf in enumerate(risk_factors):
        verified = any(
            v.get("factor_index") == i and v.get("verified", False)
            for v in verification
        )
        status = "✓ verified" if verified else "✗ unverified"
        severity = rf.get("severity", "unknown").upper()
        print(f"\n  [{severity}] {rf.get('factor', 'No description')}")
        print(f"  Status: {status}")
        print(f"  Citation: {rf.get('citation', 'No citation')[:150]}...")
    
    comparison = result.get("comparison")
    if comparison and comparison.get("summary"):
        print(f"\nHistorical Comparison:")
        print(f"  {comparison['summary']}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_analysis.py <TICKER> [10-K|10-Q]")
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    filing_type = sys.argv[2] if len(sys.argv) > 2 else "10-K"
    
    run(ticker, filing_type)