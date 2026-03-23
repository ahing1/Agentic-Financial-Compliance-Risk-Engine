"""
This endpoint streams real-time agent progress updates to the browser.

HOW SSE WORKS IN FASTAPI:
1. Client opens a connection to GET /stream/{job_id}
2. FastAPI returns a StreamingResponse with content_type "text/event-stream"
3. The response function is a generator that yields SSE-formatted strings
4. Each yield sends a message to the client without closing the connection
5. When the generator finishes, the connection closes
"""

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db.session import get_session
from app.models.job import Job
from worker.pubsub import subscribe
from app.services.auth_service import decode_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Streaming"])


@router.get("/stream/{job_id}")
def stream_job_progress(job_id: str, token: str | None=None):

    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify the job exists before opening a long-lived connection
    with get_session() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    # Always use the event generator — it reads from the Redis message list
    # so it works whether the job is pending, in progress, or already done.
    # The subscribe() function replays stored messages first, then listens
    # for new ones, so there's no race condition.
    return StreamingResponse(
        _event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _event_generator(job_id: str):
    """
    Generator that yields SSE-formatted events from Redis pub/sub.
    
    This generator blocks on subscribe(), which waits for new messages.
    Each time a message arrives, it formats it as an SSE event and yields.
    """
    try:
        for update in subscribe(job_id):
            # The double newline signals the end of an event
            event = f"data: {json.dumps(update)}\n\n"
            yield event
            
            # subscribe() already breaks on "complete"/"error",
            # but we also break here for safety
            if update.get("step") in ("complete", "error"):
                break
    except GeneratorExit:
        # Client disconnected (closed browser, navigated away)
        logger.info(f"Client disconnected from SSE stream for job {job_id}")
    except Exception as e:
        # Something went wrong with Redis or the subscription
        logger.error(f"SSE stream error for job {job_id}: {e}")
        error_event = f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"
        yield error_event


