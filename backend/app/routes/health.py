"""
A simple endpoint that checks connectivity to dependencies.
Used by:
- Cloud providers (to restart the service if it's unhealthy)
- Monitoring (to alert you if something's down)
- Demos (to show the system monitors itself)
"""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import get_session
from app.schemas.filing import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Check system health — database and Redis connectivity.
    
    Returns 200 if all systems are operational.
    Returns 503 if any dependency is unreachable.
    """
    db_status = _check_database()
    redis_status = _check_redis()
    
    overall = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"
    
    # Return 503 if anything is down so load balancers know to reroute
    from fastapi.responses import JSONResponse
    status_code = 200 if overall == "healthy" else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "database": db_status,
            "redis": redis_status,
        },
    )


def _check_database() -> str:
    """Verify PostgreSQL is reachable with a simple query."""
    try:
        with get_session() as session:
            # SELECT 1 is the lightest possible query.
            # If this fails, the database is unreachable.
            session.execute(text("SELECT 1"))
            return "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return f"error: {str(e)}"


def _check_redis() -> str:
    """Verify Redis is reachable with a PING command."""
    try:
        import os
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url)
        r.ping()  # Redis PING returns True if connected
        r.close()
        return "connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return f"error: {str(e)}"