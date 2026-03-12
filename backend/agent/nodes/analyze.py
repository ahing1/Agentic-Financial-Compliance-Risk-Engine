"""
Sends retrieved chunks to the LLM to extract structured risk factors.

OUTPUT MATCHING:
Each risk factor gets matched to its most likely source chunk via
word overlap scoring. This creates the source_chunk_id traceability link.
"""

import json
import logging
from pathlib import Path

from openai import OpenAI

from agent.state import AgentState
from app.config import settings
from app.db.session import get_session
from app.models.filing_chunk import FilingChunk

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=settings.openai_api_key)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze.txt"


def analyze_risk_factors(state: AgentState) -> dict:
    """
    Use LLM to extract structured risk factors from retrieved sections.
    """
    filing_id = state.get("filing_id")
    ticker = state.get("ticker", "Unknown")
    retrieved = state.get("retrieved_sections", [])
    
    logger.info(f"Analyzing risk factors for {ticker} ({len(retrieved)} sections)")
    
    if not retrieved:
        return {"error": "No retrieved sections to analyze", "completed": False}
    
    # --- Build sections text for the prompt ---
    sections_text = ""
    for chunk in retrieved:
        sections_text += f"\n--- Section: {chunk.get('section', 'Unknown')} "
        sections_text += f"(Chunk {chunk.get('chunk_index', '?')}) ---\n"
        sections_text += chunk.get("text", "") + "\n"
    
    # --- Load and fill prompt template ---
    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.format(
        filing_type=state.get("filing_type", "10-K"),
        company=state.get("company", ticker),
        ticker=ticker,
        sections_text=sections_text,
    )
    
    # --- Call the LLM ---
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
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return {"error": f"LLM analysis failed: {str(e)}", "completed": False}
    
    # --- Parse LLM response ---
    risk_factors = _parse_llm_response(raw_response)
    
    if not risk_factors:
        existing_messages = state.get("status_messages", [])
        return {
            "risk_factors": [],
            "status_messages": existing_messages + [{
                "step": "analyzing",
                "message": "No risk factors identified",
                "progress": 55,
            }],
        }
    
    # --- Match citations to source chunks ---
    risk_factors = _match_citations_to_chunks(risk_factors, retrieved, filing_id)
    
    logger.info(f"Identified {len(risk_factors)} risk factors")
    
    severity_counts = {}
    for rf in risk_factors:
        sev = rf.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    severity_summary = ", ".join(f"{v} {k}" for k, v in severity_counts.items())
    
    existing_messages = state.get("status_messages", [])
    progress = {
        "step": "analyzing",
        "message": f"Identified {len(risk_factors)} risk factors ({severity_summary})",
        "progress": 55,
    }
    
    return {
        "risk_factors": risk_factors,
        "status_messages": existing_messages + [progress],
    }


def _parse_llm_response(raw_response: str) -> list[dict]:
    """
    Parse the LLM's JSON response. Handles markdown fences and validation.
    """
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])
    
    try:
        parsed = json.loads(cleaned)
        
        # Handle case where LLM wraps array in an object
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(value, list):
                    parsed = value
                    break
        
        if not isinstance(parsed, list):
            logger.error(f"Expected list from LLM, got {type(parsed)}")
            return []
        
        # Validate required fields
        validated = []
        for rf in parsed:
            if isinstance(rf, dict) and "factor" in rf and "severity" in rf:
                rf["severity"] = rf.get("severity", "medium").lower()
                if rf["severity"] not in ("high", "medium", "low"):
                    rf["severity"] = "medium"
                validated.append(rf)
        
        return validated
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return []


def _match_citations_to_chunks(
    risk_factors: list[dict],
    retrieved_chunks: list[dict],
    filing_id: str,
) -> list[dict]:
    """
    Match each citation to its most likely source chunk via word overlap.
    
    Uses simple text matching rather than another embedding call
    to save API costs.
    """
    for rf in risk_factors:
        citation = rf.get("citation", "")
        best_match_id = None
        best_match_score = 0
        
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "").lower()
            citation_words = set(citation.lower().split())
            chunk_words = set(chunk_text.split())
            overlap = len(citation_words & chunk_words)
            score = overlap / max(len(citation_words), 1)
            
            if score > best_match_score:
                best_match_score = score
                best_match_id = chunk.get("chunk_id")
        
        rf["source_chunk_id"] = best_match_id
        rf["match_confidence"] = best_match_score
        
        if best_match_score < 0.3:
            logger.warning(
                f"Low citation match ({best_match_score:.2f}): {rf['factor'][:80]}..."
            )
    
    return risk_factors