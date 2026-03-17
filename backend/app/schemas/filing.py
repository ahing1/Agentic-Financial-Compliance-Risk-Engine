from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator

# request schema
class AnalyzeRequest(BaseModel):
    # req body for post /filing/analyze
    
    ticker: str = Field(
        ...,
        min_lenght=1,
        max_length=10,
        description="Stock ticker symbol"
    )

    filing_type: str = Field(
        default="10-K",
        description="Filing type: 10-K (annual) or 10-Q (quarterly)"
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v:str) -> str:
        # custom validator that runs after basic field validation

        v = v.upper().strip()
        if not v.isalpha():
            raise ValueError("Ticker must contain only letters")
        return v

    
    @field_validator("filing_type")
    @classmethod
    def validate_filing_type(cls, v: str) -> str:
        allowed = {"10-K", "10-Q"}
        if v not in allowed:
            raise ValueError(f"filing_type must be one of: {allowed}")
        return v
    
# response schemas
class JobResponse(BaseModel):
    job_id: str
    filing_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

class RiskFactorResponse(BaseModel):
    id: str
    factor: str
    severity: str
    citation: str
    source_chunk_id: str | None = None

class ReportResponse(BaseModel):
    report_id: str
    filing_id: str
    ticker: str
    company: str
    filing_type: str
    filing_date: date
    risk_score: float | None = None
    summary: str
    risk_factors: list[RiskFactorResponse]
    created_at: datetime

class FilingHistoryItem(BaseModel):
    filing_id: str
    ticker: str
    company: str
    filing_type: str
    filing_date: date
    status: str
    risk_score: float | None = None
    created_at: datetime


class FilingHistoryResponse(BaseModel):
    filings: list[FilingHistoryItem]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str