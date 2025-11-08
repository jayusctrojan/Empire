"""
Empire v7.3 - Chat UI (Gradio)
Mobile-responsive chat interface with streaming support

Task 26: Chat UI Implementation with WebSocket and streaming responses
Enhanced with comprehensive error handling and loading states
"""

import os
import gradio as gr
import asyncio
import structlog
from dotenv import load_dotenv
from app.services.chat_service import get_chat_service
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

# Initialize chat service
chat_service = get_chat_service()


async def chat_function(message: str, history: list[list[str]]):
    """
    Chat function with streaming response and progress indicators

    Args:
        message: User's message
        history: Chat history in Gradio format [[user, bot], ...]

    Yields:
        Response chunks as they arrive with loading indicators
    """
    start_time = datetime.now()
    
    logger.info(
        "Chat request received",
        message_preview=message[:100],
        message_length=len(message),
        history_length=len(history)
    )

    # Track if we're still in loading state
    loading_shown = False
    error_occurred = False
    full_response = ""

    try:
        # Stream response with progress indicators
        async for chunk in chat_service.stream_chat_response(
            message=message,
            history=history,
            use_auto_routing=True,  # Use Task 46 auto-routing
            max_iterations=3
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


# Custom CSS for better mobile responsiveness and error styling
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

# Examples for users with helpful descriptions
examples = [
    "What are California insurance requirements?",
    "Compare our policies with CA regulations",
    "Explain the document processing pipeline",
    "How does the LangGraph workflow work?",
    "Search the web for latest AI regulations",
]

# Build Gradio interface
with gr.Blocks(
    theme=gr.themes.Soft(),
    css=custom_css,
    title="Empire AI Chat"
) as demo:
    gr.Markdown(
        """
        # 🏛️ Empire AI Chat

        Powered by **Task 46: LangGraph + Arcade.dev Integration**

        Features:
        - 🔄 **Auto-routing** to optimal workflow (LangGraph/CrewAI/Simple RAG)
        - 🌊 **Real-time streaming** responses with progress indicators
        - 🔍 **Adaptive research** with iterative refinement
        - 🛠️ **External tool integration** (Google Search, etc.)
        - 🔁 **Automatic retry** with exponential backoff (up to 3 attempts)
        - 🛡️ **Comprehensive error handling** with user-friendly messages
        
        ---
        
        💡 **Status Indicators:**
        - 🔍 = Processing your query
        - ⏱️ = Timeout (query too complex)
        - 🌐 = Connection issue
        - 🔧 = Server error (retrying automatically)
        """
    )

    chatbot = gr.ChatInterface(
        fn=chat_function,
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

    # Footer with detailed info
    gr.Markdown(
        """
        ---
        ### 🎯 How It Works
        
        **Workflow Router:** Automatically selects the best processing method:
        - **LangGraph** - Complex queries requiring research and tool usage
        - **CrewAI** - Multi-agent collaborative tasks
        - **Simple RAG** - Direct knowledge base queries
        
        **Error Handling:** 
        - Automatic retry with exponential backoff (1s, 2s, 4s delays)
        - User-friendly error messages for all failure types
        - Structured logging for debugging and monitoring
        
        **API Endpoint:** [https://jb-empire-api.onrender.com/docs](https://jb-empire-api.onrender.com/docs)
        
        ---
        
        💡 **Tips:**
        - Complex questions trigger LangGraph's adaptive workflow
        - Error messages include helpful guidance for resolution
        - The system automatically retries on temporary failures
        - Loading indicators show real-time progress
        """
    )


if __name__ == "__main__":
    # Launch configuration
    port = int(os.getenv("CHAT_UI_PORT", 7860))
    server_name = os.getenv("CHAT_UI_HOST", "0.0.0.0")  # Bind to all interfaces for Render

    logger.info(
        "Launching Empire Chat UI",
        host=server_name,
        port=port,
        api_url=os.getenv("EMPIRE_API_URL", "https://jb-empire-api.onrender.com")
    )

    # Launch Gradio app with enhanced settings
    demo.queue(
        max_size=20,  # Maximum queue size
        default_concurrency_limit=10  # Concurrent requests limit
    )
    
    demo.launch(
        server_name=server_name,
        server_port=port,
        share=False,  # Don't create public share link
        show_api=False,  # Hide API docs in UI
        favicon_path=None,  # Add custom favicon later if desired
        show_error=True,  # Show detailed errors in UI during development
        quiet=False,  # Show startup logs
    )
