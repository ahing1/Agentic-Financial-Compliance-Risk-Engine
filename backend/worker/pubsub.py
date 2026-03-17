import json
import logging
from typing import Generator

import redis

logger = logging.getLogger(__name__)

_redis_client = None

def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True
        )
    return _redis_client

def _channel_name(job_id: str) -> str:
    return f"job:{job_id}:notify"

def _list_name(job_id: str) -> str:
    return f"job:{job_id}:messages"

def publish_update(job_id: str, data: dict) -> None:
    """
    Publish a progress update for a job.

    Appends the message to a Redis list (persistent, ordered) and sends a
    lightweight pub/sub notification to wake up any active subscriber.

    The list is the source of truth. Pub/sub is only a wake-up signal —
    it carries no data. This eliminates the race condition where messages
    published before the subscriber connects are lost.
    """
    r = _get_redis()
    message = json.dumps(data)

    # Append to the persistent message list
    r.rpush(_list_name(job_id), message)

    # Ping any active subscriber to read the new message
    r.publish(_channel_name(job_id), "new")

    # Auto-expire after 1 hour so completed job data doesn't linger
    r.expire(_list_name(job_id), 3600)

    logger.debug(f"Published {data.get('step')} for job {job_id}")


def subscribe(job_id: str) -> Generator[dict, None, None]:
    """
    Subscribe to progress updates for a job.

    Uses the Redis list as the source of truth with a cursor to track
    position. Pub/sub is only used as a wake-up signal (no data).

    Flow:
    1. Subscribe to pub/sub notifications
    2. Read all existing messages from the list (catch up)
    3. On each pub/sub ping, read new messages from the list
    4. Stop when a terminal message (complete/error) is received
    """
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    pubsub = r.pubsub()
    channel = _channel_name(job_id)
    list_key = _list_name(job_id)

    pubsub.subscribe(channel)
    logger.info(f"Subscribed to {channel}")

    cursor = 0  # index of next message to read from the list

    try:
        # Read any messages already in the list (published before we connected)
        for data in _read_new_messages(r, list_key, cursor):
            cursor += 1
            yield data
            if data.get("step") in ("complete", "error"):
                logger.info(f"Job {job_id} already finished (from replay)")
                return

        # Listen for wake-up notifications and read new messages from the list
        for message in pubsub.listen():
            if message["type"] != "message":
                continue

            # Read all new messages that arrived since our last read
            for data in _read_new_messages(r, list_key, cursor):
                cursor += 1
                yield data
                if data.get("step") in ("complete", "error"):
                    logger.info(f"Job {job_id} finished")
                    return
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()
        r.close()
        logger.debug(f"Cleaned up subscription for {job_id}")


def _read_new_messages(r: redis.Redis, list_key: str, cursor: int) -> list[dict]:
    """Read all messages from the list starting at the cursor position."""
    raw_messages = r.lrange(list_key, cursor, -1)
    results = []
    for raw in raw_messages:
        try:
            results.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {list_key}: {raw}")
    return results
