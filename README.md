# Agentic Financial Compliance & Risk Engine

An autonomous AI system that ingests SEC financial filings, performs multi-step risk analysis using LangGraph agents, self-verifies every citation against source text, and surfaces findings through a real-time dashboard.

**Live Demo:** [https://d3d55r1njvlev5.cloudfront.net](https://d3d55r1njvlev5.cloudfront.net)
**API Documentation:** [https://djq256xqndc7i.cloudfront.net/docs](https://djq256xqndc7i.cloudfront.net/docs)

---

## What It Does

A compliance analyst spends hours reading 200-page SEC filings to identify risk factors. This system does it autonomously in under 60 seconds.

The workflow: submit a company ticker → the system fetches the latest filing from SEC EDGAR → an AI agent parses, chunks, and embeds the document → retrieves relevant sections via vector similarity search → extracts and categorizes risk factors with severity ratings → compares against previous analyses of the same company → self-verifies every citation against source text (retrying with refined queries up to 3 times if verification fails) → generates a structured risk report with traceable citations.

Users watch the agent work in real-time through Server-Sent Events streaming each step as it executes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND                                                             │
│                                                                       │
│  Next.js (TypeScript) → S3 → CloudFront CDN (HTTPS)                │
│  Real-time agent feed via SSE, risk report viewer, filing history    │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ REST API + SSE
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ API LAYER                                                            │
│                                                                       │
│  CloudFront (HTTPS) → nginx → FastAPI                               │
│  JWT auth, rate limiting, request validation                         │
│                                                                       │
│  FastAPI ──→ Celery + Redis (async job queue)                       │
│                     │                                                 │
│                     ▼                                                 │
│              Agent Worker (LangGraph)                                │
│              Publishes progress → Redis pub/sub → SSE → Frontend    │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────────┐
│ INTELLIGENCE LAYER (LangGraph Agent)                                  │
│                                                                       │
│  Parse → Chunk & Embed → Retrieve → Analyze → Compare → Verify     │
│                ▲                                            │         │
│                └──── retry with refined queries (max 3) ────┘         │
│                                                                       │
│  ✓ verified → Generate Report                                        │
│  ✗ max retries → Flag for Human Review                               │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────────┐
│ DATA LAYER                                                            │
│                                                                       │
│  RDS PostgreSQL + pgvector    │    ElastiCache Redis                 │
│  • Filing metadata            │    • Celery job queue                │
│  • Analysis reports           │    • Pub/sub progress updates        │
│  • Risk factors with citations│                                      │
│  • Vector embeddings (RAG)    │    SEC EDGAR API (external)          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js, TypeScript | Dashboard with real-time agent visualization |
| CDN | AWS CloudFront + S3 | Static hosting, HTTPS, global edge caching |
| API | FastAPI (Python) | REST endpoints, SSE streaming, request validation |
| Auth | JWT + bcrypt | Stateless authentication, secure password hashing |
| Task Queue | Celery + Redis | Async job processing, decouples API from agent |
| Real-time | Redis pub/sub + SSE | Progress updates from worker to browser |
| AI Agent | LangGraph | Stateful agent with branching, looping, and self-correction |
| LLM | OpenAI GPT-4o | Risk analysis, comparison, citation verification |
| Embeddings | OpenAI text-embedding-3-small | Document chunk embeddings for RAG |
| Vector Search | pgvector (PostgreSQL extension) | Cosine similarity search for retrieval |
| Database | AWS RDS (PostgreSQL 16) | Relational data storage with vector extension |
| Cache | AWS ElastiCache (Redis) | Job queue broker and pub/sub message bus |
| Compute | AWS EC2 (t3.micro) | Docker containers with nginx reverse proxy |
| Containers | Docker + Docker Compose | Reproducible builds, consistent environments |
| CI/CD | GitHub Actions | Automated lint, test, and deploy on push to main |
| Reverse Proxy | nginx | Request routing, SSE buffering disabled, CORS |
| Rate Limiting | slowapi | API abuse prevention, cost control |

---

## Key Technical Decisions

### Celery + Redis over Apache Kafka

The system needs to decouple the API from the AI processing layer. Kafka is designed for high-throughput event streaming across multiple services with replay capability. This system has one producer (the API) and one consumer (the agent worker) processing low volumes. Celery + Redis solves the same decoupling problem with far less operational complexity.

**When I'd switch to Kafka:** Multiple consumer services needing the same events, throughput exceeding ~100K messages/second, or event replay needed for debugging.

### pgvector over Pinecone

The system needs vector similarity search for RAG. Pinecone is a dedicated managed vector database. pgvector is a PostgreSQL extension that adds vector operations to the existing database. Since the system already requires PostgreSQL for relational data, pgvector eliminates an entire service from the architecture — one database handles both relational queries and vector search.

**When I'd switch to Pinecone:** Vector count exceeding tens of millions where pgvector's search latency degrades, or when the vector workload needs independent scaling from the relational workload.

### SSE over WebSockets

The system needs real-time updates flowing from server to client (agent progress). SSE is unidirectional (server → client), auto-reconnects natively, and works over standard HTTP. WebSockets add bidirectional complexity that isn't needed — the client never pushes data through the streaming connection.

**When I'd switch to WebSockets:** Features requiring bidirectional real-time communication, like collaborative analysis where multiple users interact with the same filing simultaneously.

### Eventual Consistency over Strong Consistency

When the agent completes a report, there's a brief window (milliseconds) where the report exists in PostgreSQL but the frontend hasn't received the "complete" SSE event. This is acceptable because compliance reports aren't time-critical like financial transactions. The system prioritizes availability (staying responsive) over instant consistency.

### Docker Compose over Kubernetes

The system runs 3 application containers on a single EC2 instance. Kubernetes orchestrates services across many machines with independent scaling — a problem this system doesn't have. Docker Compose provides the same containerization benefits with simpler configuration.

**When I'd switch to Kubernetes:** Independent service scaling requirements, multi-node deployment, or team growing beyond 2-3 engineers.

---

## Agent Workflow

The intelligence layer is a LangGraph state machine with 7 nodes and conditional routing:

1. **Parse Filing** — Converts raw EDGAR HTML into structured, section-organized text
2. **Chunk & Embed** — Splits text into 500-800 word chunks, generates OpenAI embeddings, stores in pgvector
3. **Retrieve Relevant Sections** — Vector similarity search finds the chunks most relevant to risk analysis
4. **Analyze Risk Factors** — LLM extracts structured risk factors with severity ratings and citations
5. **Compare with Previous Filings** — Queries historical analyses, LLM categorizes changes (new/escalated/resolved/unchanged)
6. **Self-Verify Citations** — Each citation is individually checked against its source chunk by the LLM
7. **Generate Report** — Verified risk factors saved to PostgreSQL with traceability links

**Conditional Routing After Verification:**
- All citations verified → Generate Report
- Any citation failed, retry count < 3 → Loop back to Retrieve with refined queries
- Retry count ≥ 3 → Flag for Human Review

The retry loop is the key differentiator. The agent doesn't just generate output — it validates its own work and self-corrects when citations don't hold up against the source text.

---

## Infrastructure

### AWS Architecture

- **CloudFront (2 distributions):** Frontend CDN with HTTPS + API HTTPS proxy
- **S3:** Static frontend hosting (HTML/CSS/JS from Next.js export)
- **EC2 (t3.micro):** Backend + Celery worker in Docker, nginx reverse proxy
- **RDS (db.t3.micro):** Managed PostgreSQL 16 with pgvector extension, VPC-isolated
- **ElastiCache (cache.t3.micro):** Managed Redis 7 for job queue and pub/sub, VPC-isolated

### Security

- RDS and ElastiCache are in a private VPC with no public access — only reachable from EC2 via security groups
- JWT authentication on all API endpoints (except health check and auth routes)
- bcrypt password hashing (~100ms per hash, prevents brute force)
- Rate limiting: 10 submissions/minute, 100 reads/minute
- Input validation via Pydantic schemas with custom business logic validators
- CORS restricted to specific CloudFront domains

### CI/CD Pipeline

```
Push to main → Lint (Ruff + ESLint) → Test (pytest with service containers)
                                          ↓
                              ┌───────────┴───────────┐
                              ↓                       ↓
                    Deploy Backend            Deploy Frontend
                    (SSH → EC2 →              (Build → S3 upload →
                     git pull →               CloudFront cache
                     docker rebuild)          invalidation)
```

---

## Running Locally

### Prerequisites

- Docker and Docker Compose
- OpenAI API key

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/Agentic-Financial-Compliance-Risk-Engine.git
cd Agentic-Financial-Compliance-Risk-Engine

# Create environment file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and JWT_SECRET_KEY

# Start all services
docker compose up --build

# The app is running at:
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
# Health:   http://localhost:8000/health
```

### First Run

1. Open `http://localhost:3000`
2. Register an account
3. Enter a ticker (e.g., AAPL) and click Analyze
4. Watch the agent work in real-time
5. View the completed risk report

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI initialization, middleware, routes
│   │   ├── config.py            # Environment variable management
│   │   ├── models/              # SQLAlchemy database models (6 tables)
│   │   ├── schemas/             # Pydantic request/response validation
│   │   ├── routes/              # API endpoint definitions
│   │   ├── services/            # Business logic layer
│   │   ├── middleware/          # JWT auth, rate limiting
│   │   └── db/                  # Database session management
│   ├── agent/
│   │   ├── graph.py             # LangGraph agent with conditional routing
│   │   ├── state.py             # Agent state definition
│   │   ├── nodes/               # 7 agent nodes (parse, chunk, retrieve, etc.)
│   │   └── prompts/             # LLM prompt templates (separated from code)
│   ├── ingestion/
│   │   ├── edgar_client.py      # SEC EDGAR API integration
│   │   ├── parser.py            # HTML → structured text extraction
│   │   └── seed.py              # Historical data population script
│   ├── worker/
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── tasks.py             # Async task definitions
│   │   └── pubsub.py            # Redis pub/sub utility
│   ├── tests/                   # pytest suite (models, schemas, routes, parser)
│   ├── Dockerfile               # Multi-stage Python build
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx         # Dashboard with auth gating
│   │   ├── components/          # FilingInput, AgentFeed, ReportView, etc.
│   │   ├── hooks/               # useSSE, useAuth custom hooks
│   │   └── lib/                 # Typed API client, TypeScript interfaces
│   ├── Dockerfile               # Multi-stage Node.js build
│   └── next.config.js
├── docker-compose.yml           # Local orchestration (5 services)
├── DESIGN.md                    # Architecture decisions and trade-off analysis
├── .github/workflows/ci.yml    # CI/CD pipeline
└── .env.example                 # Environment variable template
```

---

## Database Schema

```
users ──(1:many)──→ jobs
filings ──(1:many)──→ filing_chunks (pgvector embeddings)
filings ──(1:many)──→ analysis_reports
analysis_reports ──(1:many)──→ risk_factors
risk_factors ──(many:1)──→ filing_chunks (citation traceability)
```

Every risk factor links back to the exact document chunk that supports it via `source_chunk_id`, creating a verifiable chain from claim → citation → source text → original filing.

---

## Future Improvements

| Improvement | Trigger Threshold |
|-------------|-------------------|
| Apache Kafka | Multiple consumer services, throughput > 100K msg/sec, event replay needed |
| Kubernetes | Independent service scaling, multi-node deployment, team > 3 engineers |
| Terraform | Cloud resources > 10 services, multiple environments needing identical config |
| Pinecone | Vector count > 10M, search latency exceeds acceptable thresholds |
| PostgreSQL read replicas | Read queries creating contention with writes |
| OpenTelemetry distributed tracing | System grows to 5+ services, cross-service debugging needed |
| OAuth2 social login | User base grows beyond demo/internal use |

---

## License

MIT