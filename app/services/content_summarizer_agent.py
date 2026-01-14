"""
Empire v7.3 - AGENT-002: Content Summarizer Agent (Task 42)

Build PDF summary generator with visual diagrams, flowcharts, key concepts,
implementation guides, and quick reference sections.

Role: Content Summary & Visualization Expert
Goal: Generate comprehensive PDF summaries with visuals
Output: processed/crewai-summaries/{department}/
Tools: pdf_generator, diagram_creator, chart_builder
LLM: Claude Sonnet 4.5

Author: Claude Code
Date: 2025-01-25
"""

import os
import re
import io
import base64
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError

# PDF Generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, grey, lightgrey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, ListFlowable, ListItem, Flowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF

# For diagram generation
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, ArrowStyle, FancyArrowPatch

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class DiagramType(str, Enum):
    """Types of diagrams that can be generated"""
    FLOWCHART = "flowchart"
    HIERARCHY = "hierarchy"
    PROCESS = "process"
    MINDMAP = "mindmap"
    TIMELINE = "timeline"
    COMPARISON = "comparison"


class SummarySection(str, Enum):
    """Standard sections in a summary PDF"""
    EXECUTIVE_SUMMARY = "executive_summary"
    KEY_CONCEPTS = "key_concepts"
    DETAILED_BREAKDOWN = "detailed_breakdown"
    FRAMEWORKS = "frameworks"
    IMPLEMENTATION_GUIDE = "implementation_guide"
    QUICK_REFERENCE = "quick_reference"
    VISUAL_ELEMENTS = "visual_elements"
    APPENDIX = "appendix"


# Color scheme for PDF styling
COLORS = {
    "primary": HexColor("#1a365d"),      # Dark blue
    "secondary": HexColor("#2b6cb0"),    # Medium blue
    "accent": HexColor("#38a169"),       # Green
    "warning": HexColor("#dd6b20"),      # Orange
    "danger": HexColor("#e53e3e"),       # Red
    "light_bg": HexColor("#f7fafc"),     # Light gray
    "dark_text": HexColor("#1a202c"),    # Near black
    "light_text": HexColor("#718096"),   # Gray
}


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ExtractedContent(BaseModel):
    """Content extracted from source document"""
    title: str
    source_type: str  # "document", "video", "course", etc.
    word_count: int
    sections: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    frameworks: List[Dict[str, Any]] = []
    key_concepts: List[str] = []
    implementation_steps: List[str] = []
    metadata: Dict[str, Any] = {}


class SummarySectionContent(BaseModel):
    """Content for a single section of the summary"""
    section_type: SummarySection
    title: str
    content: str
    bullet_points: List[str] = []
    tables: List[Dict[str, Any]] = []
    diagrams: List[str] = []  # Paths to generated diagrams


class DiagramSpec(BaseModel):
    """Specification for generating a diagram"""
    diagram_type: DiagramType
    title: str
    elements: List[Dict[str, Any]]
    connections: List[Dict[str, Any]] = []
    style: Dict[str, Any] = {}


class SummaryGenerationResult(BaseModel):
    """Result of summary generation"""
    success: bool
    pdf_path: Optional[str] = None
    department: str
    title: str
    sections_generated: List[str] = []
    diagrams_generated: int = 0
    tables_generated: int = 0
    error: Optional[str] = None
    processing_time_seconds: float = 0.0
    metadata: Dict[str, Any] = {}


# =============================================================================
# PDF GENERATOR TOOL
# =============================================================================

class PDFGeneratorTool:
    """
    Tool for generating professional PDF documents with styling.
    """

    def __init__(self, output_base_path: str = "processed/crewai-summaries"):
        self.output_base_path = output_base_path
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        logger.info("PDFGeneratorTool initialized", output_path=output_base_path)

    def _setup_custom_styles(self):
        """Set up custom paragraph styles"""
        # Helper to safely add or update style
        def add_style(name, **kwargs):
            if name in self.styles.byName:
                # Update existing style
                for key, value in kwargs.items():
                    setattr(self.styles[name], key, value)
            else:
                # Add new style
                self.styles.add(ParagraphStyle(name=name, **kwargs))

        # Title style
        add_style(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=COLORS["primary"],
            spaceAfter=30,
            alignment=TA_CENTER
        )

        # Section heading
        add_style(
            'SectionHeading',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=COLORS["primary"],
            spaceBefore=20,
            spaceAfter=12,
            borderWidth=0,
            borderColor=COLORS["secondary"],
            borderPadding=5
        )

        # Subsection heading
        add_style(
            'SubsectionHeading',
            parent=self.styles['Heading2'],
            fontSize=13,
            textColor=COLORS["secondary"],
            spaceBefore=15,
            spaceAfter=8
        )

        # Body text - use unique name to avoid conflict with default
        add_style(
            'EmpireBodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=COLORS["dark_text"],
            spaceBefore=6,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leading=14
        )

        # Bullet point
        add_style(
            'BulletPoint',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=COLORS["dark_text"],
            leftIndent=20,
            bulletIndent=10,
            spaceBefore=3,
            spaceAfter=3
        )

        # Key concept highlight
        add_style(
            'KeyConcept',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=COLORS["primary"],
            backColor=COLORS["light_bg"],
            borderWidth=1,
            borderColor=COLORS["secondary"],
            borderPadding=8,
            spaceBefore=10,
            spaceAfter=10
        )

        # Quick reference
        add_style(
            'QuickRef',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=COLORS["dark_text"],
            backColor=HexColor("#edf2f7"),
            leftIndent=10,
            rightIndent=10,
            spaceBefore=5,
            spaceAfter=5
        )

    def generate_pdf(
        self,
        department: str,
        title: str,
        sections: List[SummarySectionContent],
        filename: Optional[str] = None
    ) -> str:
        """
        Generate a PDF document from summary sections.

        Args:
            department: Department code
            title: Document title
            sections: List of section contents
            filename: Optional custom filename

        Returns:
            Path to generated PDF
        """
        # Create output directory
        output_dir = Path(self.output_base_path) / department
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title[:30])
            filename = f"{department}_{safe_title}_{timestamp}.pdf"

        output_path = output_dir / filename

        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Build content
        story = []

        # Title page
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            f"Department: {department.replace('-', ' ').title()}",
            self.styles['EmpireBodyText']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y')}",
            self.styles['EmpireBodyText']
        ))
        story.append(PageBreak())

        # Generate each section
        for section in sections:
            story.extend(self._build_section(section))

        # Footer info
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            "Generated by Empire v7.3 Content Summarizer Agent",
            self.styles['QuickRef']
        ))

        # Build PDF
        doc.build(story)

        logger.info(
            "PDF generated",
            path=str(output_path),
            sections=len(sections)
        )

        return str(output_path)

    def _build_section(self, section: SummarySectionContent) -> List[Flowable]:
        """Build flowables for a section"""
        flowables = []

        # Section heading
        flowables.append(Paragraph(section.title, self.styles['SectionHeading']))

        # Main content
        if section.content:
            # Split into paragraphs
            paragraphs = section.content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    flowables.append(Paragraph(para.strip(), self.styles['EmpireBodyText']))

        # Bullet points
        if section.bullet_points:
            flowables.append(Spacer(1, 0.2*inch))
            bullet_items = []
            for point in section.bullet_points:
                bullet_items.append(ListItem(
                    Paragraph(point, self.styles['BulletPoint']),
                    bulletColor=COLORS["accent"]
                ))
            flowables.append(ListFlowable(
                bullet_items,
                bulletType='bullet',
                start='•'
            ))

        # Tables
        for table_data in section.tables:
            flowables.append(Spacer(1, 0.2*inch))
            flowables.append(self._build_table(table_data))

        # Diagrams
        for diagram_path in section.diagrams:
            if os.path.exists(diagram_path):
                flowables.append(Spacer(1, 0.2*inch))
                img = Image(diagram_path)
                img.drawWidth = 5*inch
                img.drawHeight = 3.5*inch
                flowables.append(img)

        flowables.append(Spacer(1, 0.3*inch))
        return flowables

    def _build_table(self, table_data: Dict[str, Any]) -> Table:
        """Build a styled table from data"""
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        _title = table_data.get("title", "")  # Reserved for future table styling

        # Build data with headers
        data = []
        if headers:
            data.append(headers)
        data.extend(rows)

        if not data:
            data = [["No data"]]

        # Create table
        col_count = len(data[0]) if data else 1
        col_widths = [6*inch / col_count] * col_count

        table = Table(data, colWidths=col_widths)

        # Style the table
        style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), COLORS["primary"]),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), COLORS["light_bg"]),
            ('TEXTCOLOR', (0, 1), (-1, -1), COLORS["dark_text"]),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS["secondary"]),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]

        # Alternate row colors
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_commands.append(
                    ('BACKGROUND', (0, i), (-1, i), white)
                )

        table.setStyle(TableStyle(style_commands))
        return table


# =============================================================================
# DIAGRAM CREATOR TOOL
# =============================================================================

class DiagramCreatorTool:
    """
    Tool for creating visual diagrams using matplotlib.
    """

    def __init__(self, output_base_path: str = "processed/crewai-summaries"):
        self.output_base_path = output_base_path
        logger.info("DiagramCreatorTool initialized")

    def create_diagram(
        self,
        spec: DiagramSpec,
        department: str,
        filename: Optional[str] = None
    ) -> str:
        """
        Create a diagram based on specification.

        Args:
            spec: Diagram specification
            department: Department for output path
            filename: Optional custom filename

        Returns:
            Path to generated diagram image
        """
        # Create output directory
        output_dir = Path(self.output_base_path) / department / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', spec.title[:20])
            filename = f"diagram_{safe_title}_{timestamp}.png"

        output_path = output_dir / filename

        # Generate diagram based on type
        if spec.diagram_type == DiagramType.FLOWCHART:
            self._create_flowchart(spec, str(output_path))
        elif spec.diagram_type == DiagramType.HIERARCHY:
            self._create_hierarchy(spec, str(output_path))
        elif spec.diagram_type == DiagramType.PROCESS:
            self._create_process_diagram(spec, str(output_path))
        elif spec.diagram_type == DiagramType.TIMELINE:
            self._create_timeline(spec, str(output_path))
        elif spec.diagram_type == DiagramType.COMPARISON:
            self._create_comparison(spec, str(output_path))
        else:
            self._create_generic_diagram(spec, str(output_path))

        logger.info(
            "Diagram created",
            type=spec.diagram_type.value,
            path=str(output_path)
        )

        return str(output_path)

    def _create_flowchart(self, spec: DiagramSpec, output_path: str):
        """Create a flowchart diagram"""
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis('off')

        # Title
        ax.text(5, 9.5, spec.title, fontsize=14, fontweight='bold',
                ha='center', va='top', color='#1a365d')

        # Draw elements
        elements = spec.elements
        n_elements = len(elements)

        if n_elements == 0:
            ax.text(5, 5, "No elements defined", ha='center', va='center')
        else:
            # Calculate positions
            y_positions = [8 - i * (7 / max(n_elements - 1, 1)) for i in range(n_elements)]

            for i, elem in enumerate(elements):
                x = 5
                y = y_positions[i] if n_elements > 1 else 5

                # Draw box
                box = FancyBboxPatch(
                    (x - 1.5, y - 0.4), 3, 0.8,
                    boxstyle="round,pad=0.05,rounding_size=0.1",
                    facecolor='#edf2f7',
                    edgecolor='#2b6cb0',
                    linewidth=2
                )
                ax.add_patch(box)

                # Add text
                label = elem.get("label", f"Step {i+1}")
                ax.text(x, y, label, fontsize=9, ha='center', va='center',
                       fontweight='bold', color='#1a365d')

                # Draw arrow to next
                if i < n_elements - 1:
                    next_y = y_positions[i + 1]
                    ax.annotate('', xy=(5, next_y + 0.4), xytext=(5, y - 0.4),
                               arrowprops=dict(arrowstyle='->', color='#2b6cb0', lw=2))

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

    def _create_hierarchy(self, spec: DiagramSpec, output_path: str):
        """Create a hierarchy/tree diagram"""
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.set_xlim(0, 12)
        ax.set_ylim(0, 8)
        ax.axis('off')

        # Title
        ax.text(6, 7.5, spec.title, fontsize=14, fontweight='bold',
                ha='center', va='top', color='#1a365d')

        elements = spec.elements

        # Simple tree layout
        if elements:
            # Root at top
            root = elements[0] if elements else {"label": "Root"}
            self._draw_box(ax, 6, 6, root.get("label", "Root"), is_root=True)

            # Children below
            children = elements[1:] if len(elements) > 1 else []
            n_children = len(children)

            if n_children > 0:
                x_start = 6 - (n_children - 1) * 1.5
                for i, child in enumerate(children):
                    x = x_start + i * 3
                    y = 3.5
                    self._draw_box(ax, x, y, child.get("label", f"Item {i+1}"))
                    # Connect to root
                    ax.plot([6, x], [5.5, 4], color='#2b6cb0', linewidth=1.5)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

    def _create_process_diagram(self, spec: DiagramSpec, output_path: str):
        """Create a horizontal process flow diagram"""
        fig, ax = plt.subplots(figsize=(12, 4))
        elements = spec.elements
        n = len(elements)

        ax.set_xlim(-0.5, n + 0.5)
        ax.set_ylim(-0.5, 1.5)
        ax.axis('off')

        # Title
        ax.text(n/2, 1.3, spec.title, fontsize=14, fontweight='bold',
                ha='center', va='bottom', color='#1a365d')

        for i, elem in enumerate(elements):
            # Draw circle/box
            circle = plt.Circle((i, 0.5), 0.3, facecolor='#2b6cb0',
                               edgecolor='#1a365d', linewidth=2)
            ax.add_patch(circle)

            # Step number
            ax.text(i, 0.5, str(i + 1), fontsize=12, ha='center', va='center',
                   fontweight='bold', color='white')

            # Label below
            label = elem.get("label", f"Step {i+1}")
            ax.text(i, 0, label, fontsize=9, ha='center', va='top',
                   color='#1a365d', wrap=True)

            # Arrow to next
            if i < n - 1:
                ax.annotate('', xy=(i + 0.7, 0.5), xytext=(i + 0.35, 0.5),
                           arrowprops=dict(arrowstyle='->', color='#38a169', lw=2))

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

    def _create_timeline(self, spec: DiagramSpec, output_path: str):
        """Create a timeline diagram"""
        fig, ax = plt.subplots(figsize=(12, 3))
        elements = spec.elements
        n = len(elements)

        ax.set_xlim(-0.5, n)
        ax.set_ylim(-1, 1.5)
        ax.axis('off')

        # Title
        ax.text(n/2 - 0.5, 1.3, spec.title, fontsize=14, fontweight='bold',
                ha='center', va='bottom', color='#1a365d')

        # Draw timeline line
        ax.plot([-0.3, n - 0.7], [0.5, 0.5], color='#2b6cb0', linewidth=3)

        for i, elem in enumerate(elements):
            # Marker
            ax.plot(i, 0.5, 'o', markersize=12, color='#38a169',
                   markeredgecolor='#1a365d', markeredgewidth=2)

            # Label above/below alternating
            y_offset = 0.3 if i % 2 == 0 else -0.3
            va = 'bottom' if i % 2 == 0 else 'top'

            label = elem.get("label", f"Event {i+1}")
            ax.text(i, 0.5 + y_offset, label, fontsize=9, ha='center', va=va,
                   color='#1a365d')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

    def _create_comparison(self, spec: DiagramSpec, output_path: str):
        """Create a comparison table/diagram"""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')

        # Title
        ax.text(0.5, 0.95, spec.title, fontsize=14, fontweight='bold',
                ha='center', va='top', transform=ax.transAxes, color='#1a365d')

        elements = spec.elements
        if len(elements) >= 2:
            # Side by side comparison
            left = elements[0]
            right = elements[1]

            # Left box
            left_box = FancyBboxPatch(
                (0.05, 0.2), 0.4, 0.6,
                boxstyle="round,pad=0.02",
                facecolor='#e6fffa',
                edgecolor='#38a169',
                linewidth=2,
                transform=ax.transAxes
            )
            ax.add_patch(left_box)
            ax.text(0.25, 0.75, left.get("label", "Option A"),
                   fontsize=12, fontweight='bold', ha='center', va='center',
                   transform=ax.transAxes, color='#1a365d')

            # Right box
            right_box = FancyBboxPatch(
                (0.55, 0.2), 0.4, 0.6,
                boxstyle="round,pad=0.02",
                facecolor='#ebf8ff',
                edgecolor='#2b6cb0',
                linewidth=2,
                transform=ax.transAxes
            )
            ax.add_patch(right_box)
            ax.text(0.75, 0.75, right.get("label", "Option B"),
                   fontsize=12, fontweight='bold', ha='center', va='center',
                   transform=ax.transAxes, color='#1a365d')

            # VS in middle
            ax.text(0.5, 0.5, "VS", fontsize=16, fontweight='bold',
                   ha='center', va='center', transform=ax.transAxes,
                   color='#718096')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

    def _create_generic_diagram(self, spec: DiagramSpec, output_path: str):
        """Create a generic diagram with boxes"""
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.axis('off')

        ax.text(0.5, 0.95, spec.title, fontsize=14, fontweight='bold',
                ha='center', va='top', transform=ax.transAxes, color='#1a365d')

        elements = spec.elements
        n = len(elements)

        # Grid layout
        cols = min(3, n)
        _rows = (n + cols - 1) // cols  # Used for layout calculation

        for i, elem in enumerate(elements):
            row = i // cols
            col = i % cols

            x = 0.2 + col * 0.3
            y = 0.7 - row * 0.25

            box = FancyBboxPatch(
                (x - 0.1, y - 0.08), 0.2, 0.15,
                boxstyle="round,pad=0.02",
                facecolor='#edf2f7',
                edgecolor='#2b6cb0',
                linewidth=2,
                transform=ax.transAxes
            )
            ax.add_patch(box)

            label = elem.get("label", f"Item {i+1}")
            ax.text(x, y, label, fontsize=9, ha='center', va='center',
                   transform=ax.transAxes, color='#1a365d')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

    def _draw_box(self, ax, x, y, text, is_root=False):
        """Helper to draw a labeled box"""
        width = 2.5
        height = 0.8

        color = '#1a365d' if is_root else '#2b6cb0'
        bg_color = '#e6fffa' if is_root else '#edf2f7'

        box = FancyBboxPatch(
            (x - width/2, y - height/2), width, height,
            boxstyle="round,pad=0.05",
            facecolor=bg_color,
            edgecolor=color,
            linewidth=2
        )
        ax.add_patch(box)

        ax.text(x, y, text, fontsize=10, ha='center', va='center',
               fontweight='bold', color=color)


# =============================================================================
# CHART BUILDER TOOL
# =============================================================================

class ChartBuilderTool:
    """
    Tool for creating charts (bar charts, pie charts, etc.)
    """

    def __init__(self, output_base_path: str = "processed/crewai-summaries"):
        self.output_base_path = output_base_path
        logger.info("ChartBuilderTool initialized")

    def create_bar_chart(
        self,
        title: str,
        labels: List[str],
        values: List[float],
        department: str,
        filename: Optional[str] = None,
        ylabel: str = "Value"
    ) -> str:
        """Create a bar chart"""
        output_dir = Path(self.output_base_path) / department / "charts"
        output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"bar_chart_{timestamp}.png"

        output_path = output_dir / filename

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = ['#2b6cb0', '#38a169', '#dd6b20', '#e53e3e', '#805ad5']
        bar_colors = [colors[i % len(colors)] for i in range(len(labels))]

        bars = ax.bar(labels, values, color=bar_colors, edgecolor='white', linewidth=1.5)

        ax.set_title(title, fontsize=14, fontweight='bold', color='#1a365d', pad=20)
        ax.set_ylabel(ylabel, fontsize=10, color='#1a365d')
        ax.set_xlabel('')

        # Style
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#718096')
        ax.spines['bottom'].set_color('#718096')
        ax.tick_params(colors='#718096')

        # Value labels on bars
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                   f'{val:.1f}', ha='center', va='bottom', fontsize=9, color='#1a365d')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(str(output_path), dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

        logger.info("Bar chart created", path=str(output_path))
        return str(output_path)

    def create_pie_chart(
        self,
        title: str,
        labels: List[str],
        values: List[float],
        department: str,
        filename: Optional[str] = None
    ) -> str:
        """Create a pie chart"""
        output_dir = Path(self.output_base_path) / department / "charts"
        output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"pie_chart_{timestamp}.png"

        output_path = output_dir / filename

        fig, ax = plt.subplots(figsize=(10, 8))

        colors = ['#2b6cb0', '#38a169', '#dd6b20', '#e53e3e', '#805ad5',
                  '#319795', '#d53f8c', '#718096']

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors[:len(values)],
            explode=[0.02] * len(values),
            shadow=False,
            startangle=90
        )

        # Style
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(9)

        for text in texts:
            text.set_color('#1a365d')
            text.set_fontsize(10)

        ax.set_title(title, fontsize=14, fontweight='bold', color='#1a365d', pad=20)

        plt.tight_layout()
        plt.savefig(str(output_path), dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

        logger.info("Pie chart created", path=str(output_path))
        return str(output_path)


# =============================================================================
# CONTENT SUMMARIZER AGENT SERVICE
# =============================================================================

class ContentSummarizerAgentService:
    """
    AGENT-002: Content Summarizer Agent

    Generates comprehensive PDF summaries with:
    - Executive summary
    - Key concepts
    - Detailed breakdowns
    - Visual diagrams
    - Implementation guides
    - Quick reference sections

    LLM: Claude Sonnet 4.5
    """

    def __init__(self, output_base_path: str = "processed/crewai-summaries"):
        """Initialize the Content Summarizer Agent"""
        self.output_base_path = output_base_path

        # Initialize tools
        self.pdf_generator = PDFGeneratorTool(output_base_path)
        self.diagram_creator = DiagramCreatorTool(output_base_path)
        self.chart_builder = ChartBuilderTool(output_base_path)

        # Initialize LLM with circuit breaker for resilience
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm = ResilientAnthropicClient(
            api_key=api_key,
            service_name="content_summarizer",
            failure_threshold=5,
            recovery_timeout=60.0,
        ) if api_key else None

        # Statistics
        self.stats = {
            "summaries_generated": 0,
            "diagrams_created": 0,
            "charts_created": 0,
            "by_department": {}
        }

        logger.info(
            "ContentSummarizerAgentService (AGENT-002) initialized",
            output_path=output_base_path,
            llm_available=self.llm is not None
        )

    async def generate_summary(
        self,
        content: str,
        department: str,
        title: str,
        source_type: str = "document",
        metadata: Optional[Dict[str, Any]] = None
    ) -> SummaryGenerationResult:
        """
        Generate a comprehensive PDF summary.

        Args:
            content: Source content to summarize
            department: Target department
            title: Summary title
            source_type: Type of source (document, video, course, etc.)
            metadata: Additional metadata

        Returns:
            SummaryGenerationResult with PDF path and stats
        """
        start_time = datetime.now()

        logger.info(
            "AGENT-002 summary generation started",
            department=department,
            title=title,
            content_length=len(content)
        )

        try:
            # Step 1: Extract and structure content
            extracted = await self._extract_content(content, title, source_type)

            # Step 2: Generate section contents using LLM
            sections = await self._generate_sections(extracted, department)

            # Step 3: Create visual diagrams
            diagram_paths = await self._create_diagrams(extracted, department)

            # Add diagrams to appropriate sections
            for section in sections:
                if section.section_type == SummarySection.VISUAL_ELEMENTS:
                    section.diagrams = diagram_paths

            # Step 4: Generate PDF
            pdf_path = self.pdf_generator.generate_pdf(
                department=department,
                title=title,
                sections=sections
            )

            # Update stats
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_stats(department, len(diagram_paths))

            result = SummaryGenerationResult(
                success=True,
                pdf_path=pdf_path,
                department=department,
                title=title,
                sections_generated=[s.section_type.value for s in sections],
                diagrams_generated=len(diagram_paths),
                tables_generated=sum(len(s.tables) for s in sections),
                processing_time_seconds=processing_time,
                metadata={
                    "source_type": source_type,
                    "content_length": len(content),
                    "extracted_concepts": len(extracted.key_concepts),
                    "agent_id": "AGENT-002",
                    "timestamp": datetime.now().isoformat()
                }
            )

            logger.info(
                "AGENT-002 summary generation complete",
                pdf_path=pdf_path,
                processing_time=f"{processing_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error("AGENT-002 summary generation failed", error=str(e))
            return SummaryGenerationResult(
                success=False,
                department=department,
                title=title,
                error=str(e),
                processing_time_seconds=(datetime.now() - start_time).total_seconds()
            )

    async def _extract_content(
        self,
        content: str,
        title: str,
        source_type: str
    ) -> ExtractedContent:
        """Extract and structure content from source"""

        # Basic extraction
        word_count = len(content.split())

        # Extract sections (headings)
        sections = []
        section_pattern = r'^#+\s*(.+)|^([A-Z][^.!?]*:)'
        for match in re.finditer(section_pattern, content, re.MULTILINE):
            heading = match.group(1) or match.group(2)
            if heading:
                sections.append({
                    "title": heading.strip(':'),
                    "position": match.start()
                })

        # Extract key concepts using LLM if available
        key_concepts = []
        implementation_steps = []
        frameworks = []

        if self.llm:
            try:
                # Use LLM to extract key concepts
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250514",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": f"""Analyze this content and extract:
1. Key concepts (list 5-10 main ideas)
2. Implementation steps (if applicable, list 3-7 steps)
3. Frameworks or models mentioned (list any)

Content:
{content[:8000]}

Respond in this exact JSON format:
{{"key_concepts": ["concept1", "concept2"], "implementation_steps": ["step1", "step2"], "frameworks": [{{"name": "Framework Name", "description": "Brief description"}}]}}"""
                    }]
                )

                # Parse response
                response_text = response.content[0].text
                if "{" in response_text:
                    json_str = response_text[response_text.find("{"):response_text.rfind("}")+1]
                    import json
                    parsed = json.loads(json_str)
                    key_concepts = parsed.get("key_concepts", [])
                    implementation_steps = parsed.get("implementation_steps", [])
                    frameworks = parsed.get("frameworks", [])

            except Exception as e:
                logger.warning("LLM extraction failed", error=str(e))

        # Fallback extraction if LLM failed
        if not key_concepts:
            # Simple keyword extraction
            words = content.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 5:
                    word_freq[word] = word_freq.get(word, 0) + 1
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            key_concepts = [w[0].title() for w in sorted_words[:10]]

        # Extract tables (simple pattern)
        tables = []
        table_pattern = r'\|[^|]+\|'
        if re.search(table_pattern, content):
            tables.append({"title": "Extracted Table", "data": "See content"})

        return ExtractedContent(
            title=title,
            source_type=source_type,
            word_count=word_count,
            sections=sections,
            tables=tables,
            frameworks=frameworks,
            key_concepts=key_concepts,
            implementation_steps=implementation_steps,
            metadata={"extraction_timestamp": datetime.now().isoformat()}
        )

    async def _generate_sections(
        self,
        extracted: ExtractedContent,
        department: str
    ) -> List[SummarySectionContent]:
        """Generate content for each summary section"""
        sections = []

        # Executive Summary
        exec_summary = await self._generate_executive_summary(extracted)
        sections.append(SummarySectionContent(
            section_type=SummarySection.EXECUTIVE_SUMMARY,
            title="Executive Summary",
            content=exec_summary,
            bullet_points=[]
        ))

        # Key Concepts
        if extracted.key_concepts:
            sections.append(SummarySectionContent(
                section_type=SummarySection.KEY_CONCEPTS,
                title="Key Concepts",
                content="The following key concepts are covered in this material:",
                bullet_points=extracted.key_concepts
            ))

        # Detailed Breakdown
        if extracted.sections:
            section_list = [s["title"] for s in extracted.sections[:10]]
            sections.append(SummarySectionContent(
                section_type=SummarySection.DETAILED_BREAKDOWN,
                title="Content Structure",
                content="This material is organized into the following sections:",
                bullet_points=section_list
            ))

        # Frameworks
        if extracted.frameworks:
            framework_content = "The following frameworks and models are discussed:"
            framework_bullets = [
                f"{f.get('name', 'Framework')}: {f.get('description', 'No description')}"
                for f in extracted.frameworks
            ]
            sections.append(SummarySectionContent(
                section_type=SummarySection.FRAMEWORKS,
                title="Frameworks & Models",
                content=framework_content,
                bullet_points=framework_bullets
            ))

        # Implementation Guide
        if extracted.implementation_steps:
            sections.append(SummarySectionContent(
                section_type=SummarySection.IMPLEMENTATION_GUIDE,
                title="Implementation Guide",
                content="Follow these steps to implement the concepts:",
                bullet_points=[
                    f"Step {i+1}: {step}"
                    for i, step in enumerate(extracted.implementation_steps)
                ]
            ))

        # Quick Reference
        quick_ref = await self._generate_quick_reference(extracted)
        sections.append(SummarySectionContent(
            section_type=SummarySection.QUICK_REFERENCE,
            title="Quick Reference",
            content=quick_ref,
            bullet_points=[]
        ))

        # Visual Elements placeholder
        sections.append(SummarySectionContent(
            section_type=SummarySection.VISUAL_ELEMENTS,
            title="Visual Diagrams",
            content="The following diagrams illustrate the key concepts:",
            bullet_points=[],
            diagrams=[]  # Will be populated later
        ))

        return sections

    async def _generate_executive_summary(self, extracted: ExtractedContent) -> str:
        """Generate executive summary using LLM"""
        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250514",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": f"""Write a concise executive summary (2-3 paragraphs) for this content.

Title: {extracted.title}
Type: {extracted.source_type}
Word Count: {extracted.word_count}
Key Concepts: {', '.join(extracted.key_concepts[:5])}

The summary should:
1. Explain what the content covers
2. Highlight the main value/takeaways
3. Identify the target audience

Write in a professional, business tone."""
                    }]
                )
                return response.content[0].text
            except Exception as e:
                logger.warning("LLM summary generation failed", error=str(e))

        # Fallback
        return f"""This {extracted.source_type} titled "{extracted.title}" provides comprehensive coverage of key business and technical concepts. The material spans approximately {extracted.word_count} words and covers {len(extracted.key_concepts)} main topics.

Key areas of focus include: {', '.join(extracted.key_concepts[:5])}. The content is designed to provide actionable insights and practical guidance for professionals in this domain."""

    async def _generate_quick_reference(self, extracted: ExtractedContent) -> str:
        """Generate quick reference content"""
        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250514",
                    max_tokens=400,
                    messages=[{
                        "role": "user",
                        "content": f"""Create a brief quick reference section (1-2 paragraphs) summarizing the most important points from:

Title: {extracted.title}
Key Concepts: {', '.join(extracted.key_concepts[:5])}
Frameworks: {', '.join([f.get('name', '') for f in extracted.frameworks[:3]])}

Focus on actionable takeaways that readers can reference quickly."""
                    }]
                )
                return response.content[0].text
            except Exception as e:
                logger.warning("LLM quick reference failed", error=str(e))

        return f"Key topics: {', '.join(extracted.key_concepts[:5])}. Refer to the detailed sections above for comprehensive information."

    async def _create_diagrams(
        self,
        extracted: ExtractedContent,
        department: str
    ) -> List[str]:
        """Create visual diagrams based on extracted content"""
        diagram_paths = []

        # Create process diagram if implementation steps exist
        if extracted.implementation_steps and len(extracted.implementation_steps) >= 2:
            spec = DiagramSpec(
                diagram_type=DiagramType.PROCESS,
                title="Implementation Process",
                elements=[
                    {"label": step[:30] + "..." if len(step) > 30 else step}
                    for step in extracted.implementation_steps[:6]
                ]
            )
            path = self.diagram_creator.create_diagram(spec, department)
            diagram_paths.append(path)

        # Create hierarchy diagram if frameworks exist
        if extracted.frameworks and len(extracted.frameworks) >= 1:
            elements = [{"label": extracted.title[:25]}]
            elements.extend([
                {"label": f.get("name", "Framework")[:20]}
                for f in extracted.frameworks[:4]
            ])

            spec = DiagramSpec(
                diagram_type=DiagramType.HIERARCHY,
                title="Framework Overview",
                elements=elements
            )
            path = self.diagram_creator.create_diagram(spec, department)
            diagram_paths.append(path)

        # Create flowchart for key concepts if enough exist
        if len(extracted.key_concepts) >= 3:
            spec = DiagramSpec(
                diagram_type=DiagramType.FLOWCHART,
                title="Key Concepts Flow",
                elements=[
                    {"label": concept[:25]}
                    for concept in extracted.key_concepts[:5]
                ]
            )
            path = self.diagram_creator.create_diagram(spec, department)
            diagram_paths.append(path)

        return diagram_paths

    def _update_stats(self, department: str, diagrams: int):
        """Update processing statistics"""
        self.stats["summaries_generated"] += 1
        self.stats["diagrams_created"] += diagrams

        if department not in self.stats["by_department"]:
            self.stats["by_department"][department] = 0
        self.stats["by_department"][department] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            "agent_id": "AGENT-002",
            "agent_name": "Content Summarizer Agent"
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_content_summarizer_agent(
    output_path: str = "processed/crewai-summaries"
) -> ContentSummarizerAgentService:
    """Factory function to create content summarizer agent"""
    return ContentSummarizerAgentService(output_path)


async def generate_summary_async(
    content: str,
    department: str,
    title: str,
    source_type: str = "document"
) -> SummaryGenerationResult:
    """Convenience function for async summary generation"""
    agent = create_content_summarizer_agent()
    return await agent.generate_summary(content, department, title, source_type)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_content_summarizer_service: Optional[ContentSummarizerAgentService] = None


def get_content_summarizer_service() -> ContentSummarizerAgentService:
    """Get singleton instance of ContentSummarizerAgentService"""
    global _content_summarizer_service
    if _content_summarizer_service is None:
        _content_summarizer_service = ContentSummarizerAgentService()
    return _content_summarizer_service


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    # asyncio already imported at module level

    async def test():
        """Test the Content Summarizer Agent"""
        agent = create_content_summarizer_agent()

        # Test content
        test_content = """
        # Advanced Sales Pipeline Management Framework

        ## Introduction
        This comprehensive training module covers sophisticated techniques for
        managing enterprise B2B sales pipelines. The content is designed for
        sales managers and directors looking to optimize their pipeline operations.

        ## Module 1: Pipeline Fundamentals
        Understanding the basics of pipeline management is crucial. Key metrics include:
        - Conversion rates at each stage
        - Average deal size
        - Sales cycle length
        - Win rate by segment

        ## Module 2: Lead Scoring
        Effective lead scoring uses both demographic and behavioral signals:

        | Factor | Weight | Description |
        |--------|--------|-------------|
        | Company Size | 25% | Enterprise vs SMB |
        | Engagement | 30% | Website visits, downloads |
        | Budget | 20% | Stated budget range |
        | Timeline | 25% | Purchase timeframe |

        ## Module 3: Forecasting Methods

        ### MEDDIC Framework
        The MEDDIC qualification framework helps ensure deal quality:
        - Metrics: What are the quantified benefits?
        - Economic Buyer: Who controls the budget?
        - Decision Criteria: How will they decide?
        - Decision Process: What steps are involved?
        - Identify Pain: What problem are we solving?
        - Champion: Who is our internal advocate?

        ### Pipeline Velocity Formula
        Pipeline Velocity = (Opportunities × Avg Deal Size × Win Rate) / Sales Cycle Length

        ## Implementation Steps

        1. Audit your current pipeline stages and definitions
        2. Implement consistent lead scoring criteria
        3. Train team on qualification frameworks
        4. Set up automated reporting dashboards
        5. Establish weekly pipeline review cadence
        6. Monitor and optimize conversion rates

        ## Conclusion
        Effective pipeline management requires consistent methodology, good data hygiene,
        and regular optimization. By implementing these frameworks, teams typically see
        20-30% improvement in forecast accuracy within 6 months.
        """

        result = await agent.generate_summary(
            content=test_content,
            department="sales-marketing",
            title="Advanced Sales Pipeline Management",
            source_type="course"
        )

        print("\n" + "="*70)
        print("AGENT-002 SUMMARY GENERATION RESULT")
        print("="*70)
        print(f"\nSuccess: {result.success}")
        print(f"PDF Path: {result.pdf_path}")
        print(f"Department: {result.department}")
        print(f"Sections Generated: {result.sections_generated}")
        print(f"Diagrams Generated: {result.diagrams_generated}")
        print(f"Tables Generated: {result.tables_generated}")
        print(f"Processing Time: {result.processing_time_seconds:.2f}s")

        if result.error:
            print(f"Error: {result.error}")

        # Print stats
        print("\n=== Statistics ===")
        import json
        print(json.dumps(agent.get_stats(), indent=2))

    asyncio.run(test())
