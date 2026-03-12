import logging

from agent.state import AgentState
from ingestion.parser import parse_filing_html

logger = logging.getLogger(__name__)


def parse_filing(state: AgentState) -> dict:
    logger.info(f"Parsing filing {state.get('filing_id')}")
    
    raw_html = state.get("raw_html", "")
    
    if not raw_html:
        return {
            "error": "No raw HTML provided in state",
            "completed": False,
        }
    
    # Delegate to the parser module
    sections = parse_filing_html(raw_html)
    
    section_names = [k for k in sections.keys() if k != "full_text"]
    
    progress = {
        "step": "parsing",
        "message": f"Parsed filing, identified {len(section_names)} sections: {', '.join(section_names)}",
        "progress": 15,
    }
    
    existing_messages = state.get("status_messages", [])
    
    return {
        "sections": sections,
        "status_messages": existing_messages + [progress],
    }