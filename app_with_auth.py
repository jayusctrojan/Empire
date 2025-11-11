"""
Empire v7.3 - Chat UI with Clerk Authentication & RBAC Dashboard
Wraps Gradio chat interface with Clerk authentication and RBAC management
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import gradio as gr
import structlog
from dotenv import load_dotenv
from app.services.chat_service import get_chat_service
from rbac_dashboard import build_rbac_dashboard
from datetime import datetime

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

# Initialize FastAPI app
app = FastAPI(title="Empire AI Chat - Authenticated")

# Mount static files directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Initialize chat service
chat_service = get_chat_service()


async def chat_function_with_auth(message: str, history: list[list[str]], request: gr.Request):
    """
    Chat function with authentication token from request

    Args:
        message: User's message
        history: Chat history in Gradio format [[user, bot], ...]
        request: Gradio request object (contains headers and session info)

    Yields:
        Response chunks as they arrive with loading indicators
    """
    start_time = datetime.now()

    # Extract auth token from request headers or session
    auth_token = None

    # Try to get token from custom header (set by JavaScript)
    if hasattr(request, 'headers'):
        auth_token = request.headers.get('X-Clerk-Session-Token')

    # Try to get from session/cookies
    if not auth_token and hasattr(request, 'session'):
        auth_token = request.session.get('clerk_token')

    logger.info(
        "Chat request received",
        message_preview=message[:100],
        message_length=len(message),
        history_length=len(history),
        has_auth_token=bool(auth_token)
    )

    # Track response state
    loading_shown = False
    error_occurred = False
    full_response = ""

    try:
        # Stream response with authentication
        async for chunk in chat_service.stream_chat_response(
            message=message,
            history=history,
            use_auto_routing=True,
            max_iterations=3,
            auth_token=auth_token  # Pass token to service
        ):
            # Check if this is a loading indicator
            if "🔍 Processing your query" in chunk and not loading_shown:
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
                    "Chat request failed",
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
                "Chat request completed successfully",
                message_preview=message[:100],
                response_length=len(full_response),
                duration_ms=duration_ms
            )

    except Exception as e:
        # Catch any unexpected errors in the UI layer
        error_msg = (
            f"🚨 **UI Error: {type(e).__name__}**\n\n"
            "An unexpected error occurred in the chat interface. "
            "Please refresh the page and try again.\n\n"
            f"*Technical details: {str(e)}*"
        )

        logger.error(
            "Unexpected error in chat UI",
            error=str(e),
            error_type=type(e).__name__,
            message_preview=message[:100]
        )

        yield error_msg


# Custom CSS for the chat interface
custom_css = """
.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
}

#chatbot {
    height: calc(100vh - 250px) !important;
    min-height: 400px !important;
}

.message-wrap {
    font-size: 16px !important;
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
    #chatbot {
        height: calc(100vh - 200px) !important;
    }
}
"""

# Example queries
examples = [
    "What are California insurance requirements?",
    "Compare our policies with CA regulations",
    "Summarize the key points from the latest document",
    "What are the compliance requirements for healthcare?",
    "Explain the main regulations for financial services",
]

# Build Gradio interface
with gr.Blocks(
    theme=gr.themes.Soft(),
    css=custom_css,
    title="Empire AI Chat"
) as demo:
    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("# 🏛️ Empire AI Chat")
        with gr.Column(scale=2):
            with gr.Row():
                rbac_btn = gr.Button("🔐 RBAC Dashboard", size="sm", link="/rbac")
                logout_btn = gr.Button("🚪 Sign Out", size="sm")

    # Add JavaScript to inject auth token and handle logout/navigation
    gr.HTML("""
    <script>
    // Inject Clerk session token into Gradio requests
    window.addEventListener('load', function() {
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const token = localStorage.getItem('clerk_session_token');
            if (token && args[1]) {
                args[1].headers = args[1].headers || {};
                args[1].headers['X-Clerk-Session-Token'] = token;
            }
            return originalFetch.apply(this, args);
        };
    });

    // Handle logout
    function handleLogout() {
        localStorage.removeItem('clerk_session_token');
        window.location.href = '/';
    }

    // Handle RBAC dashboard navigation
    function goToRBAC() {
        window.location.href = '/rbac';
    }
    </script>
    """)

    chatbot = gr.ChatInterface(
        fn=chat_function_with_auth,
        chatbot=gr.Chatbot(
            elem_id="chatbot",
            height=600,
            show_copy_button=True,
            render_markdown=True,
            avatar_images=(None, "🤖"),
            show_label=False,
            container=True
        ),
        textbox=gr.Textbox(
            placeholder="Ask me anything about documents, policies, or regulations...",
            container=False,
            scale=7,
            max_lines=3,
            show_label=False
        ),
        examples=examples,
        cache_examples=False
    )

    # Simple footer
    gr.Markdown(
        """
        ---

        💡 Ask me anything about your documents and knowledge base
        """
    )

    # Wire up navigation and logout buttons
    rbac_btn.click(fn=None, js="goToRBAC()")
    logout_btn.click(fn=None, js="handleLogout()")


@app.get("/", response_class=HTMLResponse)
async def auth_page():
    """Serve the Clerk authentication page with environment variable injection"""
    auth_html_path = static_dir / "clerk_auth.html"

    if not auth_html_path.exists():
        return HTMLResponse(
            content="<h1>Authentication page not found</h1><p>Please ensure clerk_auth.html exists in the static directory.</p>",
            status_code=404
        )

    # Read HTML template and inject environment variables
    with open(auth_html_path, 'r') as f:
        html_content = f.read()

    # Replace placeholder with actual publishable key from environment
    clerk_publishable_key = os.getenv(
        "CLERK_PUBLISHABLE_KEY",
        os.getenv("VITE_CLERK_PUBLISHABLE_KEY", "")
    )

    html_content = html_content.replace(
        "{{ CLERK_PUBLISHABLE_KEY }}",
        clerk_publishable_key
    )

    return HTMLResponse(content=html_content)


# Build RBAC dashboard
rbac_demo = build_rbac_dashboard()

# Mount Gradio apps
app = gr.mount_gradio_app(app, demo, path="/chat")
app = gr.mount_gradio_app(app, rbac_demo, path="/rbac")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("CHAT_UI_PORT", 7860))
    host = os.getenv("CHAT_UI_HOST", "0.0.0.0")

    logger.info(
        "Launching Empire Chat UI with Authentication",
        host=host,
        port=port,
        auth_page="http://{}:{}/".format(host, port),
        chat_page="http://{}:{}/chat".format(host, port),
        api_url=os.getenv("EMPIRE_API_URL", "https://jb-empire-api.onrender.com")
    )

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
