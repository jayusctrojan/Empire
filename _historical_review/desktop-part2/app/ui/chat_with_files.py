"""
Empire v7.3 - Chat UI with File Upload (Gradio)
Mobile-responsive chat interface with file and image upload support

Task 21: Enable File and Image Upload in Chat
Subtask 21.4: Implement Gradio File Upload Component
"""

import os
import uuid
import httpx
import asyncio
import gradio as gr
import structlog
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from dataclasses import dataclass

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)


@dataclass
class UploadedFile:
    """Represents an uploaded file"""
    file_id: str
    filename: str
    file_type: str
    file_size: int
    mime_type: str
    description: Optional[str] = None
    is_image: bool = False


class ChatWithFilesService:
    """
    Chat service with file and image upload support

    Features:
    - Streaming responses from Empire API
    - File upload to chat session
    - Image analysis with Claude Vision
    - Context-aware Q&A with uploaded files
    """

    def __init__(self):
        """Initialize chat service with API clients"""
        self.api_base_url = os.getenv(
            "EMPIRE_API_URL",
            "http://localhost:8000"  # Default to local for development
        )
        self.timeout = httpx.Timeout(300.0, connect=10.0)
        self.max_retries = 3

        # Session tracking
        self._sessions: Dict[str, Dict[str, Any]] = {}

        logger.info("ChatWithFilesService initialized", api_url=self.api_base_url)

    def _get_or_create_session(self, session_state: Optional[Dict] = None) -> str:
        """Get or create a session ID"""
        if session_state and "session_id" in session_state:
            return session_state["session_id"]

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "created_at": datetime.utcnow(),
            "files": [],
            "messages": []
        }
        return session_id

    async def upload_file(
        self,
        file_path: str,
        session_id: str
    ) -> Tuple[bool, Optional[UploadedFile], Optional[str]]:
        """
        Upload a file to the chat session

        Args:
            file_path: Path to the file
            session_id: Chat session ID

        Returns:
            Tuple of (success, UploadedFile, error_message)
        """
        try:
            if not os.path.exists(file_path):
                return False, None, "File not found"

            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            logger.info(
                "Uploading file to chat",
                filename=filename,
                session_id=session_id,
                size=file_size
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(file_path, 'rb') as f:
                    files = {'file': (filename, f)}
                    data = {
                        'session_id': session_id,
                        'extract_text': 'true'
                    }

                    response = await client.post(
                        f"{self.api_base_url}/api/chat/upload",
                        files=files,
                        data=data
                    )

                    if response.status_code != 200:
                        error_detail = response.json().get("detail", "Upload failed")
                        return False, None, error_detail

                    result = response.json()

                    if not result.get("success"):
                        return False, None, result.get("error", "Upload failed")

                    uploaded_file = UploadedFile(
                        file_id=result["file_id"],
                        filename=result["filename"],
                        file_type=result["file_type"],
                        file_size=result["file_size"],
                        mime_type=result["mime_type"],
                        is_image=result["file_type"] == "image"
                    )

                    # Get image description if it's an image
                    if uploaded_file.is_image:
                        description = await self._get_image_description(
                            uploaded_file.file_id
                        )
                        uploaded_file.description = description

                    return True, uploaded_file, None

        except Exception as e:
            logger.error("File upload error", error=str(e), file_path=file_path)
            return False, None, str(e)

    async def _get_image_description(self, file_id: str) -> Optional[str]:
        """Get brief description of uploaded image"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base_url}/api/chat/describe/{file_id}"
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("description")

        except Exception as e:
            logger.warning("Failed to get image description", error=str(e))

        return None

    async def analyze_image(
        self,
        file_id: str,
        question: Optional[str] = None
    ) -> str:
        """
        Analyze an uploaded image

        Args:
            file_id: ID of the uploaded file
            question: Optional specific question about the image

        Returns:
            Analysis result or error message
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if question:
                    # Ask specific question
                    response = await client.post(
                        f"{self.api_base_url}/api/chat/ask",
                        json={
                            "file_id": file_id,
                            "question": question
                        }
                    )
                else:
                    # Get general analysis
                    response = await client.post(
                        f"{self.api_base_url}/api/chat/analyze",
                        json={
                            "file_id": file_id,
                            "analysis_type": "detailed"
                        }
                    )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        return result.get("description") or result.get("answer", "Analysis complete")
                    return f"Analysis failed: {result.get('error', 'Unknown error')}"

                return f"Analysis failed with status {response.status_code}"

        except Exception as e:
            logger.error("Image analysis error", error=str(e), file_id=file_id)
            return f"Analysis error: {str(e)}"

    async def chat_with_context(
        self,
        message: str,
        history: List[List[str]],
        session_id: str,
        file_ids: Optional[List[str]] = None
    ) -> str:
        """
        Send a chat message with file context

        Args:
            message: User's message
            history: Chat history
            session_id: Session ID
            file_ids: Optional list of file IDs to include as context

        Returns:
            Response string
        """
        try:
            # Build context-aware query
            context_parts = []

            # Add file context if files are uploaded
            if file_ids:
                context_parts.append("[The user has uploaded files that may be relevant to their question]")

            # Combine with user message
            full_message = message
            if context_parts:
                full_message = f"{' '.join(context_parts)}\n\nUser question: {message}"

            # Make API request
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/query/auto",
                    json={
                        "query": full_message,
                        "max_iterations": 3,
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "No answer provided")

                    # Add workflow metadata
                    formatted = f"{answer}\n"
                    if "workflow_type" in result:
                        formatted += f"\n**Workflow**: {result['workflow_type']}"
                    if "processing_time_ms" in result:
                        time_s = result['processing_time_ms'] / 1000
                        formatted += f" | **Time**: {time_s:.2f}s"

                    return formatted

                return f"API error: {response.status_code}"

        except Exception as e:
            logger.error("Chat error", error=str(e))
            return f"Error: {str(e)}"


# Initialize service
chat_service = ChatWithFilesService()


def format_file_display(file_info: UploadedFile) -> str:
    """Format file info for display in chat"""
    size_kb = file_info.file_size / 1024
    size_str = f"{size_kb:.1f}KB" if size_kb < 1024 else f"{size_kb/1024:.2f}MB"

    icon = "📷" if file_info.is_image else "📄"
    display = f"{icon} **{file_info.filename}** ({size_str})"

    if file_info.description:
        display += f"\n> {file_info.description[:200]}..."

    return display


async def process_upload(
    files: List[Any],
    session_state: Dict
) -> Tuple[str, Dict, List[Tuple[str, str]]]:
    """
    Process file uploads

    Args:
        files: List of uploaded files from Gradio
        session_state: Current session state

    Returns:
        Tuple of (status_message, updated_state, updated_history)
    """
    if not files:
        return "No files selected", session_state, []

    session_id = session_state.get("session_id", str(uuid.uuid4()))
    if "session_id" not in session_state:
        session_state["session_id"] = session_id

    if "uploaded_files" not in session_state:
        session_state["uploaded_files"] = []

    messages = []
    success_count = 0
    error_count = 0

    for file in files:
        file_path = file.name if hasattr(file, 'name') else file

        success, uploaded_file, error = await chat_service.upload_file(
            file_path=file_path,
            session_id=session_id
        )

        if success and uploaded_file:
            session_state["uploaded_files"].append({
                "file_id": uploaded_file.file_id,
                "filename": uploaded_file.filename,
                "file_type": uploaded_file.file_type,
                "is_image": uploaded_file.is_image
            })
            messages.append(("", format_file_display(uploaded_file)))
            success_count += 1
        else:
            error_count += 1
            filename = os.path.basename(file_path) if isinstance(file_path, str) else "Unknown"
            messages.append(("", f"❌ Failed to upload {filename}: {error}"))

    status = f"✅ Uploaded {success_count} file(s)"
    if error_count > 0:
        status += f", {error_count} failed"

    return status, session_state, messages


async def chat_function(
    message: str,
    history: List[List[str]],
    session_state: Dict,
    request: gr.Request = None
):
    """
    Chat function with file context support

    Args:
        message: User's message
        history: Chat history
        session_state: Session state with uploaded files
        request: Gradio request object

    Yields:
        Response chunks
    """
    if not message.strip():
        yield ""
        return

    session_id = session_state.get("session_id", str(uuid.uuid4()))
    uploaded_files = session_state.get("uploaded_files", [])

    # Check if user is asking about an uploaded image
    image_files = [f for f in uploaded_files if f.get("is_image")]

    if image_files and any(keyword in message.lower() for keyword in [
        "image", "picture", "photo", "what do you see", "describe",
        "analyze", "look at", "in this", "the image", "the picture"
    ]):
        # Analyze the most recent image
        latest_image = image_files[-1]
        yield "🔍 Analyzing image...\n\n"

        analysis = await chat_service.analyze_image(
            file_id=latest_image["file_id"],
            question=message
        )

        yield analysis
        return

    # Regular chat with file context
    yield "🔍 Processing your query...\n\n"

    file_ids = [f["file_id"] for f in uploaded_files] if uploaded_files else None

    response = await chat_service.chat_with_context(
        message=message,
        history=history,
        session_id=session_id,
        file_ids=file_ids
    )

    yield response


def clear_session(session_state: Dict) -> Tuple[Dict, List, str]:
    """Clear the current session"""
    return {"session_id": str(uuid.uuid4()), "uploaded_files": []}, [], ""


# Custom CSS
custom_css = """
.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
}

#chatbot {
    height: calc(100vh - 350px) !important;
    min-height: 400px !important;
}

.message-wrap {
    font-size: 16px !important;
}

#file-upload-area {
    border: 2px dashed #ccc !important;
    border-radius: 8px !important;
    padding: 20px !important;
    text-align: center !important;
    margin-bottom: 10px !important;
}

#file-upload-area:hover {
    border-color: #0366d6 !important;
    background-color: #f6f8fa !important;
}

.file-indicator {
    background-color: #e7f3ff !important;
    border-radius: 4px !important;
    padding: 4px 8px !important;
    margin: 2px !important;
    display: inline-block !important;
}

@media (max-width: 768px) {
    #chatbot {
        height: calc(100vh - 300px) !important;
    }
}
"""

# Examples
examples = [
    "What are California insurance requirements?",
    "Summarize the key points from the uploaded document",
    "What do you see in this image?",
    "Compare the information across all uploaded files",
]


# Build Gradio interface
def create_chat_interface():
    """Create the Gradio chat interface with file upload"""

    with gr.Blocks(
        theme=gr.themes.Soft(),
        css=custom_css,
        title="Empire AI Chat"
    ) as demo:
        # Session state
        session_state = gr.State({"session_id": str(uuid.uuid4()), "uploaded_files": []})

        gr.Markdown("# 🏛️ Empire AI Chat")
        gr.Markdown("Upload files and images for context-aware Q&A powered by Claude Vision")

        with gr.Row():
            with gr.Column(scale=4):
                # Chat interface
                chatbot = gr.Chatbot(
                    elem_id="chatbot",
                    height=500,
                    show_copy_button=True,
                    render_markdown=True,
                    avatar_images=(None, "🤖"),
                    show_label=False,
                )

                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask me anything about your documents and images...",
                        container=False,
                        scale=7,
                        max_lines=3,
                        show_label=False,
                        elem_id="chat-input"
                    )
                    submit_btn = gr.Button("Send", variant="primary", scale=1)

            with gr.Column(scale=1):
                # File upload area
                gr.Markdown("### 📁 Upload Files")
                file_upload = gr.File(
                    label="Drop files here",
                    file_types=["image", ".pdf", ".doc", ".docx", ".txt", ".md"],
                    file_count="multiple",
                    elem_id="file-upload-area"
                )
                upload_status = gr.Textbox(
                    label="Upload Status",
                    interactive=False,
                    show_label=True
                )

                # File indicators
                uploaded_files_display = gr.Markdown("*No files uploaded*")

                # Controls
                clear_btn = gr.Button("🗑️ Clear Session", variant="secondary")

        # Examples
        gr.Examples(
            examples=examples,
            inputs=msg,
            label="Example Questions"
        )

        # Footer
        gr.Markdown(
            """
            ---
            💡 Supported files: Images (JPG, PNG, GIF), Documents (PDF, DOC, TXT)
            """
        )

        # Event handlers
        async def handle_upload(files, state):
            if not files:
                return "No files selected", state, "*No files uploaded*"

            status, new_state, _ = await process_upload(files, state)

            # Update file display
            uploaded = new_state.get("uploaded_files", [])
            if uploaded:
                display = "**Uploaded Files:**\n"
                for f in uploaded:
                    icon = "📷" if f.get("is_image") else "📄"
                    display += f"\n- {icon} {f['filename']}"
            else:
                display = "*No files uploaded*"

            return status, new_state, display

        async def handle_message(message, history, state):
            if not message.strip():
                return history, ""

            history = history or []
            history.append([message, None])

            response = ""
            async for chunk in chat_function(message, history[:-1], state):
                response = chunk
                history[-1][1] = response
                yield history, ""

        def handle_clear(state):
            new_state, history, _ = clear_session(state)
            return new_state, history, "", "*No files uploaded*", "Session cleared"

        # Connect events
        file_upload.upload(
            fn=handle_upload,
            inputs=[file_upload, session_state],
            outputs=[upload_status, session_state, uploaded_files_display]
        )

        msg.submit(
            fn=handle_message,
            inputs=[msg, chatbot, session_state],
            outputs=[chatbot, msg]
        )

        submit_btn.click(
            fn=handle_message,
            inputs=[msg, chatbot, session_state],
            outputs=[chatbot, msg]
        )

        clear_btn.click(
            fn=handle_clear,
            inputs=[session_state],
            outputs=[session_state, chatbot, msg, uploaded_files_display, upload_status]
        )

    return demo


# Create the demo
demo = create_chat_interface()


if __name__ == "__main__":
    port = int(os.getenv("CHAT_UI_PORT", 7860))
    server_name = os.getenv("CHAT_UI_HOST", "0.0.0.0")

    logger.info(
        "Launching Empire Chat UI with File Upload",
        host=server_name,
        port=port,
        api_url=os.getenv("EMPIRE_API_URL", "http://localhost:8000")
    )

    demo.queue(max_size=20, default_concurrency_limit=10)

    demo.launch(
        server_name=server_name,
        server_port=port,
        share=False,
        show_api=False,
        show_error=True,
    )
