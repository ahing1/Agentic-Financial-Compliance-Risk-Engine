import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import filings, stream, health
from app.db.session import get_engine, Base

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


@app.on_event("startup")
def on_startup():
    """
    Run when the API server starts.
    
    Creates database tables if they don't exist. In production,
    you'd use Alembic migrations instead, but this is convenient
    for development — you don't need to run a separate migration
    command every time you restart the server.
    """
    import app.models
    Base.metadata.create_all(bind=get_engine())
    logger.info("Database tables created/verified")
    logger.info("Compliance Engine API started")

@app.get("/")
def root():
    return {
        "name": "Compliance Engine API",
        "version": "0.1.0",
        "docs": "/docs"
    }

