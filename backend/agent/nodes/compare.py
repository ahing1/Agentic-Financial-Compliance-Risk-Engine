"""
Queries PostgreSQL for previous analysis reports and uses the LLM
to compare current vs historical risk factors.
"""

import json
import logging
from pathlib import Path

from openai import OpenAI
from sqlalchemy import select

from agent.state import AgentState
from app.config import settings
from app.db.session import get_session
from app.models.filing import Filing
from app.models.report import AnalysisReport
from app.models.risk_factor import RiskFactor

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=settings.openai_api_key)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "compare.txt"


def compare_with_previous(state: AgentState) -> dict:
    """
    Compare current risk factors against the most recent historical analysis.
    """
    ticker = state.get("ticker", "")
    filing_id = state.get("filing_id", "")
    current_risks = state.get("risk_factors", [])
    
    logger.info(f"Comparing risks for {ticker} against historical data")
    
    if not current_risks:
        return {
            "comparison": {"note": "No current risk factors to compare"},
            "historical_risks": None,
        }
    
    # --- Fetch historical data ---
    historical = _get_previous_analysis(ticker, filing_id)
    
    # --- Handle cold start ---
    if not historical:
        logger.info(f"No historical data for {ticker} — cold start")
        
        existing_messages = state.get("status_messages", [])
        return {
            "historical_risks": None,
            "comparison": {
                "note": f"First analysis for {ticker}. No historical comparison available.",
                "new_risks": [
                    {"factor": rf["factor"], "severity": rf["severity"]}
                    for rf in current_risks
                ],
                "escalated_risks": [],
                "unchanged_risks": [],
                "resolved_risks": [],
                "summary": f"First analysis for {ticker}. All {len(current_risks)} risk factors recorded as baseline.",
            },
            "status_messages": existing_messages + [{
                "step": "comparing",
                "message": f"No previous analysis for {ticker} — first analysis",
                "progress": 70,
            }],
        }
    
    # --- Compare using LLM ---
    comparison = _compare_risks(state, current_risks, historical)
    
    existing_messages = state.get("status_messages", [])
    n_new = len(comparison.get("new_risks", []))
    n_escalated = len(comparison.get("escalated_risks", []))
    n_resolved = len(comparison.get("resolved_risks", []))
    
    return {
        "historical_risks": historical["risk_factors"],
        "comparison": comparison,
        "status_messages": existing_messages + [{
            "step": "comparing",
            "message": f"Compared against previous: {n_new} new, {n_escalated} escalated, {n_resolved} resolved",
            "progress": 70,
        }],
    }


def _get_previous_analysis(ticker: str, current_filing_id: str) -> dict | None:
    """
    Fetch the most recent completed analysis for this company,
    excluding the current filing.
    """
    with get_session() as session:
        result = session.query(
            AnalysisReport,
            Filing,
        ).join(
            Filing,
            AnalysisReport.filing_id == Filing.id,
        ).filter(
            Filing.ticker == ticker.upper(),
            Filing.id != current_filing_id,
            Filing.status == "completed",
        ).order_by(
            Filing.filing_date.desc(),
        ).first()
        
        if not result:
            return None
        
        report, filing = result
        
        risk_factors = session.query(RiskFactor).filter_by(
            report_id=report.id
        ).all()
        
        return {
            "filing_date": str(filing.filing_date),
            "filing_type": filing.filing_type,
            "risk_factors": [
                {
                    "factor": rf.factor,
                    "severity": rf.severity,
                    "citation": rf.citation,
                }
                for rf in risk_factors
            ],
        }


def _compare_risks(state: AgentState, current_risks: list[dict], historical: dict) -> dict:
    """Use the LLM to compare current and historical risk factors."""
    prompt_template = PROMPT_PATH.read_text()
    
    current_text = json.dumps(
        [{"factor": rf["factor"], "severity": rf["severity"]} for rf in current_risks],
        indent=2,
    )
    previous_text = json.dumps(historical["risk_factors"], indent=2)
    
    prompt = prompt_template.format(
        company=state.get("company", state.get("ticker", "Unknown")),
        current_filing_type=state.get("filing_type", "10-K"),
        current_date="current",
        previous_filing_type=historical.get("filing_type", "10-K"),
        previous_date=historical.get("filing_date", "previous"),
        current_risks=current_text,
        previous_risks=previous_text,
    )
    
    try:
        response = openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial compliance analyst. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        
        raw_response = response.choices[0].message.content
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        
        return json.loads(cleaned)
        
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Comparison failed: {e}")
        return {
            "note": f"LLM comparison failed: {str(e)}",
            "new_risks": [],
            "escalated_risks": [],
            "unchanged_risks": [],
            "resolved_risks": [],
            "summary": "Automated comparison unavailable.",
        }