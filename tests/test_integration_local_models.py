"""
Integration tests for local perception layer (Ollama Qwen-VL + Whisper STT).

These tests require Ollama to be running with the qwen2.5vl:32b-q8_0 model.
Skip automatically in CI or when Ollama is not available.
"""

import asyncio
import base64
import os
import tempfile
from pathlib import Path

import httpx
import pytest


def ollama_available() -> bool:
    """Check if Ollama is running and the VLM model is loaded."""
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code != 200:
            return False
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        return any("qwen2.5vl" in m for m in models)
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not ollama_available(),
        reason="Ollama not running or qwen2.5vl model not available",
    ),
]

# Minimal valid JPEG (1x1 red pixel) — shared across all tests
MINIMAL_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
    "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJ"
    "CQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEA"
    "AAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIh"
    "MUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6"
    "Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZ"
    "mqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx"
    "8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
    "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAV"
    "YnLRChYkNOEl8RcYI4Q/RFhHRFNSYVYWYoKDkuMDE1N0c4OUo7Kygp+0NDU2Nzg5"
    "OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaX"
    "mJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq"
    "8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+gD/2Q=="
)


@pytest.fixture
def test_image_path(tmp_path: Path) -> str:
    """Create a minimal valid JPEG test image."""
    path = tmp_path / "test_image.jpg"
    path.write_bytes(MINIMAL_JPEG)
    return str(path)


class TestLocalModelIntegration:

    @pytest.mark.asyncio
    async def test_qwen_vl_image_analysis(self, test_image_path):
        """Send a real image to Qwen-VL via OllamaVLMClient, verify text response."""
        from app.services.llm_client import OllamaVLMClient, _clients

        _clients.clear()
        client = OllamaVLMClient()

        with open(test_image_path, "rb") as f:
            image_bytes = f.read()

        result = await client.generate_with_images(
            system="You are a helpful image analyst.",
            prompt="Describe this image in one sentence.",
            images=[{"data": image_bytes, "mime_type": "image/jpeg"}],
            max_tokens=100,
        )

        assert isinstance(result, str)
        assert len(result) > 0
        _clients.clear()

    @pytest.mark.asyncio
    async def test_qwen_vl_multiple_frames(self, tmp_path):
        """Analyze multiple frames via VisionService.analyze_frames()."""
        from unittest.mock import patch, MagicMock
        from app.services.vision_service import VisionService
        from app.services.llm_client import OllamaVLMClient, _clients

        _clients.clear()

        frames = []
        for i in range(3):
            path = tmp_path / f"frame_{i:03d}.jpg"
            path.write_bytes(MINIMAL_JPEG)
            frames.append({
                "path": str(path),
                "timestamp_seconds": float(i),
                "frame_number": i + 1,
            })

        # Use real OllamaVLMClient but mock the file handler
        mock_handler = MagicMock()
        with patch("app.services.vision_service.get_chat_file_handler", return_value=mock_handler):
            svc = VisionService(max_retries=1)

        results = await svc.analyze_frames(frames)

        assert len(results) == 3
        for r in results:
            assert r["success"] is True
            assert isinstance(r["analysis"], str)
            assert len(r["analysis"]) > 0

        _clients.clear()
