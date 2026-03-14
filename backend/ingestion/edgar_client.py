import time
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Company tickers file — maps ticker symbols to CIK numbers
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Submissions endpoint — returns all filings for a given company
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# Archives base — where actual filing documents are stored
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

def _get_http_client():
    return httpx.Client(
        headers={
            "User-Agent": settings.edgar_user_agent,
            "Accept": "application/json, text/html"
        },
        timeout=30.0,
        follow_redirects=True
    )

def _rate_limit():
    time.sleep(settings.edgar_rate_limit)

def get_cik_from_ticker(ticker: str) -> str:
    ticker = ticker.upper().strip()
    logger.info(f"Looking up CIK for ticker: {ticker}")

    with _get_http_client() as client:
        _rate_limit()
        response = client.get(TICKERS_URL)
        response.raise_for_status()

        data = response.json()
    
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker:
            cik = str(entry["cik_str"]).zfill(10)
            logger.info(f"Found CIK {cik} for ticker {ticker} ({entry.get('title', 'Unknown')})")
            return cik
    
    raise ValueError(f"Ticker '{ticker} not found in Edgar")

def get_company_name(ticker: str) -> str:
    ticker = ticker.upper().strip()

    with _get_http_client() as client:
        _rate_limit()
        response = client.get(TICKERS_URL)
        response.raise_for_status()
        data = response.json()
    
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker:
            return entry.get("title", ticker)
    
    return ticker


def get_recent_filings(cik: str, filing_type: str = "10-K", count: int = 5) -> list[dict]:
    logger.info(f"Fetching recent {filing_type} filings for CIK {cik}")

    with _get_http_client() as client:
        _rate_limit()
        url = SUBMISSIONS_URL.format(cik=cik)
        response = client.get(url)
        response.raise_for_status()

        data = response.json()

        recent = data.get("filings", {}).get("recent", {})

        if not recent:
            recent = data.get("recent", {})
        
        forms = recent.get("form", {})
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_documents = recent.get("primaryDocument", [])

        # filter for requested filing type
        results = []
        for i, form in enumerate(forms):
            if form == filing_type and i < len(accession_numbers):
                results.append({
                    "accession_number": accession_numbers[i],
                    "filing_date": filing_dates[i],
                    "primary_document": primary_documents[i] if i < len(primary_documents) else None
                })
                if len(results) >= count:
                    break
        
        logger.info(f"Found {len(results)} {filing_type} filings for CIK {cik}")
        return results

def build_filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_stripped = cik.lstrip("0") or "0"
    accession_no_dashes = accession_number.replace("-", "")

    url = f"{ARCHIVES_BASE}/{cik_stripped}/{accession_no_dashes}/{primary_document}"
    logger.info(f"Built filing url: {url}")
    return url

def fetch_filing_html(url: str) -> str:
    logger.info(f"Fetching filing from: {url}")
    
    with _get_http_client() as client:
        _rate_limit()
        response = client.get(url)
        response.raise_for_status()
        
        html = response.text
        logger.info(f"Fetched filing: {len(html)} characters")
        return html


def fetch_latest_filing(ticker: str, filing_type: str = "10-K") -> dict:
    # Step 1: Ticker → CIK
    cik = get_cik_from_ticker(ticker)
    company = get_company_name(ticker)
    
    # Step 2: CIK → Filing metadata
    filings = get_recent_filings(cik, filing_type, count=1)
    if not filings:
        raise ValueError(f"No {filing_type} filings found for {ticker} (CIK: {cik})")
    
    latest = filings[0]
    
    # Step 3: Metadata → URL
    if not latest.get("primary_document"):
        raise ValueError(f"Filing found but no primary document available: {latest}")
    
    url = build_filing_url(cik, latest["accession_number"], latest["primary_document"])
    
    # Step 4: URL → HTML
    html = fetch_filing_html(url)
    
    return {
        "ticker": ticker.upper(),
        "company": company,
        "cik": cik,
        "filing_type": filing_type,
        "filing_date": latest["filing_date"],
        "accession_number": latest["accession_number"],
        "source_url": url,
        "html": html,
    }