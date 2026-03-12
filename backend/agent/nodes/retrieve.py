"""
HOW VECTOR SIMILARITY SEARCH WORKS:
1. Take a search query ("What are the main financial risks?")
2. Convert it to an embedding (same model that embedded the chunks)
3. Ask pgvector to find chunks whose embeddings are closest to the query
4. pgvector uses cosine distance: similar directions = similar meaning
5. Return the top-k most similar chunks

ON RETRY:
Instead of broad queries, uses targeted queries based on which
citations failed verification. The agent refines its search strategy.
"""

import logging

from openai import OpenAI
from sqlalchemy import select

from agent.state import AgentState
from app.config import settings
from app.db.session import get_session
from app.models.filing_chunk import FilingChunk

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=settings.openai_api_key)

# Default search queries for the first pass
DEFAULT_QUERIES = [
    "What are the main financial risks and risk factors?",
    "What are the key operational and business risks?",
    "What market risks and competitive threats does the company face?",
    "What regulatory and legal risks are disclosed?",
]


def retrieve_sections(state: AgentState) -> dict:
    """
    Search pgvector for chunks most relevant to risk analysis.
    """
    filing_id = state.get("filing_id")
    retry_count = state.get("retry_count", 0)
    
    logger.info(f"Retrieving sections for filing {filing_id} (retry: {retry_count})")
    
    # --- Build search queries ---
    if retry_count > 0:
        queries = _build_retry_queries(state)
        logger.info(f"Retry #{retry_count}: using {len(queries)} targeted queries")
    else:
        queries = DEFAULT_QUERIES
    
    # --- Execute similarity search ---
    all_retrieved = []
    seen_chunk_ids = set()
    
    for query in queries:
        results = _similarity_search(filing_id, query, top_k=settings.retrieval_top_k)
        
        for result in results:
            if result["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(result["chunk_id"])
                all_retrieved.append(result)
    
    # Sort by relevance (lower distance = more relevant)
    all_retrieved.sort(key=lambda x: x["score"])
    
    logger.info(f"Retrieved {len(all_retrieved)} unique chunks")
    
    existing_messages = state.get("status_messages", [])
    progress = {
        "step": "retrieval",
        "message": f"Retrieved {len(all_retrieved)} relevant sections"
            + (f" (retry #{retry_count})" if retry_count > 0 else ""),
        "progress": 45 if retry_count == 0 else 45 + (retry_count * 5),
    }
    
    return {
        "retrieved_sections": all_retrieved,
        "status_messages": existing_messages + [progress],
    }


def _similarity_search(filing_id: str, query: str, top_k: int = 8) -> list[dict]:
    """
    Execute a vector similarity search in pgvector.
    
    The <=> operator computes cosine distance:
    - 0.0 = identical vectors (maximum similarity)
    - 1.0 = perpendicular vectors (no similarity)
    - 2.0 = opposite vectors
    
    We ORDER BY ascending (smallest distance = most similar).
    """
    # Embed the query
    response = openai_client.embeddings.create(
        model=settings.embedding_model,
        input=query,
    )
    query_embedding = response.data[0].embedding
    
    # Search pgvector
    with get_session() as session:
        results = session.query(
            FilingChunk.id,
            FilingChunk.chunk_text,
            FilingChunk.section,
            FilingChunk.chunk_index,
            FilingChunk.embedding.cosine_distance(query_embedding).label("distance"),
        ).filter(
            FilingChunk.filing_id == filing_id
        ).order_by(
            "distance"
        ).limit(
            top_k
        ).all()
    
    return [
        {
            "chunk_id": str(row.id),
            "text": row.chunk_text,
            "section": row.section,
            "chunk_index": row.chunk_index,
            "score": float(row.distance),
        }
        for row in results
    ]


def _build_retry_queries(state: AgentState) -> list[str]:
    """
    Build targeted queries from failed verification results.
    
    Instead of repeating broad queries, search for specific context
    related to the citations that failed.
    """
    verification_results = state.get("verification_results", [])
    risk_factors = state.get("risk_factors", [])
    
    queries = []
    for result in verification_results:
        if not result.get("verified", True):
            factor_idx = result.get("factor_index", 0)
            if factor_idx < len(risk_factors):
                factor = risk_factors[factor_idx]
                queries.append(f"Evidence for: {factor.get('factor', '')}")
                queries.append(f"{factor.get('citation', '')[:200]}")
    
    if not queries:
        queries = DEFAULT_QUERIES
    
    return queries[:6]  # Cap at 6 to control API costs