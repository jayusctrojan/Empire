"""
BGE-Reranker-v2 API Wrapper with Authentication
Wraps Ollama's BGE-Reranker-v2 with FastAPI and API key auth
Exposes via Tailscale Funnel for secure remote access from Render services
"""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from typing import Optional

app = FastAPI(
    title="BGE-Reranker-v2 API",
    description="Authenticated reranking service using BGE-Reranker-v2 on Mac Studio",
    version="1.0.0"
)

# CORS middleware for Render services
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to your Render domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load API key from environment
RERANKER_API_KEY = os.getenv("RERANKER_API_KEY")
if not RERANKER_API_KEY:
    raise ValueError("RERANKER_API_KEY environment variable not set! Generate one with: openssl rand -hex 32")

OLLAMA_BASE_URL = "http://localhost:11434"
RERANKER_MODEL = "qllama/bge-reranker-v2-m3"


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_n: Optional[int] = 10


class RerankResult(BaseModel):
    index: int
    document: str
    score: float


class RerankResponse(BaseModel):
    results: list[RerankResult]
    query: str
    model: str


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "BGE-Reranker-v2 API",
        "status": "running",
        "endpoints": {
            "/health": "Health check",
            "/rerank": "Rerank documents (POST, requires X-API-Key header)"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint - no auth required"""
    try:
        # Check if Ollama is responsive
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        ollama_healthy = response.status_code == 200

        return {
            "status": "healthy" if ollama_healthy else "degraded",
            "ollama": "connected" if ollama_healthy else "disconnected",
            "model": RERANKER_MODEL
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/rerank", response_model=RerankResponse)
async def rerank(
    request: RerankRequest,
    x_api_key: str = Header(..., description="API key for authentication")
):
    """
    Rerank documents based on query relevance

    Args:
        request: RerankRequest with query and documents
        x_api_key: API key (passed in X-API-Key header)

    Returns:
        RerankResponse with ranked results
    """
    # Validate API key
    if x_api_key != RERANKER_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Validate input
    if not request.documents:
        raise HTTPException(
            status_code=400,
            detail="No documents provided"
        )

    if request.top_n < 1:
        raise HTTPException(
            status_code=400,
            detail="top_n must be at least 1"
        )

    try:
        # Format prompt for BGE-Reranker-v2
        # The model expects: "query: <query>\ndoc: <document>"
        results = []

        for idx, doc in enumerate(request.documents):
            prompt = f"query: {request.query}\ndoc: {doc}"

            # Call Ollama embeddings API (reranker models output embeddings)
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": RERANKER_MODEL,
                    "prompt": prompt
                },
                timeout=30
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Ollama API error: {response.text}"
                )

            # Parse response and extract relevance score
            result = response.json()
            embedding = result.get("embedding", [])

            if not embedding:
                raise HTTPException(
                    status_code=500,
                    detail="No embedding returned from model"
                )

            # For BGE-Reranker-v2, the relevance score is typically the first value
            # or we can use the sum/mean of embeddings as a proxy for relevance
            # Using the first embedding value as the relevance score
            score = float(embedding[0]) if embedding else 0.0

            results.append(RerankResult(
                index=idx,
                document=doc,
                score=score
            ))

        # Sort by score ascending (lower/more negative = more relevant for BGE-Reranker-v2)
        results.sort(key=lambda x: x.score, reverse=False)

        # Return top_n results
        top_results = results[:request.top_n]

        return RerankResponse(
            results=top_results,
            query=request.query,
            model=RERANKER_MODEL
        )

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama request timed out"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reranking error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    print("Starting BGE-Reranker-v2 API on port 8081...")
    print(f"API Key authentication enabled")
    print(f"Access via: http://localhost:8081")
    print(f"Or via Tailscale Funnel: https://jays-mac-studio.ts.net")
    uvicorn.run(app, host="0.0.0.0", port=8081)
