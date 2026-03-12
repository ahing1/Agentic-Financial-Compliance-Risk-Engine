import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    # database
    database_url: str = os.getenv("DATABASE_URL")

    # open ai
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # embedding config
    embedding_dimensions: int = 1536

    # sec edgar
    edgar_user_agent: str = os.getenv("EDGAR_USER_AGENT")
    edgar_rate_limit: float = 0.15

    # agent config
    max_agent_retries: int = 3
    retrieval_top_k: int = 8

    # chunking
    chunk_target_words: int = 600
    chunk_min_words: int = 200
    chunk_max_words: int = 1000

settings = Settings()
