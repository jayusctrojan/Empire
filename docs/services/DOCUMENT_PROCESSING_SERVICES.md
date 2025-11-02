# Document Processing Services - Empire v7.2

## Overview
These services are **REQUIRED** components of Empire's document processing pipeline, not optional. Each handles specific document types and processing needs.

---

## 1. Backblaze B2 - Primary File Storage ✅ CONFIGURED

### Purpose
- **Primary storage** for all document files
- **Backup** repository for processed data
- **Source of truth** for original files
- **Multi-modal content** storage (PDFs, audio, video, images)

### Configuration
```bash
B2_APPLICATION_KEY_ID=***REMOVED***
B2_APPLICATION_KEY=***REMOVED***
B2_BUCKET_NAME=JB-Course-KB
```

### Folder Structure
```
JB-Course-KB/
├── content/course/       # Course materials and educational content
├── pending/              # Documents awaiting processing
├── processed/            # Successfully processed documents
├── failed/               # Failed processing attempts (for retry)
└── youtube-content/      # YouTube transcripts and metadata
```

### Workflow Integration
```
1. Document Upload → pending/
2. Processing Success → processed/
3. Processing Failure → failed/
4. Course Materials → content/course/
5. YouTube Scraping → youtube-content/
```

### Python Integration
```python
from b2sdk.v2 import B2Api, InMemoryAccountInfo
import os

def init_b2():
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account(
        "production",
        os.getenv("B2_APPLICATION_KEY_ID"),
        os.getenv("B2_APPLICATION_KEY")
    )
    return b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

def upload_to_b2(local_path: str, b2_path: str):
    """Upload file to B2 bucket"""
    bucket = init_b2()
    bucket.upload_local_file(
        local_file=local_path,
        file_name=b2_path
    )

def download_from_b2(b2_path: str, local_path: str):
    """Download file from B2 bucket"""
    bucket = init_b2()
    file_version = bucket.get_file_info_by_name(b2_path)
    downloaded_file = bucket.download_file_by_name(b2_path)
    downloaded_file.save_to(local_path)

def move_to_processed(filename: str):
    """Move file from pending to processed"""
    bucket = init_b2()
    # Copy to new location
    bucket.copy_file(
        file_id=f"pending/{filename}",
        new_file_name=f"processed/{filename}"
    )
    # Delete from pending
    bucket.delete_file_version(file_id, file_name)
```

### Cost
- **Storage**: ~$5/TB/month
- **Downloads**: $0.01/GB (first 1GB free/day)
- **Uploads**: FREE
- **Estimated**: $10-20/month for Empire

---

## 2. Soniox - Audio/Video Transcription ✅ CONFIGURED

### Purpose
- **Audio transcription** for course videos, podcasts
- **Video transcription** for YouTube content
- **Multi-language** support
- **Speaker diarization** (who said what)
- **Timestamp alignment** for precise citations

### Configuration
```bash
SONIOX_API_KEY=***REMOVED***
```

### When Used
- Course video uploads
- YouTube content scraping
- Podcast processing
- Interview transcripts
- Audio-based learning materials

### Python Integration
```python
import soniox
import os

def transcribe_audio(audio_path: str) -> dict:
    """Transcribe audio file using Soniox"""
    client = soniox.SpeechClient(api_key=os.getenv("SONIOX_API_KEY"))

    with open(audio_path, "rb") as audio_file:
        result = client.transcribe_file_short(
            audio=audio_file.read(),
            model="en_v2",
            enable_speaker_diarization=True,
            enable_punctuation=True
        )

    return {
        "transcript": result.text,
        "speakers": [
            {
                "speaker": segment.speaker,
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time
            }
            for segment in result.segments
        ],
        "confidence": result.confidence
    }

def transcribe_youtube_video(youtube_url: str) -> dict:
    """Download and transcribe YouTube video"""
    # Download audio using yt-dlp
    import yt_dlp

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        audio_file = f"/tmp/{info['id']}.wav"

    # Transcribe
    transcript = transcribe_audio(audio_file)

    # Store in B2
    upload_to_b2(
        audio_file,
        f"youtube-content/{info['id']}.wav"
    )

    return {
        **transcript,
        "video_id": info['id'],
        "title": info['title'],
        "duration": info['duration']
    }
```

### Cost
- **Pricing**: $0.015/minute of audio
- **Estimated**: $10-20/month (500-1,000 minutes)
- **Free tier**: First 2 hours free

---

## 3. Mistral OCR - Complex PDF Processing ⏳ NEEDS API KEY

### Purpose
- **Complex PDFs** with poor formatting
- **Scanned documents** requiring OCR
- **Multi-column** layouts
- **Tables and diagrams** extraction
- **Handwritten notes** (limited support)

### Why Not Claude/LlamaParse?
- **LlamaParse**: Good for structured PDFs, but struggles with scanned/image-based
- **Claude Vision**: Great for single pages, expensive for 100+ page docs
- **Mistral OCR**: Specialized for high-accuracy OCR, better than Tesseract

### When Used
- Scanned insurance policies
- Old archived documents
- Poor-quality PDF scans
- Complex multi-column contracts
- Image-heavy documents

### Configuration Needed
```bash
MISTRAL_API_KEY=your-mistral-api-key
```

**Get API Key**: https://console.mistral.ai/

### Python Integration
```python
import mistralai
import os

def ocr_pdf_with_mistral(pdf_path: str) -> dict:
    """OCR complex PDF using Mistral"""
    client = mistralai.MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))

    # Upload PDF
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # OCR request
    result = client.ocr(
        file=pdf_bytes,
        options={
            "extract_tables": True,
            "extract_images": True,
            "language": "en"
        }
    )

    return {
        "text": result.text,
        "tables": result.tables,
        "images": result.images,
        "confidence": result.confidence
    }

def process_scanned_document(b2_path: str) -> dict:
    """Download from B2, OCR, and store results"""
    # Download from B2
    local_path = f"/tmp/{b2_path.split('/')[-1]}"
    download_from_b2(b2_path, local_path)

    # Check if needs OCR (scanned or low quality)
    needs_ocr = check_if_scanned(local_path)  # Your detection logic

    if needs_ocr:
        # Use Mistral OCR
        result = ocr_pdf_with_mistral(local_path)
    else:
        # Use LlamaParse (cheaper for clean PDFs)
        result = llamaparse_document(local_path)

    return result
```

### Cost
- **Pricing**: ~$0.50-1.00 per document
- **Estimated**: $20/month (20-40 documents)
- **Alternative**: Use only for failed LlamaParse attempts

---

## 4. LangExtract - Structured Data Extraction ⏳ NEEDS API KEY

### Purpose
- **Structured field extraction** (dates, amounts, IDs, names)
- **Entity recognition** with schema validation
- **Relationship extraction** between entities
- **>95% accuracy** with confidence scores
- **Gemini-powered** for precise grounding

### Why Needed
- **Claude Sonnet**: Great for synthesis, but can hallucinate structured data
- **LlamaIndex**: Good for retrieval, not specialized for extraction
- **LangExtract**: Specialized for **high-accuracy** structured extraction

### When Used
- Insurance policy field extraction (policy #, dates, amounts)
- Contract parsing (parties, terms, conditions)
- Invoice processing (line items, totals)
- Employee records (names, IDs, departments)
- Legal document analysis (clauses, obligations)

### Configuration Needed
```bash
LANGEXTRACT_API_KEY=your-langextract-api-key
# OR use Google Gemini API directly
GOOGLE_GEMINI_API_KEY=your-gemini-api-key
```

**Get API Key**:
- LangExtract: https://langextract.com/
- Google Gemini: https://ai.google.dev/

### Python Integration
```python
import requests
import os

def extract_structured_data(text: str, schema: dict) -> dict:
    """Extract structured data using LangExtract"""

    response = requests.post(
        "https://api.langextract.com/v1/extract",
        headers={
            "Authorization": f"Bearer {os.getenv('LANGEXTRACT_API_KEY')}",
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "schema": schema,
            "validate": True,
            "confidence_threshold": 0.85
        }
    )

    return response.json()

def extract_insurance_policy(document_text: str) -> dict:
    """Extract structured fields from insurance policy"""

    schema = {
        "policy_number": {"type": "string", "required": True},
        "policy_holder": {"type": "string", "required": True},
        "effective_date": {"type": "date", "format": "YYYY-MM-DD"},
        "expiration_date": {"type": "date", "format": "YYYY-MM-DD"},
        "premium_amount": {"type": "number", "currency": "USD"},
        "coverage_types": {"type": "array", "items": "string"},
        "deductible": {"type": "number", "currency": "USD"}
    }

    result = extract_structured_data(document_text, schema)

    return {
        "extracted": result["extracted"],
        "confidence": result["confidence"],
        "validated": result["validation_passed"]
    }

def extract_with_cross_validation(document_text: str, schema: dict) -> dict:
    """Extract with LangExtract + LlamaIndex cross-validation"""

    # Primary extraction with LangExtract
    langextract_result = extract_structured_data(document_text, schema)

    # Cross-validate with LlamaIndex retrieval
    relevant_chunks = llamaindex_search(document_text, top_k=5)

    # Verify extracted data appears in source chunks
    validated = verify_extraction(
        langextract_result["extracted"],
        relevant_chunks
    )

    return {
        **langextract_result,
        "cross_validated": validated,
        "source_chunks": relevant_chunks
    }
```

### Cost
- **LangExtract**: ~$0.10-0.20 per document
- **Google Gemini**: ~$0.05 per document (via API)
- **Estimated**: $10-20/month (100-200 documents)

---

## 5. Service Integration Architecture

### Document Processing Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Document Upload                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
              ┌──────────────┐
              │ Upload to B2 │
              │  (pending/)  │
              └──────┬───────┘
                     │
                     ↓
         ┌───────────────────────┐
         │   File Type Detection │
         └───────┬───────────────┘
                 │
      ┌──────────┼──────────┬──────────┐
      │          │          │          │
      ↓          ↓          ↓          ↓
┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│   PDF   │ │ Audio  │ │ Video  │ │ Image  │
└────┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
     │          │          │          │
     ↓          ↓          ↓          │
┌─────────────┐ │      ┌─────────┐   │
│Clean PDF?   │ │      │ Soniox  │   │
├─────────────┤ │      │Transcript│   │
│YES: LlamaParse│     └────┬────┘   │
│NO: Mistral  │ │          │          │
└─────┬───────┘ └──────────┼──────────┘
      │                    │
      ↓                    ↓
┌────────────────────────────────────┐
│     Extracted Text & Metadata      │
└────────────────┬───────────────────┘
                 │
                 ↓
┌────────────────────────────────────┐
│   LangExtract: Structured Fields  │
│   (Policy #, Dates, Amounts, etc) │
└────────────────┬───────────────────┘
                 │
                 ↓
┌────────────────────────────────────┐
│    Claude Sonnet: Entity Extract   │
│    (People, Orgs, Relationships)   │
└────────────────┬───────────────────┘
                 │
                 ↓
┌────────────────────────────────────┐
│  BGE-M3: Generate 1024-dim Vectors │
└────────────────┬───────────────────┘
                 │
      ┌──────────┼──────────┐
      │          │          │
      ↓          ↓          ↓
┌──────────┐ ┌──────┐ ┌──────────┐
│ Supabase │ │Neo4j │ │B2: Move  │
│ pgvector │ │Graph │ │processed/│
└──────────┘ └──────┘ └──────────┘
```

---

## 6. Service Priority Matrix

| Document Type | Primary Service | Fallback | Cost per Doc |
|---------------|----------------|----------|--------------|
| **Clean PDF** | LlamaParse | Claude Vision | $0.05 |
| **Scanned PDF** | Mistral OCR | - | $0.50-1.00 |
| **Audio/Video** | Soniox | - | $0.015/min |
| **Structured Extract** | LangExtract | Claude + Validation | $0.10-0.20 |
| **Image** | Claude Vision | - | $0.02/image |
| **Storage** | Backblaze B2 | - | $0.005/GB |

---

## 7. Monthly Cost Breakdown

```
Document Processing Services:
├── Backblaze B2           $10-20   (primary storage)
├── Soniox                 $10-20   (audio transcription)
├── Mistral OCR            $20      (complex PDFs)
├── LangExtract            $10-20   (structured extraction)
└── SUBTOTAL               $50-80/month

Core Infrastructure:
├── Supabase               $15      (pgvector)
├── Anthropic Claude       $250-300 (synthesis)
├── LlamaCloud             $50      (clean PDF parsing)
├── LlamaIndex (Render)    $7-21    (processing)
└── CrewAI (Render)        $7-21    (orchestration)

Local (FREE):
├── Neo4j                  $0
├── Redis                  $0
└── Ollama                 $0

TOTAL: $389-487/month
```

Still within $350-500 budget target! 🎯

---

## 8. Setup Checklist

### ✅ Already Configured:
- [x] Backblaze B2 (key + bucket)
- [x] Soniox (API key)

### ⏳ Needs API Keys:
- [ ] Mistral OCR - https://console.mistral.ai/
- [ ] LangExtract - https://langextract.com/
- [ ] OR Google Gemini - https://ai.google.dev/

### 📝 Next Steps:
1. Get Mistral API key (for scanned PDFs)
2. Get LangExtract or Gemini API key (for structured extraction)
3. Update `.env` file with new keys
4. Test document processing pipeline
5. Implement B2 folder management (pending → processed)

---

**Last Updated**: 2025-01-01
**Empire Version**: v7.2
**Status**: 2/4 services configured, 2 pending API keys
