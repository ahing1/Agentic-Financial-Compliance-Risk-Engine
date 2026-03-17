import logging
from datetime import datetime

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from worker.celery_app import celery_app
from worker.pubsub import publish_update
from app.db.session import get_session
from app.models.filing import Filing
from app.models.job import Job

logger = logging.getLogger(__name__)

# Lazy import: agent_graph triggers OpenAI client + SQLAlchemy engine creation.
# These must NOT be initialized before Celery's billiard forks the worker process
# on macOS, or the forked resources cause a crash ("Python quit unexpectedly").
_agent_graph = None

def _get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        from agent.graph import build_agent_graph
        _agent_graph = build_agent_graph()
    return _agent_graph

@celery_app.task(
    bind=True,
    name="worker.tasks.analyze_filing",
    max_retries=3,
    default_retry_delay=10
)
def analyze_filing(self: Task, job_id: str, filing_id: str) -> dict:

    logger.info(f"Starting analysis: job={job_id}, filing={filing_id}")
    try:
        filing_data = _load_filing(filing_id, job_id)
    except Exception as e:
        logger.error(f"Failed to load filing {filing_id}: {e}")
        _mark_job_failed(job_id, f"Failed to load filing: {str(e)}")
        publish_update(job_id, {
            "step": "error",
            "message": f"Failed to load filing data: {str(e)}",
            "progress": 0,
        })
        return {"status": "failed", "error": str(e)}
    
    publish_update(job_id, {
        "step": "started",
        "message": f"Starting analysis of {filing_data['ticker']} {filing_data['filing_type']}",
        "progress": 5,
    })
    
    initial_state = {
        "filing_id": filing_id,
        "ticker": filing_data["ticker"],
        "raw_html": filing_data["raw_html"],
        "company": filing_data["company"],
        "filing_type": filing_data["filing_type"],
        "retry_count": 0,
        "status_messages": [],
    }

    try:
        result = _run_agent_with_updates(job_id, initial_state)
    except SoftTimeLimitExceeded:
        logger.error(f"Job {job_id} exceeded soft time limit")
        _mark_job_failed(job_id, "Analysis exceeded time limit (4 minutes)")
        publish_update(job_id, {
            "step": "error",
            "message": "Analysis exceeded time limit",
            "progress": 100,
        })
        return {"status": "failed", "error": "Time limit exceeded"}
    
    except Exception as e:
        logger.error(f"Agent failed for job {job_id}: {e}")
        _mark_job_failed(job_id, str(e))
        publish_update(job_id, {
            "step": "error",
            "message": f"Analysis failed: {str(e)}",
            "progress": 100,
        })
        # Retry the task if we haven't exceeded max_retries
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            return {"status": "failed", "error": str(e)}
    
    if result.get("completed"):
        logger.info(f"Job {job_id} completed: report={result.get('report_id')}")
        return {
            "status": "completed",
            "report_id": result.get("report_id"),
        }
    else:
        logger.warning(f"Job {job_id} incomplete: {result.get('error')}")
        return {
            "status": "needs_review",
            "error": result.get("error"),
        }
    

def _run_agent_with_updates(job_id: str, initial_state: dict) -> dict:
    # Stream the agent node-by-node so we can publish updates in real time.
    # agent_graph.stream() yields {node_name: node_output} after each node completes,
    # unlike .invoke() which blocks until the entire graph finishes.
    published_count = 0
    final_state = dict(initial_state)

    graph = _get_agent_graph()
    for chunk in graph.stream(initial_state):
        # Each chunk is {node_name: node_output_dict}
        for node_name, node_output in chunk.items():
            # Merge node output into our running state
            final_state.update(node_output)

            # Publish any NEW status messages this node added
            all_messages = node_output.get("status_messages", [])
            new_messages = all_messages[published_count:]
            for msg in new_messages:
                publish_update(job_id, msg)
                _update_job_step(job_id, msg.get("step", "unknown"))
            published_count = len(final_state.get("status_messages", []))

    return final_state

def _load_filing(filing_id: str, job_id: str) -> dict:
    """Load filing data from the database for the agent."""
    with get_session() as session:
        filing = session.query(Filing).filter_by(id=filing_id).first()
        
        if not filing:
            raise ValueError(f"Filing {filing_id} not found")
        
        return {
            "ticker": filing.ticker,
            "company": filing.company,
            "filing_type": filing.filing_type,
            "raw_html": filing.raw_text,  # raw_text stores the HTML
        }


def _update_job_status(job_id: str, status: str, started_at: datetime = None):
    """Update job status in the database."""
    with get_session() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = status
            if started_at:
                job.started_at = started_at
            session.commit()


def _update_job_step(job_id: str, step: str):
    """Update the current agent step in the job record."""
    with get_session() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.current_step = step
            session.commit()


def _mark_job_failed(job_id: str, error: str):
    with get_session() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = "failed"
            job.error = error
            job.completed_at = datetime.utcnow()
            session.commit()