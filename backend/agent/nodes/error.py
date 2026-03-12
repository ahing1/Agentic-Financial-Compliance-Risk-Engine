"""
Runs when max retries are exceeded or an unrecoverable error occurs.
Saves partial results and flags the job for human review.
"""

import logging
from datetime import datetime

from agent.state import AgentState
from app.db.session import get_session
from app.models.filing import Filing
from app.models.job import Job

logger = logging.getLogger(__name__)


def handle_error(state: AgentState) -> dict:
    """Handle analysis failure — flag for human review."""
    filing_id = state.get("filing_id")
    error = state.get("error", "Max retries exceeded for citation verification")
    retry_count = state.get("retry_count", 0)
    
    logger.warning(f"Error handler for filing {filing_id}: {error} ({retry_count} retries)")
    
    with get_session() as session:
        job = session.query(Job).filter_by(
            filing_id=filing_id
        ).order_by(Job.created_at.desc()).first()
        
        if job:
            job.status = "needs_review"
            job.completed_at = datetime.utcnow()
            job.error = error
        
        filing = session.query(Filing).filter_by(id=filing_id).first()
        if filing:
            filing.status = "needs_review"
        
        session.commit()
    
    existing_messages = state.get("status_messages", [])
    
    return {
        "completed": False,
        "error": error,
        "status_messages": existing_messages + [{
            "step": "error",
            "message": f"Flagged for human review: {error}",
            "progress": 100,
        }],
    }