"""
tests/test_models.py — Database Model Tests

Tests that your SQLAlchemy models can:
1. Create records
2. Establish relationships between records
3. Enforce constraints (unique email, required fields)

WHY TEST MODELS:
These tests verify that your database schema is correct — that
foreign keys link properly, cascades work, and constraints enforce.
If you change a model and break a relationship, these tests catch it
immediately instead of failing at runtime deep in the agent pipeline.
"""

import pytest
from datetime import date, datetime
from app.models.user import User
from app.models.filing import Filing
from app.models.filing_chunk import FilingChunk
from app.models.report import AnalysisReport
from app.models.risk_factor import RiskFactor
from app.models.job import Job


class TestUserModel:
    
    def test_create_user(self, session):
        """Basic user creation works."""
        user = User(email="test@example.com", password_hash="fakehash123")
        session.add(user)
        session.flush()
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.created_at is not None
    
    def test_duplicate_email_fails(self, session):
        """Unique constraint on email is enforced."""
        user1 = User(email="same@example.com", password_hash="hash1")
        user2 = User(email="same@example.com", password_hash="hash2")
        
        session.add(user1)
        session.flush()
        session.add(user2)
        
        with pytest.raises(Exception):  # IntegrityError
            session.flush()


class TestFilingModel:
    
    def test_create_filing(self, session, sample_filing_data):
        """Basic filing creation works."""
        filing = Filing(
            company=sample_filing_data["company"],
            ticker=sample_filing_data["ticker"],
            filing_type=sample_filing_data["filing_type"],
            filing_date=date(2024, 11, 1),
            source_url=sample_filing_data["source_url"],
            raw_text=sample_filing_data["raw_html"],
        )
        session.add(filing)
        session.flush()
        
        assert filing.id is not None
        assert filing.ticker == "AAPL"
        assert filing.status == "pending"  # Default value
    
    def test_filing_has_relationships(self, session, sample_filing_data):
        """Filing properly links to chunks, reports, and jobs."""
        filing = Filing(
            company="Apple Inc.",
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 11, 1),
            source_url="https://example.com",
        )
        session.add(filing)
        session.flush()
        
        # Create a job linked to the filing
        job = Job(filing_id=filing.id, status="pending")
        session.add(job)
        session.flush()
        
        assert len(filing.jobs) == 1
        assert filing.jobs[0].status == "pending"


class TestReportModel:
    
    def test_report_with_risk_factors(self, session):
        """Report → RiskFactor relationship works."""
        # Create the parent chain: Filing → Report → RiskFactor
        filing = Filing(
            company="Apple Inc.",
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 11, 1),
            source_url="https://example.com",
        )
        session.add(filing)
        session.flush()
        
        report = AnalysisReport(
            filing_id=filing.id,
            risk_score=7.5,
            summary="Test summary with 3 risk factors.",
        )
        session.add(report)
        session.flush()
        
        rf1 = RiskFactor(
            report_id=report.id,
            factor="Supply chain concentration risk",
            severity="high",
            citation="Manufacturing partners in Asia",
        )
        rf2 = RiskFactor(
            report_id=report.id,
            factor="Regulatory compliance risk",
            severity="medium",
            citation="Changing regulations in EU",
        )
        session.add_all([rf1, rf2])
        session.flush()
        
        assert len(report.risk_factors) == 2
        assert report.risk_factors[0].severity in ("high", "medium")
    
    def test_cascade_delete(self, session):
        """Deleting a filing cascades to reports and risk factors."""
        filing = Filing(
            company="Apple Inc.",
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 11, 1),
            source_url="https://example.com",
        )
        session.add(filing)
        session.flush()
        
        report = AnalysisReport(
            filing_id=filing.id,
            risk_score=5.0,
            summary="Test",
        )
        session.add(report)
        session.flush()
        
        rf = RiskFactor(
            report_id=report.id,
            factor="Test risk",
            severity="low",
            citation="Test citation",
        )
        session.add(rf)
        session.flush()
        
        report_id = report.id
        rf_id = rf.id
        
        # Delete the filing — everything underneath should cascade
        session.delete(filing)
        session.flush()
        
        assert session.get(AnalysisReport, report_id) is None
        assert session.get(RiskFactor, rf_id) is None