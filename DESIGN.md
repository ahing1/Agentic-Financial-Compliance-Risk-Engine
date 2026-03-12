# Agentic Financial Compliance & Risk Engine

## Design Document

**Author:** Andrew Hing
**Date:** March 2026
**Status:** In Development

---

## 1. Overview

An autonomous AI system that ingests SEC financial filings, performs multi-step risk analysis using AI agents, and surfaces findings through a real-time dashboard. The system uses a LangGraph-powered agent that reads 10-K and 10-Q filings, extracts and categorizes risk factors, compares them against historical analyses, self-verifies every citation, and generates structured compliance reports.

**Target domain:** Financial compliance and risk analysis, relevant to the Philadelphia fintech corridor (Credit Genie, BlackRock, Vanguard).

**Core workflow:** A financial filing goes in. A verified, structured risk analysis report comes out.

---

## 2. Functional Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-1 | The system accepts a company ticker and fetches the latest 10-K or 10-Q filing from SEC EDGAR | Given a valid ticker (e.g., "AAPL"), the system retrieves the most recent filing from EDGAR's free API |
| FR-2 | The AI agent extracts, categorizes, and scores risk factors from the filing | Each risk factor includes a severity level (high/medium/low), description, and citation to source text |
| FR-3 | The system compares current risk factors against previous analyses of the same company | Report highlights new risks, escalated risks, resolved risks, and unchanged risks |
| FR-4 | The agent self-verifies every citation before including it in the report | Each citation is checked against the source chunk; failed citations trigger a retrieval retry (max 3 attempts) |
| FR-5 | The system generates a structured risk report | Report contains risk factors, severity scores, verified citations, historical comparison, and overall risk assessment |
| FR-6 | Users can view agent progress in real-time | SSE stream shows each agent step as it executes (parsing, retrieving, analyzing, verifying) |
| FR-7 | Users can browse historical reports and filter by company | Paginated history view with filtering by ticker and date range |

---

## 3. Non-Functional Requirements

| ID | Requirement | Justification |
|----|-------------|---------------|
| NFR-1 | API response time < 500ms for non-analysis endpoints | Users perceive sub-500ms responses as instant. Analysis endpoints are async and excluded from this target. |
| NFR-2 | The system handles concurrent analysis jobs without dropping any | Celery + Redis queue ensures jobs persist until processed. Workers scale horizontally if throughput needs increase. |
| NFR-3 | Graceful recovery from LLM API failures, EDGAR downtime, and malformed filings | Exponential backoff on retries, dead letter queue for permanently failed jobs, partial progress saved on failure. |
| NFR-4 | All API endpoints require authentication | JWT-based auth on every endpoint except health check. |
| NFR-5 | All user inputs validated and sanitized | Pydantic schemas enforce type and format constraints; business logic validates ticker format and filing type. |

---

## 4. Architecture

### 4.1 High-Level Architecture

The system is organized into four layers. Each layer has a single responsibility, and communication flows top-to-bottom for work delegation and bottom-to-top for status updates.

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT LAYER                                                     │
│                                                                   │
│   ┌───────────────────────────────┐                              │
│   │     Next.js Frontend          │                              │
│   │     (TypeScript)              │                              │
│   │                               │                              │
│   │  • Dashboard view             │                              │
│   │  • Real-time agent feed       │                              │
│   │  • Risk report viewer         │                              │
│   │  • Filing history             │                              │
│   └──────┬────────────────▲───────┘                              │
│          │                │                                       │
│          │ REST API       │ SSE stream                            │
│          │ (solid)        │ (dashed)                              │
├──────────┼────────────────┼──────────────────────────────────────┤
│ APPLICATION LAYER        │                                       │
│          │                │                                       │
│          ▼                │                                       │
│   ┌──────────────┐  ┌────┴──────────┐  ┌──────────────────┐     │
│   │   FastAPI     │  │  Task Queue   │  │  Agent Worker    │     │
│   │   Backend     │─→│  (Celery +    │─→│  (LangGraph)     │     │
│   │              │  │   Redis)      │  │                  │     │
│   │  Endpoints:  │  │              │  │ • Picks up job   │     │
│   │  POST /anal. │  │ • Job enqueue │  │ • Runs agent     │     │
│   │  GET /status │  │ • Status track│  │   graph          │     │
│   │  GET /report │  │ • Retry logic │  │ • Publishes      │     │
│   │  GET /history│  │ • Dead letter │  │   progress to    │     │
│   │  GET /stream │  │ • Pub/sub for │  │   Redis          │     │
│   │              │  │   progress    │  │                  │     │
│   │  Middleware:  │←─│              │←─│                  │     │
│   │  • JWT Auth  │  └───────────────┘  └────────┬─────────┘     │
│   │  • Rate Limit│  delivers progress   publishes progress      │
│   │  • Validation│                                │              │
│   └──────────────┘                                │              │
│                                                    │              │
├────────────────────────────────────────────────────┼──────────────┤
│ INTELLIGENCE LAYER (inside Agent Worker)           │              │
│                                                    │              │
│   Parse → Chunk & Embed → Retrieve Relevant → Analyze Risk      │
│                ▲           Sections             Factors           │
│                │                                   │              │
│        "needs  │                                   ▼              │
│         more   │           Self-Verify ←── Compare w/ Previous   │
│        context"│           Citations         Filings             │
│                │              │    │                              │
│                └──────────────┘    │                              │
│                (retry, max 3)      ▼                             │
│                              Generate Report ──→ Done            │
│                                    │                             │
│                              ✗ after 3 retries                   │
│                                    ▼                             │
│                              Flag for Human Review               │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│ DATA LAYER                                                        │
│                                                                   │
│   ┌─────────────────┐                                            │
│   │  SEC EDGAR API   │  (external, free)                         │
│   │  • 10-K filings  │                                           │
│   │  • 10-Q filings  │                                           │
│   └─────────────────┘                                            │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Single PostgreSQL Instance                              │    │
│   │                                                          │    │
│   │  ┌─────────────────────┐  ┌────────────────────────┐    │    │
│   │  │  Relational Tables  │  │  pgvector Extension    │    │    │
│   │  │                     │  │                        │    │    │
│   │  │  • users            │  │  • filing_chunks       │    │    │
│   │  │  • filings          │  │    (id, filing_id,     │    │    │
│   │  │  • analysis_reports │  │     chunk_text,        │    │    │
│   │  │  • risk_factors     │  │     chunk_index,       │    │    │
│   │  │  • jobs             │  │     embedding          │    │    │
│   │  │                     │  │     vector(1536))      │    │    │
│   │  └─────────────────────┘  │                        │    │    │
│   │                           │  Index: ivfflat on     │    │    │
│   │                           │  embedding column      │    │    │
│   │                           └────────────────────────┘    │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│   ┌─────────────────┐                                            │
│   │  Redis           │  (shared by Celery queue + pub/sub)       │
│   └─────────────────┘                                            │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### 4.2 Arrow Legend

| Arrow Type | Meaning | Example |
|------------|---------|---------|
| Solid (→) | Synchronous request/response or work delegation | REST API calls, enqueue job, worker consumes job |
| Dashed (⇢) | Streaming or async communication | SSE stream, pub/sub progress updates |
| Dotted border | Components running within the same service/instance | PostgreSQL + pgvector in single instance |

### 4.3 Request Flow (Numbered Sequence)

1. **User submits filing** — Frontend sends POST /filings/analyze to FastAPI
2. **API validates and enqueues** — FastAPI creates a job record in PostgreSQL, enqueues a Celery task via Redis, and immediately returns a job_id
3. **Frontend opens SSE** — Frontend connects to GET /stream/{job_id} and begins listening
4. **Worker picks up job** — Celery worker consumes the job from Redis queue
5. **Worker fetches filing** — Worker retrieves the filing from SEC EDGAR API
6. **Agent processes filing** — LangGraph agent runs through the Intelligence Layer pipeline
7. **Progress streams to user** — At each agent step, the worker publishes to Redis pub/sub → FastAPI receives and forwards via SSE → Frontend updates in real-time
8. **Report saved** — Agent writes completed analysis to PostgreSQL (analysis_reports + risk_factors tables)
9. **Job marked complete** — Worker updates job status to "completed" and publishes final SSE event
10. **User views report** — Frontend fetches full report via GET /filings/{id}/report

---

## 5. Database Schema

### 5.1 Relational Tables (PostgreSQL)

```sql
-- User accounts
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Filing metadata
CREATE TABLE filings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company     VARCHAR(255) NOT NULL,
    ticker      VARCHAR(10) NOT NULL,
    filing_type VARCHAR(10) NOT NULL,       -- '10-K' or '10-Q'
    filing_date DATE NOT NULL,
    source_url  TEXT NOT NULL,
    raw_text    TEXT,
    status      VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Completed analysis reports
CREATE TABLE analysis_reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id   UUID REFERENCES filings(id) ON DELETE CASCADE,
    risk_score  DECIMAL(3,1),               -- Overall risk score (e.g., 7.5/10)
    summary     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Individual risk factors within a report
CREATE TABLE risk_factors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id       UUID REFERENCES analysis_reports(id) ON DELETE CASCADE,
    factor          TEXT NOT NULL,           -- Description of the risk
    severity        VARCHAR(10) NOT NULL,    -- 'high', 'medium', 'low'
    citation        TEXT NOT NULL,           -- The claim made by the agent
    source_chunk_id UUID REFERENCES filing_chunks(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Async job tracking
CREATE TABLE jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id    UUID REFERENCES filings(id) ON DELETE CASCADE,
    user_id      UUID REFERENCES users(id),
    status       VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed, needs_review
    current_step VARCHAR(50),                   -- Current agent step for status polling
    started_at   TIMESTAMP,
    completed_at TIMESTAMP,
    error        TEXT                            -- Error message if failed
);
```

### 5.2 Vector Table (pgvector)

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Filing chunks with embeddings
CREATE TABLE filing_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id   UUID REFERENCES filings(id) ON DELETE CASCADE,
    chunk_text  TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,           -- Order within the filing
    section     VARCHAR(255),               -- Which filing section this belongs to
    embedding   vector(1536) NOT NULL       -- OpenAI embedding dimension
);

-- Vector similarity search index
-- ivfflat organizes vectors into clusters for fast approximate search
CREATE INDEX ON filing_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### 5.3 Entity Relationships

```
users ──(1:many)──→ jobs
filings ──(1:many)──→ filing_chunks
filings ──(1:many)──→ analysis_reports
analysis_reports ──(1:many)──→ risk_factors
risk_factors ──(many:1)──→ filing_chunks (citation source)
jobs ──(many:1)──→ filings
```

---

## 6. Intelligence Layer: Agent Workflow

### 6.1 LangGraph State

```python
class AgentState(TypedDict):
    filing_id: str
    ticker: str
    raw_text: str
    chunks: list[dict]
    retrieved_sections: list[dict]
    risk_factors: list[dict]
    comparison: dict | None
    verification_results: list[dict]
    retry_count: int              # Max 3 before flagging for human review
    status_messages: list[str]    # Published via Redis pub/sub at each step
```

### 6.2 Node Descriptions

| Node | Input | Output | External Calls |
|------|-------|--------|----------------|
| Parse Filing | raw_text from EDGAR | Structured sections with clean text | None |
| Chunk & Embed | Parsed sections | Chunks stored in pgvector | OpenAI Embedding API |
| Retrieve Relevant Sections | Search queries (risk-related) | Top-k similar chunks | pgvector similarity search |
| Analyze Risk Factors | Retrieved chunks | Structured risk factors with citations | LLM (GPT-4 / Claude) |
| Compare w/ Previous Filings | Current risks + historical data | Comparison report (new, escalated, resolved) | PostgreSQL query |
| Self-Verify Citations | Risk factors with citations | Verification pass/fail per citation | LLM verification call |
| Generate Report | Verified risks + comparison | Final structured report | PostgreSQL write |
| Error Handler | Failed state | Job marked needs_review | PostgreSQL update |

### 6.3 Conditional Routing

**After Self-Verify Citations:**
- All citations verified → route to **Generate Report**
- Any citation failed AND retry_count < 3 → increment retry_count, route to **Retrieve Relevant Sections** with refined queries
- Any citation failed AND retry_count >= 3 → route to **Error Handler**

**After Compare w/ Previous Filings:**
- Historical data exists → include comparison in state, continue to **Self-Verify Citations**
- No historical data (cold start) → note "no prior data" in state, continue to **Self-Verify Citations**

---

## 7. Scale Estimation

### 7.1 Data Volume

| Metric | Estimate | Source |
|--------|----------|--------|
| SEC EDGAR filings per day | ~8,000-10,000 | SEC EDGAR statistics |
| Average 10-K filing size | ~5-15 MB (HTML) | Sample downloads from EDGAR |
| Average 10-K page count | ~150-300 pages | Sample filings |
| Chunks per filing (500-word chunks) | ~300-600 | Page count ÷ ~2 chunks/page |
| Embedding size per chunk | ~6 KB | 1536 floats × 4 bytes |
| Vector storage per filing | ~1.8-3.6 MB | Chunks × 6 KB |

### 7.2 Throughput

| Metric | Estimate | Calculation |
|--------|----------|-------------|
| LLM calls per analysis | ~8-12 | Retrieve + Analyze + Compare + Verify + Generate |
| Average LLM call latency | ~3 seconds | OpenAI API typical response |
| Total processing time per filing | ~30-60 seconds | LLM calls + embedding + DB operations |
| Throughput per worker | ~60-120 filings/hour | 3600s ÷ 30-60s per filing |
| Horizontal scaling | Linear with workers | 2 workers = 2× throughput |

### 7.3 Storage Projection (first year)

| Scenario | Filings Analyzed | PostgreSQL Storage | pgvector Storage |
|----------|------------------|--------------------|------------------|
| Light usage (demo) | ~100 | ~50 MB | ~200 MB |
| Moderate (active use) | ~1,000 | ~500 MB | ~2 GB |
| Heavy (all S&P 500, quarterly) | ~2,000 | ~1 GB | ~4 GB |

All projections fit comfortably within a single PostgreSQL instance. Sharding or read replicas are not needed at this scale.

---

## 8. Technical Trade-Off Analysis

### 8.1 Task Queue: Celery + Redis vs Apache Kafka

| Consideration | Celery + Redis | Apache Kafka |
|---------------|----------------|--------------|
| Use case fit | Simple job queue with one producer, one consumer | High-throughput event streaming across multiple services |
| Operational complexity | Low — Redis is a single process, Celery is a pip install | High — requires ZooKeeper/KRaft, topic configuration, partition management |
| Throughput needed | Dozens of jobs/hour | Millions of events/second |
| Event replay | Not needed | Kafka's core strength |
| Consumer groups | One consumer type (agent worker) | Multiple consumers processing the same events differently |

**Decision:** Celery + Redis. The system has one producer (API) and one consumer type (agent worker) processing low volumes. Kafka's strengths (replay, multi-consumer, extreme throughput) are not needed and its operational overhead is not justified.

**When to reconsider:** If the system evolves to have multiple consumer types (e.g., a separate alerting service, an audit logging service, and the analysis service all needing the same events), or if throughput exceeds what Redis can handle (~100K messages/second).

### 8.2 Vector Database: pgvector vs Pinecone

| Consideration | pgvector | Pinecone |
|---------------|----------|----------|
| Infrastructure | Extension on existing PostgreSQL — no new service | Separate managed service to deploy and connect to |
| Cost | Free (included with Postgres) | Paid service with per-query pricing |
| Vector capacity | Handles millions of vectors comfortably | Optimized for hundreds of millions+ |
| Operational burden | Zero additional — same backup, monitoring, and maintenance as your existing DB | Separate monitoring, connection management, failure modes |

**Decision:** pgvector. The expected vector count (~50K-500K) is well within pgvector's capability. Using the existing PostgreSQL instance eliminates an entire service from the architecture.

**When to reconsider:** If vector count exceeds tens of millions and similarity search latency degrades below acceptable thresholds, or if the vector workload needs independent scaling from the relational workload.

### 8.3 Real-time Updates: SSE vs WebSockets

| Consideration | SSE | WebSockets |
|---------------|-----|------------|
| Data direction | Server → Client only | Bidirectional |
| Auto-reconnect | Built into browser EventSource API | Must implement manually |
| Protocol | Standard HTTP | Protocol upgrade required |
| Complexity | Simple — just a streaming HTTP response | More complex — connection management, heartbeats |

**Decision:** SSE. The use case is purely server-to-client (backend tells frontend what the agent is doing). The frontend never needs to push data back through the streaming connection — it uses REST for all client-to-server communication. SSE is simpler and provides automatic reconnection.

**When to reconsider:** If the system adds features requiring bidirectional real-time communication, such as a collaborative interface where multiple users interact with the same analysis in real-time.

### 8.4 Consistency Model: Eventual vs Strong

The system uses eventual consistency for analysis results. When the agent completes a report, there is a brief window (milliseconds) where the report exists in PostgreSQL but the frontend hasn't received the "complete" SSE event. This is acceptable because compliance reports are not time-critical in the way financial transactions are — a sub-second delay between storage and display has no practical impact.

This relates to the **CAP Theorem**: in any distributed system, you can guarantee at most two of Consistency, Availability, and Partition Tolerance. Since network partitions are unavoidable, the real choice is between consistency and availability. This system chooses availability — it remains responsive even if data takes a moment to propagate across components.

**When to reconsider:** If the system processes real-time trading signals where stale data could cause financial loss.

---

## 9. API Specification

### 9.1 Endpoints

| Method | Path | Purpose | Auth Required |
|--------|------|---------|---------------|
| POST | /filings/analyze | Submit a filing for analysis | Yes |
| GET | /filings/{id}/status | Check job status | Yes |
| GET | /filings/{id}/report | Retrieve completed report | Yes |
| GET | /filings/history | List past analyses (paginated) | Yes |
| GET | /stream/{job_id} | SSE stream of agent progress | Yes |
| POST | /auth/register | Create account | No |
| POST | /auth/login | Get JWT token | No |
| GET | /health | System health check | No |

### 9.2 Example Request/Response

**POST /filings/analyze**
```json
// Request
{
    "ticker": "AAPL",
    "filing_type": "10-K"
}

// Response (immediate)
{
    "job_id": "abc123-def456",
    "status": "pending",
    "message": "Analysis job enqueued"
}
```

**GET /stream/{job_id} (SSE)**
```
data: {"step": "fetching_filing", "message": "Retrieving 10-K for AAPL from EDGAR", "progress": 10}

data: {"step": "parsing", "message": "Parsed 247 pages, identified 12 sections", "progress": 20}

data: {"step": "embedding", "message": "Created 340 chunks with embeddings", "progress": 35}

data: {"step": "retrieval", "message": "Retrieved 8 relevant sections", "progress": 45}

data: {"step": "analyzing", "message": "Identified 6 risk factors", "progress": 60}

data: {"step": "comparing", "message": "2 new risks vs 2024 filing, 1 escalated", "progress": 75}

data: {"step": "verifying", "message": "5/6 citations verified, retrying 1", "progress": 85}

data: {"step": "complete", "report_id": "rpt-789", "progress": 100}
```

---

## 10. Security

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Authentication | JWT tokens (bcrypt password hashing) | Verify user identity on every request |
| Rate limiting | slowapi middleware (100 req/min authenticated, 10 req/min unauthenticated) | Prevent abuse and control LLM API costs |
| Input validation | Pydantic schemas + business logic checks | Reject malformed or malicious input |
| CORS | Restrict origins to frontend domain | Prevent unauthorized cross-origin requests |

---

## 11. Observability

| Component | Tool | Purpose |
|-----------|------|---------|
| Structured logging | Python logging (JSON format) | Audit trail for every agent decision; searchable and filterable |
| Health check | GET /health endpoint | Monitors PostgreSQL and Redis connectivity; used by cloud provider for liveness checks |
| Metrics (optional) | Prometheus endpoint | Track: avg processing time per filing, filings processed by status, citation verification failure rate |

---

## 12. Deployment

| Environment | Tool | Purpose |
|-------------|------|---------|
| Local development | Docker Compose | Single command (`docker-compose up`) starts all 5 services |
| Production | Railway / Render / AWS ECS | Live URL for demos and resume |
| CI/CD | GitHub Actions | Automated testing (pytest), linting (Ruff + ESLint), deploy on merge to main |

### 12.1 Services in Docker Compose

```yaml
services:
  frontend:   # Next.js (port 3000)
  backend:    # FastAPI (port 8000)
  worker:     # Celery worker (same image as backend, different command)
  postgres:   # PostgreSQL + pgvector (port 5432)
  redis:      # Redis (port 6379)
```

---

## 13. Future Improvements

These are technologies and patterns intentionally scoped out of the current design. Each includes the specific threshold that would trigger its adoption.

| Improvement | Trigger Threshold |
|-------------|-------------------|
| **Apache Kafka** (replace Celery + Redis) | Multiple consumer services need the same events; throughput exceeds ~100K messages/second; event replay needed for debugging |
| **Kubernetes** (replace Docker Compose in production) | Multiple services need independent scaling; team grows beyond 2-3 engineers; deployment complexity requires automated orchestration |
| **Terraform / Pulumi** (Infrastructure as Code) | Cloud resources exceed ~10 managed services; multiple environments (staging, production) need identical configuration |
| **Pinecone** (replace pgvector) | Vector count exceeds tens of millions; similarity search latency exceeds acceptable thresholds with pgvector |
| **PostgreSQL read replicas / sharding** | Database size exceeds single-instance capacity; read queries create contention with write operations |
| **OpenTelemetry distributed tracing** | System grows to 5+ services where tracing a request across service boundaries becomes necessary for debugging |
| **OAuth2 social login** | User base grows beyond internal/demo use; users expect Google/GitHub authentication |

---

## 14. Evaluation Strategy

The AI agent's accuracy is measured against a manually annotated test set.

| Metric | Definition | Target |
|--------|------------|--------|
| Citation accuracy | % of agent citations that match the source text | > 85% |
| Risk factor recall | % of manually-identified risks the agent also found | > 90% |
| Risk factor precision | % of agent-identified risks that are actually real risks | > 80% |
| Severity agreement | % of risks where agent severity matches human annotation | > 75% |

**Test set:** 10-20 filings from different companies and industries, manually annotated with expected risk factors, severity levels, and source locations.