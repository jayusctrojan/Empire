"""
Empire v7.3 - Report Download API Routes

Provides endpoints for downloading research reports in various formats:
- PDF
- Markdown
- HTML

Features:
- Streaming downloads for large files
- Content-Disposition headers for proper file naming
- B2 storage integration
- Format conversion support

Author: Claude Code
Date: 2025-01-24
"""

import html
import io
import os
from typing import Optional
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from app.core.supabase_client import get_supabase_client
from app.services.b2_storage import get_b2_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["report-downloads"])


# ==============================================================================
# Response Models
# ==============================================================================

class ReportInfo(BaseModel):
    """Information about a report"""
    job_id: int
    title: str
    query: str
    status: str
    formats_available: list[str]
    created_at: str
    completed_at: Optional[str] = None
    word_count: Optional[int] = None
    pdf_url: Optional[str] = None
    markdown_url: Optional[str] = None
    html_url: Optional[str] = None


class DownloadResponse(BaseModel):
    """Download response with URL"""
    job_id: int
    format: str
    download_url: str
    filename: str
    size_bytes: Optional[int] = None
    expires_in_seconds: int = 3600


# ==============================================================================
# Helper Functions
# ==============================================================================

def get_job_report_info(job_id: int) -> dict:
    """Get report information from database"""
    supabase = get_supabase_client()

    result = supabase.table("research_jobs").select(
        "id, query, status, created_at, completed_at, report_content, report_url, metadata"
    ).eq("id", job_id).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return result.data


def sanitize_filename(query: Optional[str], max_length: int = 50) -> str:
    """Create a safe filename from query"""
    query = "" if query is None else str(query)
    # Remove special characters
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in query)
    # Truncate and clean
    safe = safe[:max_length].strip().replace(" ", "_")
    return safe or "report"


async def get_report_content(job_id: int, format_type: str) -> tuple[bytes, str]:
    """
    Get report content in the specified format.

    Returns:
        Tuple of (content_bytes, content_type)
    """
    job = get_job_report_info(job_id)

    if job["status"] not in ["completed", "generating_report"]:
        raise HTTPException(
            status_code=400,
            detail=f"Report not available. Job status: {job['status']}"
        )

    # Check B2 storage first for pre-generated files
    b2 = get_b2_service()
    metadata = job.get("metadata", {}) or {}

    if format_type == "pdf":
        pdf_key = metadata.get("pdf_key") or f"reports/{job_id}/report.pdf"
        try:
            content = await b2.download_file(pdf_key)
            if content:
                return content, "application/pdf"
        except Exception as e:
            logger.debug(f"PDF not in B2: {e}")

        # Generate PDF from markdown if not available
        markdown_content = job.get("report_content", "")
        if not markdown_content:
            raise HTTPException(
                status_code=404,
                detail="Report content not available for PDF generation"
            )

        pdf_bytes = await generate_pdf_from_markdown(markdown_content, job)
        return pdf_bytes, "application/pdf"

    elif format_type == "markdown":
        markdown_content = job.get("report_content", "")
        if not markdown_content:
            raise HTTPException(status_code=404, detail="Markdown report not available")
        return markdown_content.encode("utf-8"), "text/markdown"

    elif format_type == "html":
        markdown_content = job.get("report_content", "")
        if not markdown_content:
            raise HTTPException(status_code=404, detail="Report content not available")

        html_content = await convert_markdown_to_html(markdown_content, job)
        return html_content.encode("utf-8"), "text/html"

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format_type}")


async def generate_pdf_from_markdown(markdown: str, job: dict) -> bytes:
    """Generate PDF from markdown content"""
    try:
        import markdown2
        from weasyprint import HTML, CSS

        # Convert markdown to HTML
        html_content = markdown2.markdown(
            markdown,
            extras=["tables", "fenced-code-blocks", "header-ids", "toc"],
            safe_mode="escape"
        )

        # Wrap in complete HTML document with styling
        query = html.escape(job.get("query") or "Research Report")
        created_at = job.get("created_at") or datetime.utcnow().isoformat()

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{query}</title>
            <style>
                @page {{
                    size: letter;
                    margin: 2cm;
                    @top-right {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 10px;
                        color: #666;
                    }}
                    @bottom-center {{
                        content: "Empire Research Report";
                        font-size: 10px;
                        color: #666;
                    }}
                }}
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.6;
                    color: #333;
                }}
                h1 {{
                    color: #1a365d;
                    border-bottom: 2px solid #1a365d;
                    padding-bottom: 10px;
                    font-size: 24pt;
                }}
                h2 {{
                    color: #2c5282;
                    margin-top: 30px;
                    font-size: 18pt;
                }}
                h3 {{
                    color: #3182ce;
                    font-size: 14pt;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f7fafc;
                }}
                code {{
                    background-color: #f7fafc;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-family: monospace;
                }}
                pre {{
                    background-color: #f7fafc;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
                blockquote {{
                    border-left: 4px solid #3182ce;
                    margin: 20px 0;
                    padding-left: 20px;
                    color: #666;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 40px;
                }}
                .meta {{
                    color: #666;
                    font-size: 10pt;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{query}</h1>
                <div class="meta">
                    Generated: {created_at[:10]} | Empire Research System
                </div>
            </div>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF
        pdf_bytes = HTML(string=full_html).write_pdf()
        return pdf_bytes

    except ImportError:
        logger.warning("weasyprint_not_installed")
        raise HTTPException(
            status_code=501,
            detail="PDF generation unavailable - weasyprint not installed"
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


async def convert_markdown_to_html(markdown: str, job: dict) -> str:
    """Convert markdown to styled HTML"""
    try:
        import markdown2

        html_content = markdown2.markdown(
            markdown,
            extras=["tables", "fenced-code-blocks", "header-ids", "toc", "strike"],
            safe_mode="escape"
        )

        query = html.escape(job.get("query") or "Research Report")
        created_at = job.get("created_at") or datetime.utcnow().isoformat()

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{query} - Empire Research Report</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background-color: #f9fafb;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #1a365d;
                    border-bottom: 3px solid #3182ce;
                    padding-bottom: 15px;
                    margin-bottom: 30px;
                }}
                h2 {{
                    color: #2c5282;
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e2e8f0;
                }}
                h3 {{ color: #3182ce; }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #e2e8f0;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f7fafc;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{ background-color: #f7fafc; }}
                code {{
                    background-color: #f7fafc;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-family: 'SF Mono', Monaco, monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background-color: #2d3748;
                    color: #e2e8f0;
                    padding: 20px;
                    border-radius: 8px;
                    overflow-x: auto;
                }}
                pre code {{
                    background: transparent;
                    color: inherit;
                    padding: 0;
                }}
                blockquote {{
                    border-left: 4px solid #3182ce;
                    margin: 20px 0;
                    padding: 10px 20px;
                    background-color: #f7fafc;
                    border-radius: 0 8px 8px 0;
                }}
                a {{
                    color: #3182ce;
                    text-decoration: none;
                }}
                a:hover {{ text-decoration: underline; }}
                .header {{
                    text-align: center;
                    margin-bottom: 40px;
                }}
                .meta {{
                    color: #718096;
                    font-size: 0.9em;
                    margin-top: 10px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e2e8f0;
                    color: #718096;
                    font-size: 0.85em;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{query}</h1>
                    <div class="meta">
                        Generated on {created_at[:10]} by Empire Research System
                    </div>
                </div>
                {html_content}
                <div class="footer">
                    <p>Generated by Empire Research System v7.3</p>
                </div>
            </div>
        </body>
        </html>
        """

    except ImportError:
        # Fallback: basic HTML wrapping
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Research Report</title></head>
        <body><pre>{html.escape(markdown)}</pre></body>
        </html>
        """


# ==============================================================================
# API Endpoints
# ==============================================================================

@router.get("/{job_id}/info", response_model=ReportInfo)
async def get_report_info(job_id: int):
    """
    Get information about a research report.

    Returns available formats and metadata.
    """
    job = get_job_report_info(job_id)

    formats = []
    if job.get("report_content"):
        formats.extend(["markdown", "html", "pdf"])
    elif job.get("report_url"):
        formats.append("pdf")

    metadata = job.get("metadata", {}) or {}

    return ReportInfo(
        job_id=job_id,
        title=job.get("query", "Research Report")[:100],
        query=job.get("query", ""),
        status=job.get("status", "unknown"),
        formats_available=formats,
        created_at=job.get("created_at", ""),
        completed_at=job.get("completed_at"),
        word_count=metadata.get("word_count"),
        pdf_url=job.get("report_url"),
        markdown_url=f"/api/reports/{job_id}/download/markdown" if "markdown" in formats else None,
        html_url=f"/api/reports/{job_id}/download/html" if "html" in formats else None
    )


@router.get("/{job_id}/download/pdf")
async def download_pdf(
    job_id: int,
    inline: bool = Query(False, description="Display inline instead of download")
):
    """
    Download research report as PDF.

    Args:
        job_id: Research job ID
        inline: If true, display in browser instead of downloading
    """
    logger.info("PDF download requested", job_id=job_id)

    job = get_job_report_info(job_id)
    content, content_type = await get_report_content(job_id, "pdf")

    filename = f"{sanitize_filename(job.get('query', 'report'))}.pdf"
    disposition = "inline" if inline else "attachment"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/{job_id}/download/markdown")
async def download_markdown(
    job_id: int,
    inline: bool = Query(False, description="Display inline instead of download")
):
    """
    Download research report as Markdown.

    Args:
        job_id: Research job ID
        inline: If true, display in browser instead of downloading
    """
    logger.info("Markdown download requested", job_id=job_id)

    job = get_job_report_info(job_id)
    content, content_type = await get_report_content(job_id, "markdown")

    filename = f"{sanitize_filename(job.get('query', 'report'))}.md"
    disposition = "inline" if inline else "attachment"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/{job_id}/download/html")
async def download_html(
    job_id: int,
    inline: bool = Query(True, description="Display inline (default) or download")
):
    """
    Download research report as HTML.

    Args:
        job_id: Research job ID
        inline: If true (default), display in browser
    """
    logger.info("HTML download requested", job_id=job_id)

    job = get_job_report_info(job_id)
    content, content_type = await get_report_content(job_id, "html")

    filename = f"{sanitize_filename(job.get('query', 'report'))}.html"
    disposition = "inline" if inline else "attachment"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/{job_id}/download-url/{format}")
async def get_download_url(
    job_id: int,
    format: str,
    expires_in: int = Query(3600, description="URL expiration in seconds")
) -> DownloadResponse:
    """
    Get a pre-signed download URL for the report.

    Useful for sharing or async downloads.

    Args:
        job_id: Research job ID
        format: Format (pdf, markdown, html)
        expires_in: URL expiration time in seconds
    """
    if format not in ["pdf", "markdown", "html"]:
        raise HTTPException(status_code=400, detail="Invalid format")

    job = get_job_report_info(job_id)
    filename = f"{sanitize_filename(job.get('query', 'report'))}.{format if format != 'markdown' else 'md'}"

    # For B2-stored files, generate presigned URL
    b2 = get_b2_service()
    metadata = job.get("metadata", {}) or {}

    if format == "pdf" and metadata.get("pdf_key"):
        download_url = await b2.get_presigned_url(
            metadata["pdf_key"],
            expires_in=expires_in
        )
        return DownloadResponse(
            job_id=job_id,
            format=format,
            download_url=download_url,
            filename=filename,
            expires_in_seconds=expires_in
        )

    # For other formats, return the direct API endpoint
    base_url = os.getenv("API_BASE_URL", "https://jb-empire-api.onrender.com")
    download_url = f"{base_url}/api/reports/{job_id}/download/{format}"

    return DownloadResponse(
        job_id=job_id,
        format=format,
        download_url=download_url,
        filename=filename,
        expires_in_seconds=expires_in
    )


@router.get("/{job_id}/stream/pdf")
async def stream_pdf(job_id: int):
    """
    Stream PDF download for large reports.

    Uses chunked transfer encoding for memory efficiency.
    """
    job = get_job_report_info(job_id)

    # Check for pre-generated PDF in B2
    b2 = get_b2_service()
    metadata = job.get("metadata", {}) or {}
    pdf_key = metadata.get("pdf_key") or f"reports/{job_id}/report.pdf"

    async def generate_chunks():
        try:
            # Try streaming from B2
            async for chunk in b2.stream_download(pdf_key):
                yield chunk
        except Exception:
            # Fall back to generating PDF
            content, _ = await get_report_content(job_id, "pdf")
            chunk_size = 8192
            for i in range(0, len(content), chunk_size):
                yield content[i:i + chunk_size]

    filename = f"{sanitize_filename(job.get('query', 'report'))}.pdf"

    return StreamingResponse(
        generate_chunks(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
