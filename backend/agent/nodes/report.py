"""
Final success node. Filters to verified-only risk factors, calculates
a risk score, and persists everything to PostgreSQL in one transaction.
"""

import logging
from datetime import datetime

from agent.state import AgentState
from app.db.session import get_session
from app.models.filing import Filing
from app.models.job import Job
from app.models.report import AnalysisReport
from app.models.risk_factor import RiskFactor

logger = logging.getLogger(__name__)


def generate_report(state: AgentState) -> dict:
    """Save the final analysis to PostgreSQL."""
    filing_id = state.get("filing_id")
    risk_factors = state.get("risk_factors", [])
    verification_results = state.get("verification_results", [])
    comparison = state.get("comparison")
    
    # --- Filter to verified only ---
    verified_indices = {
        r["factor_index"] for r in verification_results if r.get("verified", False)
    }
    verified_risks = [
        rf for i, rf in enumerate(risk_factors) if i in verified_indices
    ]
    
    logger.info(f"{len(verified_risks)}/{len(risk_factors)} passed verification")
    
    # --- Calculate score and build summary ---
    risk_score = _calculate_risk_score(verified_risks)
    summary = _build_summary(verified_risks, comparison, state.get("ticker", "Unknown"))
    
    # --- Save to database ---
    report_id = _save_to_database(
        filing_id=filing_id,
        risk_score=risk_score,
        summary=summary,
        verified_risks=verified_risks,
    )
    
    existing_messages = state.get("status_messages", [])
    
    return {
        "report_id": str(report_id),
        "completed": True,
        "error": None,
        "status_messages": existing_messages + [{
            "step": "complete",
            "message": f"Report generated: {len(verified_risks)} risks (score: {risk_score}/10)",
            "progress": 100,
        }],
    }


def _calculate_risk_score(risk_factors: list[dict]) -> float:
    """
    Score: high=3pts, medium=2pts, low=1pt, normalized to 0-10.
    """
    severity_weights = {"high": 3, "medium": 2, "low": 1}
    total = sum(severity_weights.get(rf.get("severity", "low"), 1) for rf in risk_factors)
    return min(10.0, round((total / 30) * 10, 1))


def _build_summary(risk_factors: list[dict], comparison: dict | None, ticker: str) -> str:
    severity_counts = {}
    for rf in risk_factors:
        sev = rf.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    parts = [
        f"Analysis of {ticker}: {len(risk_factors)} verified risk factors — "
        f"{severity_counts.get('high', 0)} high, "
        f"{severity_counts.get('medium', 0)} medium, "
        f"{severity_counts.get('low', 0)} low."
    ]
    
    if comparison and comparison.get("summary"):
        parts.append(comparison["summary"])
    
    return " ".join(parts)


def _save_to_database(filing_id, risk_score, summary, verified_risks) -> str:
    """Persist report + risk factors in one transaction."""
    with get_session() as session:
        report = AnalysisReport(
            filing_id=filing_id,
            risk_score=risk_score,
            summary=summary,
        )
        session.add(report)
        session.flush()  # Get generated ID without committing
        
        for rf in verified_risks:
            risk_factor = RiskFactor(
                report_id=report.id,
                factor=rf.get("factor", ""),
                severity=rf.get("severity", "medium"),
                citation=rf.get("citation", ""),
                source_chunk_id=rf.get("source_chunk_id"),
            )
            session.add(risk_factor)
        
        # Update filing and job status
        filing = session.query(Filing).filter_by(id=filing_id).first()
        if filing:
            filing.status = "completed"
        
        job = session.query(Job).filter_by(
            filing_id=filing_id
        ).order_by(Job.created_at.desc()).first()
        if job:
            job.status = "completed"
            job.completed_at = datetime.utcnow()
        
        session.commit()
        return str(report.id)