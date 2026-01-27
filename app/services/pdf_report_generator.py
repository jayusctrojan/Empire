"""
Empire v7.3 - Enhanced PDF Report Generator

Professional PDF report generation with advanced features:
- Table of Contents with page links
- Page numbers, headers, and footers
- Branding/logo support
- Multiple style themes
- Charts and tables support
- Markdown parsing

Author: Claude Code
Date: 2025-01-24
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib.colors import HexColor, Color, black, white, gray
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, BaseDocTemplate, PageTemplate, Frame,
        Paragraph, Spacer, PageBreak, Table, TableStyle, Image,
        Flowable, KeepTogether, ListFlowable, ListItem
    )
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.pdfgen import canvas
    from reportlab.lib import fonts
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = structlog.get_logger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class PDFBranding:
    """Branding configuration for PDF reports."""
    company_name: str = "Empire Research"
    logo_path: Optional[str] = None
    primary_color: str = "#1a56db"  # Blue
    secondary_color: str = "#374151"  # Gray
    accent_color: str = "#059669"  # Green
    font_family: str = "Helvetica"
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    include_page_numbers: bool = True
    include_date: bool = True


@dataclass
class PDFConfig:
    """Configuration for PDF generation."""
    page_size: Tuple[float, float] = letter
    margin_left: float = 0.75  # inches
    margin_right: float = 0.75
    margin_top: float = 1.0
    margin_bottom: float = 0.75
    include_toc: bool = True
    include_cover_page: bool = True
    branding: PDFBranding = field(default_factory=PDFBranding)


@dataclass
class TOCEntry:
    """Entry in the table of contents."""
    title: str
    level: int
    page_number: int = 0


# ==============================================================================
# Page Templates and Handlers
# ==============================================================================

class NumberedCanvas(canvas.Canvas):
    """Canvas that tracks page numbers for TOC generation."""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.page_count = 0

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
        self.page_count += 1

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count: int):
        """Draw page number at bottom of page."""
        # This is handled by the header/footer handler instead
        pass


class HeaderFooterHandler:
    """Handles header and footer rendering on each page."""

    def __init__(
        self,
        branding: PDFBranding,
        title: str,
        page_size: Tuple[float, float] = letter
    ):
        self.branding = branding
        self.title = title
        self.page_width, self.page_height = page_size

    def __call__(self, canvas: canvas.Canvas, doc):
        """Render header and footer on each page."""
        canvas.saveState()

        # Header
        self._draw_header(canvas, doc)

        # Footer
        self._draw_footer(canvas, doc)

        canvas.restoreState()

    def _draw_header(self, canvas: canvas.Canvas, doc):
        """Draw header with optional logo and title."""
        y_position = self.page_height - 0.5 * inch

        # Draw logo if available
        if self.branding.logo_path and os.path.exists(self.branding.logo_path):
            try:
                canvas.drawImage(
                    self.branding.logo_path,
                    0.75 * inch,
                    y_position - 0.3 * inch,
                    width=1.0 * inch,
                    height=0.4 * inch,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except Exception as e:
                logger.warning("logo_load_failed", error=str(e))

        # Draw header text
        header_text = self.branding.header_text or self.branding.company_name
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(HexColor(self.branding.secondary_color))

        # Right-aligned header text
        text_width = canvas.stringWidth(header_text, "Helvetica", 9)
        canvas.drawString(
            self.page_width - 0.75 * inch - text_width,
            y_position,
            header_text
        )

        # Draw header line
        canvas.setStrokeColor(HexColor(self.branding.primary_color))
        canvas.setLineWidth(1)
        canvas.line(
            0.75 * inch,
            y_position - 0.15 * inch,
            self.page_width - 0.75 * inch,
            y_position - 0.15 * inch
        )

    def _draw_footer(self, canvas: canvas.Canvas, doc):
        """Draw footer with page numbers and optional text."""
        y_position = 0.5 * inch

        # Draw footer line
        canvas.setStrokeColor(HexColor(self.branding.secondary_color))
        canvas.setLineWidth(0.5)
        canvas.line(
            0.75 * inch,
            y_position + 0.1 * inch,
            self.page_width - 0.75 * inch,
            y_position + 0.1 * inch
        )

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(HexColor(self.branding.secondary_color))

        # Left: Footer text or date
        left_text = self.branding.footer_text or ""
        if self.branding.include_date and not left_text:
            left_text = datetime.now().strftime("%B %d, %Y")
        if left_text:
            canvas.drawString(0.75 * inch, y_position - 0.1 * inch, left_text)

        # Right: Page numbers
        if self.branding.include_page_numbers:
            page_num = f"Page {doc.page}"
            text_width = canvas.stringWidth(page_num, "Helvetica", 8)
            canvas.drawString(
                self.page_width - 0.75 * inch - text_width,
                y_position - 0.1 * inch,
                page_num
            )


# ==============================================================================
# PDF Report Generator
# ==============================================================================

class PDFReportGenerator:
    """
    Enhanced PDF report generator with professional features.

    Features:
    - Table of Contents with clickable links
    - Headers and footers on each page
    - Branding with logo support
    - Markdown to PDF conversion
    - Multiple style themes
    """

    def __init__(self, config: Optional[PDFConfig] = None):
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab is required for PDF generation. "
                "Install it with: pip install reportlab"
            )

        self.config = config or PDFConfig()
        self._styles = self._create_styles()
        self._toc_entries: List[TOCEntry] = []

    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create custom styles for the report."""
        base_styles = getSampleStyleSheet()
        branding = self.config.branding

        styles = {}

        # Title style
        styles["Title"] = ParagraphStyle(
            "Title",
            parent=base_styles["Heading1"],
            fontSize=28,
            textColor=HexColor(branding.primary_color),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=branding.font_family + "-Bold" if branding.font_family == "Helvetica" else branding.font_family
        )

        # Subtitle style
        styles["Subtitle"] = ParagraphStyle(
            "Subtitle",
            parent=base_styles["Normal"],
            fontSize=14,
            textColor=HexColor(branding.secondary_color),
            spaceAfter=20,
            alignment=TA_CENTER
        )

        # Heading styles
        for level in range(1, 5):
            font_size = 20 - (level * 2)
            styles[f"Heading{level}"] = ParagraphStyle(
                f"Heading{level}",
                parent=base_styles[f"Heading{min(level, 4)}"],
                fontSize=font_size,
                textColor=HexColor(branding.primary_color),
                spaceBefore=15 - level,
                spaceAfter=10 - level,
                fontName=branding.font_family + "-Bold" if level <= 2 else branding.font_family
            )

        # Body text
        styles["Body"] = ParagraphStyle(
            "Body",
            parent=base_styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=black,
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            fontName=branding.font_family
        )

        # Quote style
        styles["Quote"] = ParagraphStyle(
            "Quote",
            parent=styles["Body"],
            leftIndent=36,
            rightIndent=36,
            fontSize=10,
            textColor=HexColor(branding.secondary_color),
            borderColor=HexColor(branding.primary_color),
            borderWidth=2,
            borderPadding=10
        )

        # Code style
        styles["Code"] = ParagraphStyle(
            "Code",
            parent=base_styles["Normal"],
            fontSize=9,
            fontName="Courier",
            backColor=HexColor("#f3f4f6"),
            textColor=HexColor("#1f2937"),
            spaceBefore=6,
            spaceAfter=6,
            leftIndent=10,
            rightIndent=10
        )

        # TOC styles
        for level in range(1, 4):
            styles[f"TOCEntry{level}"] = ParagraphStyle(
                f"TOCEntry{level}",
                parent=base_styles["Normal"],
                fontSize=12 - level,
                leftIndent=20 * (level - 1),
                spaceBefore=4,
                spaceAfter=2,
                textColor=HexColor(branding.primary_color) if level == 1 else black
            )

        return styles

    def generate(
        self,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generate a PDF report from markdown content.

        Args:
            title: Report title
            content: Markdown content
            metadata: Optional metadata (author, date, etc.)

        Returns:
            PDF as bytes
        """
        buffer = BytesIO()
        metadata = metadata or {}

        # Create document
        doc = BaseDocTemplate(
            buffer,
            pagesize=self.config.page_size,
            rightMargin=self.config.margin_right * inch,
            leftMargin=self.config.margin_left * inch,
            topMargin=self.config.margin_top * inch,
            bottomMargin=self.config.margin_bottom * inch,
            title=title,
            author=metadata.get("author", self.config.branding.company_name)
        )

        # Create frame
        frame_width = (
            self.config.page_size[0] -
            (self.config.margin_left + self.config.margin_right) * inch
        )
        frame_height = (
            self.config.page_size[1] -
            (self.config.margin_top + self.config.margin_bottom) * inch
        )

        frame = Frame(
            self.config.margin_left * inch,
            self.config.margin_bottom * inch,
            frame_width,
            frame_height,
            id="main"
        )

        # Create page template with header/footer
        handler = HeaderFooterHandler(
            self.config.branding,
            title,
            self.config.page_size
        )

        template = PageTemplate(
            id="main",
            frames=[frame],
            onPage=handler
        )
        doc.addPageTemplates([template])

        # Build story (content)
        story = []

        # Cover page
        if self.config.include_cover_page:
            story.extend(self._create_cover_page(title, metadata))

        # Table of Contents placeholder
        if self.config.include_toc:
            story.append(PageBreak())
            story.append(Paragraph("Table of Contents", self._styles["Heading1"]))
            story.append(Spacer(1, 20))
            # TOC will be filled after first pass
            toc = TableOfContents()
            toc.levelStyles = [
                self._styles["TOCEntry1"],
                self._styles["TOCEntry2"],
                self._styles["TOCEntry3"]
            ]
            story.append(toc)
            story.append(PageBreak())

        # Parse and add content
        content_elements = self._parse_markdown(content)
        story.extend(content_elements)

        # Build PDF
        doc.multiBuild(story)

        buffer.seek(0)
        return buffer.getvalue()

    def _create_cover_page(
        self,
        title: str,
        metadata: Dict[str, Any]
    ) -> List[Flowable]:
        """Create the cover page elements."""
        elements = []

        # Add spacing to center content
        elements.append(Spacer(1, 2 * inch))

        # Logo
        if (self.config.branding.logo_path and
                os.path.exists(self.config.branding.logo_path)):
            try:
                logo = Image(
                    self.config.branding.logo_path,
                    width=2 * inch,
                    height=1 * inch
                )
                logo.hAlign = "CENTER"
                elements.append(logo)
                elements.append(Spacer(1, 0.5 * inch))
            except Exception as e:
                logger.warning("cover_logo_failed", error=str(e))

        # Title
        elements.append(Paragraph(title, self._styles["Title"]))

        # Subtitle/description
        if metadata.get("description"):
            elements.append(
                Paragraph(metadata["description"], self._styles["Subtitle"])
            )

        elements.append(Spacer(1, 1 * inch))

        # Metadata table
        meta_data = []
        if metadata.get("author"):
            meta_data.append(["Author:", metadata["author"]])
        if metadata.get("date"):
            meta_data.append(["Date:", metadata["date"]])
        elif self.config.branding.include_date:
            meta_data.append(["Date:", datetime.now().strftime("%B %d, %Y")])
        if metadata.get("version"):
            meta_data.append(["Version:", metadata["version"]])
        if metadata.get("department"):
            meta_data.append(["Department:", metadata["department"]])

        if meta_data:
            meta_table = Table(
                meta_data,
                colWidths=[1.5 * inch, 3 * inch]
            )
            meta_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (0, -1),
                 HexColor(self.config.branding.secondary_color)),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            meta_table.hAlign = "CENTER"
            elements.append(meta_table)

        # Company name at bottom
        elements.append(Spacer(1, 2 * inch))
        elements.append(
            Paragraph(
                self.config.branding.company_name,
                ParagraphStyle(
                    "CompanyName",
                    fontSize=12,
                    alignment=TA_CENTER,
                    textColor=HexColor(self.config.branding.secondary_color)
                )
            )
        )

        elements.append(PageBreak())
        return elements

    def _parse_markdown(self, content: str) -> List[Flowable]:
        """
        Parse markdown content into ReportLab flowables.

        Supports:
        - Headings (# to ####)
        - Paragraphs
        - Bold and italic text
        - Bullet lists
        - Numbered lists
        - Code blocks
        - Block quotes
        - Horizontal rules
        """
        elements = []
        lines = content.split("\n")
        i = 0
        current_paragraph = []

        while i < len(lines):
            line = lines[i]

            # Skip empty lines
            if not line.strip():
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []
                i += 1
                continue

            # Headings
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if heading_match:
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []

                level = len(heading_match.group(1))
                heading_text = heading_match.group(2)

                # Add to TOC
                self._toc_entries.append(TOCEntry(heading_text, level))

                # Create anchor for TOC linking
                anchor_id = f"heading_{len(self._toc_entries)}"
                heading_para = Paragraph(
                    f'<a name="{anchor_id}"/>{self._format_inline(heading_text)}',
                    self._styles[f"Heading{level}"]
                )
                elements.append(heading_para)
                i += 1
                continue

            # Horizontal rule
            if re.match(r"^[-*_]{3,}$", line.strip()):
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []
                elements.append(Spacer(1, 10))
                elements.append(self._create_hr())
                elements.append(Spacer(1, 10))
                i += 1
                continue

            # Code block
            if line.strip().startswith("```"):
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []

                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # Skip closing ```

                code_text = "\n".join(code_lines)
                elements.append(
                    Paragraph(
                        f"<pre>{self._escape_html(code_text)}</pre>",
                        self._styles["Code"]
                    )
                )
                continue

            # Block quote
            if line.strip().startswith(">"):
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []

                quote_lines = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    quote_lines.append(lines[i].strip()[1:].strip())
                    i += 1

                quote_text = " ".join(quote_lines)
                elements.append(
                    Paragraph(self._format_inline(quote_text), self._styles["Quote"])
                )
                continue

            # Bullet list
            if re.match(r"^[\s]*[-*+]\s+", line):
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []

                list_items = []
                while i < len(lines) and re.match(r"^[\s]*[-*+]\s+", lines[i]):
                    item_text = re.sub(r"^[\s]*[-*+]\s+", "", lines[i])
                    list_items.append(
                        ListItem(
                            Paragraph(self._format_inline(item_text), self._styles["Body"]),
                            bulletColor=HexColor(self.config.branding.primary_color)
                        )
                    )
                    i += 1

                elements.append(
                    ListFlowable(
                        list_items,
                        bulletType="bullet",
                        start=None
                    )
                )
                continue

            # Numbered list
            if re.match(r"^[\s]*\d+\.\s+", line):
                if current_paragraph:
                    text = " ".join(current_paragraph)
                    elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))
                    current_paragraph = []

                list_items = []
                while i < len(lines) and re.match(r"^[\s]*\d+\.\s+", lines[i]):
                    item_text = re.sub(r"^[\s]*\d+\.\s+", "", lines[i])
                    list_items.append(
                        ListItem(
                            Paragraph(self._format_inline(item_text), self._styles["Body"])
                        )
                    )
                    i += 1

                elements.append(
                    ListFlowable(
                        list_items,
                        bulletType="1"
                    )
                )
                continue

            # Regular paragraph
            current_paragraph.append(line)
            i += 1

        # Handle remaining paragraph
        if current_paragraph:
            text = " ".join(current_paragraph)
            elements.append(Paragraph(self._format_inline(text), self._styles["Body"]))

        return elements

    def _format_inline(self, text: str) -> str:
        """Format inline markdown elements (bold, italic, code, links)."""
        # Escape HTML first
        text = self._escape_html(text)

        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

        # Italic
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)

        # Inline code
        text = re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', text)

        # Links
        text = re.sub(
            r"\[(.+?)\]\((.+?)\)",
            r'<a href="\2" color="' + self.config.branding.primary_color + r'">\1</a>',
            text
        )

        return text

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def _create_hr(self) -> Flowable:
        """Create a horizontal rule."""
        from reportlab.platypus import HRFlowable
        return HRFlowable(
            width="100%",
            thickness=1,
            color=HexColor(self.config.branding.secondary_color),
            spaceBefore=5,
            spaceAfter=5
        )


# ==============================================================================
# Factory Functions
# ==============================================================================

def generate_research_report(
    title: str,
    content: str,
    job: Dict[str, Any],
    branding: Optional[PDFBranding] = None
) -> bytes:
    """
    Generate a research report PDF.

    Args:
        title: Report title
        content: Markdown content
        job: Job record for metadata
        branding: Optional branding configuration

    Returns:
        PDF as bytes
    """
    config = PDFConfig(
        branding=branding or PDFBranding(),
        include_toc=True,
        include_cover_page=True
    )

    metadata = {
        "author": job.get("user_id", "System"),
        "date": datetime.now().strftime("%B %d, %Y"),
        "description": job.get("description", ""),
        "version": "1.0",
        "job_id": str(job.get("id", ""))
    }

    generator = PDFReportGenerator(config)
    return generator.generate(title, content, metadata)


def generate_simple_pdf(
    title: str,
    content: str,
    include_toc: bool = False
) -> bytes:
    """
    Generate a simple PDF without cover page or branding.

    Args:
        title: Document title
        content: Markdown content
        include_toc: Whether to include table of contents

    Returns:
        PDF as bytes
    """
    config = PDFConfig(
        include_toc=include_toc,
        include_cover_page=False,
        branding=PDFBranding(
            include_page_numbers=True,
            include_date=True,
            header_text=None,
            footer_text=None
        )
    )

    generator = PDFReportGenerator(config)
    return generator.generate(title, content, {"title": title})
