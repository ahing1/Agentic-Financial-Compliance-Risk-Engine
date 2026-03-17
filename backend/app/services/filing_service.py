import logging
from datetime import datetime

from app.db.session import get_session
from app.models.filing import Filing
from app.models.job import Job
from app.models.report import AnalysisReport
from app.models.risk_factor import RiskFactor
from ingestion.edgar_client import fetch_latest_filing
from worker.tasks import analyze_filing

logger = logging.getLogger(__name__)


def submit_filing(ticker: str, filing_type: str = "10-K") -> dict:
    """
    Submit a filing for analysis.
    
    This function:
    1. Fetches the filing from EDGAR
    2. Creates Filing and Job records in PostgreSQL
    3. Enqueues the analysis task in Celery
    4. Returns the job_id immediately
    
    The actual analysis happens asynchronously in the Celery worker.
    """
    logger.info(f"Submitting {ticker} {filing_type} for analysis")
    
    filing_data = fetch_latest_filing(ticker, filing_type)
    
    with get_session() as session:
        filing = Filing(
            company=filing_data["company"],
            ticker=filing_data["ticker"],
            filing_type=filing_data["filing_type"],
            filing_date=datetime.strptime(filing_data["filing_date"], "%Y-%m-%d").date(),
            source_url=filing_data["source_url"],
            raw_text=filing_data["html"],
            status="pending",
        )
        session.add(filing)
        session.flush()
        
        job = Job(
            filing_id=filing.id,
            status="pending",
        )
        session.add(job)
        session.flush()
        
        filing_id = str(filing.id)
        job_id = str(job.id)
        
        session.commit()
    
    #  Enqueue the analysis task
    analyze_filing.delay(job_id, filing_id)
    
    logger.info(f"Enqueued analysis: job={job_id}, filing={filing_id}")
    
    return {
        "job_id": job_id,
        "filing_id": filing_id,
        "status": "pending",
        "message": f"Analysis of {ticker} {filing_type} enqueued",
    }


def get_job_status(filing_id: str) -> dict | None:
    with get_session() as session:
        job = session.query(Job).filter_by(
            filing_id=filing_id
        ).order_by(Job.created_at.desc()).first()
        
        if not job:
            return None
        
        return {
            "job_id": str(job.id),
            "status": job.status,
            "current_step": job.current_step,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error": job.error,
        }


def get_report(filing_id: str) -> dict | None:
    with get_session() as session:
        # Join Filing + AnalysisReport to get everything in one query
        filing = session.query(Filing).filter_by(id=filing_id).first()
        
        if not filing:
            return None
        
        # Get the most recent report for this filing
        report = session.query(AnalysisReport).filter_by(
            filing_id=filing_id
        ).order_by(AnalysisReport.created_at.desc()).first()
        
        if not report:
            return None
        
        # Get all risk factors for this report
        risk_factors = session.query(RiskFactor).filter_by(
            report_id=report.id
        ).all()
        
        return {
            "report_id": str(report.id),
            "filing_id": str(filing.id),
            "ticker": filing.ticker,
            "company": filing.company,
            "filing_type": filing.filing_type,
            "filing_date": filing.filing_date,
            "risk_score": float(report.risk_score) if report.risk_score else None,
            "summary": report.summary,
            "risk_factors": [
                {
                    "id": str(rf.id),
                    "factor": rf.factor,
                    "severity": rf.severity,
                    "citation": rf.citation,
                    "source_chunk_id": str(rf.source_chunk_id) if rf.source_chunk_id else None,
                }
                for rf in risk_factors
            ],
            "created_at": report.created_at,
        }


def get_filing_history(
    page: int = 1,
    page_size: int = 20,
    ticker: str | None = None,
) -> dict:
    with get_session() as session:
        query = session.query(Filing).filter(
            Filing.status.in_(["completed", "needs_review"])
        )
        
        if ticker:
            query = query.filter(Filing.ticker == ticker.upper())
        
        total = query.count()
        
        offset = (page - 1) * page_size
        filings = query.order_by(
            Filing.created_at.desc()
        ).offset(offset).limit(page_size).all()
        
        # Build response with risk scores from reports
        items = []
        for filing in filings:
            # Get the latest report's risk score
            report = session.query(AnalysisReport).filter_by(
                filing_id=filing.id
            ).order_by(AnalysisReport.created_at.desc()).first()
            
            items.append({
                "filing_id": str(filing.id),
                "ticker": filing.ticker,
                "company": filing.company,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date,
                "status": filing.status,
                "risk_score": float(report.risk_score) if report and report.risk_score else None,
                "created_at": filing.created_at,
            })
        
        return {
            "filings": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }