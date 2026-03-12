"""
Takes parsed sections and:
1. Splits them into chunks (500-800 words each)
2. Generates embeddings via OpenAI's API
3. Stores chunks + embeddings in pgvector

CHUNKING STRATEGY:
- Split by section first (natural boundaries)
- Within each section, split by paragraphs
- Merge small paragraphs until target size reached
- Split paragraphs that are too large

SKIP-ON-RETRY:
Checks if chunks already exist for this filing before doing any work.
On retry loops, chunks are already in pgvector — no need to re-embed.
"""

import logging
from uuid import uuid4

from openai import OpenAI

from agent.state import AgentState
from app.config import settings
from app.db.session import get_session
from app.models.filing_chunk import FilingChunk

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=settings.openai_api_key)


def chunk_and_embed(state: AgentState) -> dict:
    """
    Split filing into chunks, generate embeddings, store in pgvector.
    Skips if chunks already exist (retry case).
    """
    filing_id = state.get("filing_id")
    logger.info(f"Chunk & embed node for filing {filing_id}")
    
    # --- Skip check: do chunks already exist? ---
    if state.get("chunks_stored", False):
        logger.info("Chunks already stored, skipping")
        return {}
    
    # Also check the database in case of a restart
    with get_session() as session:
        existing_count = session.query(FilingChunk).filter_by(
            filing_id=filing_id
        ).count()
        
        if existing_count > 0:
            logger.info(f"Found {existing_count} existing chunks in DB, skipping")
            existing_messages = state.get("status_messages", [])
            return {
                "chunks_stored": True,
                "chunk_count": existing_count,
                "status_messages": existing_messages + [{
                    "step": "embedding",
                    "message": f"Using {existing_count} existing chunks",
                    "progress": 30,
                }],
            }
    
    # --- Get parsed sections ---
    sections = state.get("sections", {})
    if not sections:
        return {"error": "No parsed sections available", "completed": False}
    
    # --- Chunk the text ---
    chunks = _create_chunks(sections, filing_id)
    
    if not chunks:
        return {"error": "No chunks created from filing", "completed": False}
    
    logger.info(f"Created {len(chunks)} chunks")
    
    # --- Generate embeddings ---
    chunks_with_embeddings = _generate_embeddings(chunks)
    
    # --- Store in database ---
    _store_chunks(chunks_with_embeddings, filing_id)
    
    existing_messages = state.get("status_messages", [])
    progress = {
        "step": "embedding",
        "message": f"Created {len(chunks)} chunks with embeddings",
        "progress": 30,
    }
    
    return {
        "chunks_stored": True,
        "chunk_count": len(chunks),
        "status_messages": existing_messages + [progress],
    }


def _create_chunks(sections: dict[str, str], filing_id: str) -> list[dict]:
    """
    Split sections into chunks of roughly 500-800 words.
    
    Strategy:
    1. For each section, split into paragraphs (double newline)
    2. Accumulate paragraphs until target size reached
    3. If a single paragraph exceeds max, split by sentences
    """
    chunks = []
    chunk_index = 0
    
    for section_name, section_text in sections.items():
        if section_name == "full_text":
            continue
        
        paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
        current_chunk_text = ""
        
        for paragraph in paragraphs:
            paragraph_words = len(paragraph.split())
            current_words = len(current_chunk_text.split()) if current_chunk_text else 0
            
            if current_words + paragraph_words <= settings.chunk_max_words:
                current_chunk_text += ("\n\n" + paragraph) if current_chunk_text else paragraph
            else:
                if current_words >= settings.chunk_min_words:
                    chunks.append({
                        "chunk_text": current_chunk_text.strip(),
                        "chunk_index": chunk_index,
                        "section": section_name,
                    })
                    chunk_index += 1
                    current_chunk_text = paragraph
                elif paragraph_words > settings.chunk_max_words:
                    if current_chunk_text:
                        chunks.append({
                            "chunk_text": current_chunk_text.strip(),
                            "chunk_index": chunk_index,
                            "section": section_name,
                        })
                        chunk_index += 1
                    
                    sentence_chunks = _split_large_text(paragraph, section_name, chunk_index)
                    chunks.extend(sentence_chunks)
                    chunk_index += len(sentence_chunks)
                    current_chunk_text = ""
                else:
                    current_chunk_text += ("\n\n" + paragraph) if current_chunk_text else paragraph
        
        # Don't forget the last chunk in this section
        if current_chunk_text and len(current_chunk_text.split()) >= settings.chunk_min_words:
            chunks.append({
                "chunk_text": current_chunk_text.strip(),
                "chunk_index": chunk_index,
                "section": section_name,
            })
            chunk_index += 1
        elif current_chunk_text and chunks:
            # Too short — append to previous chunk rather than creating an orphan
            chunks[-1]["chunk_text"] += "\n\n" + current_chunk_text.strip()
    
    # Fallback: if no section-based chunks, chunk the full text
    if not chunks and "full_text" in sections:
        logger.warning("No section-based chunks, falling back to full text")
        chunks = _chunk_full_text(sections["full_text"])
    
    return chunks


def _split_large_text(text: str, section: str, start_index: int) -> list[dict]:
    """Split a large text block into chunks by sentences."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    chunk_index = start_index
    
    for sentence in sentences:
        if len((current_chunk + " " + sentence).split()) > settings.chunk_target_words and current_chunk:
            chunks.append({
                "chunk_text": current_chunk.strip(),
                "chunk_index": chunk_index,
                "section": section,
            })
            chunk_index += 1
            current_chunk = sentence
        else:
            current_chunk += (" " + sentence) if current_chunk else sentence
    
    if current_chunk:
        chunks.append({
            "chunk_text": current_chunk.strip(),
            "chunk_index": chunk_index,
            "section": section,
        })
    
    return chunks


def _chunk_full_text(text: str) -> list[dict]:
    """Fallback: chunk full text without section awareness."""
    words = text.split()
    chunks = []
    chunk_index = 0
    
    for i in range(0, len(words), settings.chunk_target_words):
        chunk_text = " ".join(words[i:i + settings.chunk_target_words])
        if len(chunk_text.split()) >= settings.chunk_min_words:
            chunks.append({
                "chunk_text": chunk_text,
                "chunk_index": chunk_index,
                "section": "Unknown",
            })
            chunk_index += 1
    
    return chunks


def _generate_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Generate embeddings via OpenAI's embedding API.
    
    We batch the calls — OpenAI accepts up to 2048 texts per request.
    Batching is faster and cheaper than one at a time.
    """
    logger.info(f"Generating embeddings for {len(chunks)} chunks")
    
    texts = [chunk["chunk_text"] for chunk in chunks]
    
    batch_size = 100
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        logger.debug(f"Embedding batch {i // batch_size + 1} ({len(batch)} chunks)")
        
        response = openai_client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)
    
    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding
    
    logger.info(f"Generated {len(all_embeddings)} embeddings")
    return chunks


def _store_chunks(chunks: list[dict], filing_id: str):
    """
    Store chunks in pgvector. Single transaction — all or nothing.
    """
    logger.info(f"Storing {len(chunks)} chunks for filing {filing_id}")
    
    with get_session() as session:
        for chunk in chunks:
            db_chunk = FilingChunk(
                filing_id=filing_id,
                chunk_text=chunk["chunk_text"],
                chunk_index=chunk["chunk_index"],
                section=chunk.get("section"),
                embedding=chunk["embedding"],
            )
            session.add(db_chunk)
        
        session.commit()
        logger.info(f"Stored {len(chunks)} chunks successfully")