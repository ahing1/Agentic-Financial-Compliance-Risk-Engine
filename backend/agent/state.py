from typing import TypedDict


class AgentState(TypedDict, total=False):
    
    # --- Input fields ---
    filing_id: str
    ticker: str
    raw_html: str
    
    # --- Parse node output ---
    sections: dict[str, str]
    
    # --- Chunk & Embed node output ---
    chunks_stored: bool
    chunk_count: int
    
    # --- Retrieve node output ---
    retrieved_sections: list[dict]
    
    # --- Analyze node output ---
    risk_factors: list[dict]
    
    # --- Compare node output ---
    historical_risks: list[dict] | None
    comparison: dict | None
    
    # --- Verify node output ---
    verification_results: list[dict]
    
    # --- Control flow ---
    retry_count: int
    
    # --- Progress tracking ---
    status_messages: list[dict]
    
    # --- Output fields ---
    report_id: str | None
    completed: bool
    error: str | None