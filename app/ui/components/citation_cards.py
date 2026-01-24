"""
Empire v7.3 - Gradio Citation Component - Task 16
Inline citations with expandable cards for source context display

Features:
- Clickable inline citation markers
- Expandable citation cards with full source context
- Document metadata display
- Mobile responsive design
- Accessibility compliant (WCAG 2.1 AA)
"""

import os
import gradio as gr
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from html import escape

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class SourceType(str, Enum):
    """Types of citation sources."""
    DOCUMENT = "document"
    WEBPAGE = "webpage"
    DATABASE = "database"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    API = "api"
    USER_MEMORY = "user_memory"
    UNKNOWN = "unknown"


@dataclass
class CitationSource:
    """Represents a single citation source with metadata."""
    citation_id: str
    title: str
    source_type: SourceType = SourceType.DOCUMENT
    excerpt: str = ""
    full_content: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    section: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "citation_id": self.citation_id,
            "title": self.title,
            "source_type": self.source_type.value,
            "excerpt": self.excerpt,
            "full_content": self.full_content,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "section": self.section,
            "url": self.url,
            "author": self.author,
            "date": self.date,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata
        }


@dataclass
class CitationGroup:
    """Group of citations for a response."""
    response_id: str
    citations: List[CitationSource] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_citation(self, citation: CitationSource):
        """Add a citation to the group."""
        self.citations.append(citation)

    def get_citation(self, citation_id: str) -> Optional[CitationSource]:
        """Get a citation by ID."""
        for citation in self.citations:
            if citation.citation_id == citation_id:
                return citation
        return None


# ============================================================================
# Source Type Icons and Styling
# ============================================================================

SOURCE_TYPE_STYLES = {
    SourceType.DOCUMENT: {
        "icon": "📄",
        "color": "#3b82f6",
        "label": "Document",
        "bg_color": "#dbeafe"
    },
    SourceType.WEBPAGE: {
        "icon": "🌐",
        "color": "#10b981",
        "label": "Web Page",
        "bg_color": "#d1fae5"
    },
    SourceType.DATABASE: {
        "icon": "🗄️",
        "color": "#8b5cf6",
        "label": "Database",
        "bg_color": "#ede9fe"
    },
    SourceType.KNOWLEDGE_GRAPH: {
        "icon": "🔗",
        "color": "#f59e0b",
        "label": "Knowledge Graph",
        "bg_color": "#fef3c7"
    },
    SourceType.API: {
        "icon": "⚡",
        "color": "#ef4444",
        "label": "API",
        "bg_color": "#fee2e2"
    },
    SourceType.USER_MEMORY: {
        "icon": "💭",
        "color": "#ec4899",
        "label": "Memory",
        "bg_color": "#fce7f3"
    },
    SourceType.UNKNOWN: {
        "icon": "❓",
        "color": "#6b7280",
        "label": "Unknown",
        "bg_color": "#f3f4f6"
    }
}


# ============================================================================
# Custom CSS for Citation Components
# ============================================================================

CITATION_CSS = """
/* Citation Container */
.citation-container {
    margin: 16px 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
}

/* Inline Citation Marker */
.citation-marker {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    background: #3b82f6;
    color: white;
    border-radius: 50%;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    margin: 0 2px;
    vertical-align: super;
    transition: all 0.2s ease;
    text-decoration: none;
}

.citation-marker:hover {
    background: #2563eb;
    transform: scale(1.1);
}

.citation-marker:focus {
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
}

/* Citation Card */
.citation-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
}

.citation-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    border-color: #cbd5e1;
}

.citation-card.expanded {
    border-left: 4px solid #3b82f6;
}

/* Citation Header */
.citation-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    cursor: pointer;
}

.citation-title-section {
    flex: 1;
}

.citation-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: #3b82f6;
    color: white;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 600;
    margin-right: 10px;
    flex-shrink: 0;
}

.citation-title {
    font-size: 15px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
}

.citation-meta {
    font-size: 12px;
    color: #64748b;
    margin-top: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.citation-meta-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

/* Source Type Badge */
.source-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 500;
}

/* Expand/Collapse Toggle */
.citation-toggle {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: #64748b;
    transition: transform 0.2s ease;
}

.citation-toggle:hover {
    color: #3b82f6;
}

.citation-toggle.expanded {
    transform: rotate(180deg);
}

/* Citation Excerpt */
.citation-excerpt {
    font-size: 14px;
    color: #475569;
    margin-top: 12px;
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
    line-height: 1.6;
}

/* Citation Full Content (expandable) */
.citation-content {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #e2e8f0;
    display: none;
}

.citation-content.visible {
    display: block;
    animation: slideDown 0.3s ease;
}

@keyframes slideDown {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.citation-full-text {
    font-size: 14px;
    color: #334155;
    line-height: 1.7;
    max-height: 300px;
    overflow-y: auto;
    padding: 12px;
    background: #f1f5f9;
    border-radius: 8px;
}

/* Relevance Score */
.relevance-score {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #64748b;
    margin-top: 8px;
}

.relevance-bar {
    width: 60px;
    height: 4px;
    background: #e2e8f0;
    border-radius: 2px;
    overflow: hidden;
}

.relevance-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
}

/* Action Buttons */
.citation-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    flex-wrap: wrap;
}

.citation-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: white;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s ease;
}

.citation-action-btn:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
}

.citation-action-btn.primary {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
}

.citation-action-btn.primary:hover {
    background: #2563eb;
}

/* Citations List */
.citations-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.citations-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 8px;
}

.citations-count {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
}

.citations-filter {
    display: flex;
    gap: 8px;
}

/* Mobile Responsiveness */
@media (max-width: 768px) {
    .citation-card {
        padding: 12px;
    }

    .citation-header {
        flex-direction: column;
        gap: 8px;
    }

    .citation-meta {
        flex-direction: column;
        gap: 4px;
    }

    .citation-actions {
        flex-direction: column;
    }

    .citation-action-btn {
        width: 100%;
        justify-content: center;
    }
}

/* Accessibility */
@media (prefers-contrast: high) {
    .citation-card {
        border-width: 2px;
    }

    .citation-marker {
        outline: 2px solid currentColor;
    }
}

@media (prefers-reduced-motion: reduce) {
    .citation-card,
    .citation-toggle,
    .citation-marker,
    .citation-content {
        transition: none;
        animation: none;
    }
}

/* Print Styles */
@media print {
    .citation-toggle,
    .citation-actions {
        display: none;
    }

    .citation-content {
        display: block !important;
    }
}
"""


# ============================================================================
# HTML Generation Functions
# ============================================================================

def create_inline_citation_html(citation_number: int, citation_id: str) -> str:
    """
    Create an inline citation marker (superscript number).

    Args:
        citation_number: Display number for the citation
        citation_id: Unique identifier for the citation

    Returns:
        HTML string for inline citation marker
    """
    return f'''<a href="#citation-{escape(citation_id)}"
               class="citation-marker"
               role="link"
               aria-label="Citation {citation_number}"
               tabindex="0"
               data-citation-id="{escape(citation_id)}"
               onclick="expandCitation('{escape(citation_id)}')">{citation_number}</a>'''


def create_citation_card_html(
    citation: CitationSource,
    citation_number: int,
    expanded: bool = False,
    show_full_content: bool = True
) -> str:
    """
    Create HTML for a single citation card.

    Args:
        citation: CitationSource object
        citation_number: Display number for the citation
        expanded: Whether the card is expanded by default
        show_full_content: Whether to include full content section

    Returns:
        HTML string for citation card
    """
    source_style = SOURCE_TYPE_STYLES.get(citation.source_type, SOURCE_TYPE_STYLES[SourceType.UNKNOWN])

    # Build metadata items
    meta_items = []
    if citation.author:
        meta_items.append(f'<span class="citation-meta-item">👤 {escape(citation.author)}</span>')
    if citation.date:
        meta_items.append(f'<span class="citation-meta-item">📅 {escape(citation.date)}</span>')
    if citation.page_number:
        meta_items.append(f'<span class="citation-meta-item">📖 Page {citation.page_number}</span>')
    if citation.section:
        meta_items.append(f'<span class="citation-meta-item">📑 {escape(citation.section)}</span>')

    meta_html = "".join(meta_items) if meta_items else ""

    # Relevance score bar
    relevance_percent = min(100, max(0, int(citation.relevance_score * 100)))
    if relevance_percent >= 80:
        relevance_color = "#10b981"
    elif relevance_percent >= 60:
        relevance_color = "#f59e0b"
    else:
        relevance_color = "#6b7280"

    relevance_html = f'''
    <div class="relevance-score">
        <span>Relevance:</span>
        <div class="relevance-bar">
            <div class="relevance-fill" style="width: {relevance_percent}%; background: {relevance_color};"></div>
        </div>
        <span>{relevance_percent}%</span>
    </div>
    '''

    # Full content section
    content_html = ""
    if show_full_content and citation.full_content:
        content_class = "citation-content visible" if expanded else "citation-content"
        content_html = f'''
        <div class="{content_class}" id="content-{escape(citation.citation_id)}">
            <h4 style="margin: 0 0 8px 0; font-size: 13px; color: #64748b;">Full Source Text</h4>
            <div class="citation-full-text">{escape(citation.full_content)}</div>
        </div>
        '''

    # Action buttons
    actions_html = ""
    if citation.url or citation.document_id:
        action_buttons = []
        if citation.url:
            action_buttons.append(f'''
            <a href="{escape(citation.url)}" target="_blank" rel="noopener noreferrer" class="citation-action-btn">
                🔗 View Source
            </a>
            ''')
        if citation.document_id:
            action_buttons.append(f'''
            <button class="citation-action-btn" onclick="viewDocument('{escape(citation.document_id)}')">
                📄 Open Document
            </button>
            ''')
        actions_html = f'<div class="citation-actions">{"".join(action_buttons)}</div>'

    card_class = "citation-card expanded" if expanded else "citation-card"
    toggle_class = "citation-toggle expanded" if expanded else "citation-toggle"

    return f'''
    <article class="{card_class}"
             id="citation-{escape(citation.citation_id)}"
             aria-labelledby="title-{escape(citation.citation_id)}"
             role="article">
        <div class="citation-header"
             onclick="toggleCitation('{escape(citation.citation_id)}')"
             role="button"
             tabindex="0"
             aria-expanded="{str(expanded).lower()}"
             aria-controls="content-{escape(citation.citation_id)}">
            <div class="citation-title-section">
                <h3 class="citation-title" id="title-{escape(citation.citation_id)}">
                    <span class="citation-number">{citation_number}</span>
                    <span class="source-badge" style="background: {source_style['bg_color']}; color: {source_style['color']};">
                        {source_style['icon']} {source_style['label']}
                    </span>
                    {escape(citation.title)}
                </h3>
                <div class="citation-meta">{meta_html}</div>
            </div>
            <button class="{toggle_class}"
                    aria-label="Expand citation details"
                    type="button">
                ▼
            </button>
        </div>

        {f'<div class="citation-excerpt">{escape(citation.excerpt)}</div>' if citation.excerpt else ''}

        {relevance_html}
        {content_html}
        {actions_html}
    </article>
    '''


def create_citations_list_html(
    citations: List[CitationSource],
    title: str = "Sources",
    show_filter: bool = True,
    collapsed_by_default: bool = True
) -> str:
    """
    Create HTML for a list of citations.

    Args:
        citations: List of CitationSource objects
        title: Header title
        show_filter: Whether to show filter controls
        collapsed_by_default: Whether cards are collapsed by default

    Returns:
        HTML string for citations list
    """
    if not citations:
        return '''
        <div class="citation-container" role="region" aria-label="No citations">
            <p style="color: #64748b; font-style: italic;">No citations available for this response.</p>
        </div>
        '''

    # Build citation cards
    cards_html = ""
    for i, citation in enumerate(citations, 1):
        cards_html += create_citation_card_html(
            citation=citation,
            citation_number=i,
            expanded=not collapsed_by_default
        )

    # Filter buttons
    filter_html = ""
    if show_filter and len(citations) > 3:
        source_types = set(c.source_type for c in citations)
        filter_buttons = []
        filter_buttons.append('<button class="citation-action-btn primary" onclick="filterCitations(\'all\')">All</button>')
        for st in source_types:
            style = SOURCE_TYPE_STYLES.get(st, SOURCE_TYPE_STYLES[SourceType.UNKNOWN])
            filter_buttons.append(
                f'<button class="citation-action-btn" onclick="filterCitations(\'{st.value}\')">'
                f'{style["icon"]} {style["label"]}</button>'
            )
        filter_html = f'<div class="citations-filter">{"".join(filter_buttons)}</div>'

    return f'''
    <div class="citation-container" role="region" aria-label="{escape(title)}">
        <div class="citations-header">
            <span class="citations-count">📚 {len(citations)} {title}</span>
            {filter_html}
        </div>
        <div class="citations-list" role="list">
            {cards_html}
        </div>
    </div>
    '''


def create_inline_text_with_citations(
    text: str,
    citations: List[CitationSource]
) -> str:
    """
    Process text with citation markers and return HTML with inline citations.

    Args:
        text: Text containing citation markers like [1], [2], etc.
        citations: List of CitationSource objects matching the markers

    Returns:
        HTML string with clickable inline citations
    """
    import re

    # Replace [n] markers with clickable citation links
    def replace_marker(match):
        num = int(match.group(1))
        if 1 <= num <= len(citations):
            citation = citations[num - 1]
            return create_inline_citation_html(num, citation.citation_id)
        return match.group(0)

    processed_text = re.sub(r'\[(\d+)\]', replace_marker, text)

    return processed_text


# ============================================================================
# JavaScript for Interactivity
# ============================================================================

CITATION_JS = """
<script>
function toggleCitation(citationId) {
    const card = document.getElementById('citation-' + citationId);
    const content = document.getElementById('content-' + citationId);
    const toggle = card.querySelector('.citation-toggle');
    const header = card.querySelector('.citation-header');

    if (content) {
        const isExpanded = content.classList.contains('visible');

        if (isExpanded) {
            content.classList.remove('visible');
            card.classList.remove('expanded');
            toggle.classList.remove('expanded');
            header.setAttribute('aria-expanded', 'false');
        } else {
            content.classList.add('visible');
            card.classList.add('expanded');
            toggle.classList.add('expanded');
            header.setAttribute('aria-expanded', 'true');
        }
    }
}

function expandCitation(citationId) {
    // Scroll to citation
    const card = document.getElementById('citation-' + citationId);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Expand the card
        const content = document.getElementById('content-' + citationId);
        if (content && !content.classList.contains('visible')) {
            toggleCitation(citationId);
        }

        // Highlight briefly
        card.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.5)';
        setTimeout(() => {
            card.style.boxShadow = '';
        }, 2000);
    }
}

function filterCitations(sourceType) {
    const cards = document.querySelectorAll('.citation-card');
    const buttons = document.querySelectorAll('.citations-filter .citation-action-btn');

    // Update button states
    buttons.forEach(btn => {
        btn.classList.remove('primary');
        if (btn.textContent.toLowerCase().includes(sourceType) ||
            (sourceType === 'all' && btn.textContent === 'All')) {
            btn.classList.add('primary');
        }
    });

    // Filter cards
    cards.forEach(card => {
        if (sourceType === 'all') {
            card.style.display = '';
        } else {
            const badge = card.querySelector('.source-badge');
            if (badge && badge.textContent.toLowerCase().includes(sourceType.replace('_', ' '))) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        }
    });
}

function viewDocument(documentId) {
    // Emit event for parent to handle
    window.dispatchEvent(new CustomEvent('viewDocument', {
        detail: { documentId: documentId }
    }));

    // Fallback: log if no handler
    console.log('View document requested:', documentId);
}

// Keyboard navigation
document.addEventListener('keydown', function(e) {
    if (e.target.classList.contains('citation-marker') && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        const citationId = e.target.dataset.citationId;
        expandCitation(citationId);
    }

    if (e.target.closest('.citation-header') && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        const citationId = e.target.closest('.citation-card').id.replace('citation-', '');
        toggleCitation(citationId);
    }
});
</script>
"""


# ============================================================================
# Gradio Components
# ============================================================================

def create_citation_display_component() -> gr.Blocks:
    """
    Create a reusable Gradio Blocks component for displaying citations.

    Returns:
        gr.Blocks: Gradio Blocks component
    """
    with gr.Blocks(css=CITATION_CSS) as citation_component:
        # Hidden state for citations
        citations_state = gr.State(value=[])

        with gr.Column(elem_classes="citation-display-wrapper"):
            # Citations HTML display
            citations_html = gr.HTML(
                value="",
                elem_id="citations-display"
            )

            # JavaScript for interactivity (injected once)
            js_injector = gr.HTML(  # noqa: F841
                value=CITATION_JS,
                visible=False
            )

        def update_citations_display(citations_data: List[Dict[str, Any]]) -> str:
            """Update the citations display from data."""
            if not citations_data:
                return create_citations_list_html([])

            # Convert dict data to CitationSource objects
            citations = []
            for data in citations_data:
                try:
                    source_type = SourceType(data.get("source_type", "unknown"))
                except ValueError:
                    source_type = SourceType.UNKNOWN

                citation = CitationSource(
                    citation_id=data.get("citation_id", ""),
                    title=data.get("title", "Untitled"),
                    source_type=source_type,
                    excerpt=data.get("excerpt", ""),
                    full_content=data.get("full_content"),
                    document_id=data.get("document_id"),
                    page_number=data.get("page_number"),
                    section=data.get("section"),
                    url=data.get("url"),
                    author=data.get("author"),
                    date=data.get("date"),
                    relevance_score=data.get("relevance_score", 0.0),
                    metadata=data.get("metadata", {})
                )
                citations.append(citation)

            return create_citations_list_html(citations)

        citations_state.change(
            fn=update_citations_display,
            inputs=[citations_state],
            outputs=[citations_html]
        )

    return citation_component


def create_response_with_citations_component() -> gr.Blocks:
    """
    Create a component that displays a response with inline citations.

    Returns:
        gr.Blocks: Gradio Blocks component
    """
    with gr.Blocks(css=CITATION_CSS) as response_component:
        response_state = gr.State(value={"text": "", "citations": []})

        with gr.Column():
            # Response text with inline citations
            response_html = gr.HTML(
                value="",
                elem_id="response-with-citations"
            )

            # Expandable citations section
            with gr.Accordion("📚 View Sources", open=False):
                citations_html = gr.HTML(
                    value="",
                    elem_id="citations-list"
                )

            # JavaScript injector
            gr.HTML(value=CITATION_JS, visible=False)

        def update_response(state):
            """Update response and citations display."""
            text = state.get("text", "")
            citations_data = state.get("citations", [])

            # Convert to CitationSource objects
            citations = []
            for data in citations_data:
                try:
                    source_type = SourceType(data.get("source_type", "unknown"))
                except ValueError:
                    source_type = SourceType.UNKNOWN

                citation = CitationSource(
                    citation_id=data.get("citation_id", f"cite-{len(citations) + 1}"),
                    title=data.get("title", "Untitled"),
                    source_type=source_type,
                    excerpt=data.get("excerpt", ""),
                    full_content=data.get("full_content"),
                    document_id=data.get("document_id"),
                    page_number=data.get("page_number"),
                    section=data.get("section"),
                    url=data.get("url"),
                    author=data.get("author"),
                    date=data.get("date"),
                    relevance_score=data.get("relevance_score", 0.0),
                    metadata=data.get("metadata", {})
                )
                citations.append(citation)

            # Process text with inline citations
            response_with_citations = create_inline_text_with_citations(text, citations)

            # Create citations list
            citations_list = create_citations_list_html(citations)

            return response_with_citations, citations_list

        response_state.change(
            fn=update_response,
            inputs=[response_state],
            outputs=[response_html, citations_html]
        )

    return response_component


# ============================================================================
# Utility Functions
# ============================================================================

def parse_citations_from_response(
    response_text: str,
    sources: List[Dict[str, Any]]
) -> tuple[str, List[CitationSource]]:
    """
    Parse a response with citations and create CitationSource objects.

    Args:
        response_text: Response text with [n] citation markers
        sources: List of source dictionaries from the backend

    Returns:
        Tuple of (processed_text_html, list_of_citations)
    """
    citations = []

    for i, source in enumerate(sources, 1):
        citation = CitationSource(
            citation_id=source.get("id", f"cite-{i}"),
            title=source.get("title", source.get("filename", f"Source {i}")),
            source_type=SourceType(source.get("type", "document")),
            excerpt=source.get("excerpt", source.get("text", "")[:500]),
            full_content=source.get("full_text", source.get("content")),
            document_id=source.get("document_id"),
            page_number=source.get("page"),
            section=source.get("section", source.get("chunk_id")),
            url=source.get("url"),
            author=source.get("author"),
            date=source.get("date", source.get("created_at")),
            relevance_score=source.get("score", source.get("relevance", 0.0)),
            metadata=source.get("metadata", {})
        )
        citations.append(citation)

    processed_text = create_inline_text_with_citations(response_text, citations)

    return processed_text, citations


def format_response_with_sources(
    answer: str,
    sources: List[Dict[str, Any]],
    include_sources_section: bool = True
) -> str:
    """
    Format a complete response with inline citations and sources section.

    Args:
        answer: The answer text with citation markers
        sources: List of source dictionaries
        include_sources_section: Whether to append sources list

    Returns:
        Complete HTML formatted response
    """
    processed_text, citations = parse_citations_from_response(answer, sources)

    result = f'<div class="response-content">{processed_text}</div>'

    if include_sources_section and citations:
        result += create_citations_list_html(citations)

    # Include JS for interactivity
    result += CITATION_JS

    return result


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "SourceType",
    "CitationSource",
    "CitationGroup",
    "CITATION_CSS",
    "CITATION_JS",
    "SOURCE_TYPE_STYLES",
    "create_inline_citation_html",
    "create_citation_card_html",
    "create_citations_list_html",
    "create_inline_text_with_citations",
    "create_citation_display_component",
    "create_response_with_citations_component",
    "parse_citations_from_response",
    "format_response_with_sources",
]
