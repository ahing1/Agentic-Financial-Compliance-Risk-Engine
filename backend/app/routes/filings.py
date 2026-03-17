import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.filing import (
    AnalyzeRequest,
    JobResponse,
    JobStatusResponse,
    ReportResponse,
    FilingHistoryResponse,
)
from app.services.filing_service import (
    submit_filing,
    get_job_status,
    get_report,
    get_filing_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix = "/filings", tags=["Filings"])

@router.post("/analyze", response_model=JobResponse)
def analyze_filing(request: AnalyzeRequest):
    try:
        result = submit_filing(request.ticker, request.filing_type)
        return JobResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit filing: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit filing for analysis")

@router.get("/history", response_model = FilingHistoryResponse)
def list_filing_history(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    ticker: str | None = Query(default=None, description="Filter by ticker")
):
    result = get_filing_history(page=page, page_size=page_size, ticker=ticker)
    return FilingHistoryResponse(**result)

@router.get("/{filing_id}/status", response_model=JobStatusResponse)
def get_filing_status(filing_id: str):

    result = get_job_status(filing_id)
    if not result:
        raise HTTPException(status_code = 404, detail="Filing not found")
    return JobStatusResponse(**result)

@router.get("/{filing_id}/report", response_model = ReportResponse)
def get_filing_report(filing_id: str):
    result = get_report(filing_id)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found or analysis not complete")
    return ReportResponse(**result)
    