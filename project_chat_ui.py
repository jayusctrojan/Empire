"""
Empire v7.3 - Project Chat UI (Gradio)
Project-scoped chat interface with source count banner

Task 65: Integrate project-scoped RAG into Project Chat
- Shows "Project-scoped chat (X ready sources)" banner
- Uses project RAG endpoint with hybrid search
- Falls back to global-only when no project sources
"""

import os
import gradio as gr
import asyncio
import structlog
from dotenv import load_dotenv
from app.services.chat_service import get_chat_service, ProjectChatContext
from datetime import datetime
from typing import Optional

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger(__name__)

# Initialize chat service
chat_service = get_chat_service()


def create_project_chat_function(project_id: str):
    """
    Factory function to create a project-scoped chat function.

    Args:
        project_id: The project ID to scope the chat to

    Returns:
        Async chat function for Gradio
    """
    async def project_chat_function(
        message: str,
        history: list[list[str]],
        request: gr.Request = None
    ):
        """
        Project-scoped chat function with streaming response

        Args:
            message: User's message
            history: Chat history in Gradio format [[user, bot], ...]
            request: Gradio request object (optional, for auth token extraction)

        Yields:
            Response chunks as they arrive with project-scoped context
        """
        start_time = datetime.now()

        # Extract auth token if available
        auth_token = None
        if request:
            if hasattr(request, 'headers'):
                auth_token = request.headers.get('X-Clerk-Session-Token')
            if not auth_token and hasattr(request, 'session'):
                auth_token = request.session.get('clerk_token')

        logger.info(
            "Project chat request received",
            project_id=project_id,
            message_preview=message[:100],
            message_length=len(message),
            history_length=len(history),
            has_auth_token=bool(auth_token)
        )

        # Track state
        loading_shown = False
        error_occurred = False
        full_response = ""

        try:
            # Stream project-scoped response
            async for chunk in chat_service.stream_project_chat_response(
                message=message,
                project_id=project_id,
                history=history,
                auth_token=auth_token,
                include_global_kb=True,
                enable_query_expansion=True
            ):
                # Check if this is a loading indicator
                if "🔍" in chunk and ("Searching" in chunk or "No project sources" in chunk) and not loading_shown:
                    loading_shown = True
                    full_response = chunk
                    yield full_response
                    continue

                # Check if this is an error message
                if any(emoji in chunk for emoji in ["❌", "⏱️", "🌐", "⚠️", "🔐", "🔍", "🚦", "🔧", "📄"]):
                    error_occurred = True
                    full_response = chunk
                    yield full_response

                    logger.error(
                        "Project chat request failed",
                        project_id=project_id,
                        message_preview=message[:100],
                        error_preview=chunk[:200],
                        duration_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
                    continue

                # Normal response - replace loading indicator
                if loading_shown:
                    full_response = chunk  # Replace loading indicator
                    loading_shown = False
                else:
                    full_response += chunk

                yield full_response

            # Log successful completion
            if not error_occurred:
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(
                    "Project chat request completed successfully",
                    project_id=project_id,
                    message_preview=message[:100],
                    response_length=len(full_response),
                    duration_ms=duration_ms
                )

        except Exception as e:
            error_msg = (
                f"🚨 **UI Error: {type(e).__name__}**\n\n"
                "An unexpected error occurred in the chat interface. "
                "Please refresh the page and try again.\n\n"
                f"*Technical details: {str(e)}*"
            )

            logger.error(
                "Unexpected error in project chat UI",
                project_id=project_id,
                error=str(e),
                error_type=type(e).__name__,
                message_preview=message[:100]
            )

            yield error_msg

    return project_chat_function


async def get_project_banner_info(project_id: str, auth_token: Optional[str] = None) -> str:
    """
    Get the project banner information showing source counts.

    Args:
        project_id: Project ID
        auth_token: Optional auth token

    Returns:
        Markdown string for banner display
    """
    try:
        context = await chat_service.get_project_context(
            project_id=project_id,
            user_id="",
            auth_token=auth_token
        )

        if context.has_sources:
            project_name = context.project_name or "Project"
            return f"📁 **{project_name}** — {context.ready_source_count} source(s) ready | {context.source_count} total"
        else:
            return "📁 **Project Chat** — No sources added yet. Add files or URLs to enable project-scoped search."

    except Exception as e:
        logger.error("Error getting project banner info", project_id=project_id, error=str(e))
        return "📁 **Project Chat** — Unable to load source information"


# Custom CSS for project chat (extends base chat CSS)
project_chat_css = """
.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
}

#project-chatbot {
    height: calc(100vh - 300px) !important;
    min-height: 350px !important;
}

.project-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 12px;
    font-weight: 500;
}

.project-banner-no-sources {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.message-wrap {
    font-size: 16px !important;
}

/* Style for project-specific status messages */
.message-wrap:has-text("📁") {
    background-color: #f0f4ff !important;
    border-left: 4px solid #667eea !important;
}

/* Style for error messages */
.message-wrap:has-text("❌"),
.message-wrap:has-text("⚠️"),
.message-wrap:has-text("🚨") {
    background-color: #fee !important;
    border-left: 4px solid #c33 !important;
}

/* Style for loading messages */
.message-wrap:has-text("🔍") {
    background-color: #e7f3ff !important;
    border-left: 4px solid #0366d6 !important;
}

/* Style for success/info messages */
.message-wrap:has-text("✅") {
    background-color: #efe !important;
    border-left: 4px solid #3c3 !important;
}

@media (max-width: 768px) {
    #project-chatbot {
        height: calc(100vh - 250px) !important;
    }

    .project-banner {
        padding: 10px 12px;
        font-size: 14px;
    }
}
"""


def create_project_chat_ui(project_id: str, project_name: Optional[str] = None):
    """
    Create a project-scoped chat UI component.

    Args:
        project_id: Project ID for scoping queries
        project_name: Optional project name for display

    Returns:
        Gradio Blocks component for project chat
    """
    # Project-specific examples
    examples = [
        "What are the key points from my uploaded documents?",
        "Summarize the main topics across my project sources",
        "Find information about [specific topic] in my files",
        "Compare the content across my project documents",
        "What are the most important findings?",
    ]

    # Create the chat function for this project
    chat_fn = create_project_chat_function(project_id)

    # Build Gradio interface
    with gr.Blocks(
        theme=gr.themes.Soft(),
        css=project_chat_css,
        title=f"Project Chat - {project_name or project_id}"
    ) as demo:

        # Project header with source count banner
        with gr.Row():
            gr.Markdown(
                f"# 📁 Project Chat",
                elem_classes=["project-header"]
            )

        # Dynamic banner showing source count (updated on load)
        banner_display = gr.Markdown(
            f"📁 **{project_name or 'Project'}** — Loading sources...",
            elem_classes=["project-banner"]
        )

        # Chat interface
        chatbot = gr.ChatInterface(
            fn=chat_fn,
            chatbot=gr.Chatbot(
                elem_id="project-chatbot",
                height=500,
                show_copy_button=True,
                render_markdown=True,
                avatar_images=(None, "🤖"),
                show_label=False,
                container=True
            ),
            textbox=gr.Textbox(
                placeholder="Ask about your project documents...",
                container=False,
                scale=7,
                max_lines=3,
                show_label=False
            ),
            examples=examples,
            cache_examples=False
        )

        # Footer with help text
        gr.Markdown(
            """
            ---
            💡 **Tips**: Ask questions about your uploaded files, URLs, or YouTube videos.
            The chat searches both your project sources and the global knowledge base.
            """
        )

        # Update banner on load
        async def update_banner():
            return await get_project_banner_info(project_id)

        demo.load(update_banner, outputs=banner_display)

    return demo


def create_embedded_project_chat(project_id: str, project_name: Optional[str] = None):
    """
    Create a minimal embedded project chat component (for embedding in other UIs).

    Args:
        project_id: Project ID
        project_name: Optional project name

    Returns:
        Gradio component suitable for embedding
    """
    chat_fn = create_project_chat_function(project_id)

    with gr.Blocks(css=project_chat_css) as component:
        # Compact banner
        banner = gr.Markdown(
            f"🔍 **Project Sources**: Loading...",
            elem_classes=["project-banner"]
        )

        # Minimal chat interface
        chatbot = gr.Chatbot(
            elem_id="project-chatbot",
            height=400,
            show_copy_button=True,
            render_markdown=True,
            show_label=False
        )

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Ask about your project...",
                scale=7,
                show_label=False
            )
            submit = gr.Button("Send", scale=1)

        # Handle submit
        async def respond(message, history):
            response = ""
            async for chunk in chat_fn(message, history):
                response = chunk
            return "", history + [[message, response]]

        submit.click(respond, [msg, chatbot], [msg, chatbot])
        msg.submit(respond, [msg, chatbot], [msg, chatbot])

        # Update banner
        async def update_banner():
            return await get_project_banner_info(project_id)

        component.load(update_banner, outputs=banner)

    return component


# Standalone launch for testing
if __name__ == "__main__":
    import sys

    # Get project_id from command line or use default
    project_id = sys.argv[1] if len(sys.argv) > 1 else "test-project-id"
    project_name = sys.argv[2] if len(sys.argv) > 2 else "Test Project"

    port = int(os.getenv("PROJECT_CHAT_UI_PORT", 7861))
    server_name = os.getenv("PROJECT_CHAT_UI_HOST", "0.0.0.0")

    logger.info(
        "Launching Project Chat UI",
        project_id=project_id,
        project_name=project_name,
        host=server_name,
        port=port,
        api_url=os.getenv("EMPIRE_API_URL", "https://jb-empire-api.onrender.com")
    )

    demo = create_project_chat_ui(project_id, project_name)

    demo.queue(
        max_size=20,
        default_concurrency_limit=10
    )

    demo.launch(
        server_name=server_name,
        server_port=port,
        share=False,
        show_api=False,
        show_error=True,
        quiet=False
    )
