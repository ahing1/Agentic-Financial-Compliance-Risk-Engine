"""
tests/test_parser.py — Filing Parser Tests

Tests that the HTML parser correctly extracts text and identifies
sections from EDGAR filings.

These tests don't need a database — they test pure functions.
No fixtures required except the test data.
"""

from ingestion.parser import parse_filing_html, get_section_or_full_text


class TestParseFilingHtml:
    
    def test_extracts_clean_text(self):
        """HTML tags are stripped, clean text is returned."""
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
            <h1>Filing Content</h1>
            <p>This is a paragraph about the company.</p>
            <script>alert('evil');</script>
        </body>
        </html>
        """
        result = parse_filing_html(html)
        
        # full_text should always exist
        assert "full_text" in result
        # Clean text should contain the paragraph content
        assert "This is a paragraph about the company" in result["full_text"]
        # Script content should be stripped
        assert "alert" not in result["full_text"]
        # Style content should be stripped
        assert "color: red" not in result["full_text"]
    
    def test_identifies_risk_factors_section(self):
        """Detects 'Item 1A: Risk Factors' section."""
        html = """
        <html><body>
            <h1>Item 1: Business</h1>
            <p>We sell products worldwide.</p>
            <h1>Item 1A: Risk Factors</h1>
            <p>The company faces significant supply chain risks due to its heavy reliance on manufacturing partners located in the Asia-Pacific region.</p>
            <p>Currency fluctuations may materially impact revenue and operating margins in international markets where the company conducts business.</p>
            <h1>Item 2: Properties</h1>
            <p>We have offices in California.</p>
        </body></html>
        """
        result = parse_filing_html(html)
        
        assert "Risk Factors" in result
        assert "supply chain risks" in result["Risk Factors"]
        # Risk Factors section should NOT contain Properties content
        assert "offices in California" not in result["Risk Factors"]
    
    def test_handles_empty_html(self):
        """Doesn't crash on empty or minimal HTML."""
        result = parse_filing_html("")
        assert "full_text" in result
        
        result = parse_filing_html("<html><body></body></html>")
        assert "full_text" in result
    
    def test_handles_no_standard_sections(self):
        """Returns full_text even when no Item headings are found."""
        html = """
        <html><body>
            <p>This filing has no standard section headings.</p>
            <p>But it still has content that should be extractable.</p>
        </body></html>
        """
        result = parse_filing_html(html)
        
        assert "full_text" in result
        assert "no standard section headings" in result["full_text"]
        # No section keys other than full_text
        section_keys = [k for k in result.keys() if k != "full_text"]
        assert len(section_keys) == 0


class TestGetSectionOrFullText:
    
    def test_returns_preferred_section(self):
        """Returns the requested section when it exists."""
        sections = {
            "Risk Factors": "Some risk content here",
            "full_text": "The entire document text",
        }
        result = get_section_or_full_text(sections, "Risk Factors")
        assert result == "Some risk content here"
    
    def test_falls_back_to_full_text(self):
        """Returns full_text when preferred section doesn't exist."""
        sections = {
            "full_text": "The entire document text",
        }
        result = get_section_or_full_text(sections, "Risk Factors")
        assert result == "The entire document text"