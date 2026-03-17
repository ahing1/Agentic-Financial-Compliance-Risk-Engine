# Troubleshooting Log

Problems encountered during development and how they were resolved.

---

## 1. "Python quit unexpectedly" crash when submitting a ticker

**Symptom:** After submitting a ticker for analysis, macOS shows a "Python quit unexpectedly" dialog. The Celery worker crashes with no Python traceback. The worker starts fine — the crash only happens during task execution.

**Root Cause:** Two issues combined:

1. **Celery's default prefork pool + macOS + Python 3.14.** Celery's default pool uses `fork()` to create child processes. On macOS, Apple's Objective-C runtime isn't fork-safe — when a forked child touches any ObjC code (which Python's SSL, networking, and GUI frameworks use under the hood), macOS kills the process. Python 3.14's C API changes make this worse since many C extensions (`lxml`, `psycopg2-binary`, `pydantic_core`) ship pre-compiled binaries that may be ABI-incompatible.

2. **Multiple Celery workers running simultaneously.** A prefork worker (without `--pool=solo`) was running alongside the solo worker, and it would grab tasks first, fork, and segfault.

**Fix:**
- Run Celery with `--pool=solo` (no forking — tasks run inline in the main process)
- Kill stale workers before starting a new one (`ps aux | grep celery`)
- Added `faulthandler` to top of `celery_app.py` to capture segfault tracebacks in `/tmp/celery_crash.log`
- Switched `lxml` to `html.parser` (pure Python, can't segfault)
- Switched `psycopg2-binary` to `psycopg[binary]` v3 (pure Python fallback available)
- Lazy-initialized OpenAI clients (single shared client created on first use instead of 5 global clients at import time)
- Lazy graph construction (build graph on first task, not at import time)

**Files changed:**
- `backend/worker/celery_app.py` — faulthandler + celery config
- `backend/ingestion/parser.py` — `BeautifulSoup(html, "lxml")` to `BeautifulSoup(html, "html.parser")`
- `backend/requirements.txt` — removed `lxml`, replaced `psycopg2-binary` with `psycopg[binary]>=3.2`
- `backend/agent/clients.py` — new file, shared lazy OpenAI client
- `backend/agent/nodes/analyze.py`, `chunk.py`, `compare.py`, `retrieve.py`, `verify.py` — use `get_openai_client()` instead of module-level `OpenAI()`
- `backend/agent/graph.py` — removed `agent_graph = build_agent_graph()` at module level
- `backend/worker/tasks.py` — lazy graph construction via `build_agent_graph()`
- `backend/app/db/session.py` — rewrite connection string prefix for psycopg v3

---

## 2. 404 on report fetch after analysis completes

**Symptom:** `GET /filings/{filing_id}/report` returns 404 even though the analysis appeared to complete. The frontend shows an error, but submitting again works. Logs show: `"GET /filings/3f812a9a-.../report HTTP/1.1" 404 Not Found`.

**Root Cause:** Two issues:

1. **Stale filing ID from a crashed run.** Each ticker submission creates a new Filing + Job with a new `filing_id`. The 404 was from a previous submission where the prefork worker crashed before saving the report. The `filing_id` from that run had no report in the database. When the user submitted again, a new `filing_id` was created and that one succeeded — but the old 404 was still visible in logs.

2. **Race condition on transition.** The frontend's view transition from "processing" to "viewing_report" was triggered during React's render phase (not in a `useEffect`), which could fire multiple times. It also only waited 1 second after the SSE "complete" event before fetching the report, which may not be enough time for the DB transaction to commit.

**Fix:**
- `ReportView.tsx` — Added retry logic (3 attempts, 2 seconds apart) so if the report isn't committed yet, the frontend retries instead of showing an error immediately
- `page.tsx` — Moved the view transition into a `useEffect` (React best practice) and increased delay from 1s to 1.5s

**Files changed:**
- `frontend/src/components/ReportView.tsx` — retry on 404
- `frontend/src/app/page.tsx` — `useEffect` for view transition, added `useEffect` to imports
