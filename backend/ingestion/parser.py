import re
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SECTION_PATTERNS = [
    (r"item\s+1a[\.\:\s\-—]+\s*risk\s+factors", "Risk Factors"),
    (r"item\s+1[\.\:\s\-—]+\s*business", "Business"),
    (r"item\s+1b[\.\:\s\-—]+\s*unresolved", "Unresolved Staff Comments"),
    (r"item\s+2[\.\:\s\-—]+\s*properties", "Properties"),
    (r"item\s+3[\.\:\s\-—]+\s*legal", "Legal Proceedings"),
    (r"item\s+7a[\.\:\s\-—]+\s*quantitative", "Market Risk Disclosures"),
    (r"item\s+7[\.\:\s\-—]+\s*management", "MD&A"),
    (r"item\s+8[\.\:\s\-—]+\s*financial\s+statements", "Financial Statements"),
]

def parse_filing_html(html: str) -> dict[str, str]:

    logger.info(f"Parsing filing HTML ({len(html)} characters)")
    
    # --- Step 1: HTML → Plain Text ---
    # BeautifulSoup parses HTML into a tree structure.
    soup = BeautifulSoup(html, "lxml")
    
    # Remove <script> and <style> tags — they contain code/CSS, not content
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    
    # get_text() extracts all visible text from the HTML tree.
    raw_text = soup.get_text(separator="\n", strip=True)
    
    # --- Step 2: Clean up the text ---
    clean_text = re.sub(r"\n{3,}", "\n\n", raw_text)
    clean_text = re.sub(r"[ \t]{2,}", " ", clean_text)
    clean_text = re.sub(r"Table\s+of\s+Contents", "", clean_text, flags=re.IGNORECASE)
    
    logger.info(f"Extracted {len(clean_text)} characters of clean text")
    
    # --- Step 3: Identify sections ---
    sections = {"full_text": clean_text}
    sections.update(_extract_sections(clean_text))
    
    logger.info(f"Identified sections: {[k for k in sections.keys() if k != 'full_text']}")
    return sections

def _extract_sections(text: str) -> dict[str, str]:
    found_sections = []
    
    for pattern, section_name in SECTION_PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        
        if matches:
            last_match = matches[-1]
            found_sections.append((last_match.start(), section_name, last_match.end()))
            logger.debug(f"Found section '{section_name}' at position {last_match.start()}")
    
    if not found_sections:
        logger.warning("No standard sections found in filing")
        return {}
    
    # Sort by position in text
    found_sections.sort(key=lambda x: x[0])
    
    # Extract text between consecutive section headings
    sections = {}
    for i, (start_pos, section_name, heading_end) in enumerate(found_sections):
        content_start = heading_end
        
        if i + 1 < len(found_sections):
            content_end = found_sections[i + 1][0]
        else:
            content_end = min(content_start + 50000, len(text))
        
        content = text[content_start:content_end].strip()
        
        if len(content) > 100:
            sections[section_name] = content
            logger.info(f"Section '{section_name}': {len(content)} characters")
    
    return sections

def get_section_or_full_text(sections: dict[str, str], preferred_section: str = "Risk Factors") -> str:
    if preferred_section in sections:
        return sections[preferred_section]
    
    logger.warning(
        f"Section '{preferred_section}' not found. "
        f"Available: {[k for k in sections.keys() if k != 'full_text']}. "
        f"Falling back to full text."
    )
    return sections.get("full_text", "")