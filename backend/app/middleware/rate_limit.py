import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _get_client_identifier(request: Request) -> str:
    """
    Identify the client for rate limiting purposes.
    
    We use the client's IP address as the identifier.
    In production behind a load balancer, you'd read the
    X-Forwarded-For header instead (the real client IP).
    """
    # Check for forwarded IP (behind nginx/CloudFront)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The first one is the real client
        return forwarded.split(",")[0].strip()
    
    return get_remote_address(request)


# Create the limiter instance.
# key_func determines how clients are identified.
# default_limits sets the rate for endpoints that don't specify their own.
limiter = Limiter(
    key_func=_get_client_identifier,
    default_limits=["100/minute"],
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom response when rate limit is exceeded.
    """
    logger.warning(f"Rate limit exceeded for {_get_client_identifier(request)}: {exc.detail}")
    
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "limit": str(exc.detail),
        },
        headers={
            "Retry-After": "60",
        },
    )