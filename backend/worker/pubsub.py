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
    return f"job: {job_id}:updates"

#publish a progress update for a job which is called by each celery worker at each agent step
def publish_update(job_id: str, data: dict) -> None: 
    r = _get_redis()
    channel = _channel_name(job_id)
    message = json.dumps(data)

    receivers = r.publish(channel, message) #send message to all current subscribers of this channel
    logger.debug(f"Published to {channel}: {data.get('step')} ({receivers} receivers)")

def subscribe(job_id: str) -> Generator[dict, None, None]:

    r = redis.Redis(host = "localhost", port=6379, db = 0, decode_responses=True)
    pubsub = r.pubsub()
    channel = _channel_name(job_id)

    pubsub.subscribe(channel)
    logger.info(f"Subscribed to {channel}")

    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    yield data

                    if data.get("step") in ("complete", "error"):
                        logger.info(f"Job {job_id} finished, closing subscription")
                        break
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON on {channel}: {message['data']}")
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()
        r.close()
        logger.debug(f"Unsubscribed from {channel}")