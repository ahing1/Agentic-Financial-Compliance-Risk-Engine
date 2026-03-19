"""
tests/test_schemas.py — Pydantic Schema Validation Tests

Tests that your request schemas correctly validate input and reject
bad data. These tests are important because schemas are your first
line of defense — they reject malformed requests before your code runs.

These are pure unit tests — no database, no network, no fixtures needed.
"""

import pytest
from pydantic import ValidationError
from app.schemas.filing import AnalyzeRequest


class TestAnalyzeRequest:
    
    def test_valid_request(self):
        """Accepts a valid ticker and filing type."""
        req = AnalyzeRequest(ticker="AAPL", filing_type="10-K")
        assert req.ticker == "AAPL"
        assert req.filing_type == "10-K"
    
    def test_ticker_uppercased(self):
        """Automatically uppercases the ticker."""
        req = AnalyzeRequest(ticker="aapl")
        assert req.ticker == "AAPL"
    
    def test_ticker_stripped(self):
        """Strips whitespace from ticker."""
        req = AnalyzeRequest(ticker="  AAPL  ")
        assert req.ticker == "AAPL"
    
    def test_default_filing_type(self):
        """Defaults to 10-K when filing_type not specified."""
        req = AnalyzeRequest(ticker="AAPL")
        assert req.filing_type == "10-K"
    
    def test_10q_accepted(self):
        """Accepts 10-Q as a valid filing type."""
        req = AnalyzeRequest(ticker="AAPL", filing_type="10-Q")
        assert req.filing_type == "10-Q"
    
    def test_empty_ticker_rejected(self):
        """Rejects empty ticker."""
        with pytest.raises(ValidationError):
            AnalyzeRequest(ticker="")
    
    def test_numeric_ticker_rejected(self):
        """Rejects tickers with numbers."""
        with pytest.raises(ValidationError):
            AnalyzeRequest(ticker="ABC123")
    
    def test_invalid_filing_type_rejected(self):
        """Rejects filing types other than 10-K and 10-Q."""
        with pytest.raises(ValidationError):
            AnalyzeRequest(ticker="AAPL", filing_type="8-K")
    
    def test_very_long_ticker_rejected(self):
        """Rejects tickers longer than 10 characters."""
        with pytest.raises(ValidationError):
            AnalyzeRequest(ticker="A" * 11)