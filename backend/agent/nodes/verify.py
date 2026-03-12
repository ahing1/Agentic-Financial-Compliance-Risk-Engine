"""
For each risk factor:
1. Fetches the source chunk from the database
2. Asks the LLM: "Does this text actually support this claim?"
3. Records pass/fail

EACH CITATION IS VERIFIED SEPARATELY:
One LLM call per risk factor. Batch verification risks the LLM
rubber-stamping everything. Individual verification is more reliable.
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

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "verify.txt"


def verify_citations(state: AgentState) -> dict:
    """Verify each risk factor's citation against its source chunk."""
    risk_factors = state.get("risk_factors", [])
    
    logger.info(f"Verifying {len(risk_factors)} citations")
    
    if not risk_factors:
        return {"verification_results": []}
    
    prompt_template = PROMPT_PATH.read_text()
    
    results = []
    verified_count = 0
    
    for i, rf in enumerate(risk_factors):
        source_chunk_id = rf.get("source_chunk_id")
        
        # --- Fetch source chunk ---
        source_text = _get_chunk_text(source_chunk_id)
        
        if not source_text:
            logger.warning(f"Source chunk {source_chunk_id} not found for factor {i}")
            results.append({
                "factor_index": i,
                "verified": False,
                "explanation": "Source chunk not found in database",
            })
            continue
        
        # --- Verify with LLM ---
        verification = _verify_single_citation(
            prompt_template=prompt_template,
            risk_factor=rf.get("factor", ""),
            citation=rf.get("citation", ""),
            source_text=source_text,
        )
        
        verification["factor_index"] = i
        results.append(verification)
        
        if verification["verified"]:
            verified_count += 1
    
    failed_count = len(results) - verified_count
    existing_messages = state.get("status_messages", [])
    progress = {
        "step": "verifying",
        "message": f"{verified_count}/{len(results)} citations verified"
            + (f", {failed_count} need retry" if failed_count > 0 else ""),
        "progress": 82,
    }
    
    return {
        "verification_results": results,
        "status_messages": existing_messages + [progress],
    }


def _get_chunk_text(chunk_id: str | None) -> str | None:
    """Fetch a chunk's text from the database."""
    if not chunk_id:
        return None
    
    with get_session() as session:
        chunk = session.query(FilingChunk).filter_by(id=chunk_id).first()
        return chunk.chunk_text if chunk else None


def _verify_single_citation(
    prompt_template: str,
    risk_factor: str,
    citation: str,
    source_text: str,
) -> dict:
    """Ask the LLM to verify one citation against its source text."""
    prompt = prompt_template.format(
        risk_factor=risk_factor,
        citation=citation,
        source_text=source_text,
    )
    
    try:
        response = openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a fact-checker. Be strict. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])
        
        result = json.loads(raw)
        
        return {
            "verified": bool(result.get("verified", False)),
            "explanation": result.get("explanation", "No explanation provided"),
        }
        
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Verification failed: {e}")
        return {
            "verified": False,
            "explanation": f"Verification error: {str(e)}",
        }