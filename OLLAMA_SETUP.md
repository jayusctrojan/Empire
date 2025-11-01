# Ollama Setup Guide for Empire v7.2

## Quick Install (5 minutes)

### Step 1: Install Ollama

```bash
# Install via Homebrew (recommended)
brew install ollama

# OR download installer from: https://ollama.com/download
```

### Step 2: Start Ollama Service

```bash
# Start as background service (recommended - starts on boot)
brew services start ollama

# OR run manually in terminal (for testing)
# ollama serve
```

### Step 3: Pull BGE-M3 Embeddings Model

```bash
# Pull the 1024-dim embedding model (~2.2GB)
ollama pull bge-m3

# This will take 2-5 minutes depending on your internet speed
```

### Step 4: Pull BGE-Reranker-v2 Model

```bash
# Pull the reranking model (~1.5GB)
ollama pull bge-reranker-v2-m3

# This will take 1-3 minutes
```

### Step 5: Verify Installation

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# You should see both models listed:
# {
#   "models": [
#     {
#       "name": "bge-m3:latest",
#       "modified_at": "...",
#       "size": 2345678901
#     },
#     {
#       "name": "bge-reranker-v2-m3:latest",
#       "modified_at": "...",
#       "size": 1234567890
#     }
#   ]
# }
```

### Step 6: Test Embedding Generation

```bash
# Test BGE-M3 embeddings
curl http://localhost:11434/api/embeddings -d '{
  "model": "bge-m3",
  "prompt": "California insurance policy document"
}'

# Should return JSON with 1024-dim vector:
# {
#   "embedding": [0.123, -0.456, 0.789, ...]
# }
```

### Step 7: Test Reranking

```bash
# Test BGE-Reranker
curl http://localhost:11434/api/generate -d '{
  "model": "bge-reranker-v2-m3",
  "prompt": "query: insurance policy\ndoc: This document contains insurance policy details...",
  "stream": false
}'

# Should return relevance score
```

---

## Troubleshooting

### Issue: "command not found: ollama"

**Solution:**
```bash
# Make sure Homebrew path is in your shell
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Then try again
ollama --version
```

### Issue: "connection refused" when testing

**Solution:**
```bash
# Check if Ollama is running
brew services list | grep ollama

# If not running, start it
brew services start ollama

# Wait 5 seconds, then test again
curl http://localhost:11434/api/tags
```

### Issue: Models download slowly

**Solution:**
- BGE-M3 is 2.2GB, BGE-Reranker is 1.5GB
- Total ~3.7GB download
- Be patient, it's a one-time download
- Models are cached at `~/.ollama/models/`

### Issue: "insufficient memory" error

**Solution:**
- Your Mac Studio has 96GB RAM, so this shouldn't happen
- If it does, close other applications
- Each model uses 2-4GB RAM when loaded

---

## Verify Everything Works

### Test Script

Create a test file to verify both models work:

```bash
# Create test script
cat > /tmp/test_ollama.sh << 'EOF'
#!/bin/bash

echo "Testing Ollama Installation..."
echo ""

echo "1. Checking Ollama is running..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama is running"
else
    echo "❌ Ollama is not running"
    exit 1
fi

echo ""
echo "2. Testing BGE-M3 embeddings..."
EMBEDDING=$(curl -s http://localhost:11434/api/embeddings -d '{
  "model": "bge-m3",
  "prompt": "test"
}')

if echo "$EMBEDDING" | grep -q "embedding"; then
    echo "✅ BGE-M3 is working"
    # Count dimensions
    DIM=$(echo "$EMBEDDING" | jq '.embedding | length')
    echo "   Vector dimensions: $DIM"
else
    echo "❌ BGE-M3 failed"
fi

echo ""
echo "3. Testing BGE-Reranker-v2..."
RERANK=$(curl -s http://localhost:11434/api/generate -d '{
  "model": "bge-reranker-v2-m3",
  "prompt": "query: test\ndoc: test document",
  "stream": false
}')

if echo "$RERANK" | grep -q "response"; then
    echo "✅ BGE-Reranker-v2 is working"
else
    echo "❌ BGE-Reranker-v2 failed"
fi

echo ""
echo "All tests complete!"
EOF

# Make executable
chmod +x /tmp/test_ollama.sh

# Run tests
/tmp/test_ollama.sh
```

---

## Configuration for Empire

### Update .env File

Your `.env` already has:
```bash
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=bge-m3
RERANKER_MODEL=bge-reranker-v2-m3
```

No changes needed! ✅

### Python Integration Example

```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "bge-reranker-v2-m3")

def generate_embeddings(text: str) -> list[float]:
    """Generate 1024-dim embeddings using BGE-M3"""
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=30
    )
    response.raise_for_status()
    return response.json()["embedding"]

def rerank_documents(query: str, documents: list[str], top_k: int = 10) -> list[dict]:
    """Rerank documents using BGE-Reranker-v2"""
    results = []

    for doc in documents:
        prompt = f"query: {query}\ndoc: {doc}"
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": RERANKER_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()

        # Extract relevance score from response
        score = response.json().get("score", 0)
        results.append({"document": doc, "score": score})

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

# Test it
if __name__ == "__main__":
    # Test embeddings
    embedding = generate_embeddings("California insurance policy")
    print(f"✅ Generated embedding with {len(embedding)} dimensions")

    # Test reranking
    docs = [
        "This document discusses California insurance policies.",
        "This is about New York real estate law.",
        "Employee benefits and insurance coverage details."
    ]
    results = rerank_documents("California insurance", docs, top_k=3)
    print(f"✅ Reranked {len(results)} documents")
    for i, result in enumerate(results, 1):
        print(f"  {i}. Score: {result['score']:.4f} - {result['document'][:50]}...")
```

---

## Performance Notes

### Mac Studio M3 Ultra (96GB)

**BGE-M3 Performance:**
- First run: ~500ms (model loading)
- Subsequent runs: ~50-100ms per embedding
- Batch processing: Can do 10-20 embeddings/second
- Memory usage: ~3GB when loaded

**BGE-Reranker-v2 Performance:**
- First run: ~300ms (model loading)
- Subsequent runs: ~30-50ms per document
- Can rerank 100 documents in ~3-5 seconds
- Memory usage: ~2GB when loaded

**Total Memory Usage:**
- Both models loaded: ~5-6GB
- Your Mac Studio has 96GB, so plenty of headroom
- Models stay in memory for fast inference

---

## Remote Access via Tailscale

### Setup (for production deployment)

1. **Install Tailscale on Mac Studio:**
```bash
brew install --cask tailscale
sudo tailscale up
```

2. **Get Tailscale IP:**
```bash
tailscale ip -4
# Example: 100.x.x.x
```

3. **Update .env for production:**
```bash
# For remote Render services to access Mac Studio
OLLAMA_BASE_URL=http://100.x.x.x:11434  # Use Tailscale IP
```

4. **Test from another device:**
```bash
# From your laptop (with Tailscale connected)
curl http://100.x.x.x:11434/api/tags
```

---

## Maintenance

### Update Models

```bash
# Check for updates
ollama list

# Update a model
ollama pull bge-m3
ollama pull bge-reranker-v2-m3
```

### Monitor Resource Usage

```bash
# Check Ollama service status
brew services info ollama

# View logs
tail -f $(brew --prefix)/var/log/ollama.log

# Check memory usage
ps aux | grep ollama
```

### Restart Ollama

```bash
# Restart service
brew services restart ollama

# Or if running manually
# Kill the process and restart:
# pkill ollama
# ollama serve
```

---

## Summary Checklist

- [ ] Install Ollama via Homebrew
- [ ] Start Ollama as background service
- [ ] Pull BGE-M3 model (~2.2GB, 2-5 min)
- [ ] Pull BGE-Reranker-v2 model (~1.5GB, 1-3 min)
- [ ] Verify with curl commands
- [ ] Run test script
- [ ] Test Python integration
- [ ] (Optional) Setup Tailscale for remote access

**Total time: ~10-15 minutes (including downloads)**

---

## Next Steps

After Ollama is set up:
1. ✅ Mark "Ollama installed with BGE-M3 model" as complete in PRE_DEV_CHECKLIST.md
2. ✅ Mark "Ollama installed with BGE-Reranker-v2" as complete in PRE_DEV_CHECKLIST.md
3. Continue with Supabase setup
4. Start FastAPI development

---

**Last Updated**: 2025-01-01
**Empire Version**: v7.2
**For**: Mac Studio M3 Ultra (96GB)
