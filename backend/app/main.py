import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler

from app.routes import filings, stream, health, auth
from app.db.session import get_engine, Base
from app.logging_config import setup_logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Compliance Engine API",
    description="Agentic Financial Compliance & Risk Analysis Engine",
    version="0.1.0"
)

is_production = os.getenv("ENVIRONMENT", "development") == "production"
setup_logging(json_format=is_production, level="INFO")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(filings.router)
app.include_router(stream.router)
app.include_router(health.router)
app.include_router(auth.router)


@app.on_event("startup")
def on_startup():
    """
    Run when the API server starts.
    
    Creates database tables if they don't exist. In production,
    you'd use Alembic migrations instead, but this is convenient
    for development — you don't need to run a separate migration
    command every time you restart the server.
    """
    from sqlalchemy import text
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    logger.info("Compliance Engine API started")

@app.get("/")
def root():
    return {
        "name": "Compliance Engine API",
        "version": "0.1.0",
        "docs": "/docs"
    }

