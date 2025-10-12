# 3. Specific Requirements

## 3.1 Functional Requirements

### 3.1.1 Document Processing Requirements (Core - All Versions)

#### 3.1.1.1 Unified MarkItDown Processing

**FR-001:** The system SHALL accept documents in 40+ supported formats

*Priority: Essential*
*Source: Product Management*
*Verification: Integration Testing*
*Status: Active - All Versions*

**FR-002:** The system SHALL convert all supported formats to clean Markdown using MarkItDown MCP

*Priority: Essential*
*Dependencies: TC-003*
*Status: Active - All Versions*

**FR-003:** The system SHALL preserve document structure including headings, lists, and paragraphs

*Priority: Essential*
*Status: Active - All Versions*

**FR-004:** The system SHALL extract and preserve tables with proper formatting

*Priority: High*
*Status: Active - All Versions*

**FR-005:** The system SHALL handle embedded images by extracting and referencing them

*Priority: High*
*Status: Active - All Versions*

**FR-006:** The system SHALL extract document metadata including title, author, creation date

*Priority: Medium*
*Status: Active - All Versions*

**Supported Formats via MarkItDown MCP:**
- **Microsoft Office:** DOCX, XLSX, PPTX, DOC, XLS, PPT
- **Web Formats:** HTML, XML, MHTML, JSON, YAML
- **Archives:** ZIP, EPUB, TAR, GZ
- **Images:** JPG, PNG, GIF, BMP, TIFF, SVG, WEBP
- **Data:** CSV, TSV, JSON, YAML, TOML
- **Text:** TXT, MD, RTF, LOG
- **Simple PDFs:** Text-based PDFs without complex formatting

#### 3.1.1.2 Intelligent PDF Routing

**FR-007:** The system SHALL assess PDF complexity before processing

*Priority: Essential*
*Status: Active - All Versions*

**FR-008:** The system SHALL route simple text-based PDFs to MarkItDown MCP

*Priority: Essential*
*Status: Active - All Versions*

**FR-009:** The system SHALL route complex PDFs to Mistral OCR when:
- Document contains complex tables or layouts
- Document contains diagrams or flowcharts
- Document contains mathematical formulas
- File size exceeds 10MB
- MarkItDown processing fails

*Priority: Essential*
*Note: v5.0 - Only complex PDFs use cloud OCR, simple PDFs processed locally*
*Status: Active - All Versions*

**FR-010:** The system SHALL merge OCR output seamlessly with main pipeline

*Priority: High*
*Status: Active - All Versions*

```python
# PDF Complexity Assessment Logic
def assessPDFComplexity(file):
    criteria = {
        hasComplexTables: checkForComplexTables(file),
        hasDiagrams: checkForDiagrams(file),
        hasFormulas: checkForMathFormulas(file),
        largeFileSize: file.size > 10485760,  # 10MB
        hasMultiColumn: checkForMultiColumnLayout(file)
    }
    return Object.values(criteria).some(v => v === true)
```

#### 3.1.1.3 Mistral OCR Processing (Complex PDFs Only)

**FR-011:** The system SHALL upload complex PDFs to Mistral OCR API

*Priority: Essential*
*Note: v5.0 - Used sparingly, only for complex PDFs*
*Status: Active - All Versions*

**FR-012:** The system SHALL poll Mistral API for OCR completion status

*Priority: Essential*
*Status: Active - All Versions*

**FR-013:** The system SHALL extract Markdown-formatted text from OCR results

*Priority: Essential*
*Status: Active - All Versions*

**FR-014:** The system SHALL handle OCR timeouts with retry logic (3 attempts)

*Priority: High*
*Status: Active - All Versions*

**FR-015:** The system SHALL fallback to basic text extraction if OCR fails

*Priority: Medium*
*Status: Active - All Versions*

### 3.1.2 Multimedia Processing Requirements (All Versions)

#### 3.1.2.1 YouTube Content Extraction

**FR-016:** The system SHALL extract YouTube video metadata including:
- Title, description, duration
- Channel information
- Upload date, view count
- Tags and categories

*Priority: High*
*Status: Active - All Versions*

**FR-017:** The system SHALL retrieve video transcripts using three-tier hierarchy:
1. Official YouTube captions (highest priority)
2. Auto-generated captions (medium priority)
3. Soniox transcription of audio (fallback)

*Priority: Essential*
*Status: Active - All Versions*

**FR-018:** The system SHALL extract video frames at configurable intervals (default: 30 seconds)

*Priority: Medium*
*Note: v5.0 - Frames analyzed locally with Qwen2.5-VL*
*Status: Active - All Versions*

**FR-019:** The system SHALL analyze extracted frames for educational content

*Priority: Low*
*Note: v5.0 - Uses local Qwen2.5-VL instead of cloud*
*Status: Active - All Versions*

**FR-020:** The system SHALL create timestamped descriptions of visual content

*Priority: Low*
*Status: Active - All Versions*

**FR-021:** The system SHALL output unified Markdown document with transcript and metadata

*Priority: Essential*
*Status: Active - All Versions*

#### 3.1.2.2 Audio/Video Transcription

**FR-022:** The system SHALL transcribe audio/video files using Soniox API

*Priority: Essential*
*Note: Cloud-based service, no local alternative currently*
*Status: Active - All Versions*

**FR-023:** The system SHALL enable speaker diarization for multi-speaker content

*Priority: High*
*Status: Active - All Versions*

**FR-024:** The system SHALL support automatic language detection

*Priority: Medium*
*Status: Active - All Versions*

**FR-025:** The system SHALL handle files up to 300MB

*Priority: Essential*
*Status: Active - All Versions*

**FR-026:** The system SHALL output transcripts as properly formatted Markdown

*Priority: Essential*
*Status: Active - All Versions*

**FR-027:** The system SHALL include speaker labels and timestamps in output

*Priority: High*
*Status: Active - All Versions*

**Supported Audio Formats:** MP3, WAV, FLAC, AAC, OGG, WMA, M4A, OPUS
**Supported Video Formats:** MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPG

#### 3.1.2.3 Web Content Ingestion

**FR-028:** The system SHALL integrate Firecrawl for web scraping capabilities

*Priority: Essential*
*Note: Cloud service for web scraping*
*Status: Active - All Versions*

**FR-029:** The system SHALL support scheduled crawling of specified URLs

*Priority: High*
*Status: Active - All Versions*

**FR-030:** The system SHALL extract clean Markdown from web pages

*Priority: Essential*
*Status: Active - All Versions*

**FR-031:** The system SHALL handle JavaScript-rendered content

*Priority: Medium*
*Status: Active - All Versions*

**FR-032:** The system SHALL respect robots.txt and rate limiting

*Priority: Essential*
*Status: Active - All Versions*

**FR-033:** The system SHALL support webhook callbacks for crawl completion

*Priority: Medium*
*Status: Active - All Versions*

#### 3.1.2.4 SFTP/Local File Monitoring (v3.2+)

**FR-034:** The system SHALL monitor SFTP servers for new files

*Priority: High*
*Note: Added in v3.2*
*Status: Active - v3.2+*

**FR-035:** The system SHALL support local directory monitoring

*Priority: High*
*Note: Added in v3.2*
*Status: Active - v3.2+*

**FR-036:** The system SHALL process files automatically upon detection

*Priority: Essential*
*Status: Active - v3.2+*

### 3.1.3 Local AI Processing Requirements (NEW v5.0)

#### 3.1.3.1 Local LLM Inference

**LLR-001:** The system SHALL run Llama 3.3 70B locally on Mac Studio

*Priority: Essential*
*Hardware: Mac Studio M3 Ultra (96GB)*
*Performance: 32 tokens/second*
*Status: Active - v5.0*

**LLR-002:** The system SHALL prioritize local inference for all reasoning tasks

*Priority: Essential*
*Target: 98% of all inference*
*Status: Active - v5.0*

**LLR-003:** The system SHALL use Open WebUI for local LLM interaction

*Priority: Essential*
*Status: Active - v5.0*

**LLR-004:** The system SHALL provide LiteLLM API compatibility layer

*Priority: High*
*Purpose: Drop-in replacement for cloud APIs*
*Status: Active - v5.0*

**LLR-005:** The system SHALL manage models via Ollama

*Priority: Essential*
*Status: Active - v5.0*

**LLR-006:** The system SHALL support GGUF model format

*Priority: Essential*
*Storage: Efficient local model storage*
*Status: Active - v5.0*

#### 3.1.3.2 Local Embeddings

**LLR-007:** The system SHALL generate embeddings using local nomic-embed-text (2GB)

*Priority: Essential*
*Replaces: OpenAI text-embedding-3-small*
*Status: Active - v5.0*

**LLR-008:** The system SHALL create embeddings without external API calls

*Priority: Essential*
*Benefit: Zero latency, no cost*
*Status: Active - v5.0*

**LLR-009:** The system SHALL cache embeddings locally

*Priority: High*
*Storage: Mac Studio SSD*
*Status: Active - v5.0*

#### 3.1.3.3 Local Reranking

**LLR-010:** The system SHALL perform search reranking using local BGE-reranker

*Priority: High*
*Purpose: Optimize search results locally*
*Status: Active - v5.0*

**LLR-011:** The system SHALL fallback to Cohere only when necessary

*Priority: Medium*
*Condition: Complex multi-language queries*
*Status: Active - v5.0*

### 3.1.4 Visual Content Processing (UPDATED v5.0)

#### 3.1.4.1 Local Vision Analysis

**VIS-001:** The system SHALL process images using local Qwen2.5-VL-7B (5GB)

*Priority: Essential*
*Replaces: Mistral Pixtral-12B API*
*Performance: Real-time analysis*
*Status: Active - v5.0*

**VIS-002:** The system SHALL support visual query types including:
- Object identification ("What objects are in this image?")
- Text extraction from images ("What text is visible?")
- Diagram interpretation ("Explain this flowchart")
- Chart analysis ("What trend does this graph show?")
- Technical drawing comprehension ("What components are shown?")

*Priority: High*
*Note: All processed locally on Mac Studio*
*Status: Active - v5.0*

**VIS-003:** The system SHALL generate searchable descriptions for all extracted images

*Priority: Essential*
*Status: Active - v5.0*

**VIS-004:** The system SHALL store visual analysis results as metadata:

```json
{
  "image_id": "uuid",
  "source_document": "string",
  "visual_description": "string",
  "detected_objects": ["array"],
  "extracted_text": "string",
  "chart_data": {},
  "query_history": [],
  "processing_location": "local_mac_studio"
}
```

*Priority: High*
*Status: Active - v5.0*

**VIS-005:** The system SHALL cache visual analysis to avoid reprocessing

*Priority: Medium*
*Status: Active - v5.0*

**VIS-006:** The system SHALL support batch visual processing (up to 50 images)

*Priority: Medium*
*Note: Limited by Mac Studio memory*
*Status: Active - v5.0*

**VIS-007:** The system SHALL fallback to OCR for text-heavy images

*Priority: High*
*Status: Active - v5.0*

### 3.1.5 Hybrid RAG System Requirements (All Versions)

#### 3.1.5.1 Hash-Based Change Detection

**FR-046:** The system SHALL compute SHA-256 hash for all processed content

*Priority: Essential*
*Rationale: Prevents redundant processing*
*Status: Active - All Versions*

**FR-047:** The system SHALL check existing hash before initiating processing

*Priority: Essential*
*Status: Active - All Versions*

**FR-048:** The system SHALL skip processing when hash matches existing record

*Priority: Essential*
*Status: Active - All Versions*

**FR-049:** The system SHALL update vectors only when content hash changes

*Priority: Essential*
*Status: Active - All Versions*

**FR-050:** The system SHALL maintain complete hash history in PostgreSQL

*Priority: High*
*Status: Active - All Versions*

**FR-051:** The system SHALL synchronize hash records to Airtable for audit

*Priority: Medium*
*Status: Active - All Versions*

#### 3.1.5.2 Hybrid Search with Reranking

**FR-052:** The system SHALL implement hybrid search combining vector and keyword search

*Priority: Essential*
*Status: Active - All Versions*

**FR-053:** The system SHALL integrate reranking for result optimization

*Priority: Essential*
*Note: v5.0 - Primarily local BGE-reranker, Cohere as fallback*
*Status: Active - All Versions*

**FR-054:** The system SHALL support configurable top-k retrieval (default: 30)

*Priority: High*
*Status: Active - All Versions*

**FR-055:** The system SHALL rerank results to top-10 most relevant

*Priority: Essential*
*Status: Active - All Versions*

**FR-056:** The system SHALL maintain original relevance scores for analysis

*Priority: Medium*
*Status: Active - All Versions*

**FR-057:** The system SHALL support fallback to basic search if reranking fails

*Priority: High*
*Status: Active - All Versions*

#### 3.1.5.3 Knowledge Graph Integration (LightRAG)

**FR-061:** The system SHALL integrate LightRAG API for graph-based knowledge storage

*Priority: Essential*
*Note: Cloud-based service*
*Status: Active - All Versions*

**FR-062:** The system SHALL extract entities and relationships from documents

*Priority: Essential*
*Note: v5.0 - Extraction via local Llama 70B*
*Status: Active - All Versions*

**FR-063:** The system SHALL support hybrid queries (vector + graph)

*Priority: Essential*
*Status: Active - All Versions*

**FR-064:** The system SHALL maintain graph consistency with vector store

*Priority: High*
*Status: Active - All Versions*

**FR-065:** The system SHALL support graph traversal queries

*Priority: Medium*
*Status: Active - All Versions*

**FR-066:** The system SHALL update graph incrementally with new documents

*Priority: High*
*Status: Active - All Versions*

**FR-067:** The system SHALL provide graph visualization endpoints

*Priority: Low*
*Status: Active - All Versions*

### 3.1.6 Content Intelligence Requirements (UPDATED v5.0)

#### 3.1.6.1 Semantic Processing

**FR-068:** The system SHALL chunk content using configurable parameters:
- Default chunk size: 1000 characters
- Default overlap: 200 characters
- Sentence boundary respect: enabled

*Priority: Essential*
*Status: Active - All Versions*

**FR-069:** The system SHALL generate embeddings for all chunks

*Priority: Essential*
*Note: v5.0 - Uses local nomic-embed-text instead of OpenAI*
*Status: Active - All Versions*

**FR-070:** The system SHALL extract key entities, topics, and concepts

*Priority: High*
*Note: v5.0 - Uses local Llama 70B*
*Status: Active - All Versions*

**FR-071:** The system SHALL generate document and chunk-level summaries

*Priority: Medium*
*Note: v5.0 - Uses local Llama 70B*
*Status: Active - All Versions*

#### 3.1.6.2 Contextual Embeddings

**FR-072:** The system SHALL create contextual descriptions for chunks

*Priority: High*
*Note: v5.0 - Generated by local Llama 70B*
*Status: Active - All Versions*

**FR-073:** The system SHALL create 2-3 sentence context descriptions for each chunk

*Priority: High*
*Status: Active - All Versions*

**FR-074:** The system SHALL prepend context to chunks before embedding

*Priority: High*
*Status: Active - All Versions*

**FR-075:** The system SHALL make contextual embedding configurable per document

*Priority: Medium*
*Status: Active - All Versions*

**FR-076:** The system SHALL cache contextual descriptions for reuse

*Priority: Low*
*Status: Active - All Versions*

#### 3.1.6.3 Tabular Data Processing

**FR-082:** The system SHALL detect and extract tables from documents

*Priority: Essential*
*Status: Active - All Versions*

**FR-083:** The system SHALL store tabular data in PostgreSQL as JSONB

*Priority: Essential*
*Location: Supabase (cloud)*
*Status: Active - All Versions*

**FR-084:** The system SHALL enable SQL queries against extracted tables

*Priority: Essential*
*Status: Active - All Versions*

**FR-085:** The system SHALL support aggregations (SUM, AVG, MAX, MIN, COUNT)

*Priority: High*
*Status: Active - All Versions*

**FR-086:** The system SHALL support GROUP BY and JOIN operations

*Priority: Medium*
*Status: Active - All Versions*

**FR-087:** The system SHALL integrate SQL results into RAG responses

*Priority: Essential*
*Status: Active - All Versions*

**FR-088:** The system SHALL maintain table schema in record manager

*Priority: High*
*Status: Active - All Versions*

### 3.1.7 Memory Management Requirements (REPLACED v5.0)

#### 3.1.7.1 mem-agent Local Memory (v5.0)

**MEM-001:** The system SHALL use mem-agent MCP for persistent memory management

*Priority: Essential*
*Model: 4B parameters, 3GB memory usage*
*Location: Mac Studio local*
*Replaces: Zep cloud service*
*Status: Active - v5.0*

**MEM-002:** The system SHALL retrieve memories in <500ms locally

*Priority: Essential*
*Target: <100ms typical*
*Status: Active - v5.0*

**MEM-003:** The system SHALL store memories in human-readable Markdown format

*Priority: Essential*
*Location: Mac Studio SSD*
*Status: Active - v5.0*

**MEM-004:** The system SHALL maintain user-specific memory contexts

*Priority: Essential*
*Status: Active - v5.0*

**MEM-005:** The system SHALL automatically backup memories to encrypted B2

*Priority: Essential*
*Frequency: Every 5 minutes*
*Encryption: Client-side before upload*
*Status: Active - v5.0*

**MEM-006:** The system SHALL support memory CRUD operations:
- Create new memories from interactions
- Read relevant memories for context
- Update existing memories with new information
- Delete outdated or incorrect memories

*Priority: Essential*
*Status: Active - v5.0*

**MEM-007:** The system SHALL implement memory relevance scoring (0-100)

*Priority: High*
*Status: Active - v5.0*

**MEM-008:** The system SHALL prune memories to maintain context window

*Priority: High*
*Strategy: Keep most relevant, summarize old*
*Status: Active - v5.0*

**MEM-009:** The system SHALL support memory search and filtering

*Priority: Medium*
*Status: Active - v5.0*

**MEM-010:** The system SHALL maintain memory versioning

*Priority: Low*
*Status: Active - v5.0*

### 3.1.8 Agent Architecture Requirements (All Versions)

**FR-099:** The system SHALL implement two distinct agent configurations:
- Agent A: With persistent memory (mem-agent in v5.0, Zep in v4.0)
- Agent B: Without persistent memory (session only)

*Priority: Essential*
*Status: Active - All Versions*

**FR-100:** The system SHALL route users to appropriate agent based on:
- User preferences
- Use case requirements
- Privacy settings

*Priority: High*
*Status: Active - All Versions*

**FR-101:** The system SHALL maintain separate conversation histories

*Priority: Essential*
*Status: Active - All Versions*

**FR-102:** The system SHALL support agent switching within sessions

*Priority: Medium*
*Status: Active - All Versions*

**FR-103:** The system SHALL clearly identify active agent to users

*Priority: High*
*Status: Active - All Versions*

### 3.1.9 Multi-Agent Analysis Requirements (Cloud-Based)

**FR-110:** The system SHALL execute CrewAI analysis using 1-5 specialized agents

*Priority: High*
*Location: Cloud (Render)*
*Status: Active - All Versions*

**FR-111:** The system SHALL adapt agent complexity based on content type

*Priority: Medium*
*Status: Active - All Versions*

**FR-112:** The system SHALL generate organizational recommendations including:
- Process improvements
- Knowledge gaps
- Training needs
- Strategic opportunities
- Risk assessments

*Priority: High*
*Note: v5.0 - Analysis powered by local Llama 70B*
*Status: Active - All Versions*

**FR-113:** The system SHALL handle long-running analysis (up to 30 minutes)

*Priority: Medium*
*Status: Active - All Versions*

**FR-114:** The system SHALL provide progress updates during analysis

*Priority: Low*
*Status: Active - All Versions*

**FR-115:** The system SHALL support custom agent configurations

*Priority: Medium*
*Status: Active - All Versions*

**FR-116:** The system SHALL enable agent collaboration for complex queries

*Priority: High*
*Status: Active - All Versions*

### 3.1.10 Vector Storage Requirements (Cloud-Based)

**FR-117:** The system SHALL store vectors in Pinecone immediately after processing

*Priority: Essential*
*Location: Cloud*
*Note: Pinecone remains cloud-based in v5.0*
*Status: Active - All Versions*

**FR-118:** The system SHALL use namespace organization (default: "course_vectors")

*Priority: Essential*
*Status: Active - All Versions*

**FR-119:** The system SHALL batch vector uploads (max 100 vectors per batch)

*Priority: High*
*Status: Active - All Versions*

**FR-120:** The system SHALL include enriched metadata with each vector:

```json
{
  "vector_id": "uuid",
  "values": [0.1, 0.2, ...],
  "metadata": {
    "document_id": "string",
    "chunk_index": 0,
    "content": "string",
    "document_type": "string",
    "source_format": "string",
    "topics": ["array"],
    "complexity": "low|medium|high",
    "timestamp": "ISO8601",
    "hash": "sha256",
    "contextual_summary": "string",
    "embedding_model": "nomic-embed-text",  // v5.0
    "processing_location": "mac_studio"      // v5.0
  }
}
```

*Priority: Essential*
*Status: Active - All Versions*

**FR-121:** The system SHALL support vector updates without full reindexing

*Priority: High*
*Status: Active - All Versions*

**FR-122:** The system SHALL implement vector similarity search with cosine distance

*Priority: Essential*
*Status: Active - All Versions*

**FR-123:** The system SHALL support metadata-filtered vector queries

*Priority: Essential*
*Status: Active - All Versions*

### 3.1.11 Privacy and Security Requirements (ENHANCED v5.0)

#### 3.1.11.1 Local-First Processing

**PRV-001:** The system SHALL process sensitive documents on Mac Studio only

*Priority: Essential*
*Sensitive: Financial, healthcare, legal, PII*
*Status: Active - v5.0*

**PRV-002:** The system SHALL detect sensitive content automatically

*Priority: Essential*
*Method: Local pattern matching and classification*
*Status: Active - v5.0*

**PRV-003:** The system SHALL never transmit sensitive data to cloud

*Priority: Essential*
*Exception: Encrypted backups only*
*Status: Active - v5.0*

**PRV-004:** The system SHALL maintain complete offline capability

*Priority: Essential*
*Coverage: All core functions except cloud storage*
*Status: Active - v5.0*

#### 3.1.11.2 Zero-Knowledge Backup

**PRV-005:** The system SHALL encrypt all data client-side before backup

*Priority: Essential*
*Encryption: AES-256*
*Status: Active - v5.0*

**PRV-006:** The system SHALL never transmit encryption keys

*Priority: Essential*
*Storage: Local keychain only*
*Status: Active - v5.0*

**PRV-007:** The system SHALL implement zero-knowledge architecture

*Priority: Essential*
*Result: Backblaze cannot decrypt user data*
*Status: Active - v5.0*

## 3.2 Non-Functional Requirements

### 3.2.1 Performance Requirements (ENHANCED v5.0)

**NFR-001:** The system SHALL process documents up to 300MB within 30 minutes

*Measurement: 95th percentile processing time*
*Status: Active - All Versions*

**NFR-002:** The system SHALL handle concurrent processing of up to 10 workflows

*Measurement: System stability under load*
*Note: v5.0 - Increased from 5 to 10 with Mac Studio*
*Status: Enhanced - v5.0*

**NFR-003:** The system SHALL achieve 32 tokens/second for LLM inference

*Measurement: Llama 3.3 70B performance*
*Hardware: Mac Studio M3 Ultra*
*Status: Active - v5.0*

**NFR-004:** The system SHALL complete hash checking within 500ms

*Measurement: 99th percentile response time*
*Status: Active - All Versions*

**NFR-005:** The system SHALL complete MarkItDown conversion within 60 seconds

*Measurement: 95th percentile for documents <50MB*
*Status: Active - All Versions*

**NFR-006:** The system SHALL maintain sub-100ms vector search latency

*Measurement: 95th percentile query time*
*Note: Pinecone cloud latency*
*Status: Active - All Versions*

**NFR-007:** The system SHALL support 500+ documents per day throughput

*Measurement: Daily processing capacity*
*Note: v5.0 - Increased from 100+ to 500+*
*Status: Enhanced - v5.0*

**NFR-008:** The system SHALL complete local reranking within 500ms

*Measurement: BGE-reranker performance*
*Note: v5.0 - Local reranking primary*
*Status: Active - v5.0*

**NFR-009:** The system SHALL retrieve memories from mem-agent within 500ms

*Measurement: 95th percentile retrieval time*
*Target: <100ms typical*
*Status: Active - v5.0*

**NFR-010:** The system SHALL process visual queries locally within 2 seconds

*Measurement: Qwen2.5-VL performance*
*Status: Active - v5.0*

**NFR-011:** The system SHALL maintain 98% local processing ratio

*Measurement: Local vs cloud processing metrics*
*Status: Active - v5.0*

**NFR-012:** The system SHALL achieve 80%+ cache hit rate

*Measurement: Cache effectiveness*
*Status: Active - All Versions*

### 3.2.2 Reliability Requirements

**NFR-020:** The system SHALL maintain 99.5% uptime availability

*Measurement: Monthly uptime percentage*
*Note: v5.0 - Improved from 99%*
*Status: Enhanced - v5.0*

**NFR-021:** The system SHALL implement automatic retry logic for all external API calls:
- Initial retry: 1 second
- Exponential backoff: 2x
- Maximum retries: 3
- Maximum delay: 30 seconds

*Measurement: Retry success rate*
*Status: Active - All Versions*

**NFR-022:** The system SHALL gracefully degrade when external services fail

*Measurement: System stability during outages*
*Note: v5.0 - Most processing continues locally*
*Status: Active - All Versions*

**NFR-023:** The system SHALL maintain data consistency across all storage layers

*Measurement: Consistency check results*
*Status: Active - All Versions*

**NFR-024:** The system SHALL recover from failures without data loss

*Measurement: Recovery testing results*
*Status: Active - All Versions*

**NFR-025:** The system SHALL achieve 4-hour RTO (Recovery Time Objective)

*Measurement: Disaster recovery drills*
*Status: Active - v5.0*

**NFR-026:** The system SHALL achieve 1-hour RPO (Recovery Point Objective)

*Measurement: Maximum data loss window*
*Status: Active - v5.0*

### 3.2.3 Scalability Requirements

**NFR-030:** The system SHALL scale to handle 100,000+ documents in storage

*Measurement: Storage performance at scale*
*Note: v5.0 - Increased capacity*
*Status: Enhanced - v5.0*

**NFR-031:** The system SHALL support up to 10M vectors with maintained performance

*Measurement: Vector search latency at scale*
*Note: v5.0 - Increased from 1M*
*Status: Enhanced - v5.0*

**NFR-032:** The system SHALL utilize Mac Studio resources efficiently:
- CPU usage: <60% average
- GPU usage: <70% during inference
- Memory: ~65GB for models, 31GB free

*Measurement: Resource monitoring*
*Status: Active - v5.0*

**NFR-033:** The system SHALL support incremental capacity increases

*Measurement: Scaling without downtime*
*Status: Active - All Versions*

### 3.2.4 Security Requirements (ENHANCED v5.0)

**SR-001:** The system SHALL authenticate all API requests using JWT tokens

*Priority: Essential*
*Status: Active - All Versions*

**SR-002:** The system SHALL implement role-based access control (RBAC)

*Priority: Essential*
*Status: Active - All Versions*

**SR-003:** The system SHALL encrypt data in transit using TLS 1.3

*Priority: Essential*
*Status: Active - All Versions*

**SR-004:** The system SHALL encrypt sensitive data at rest using AES-256

*Priority: Essential*
*Status: Active - All Versions*

**SR-005:** The system SHALL implement FileVault full disk encryption

*Priority: Essential*
*Hardware: Mac Studio*
*Status: Active - v5.0*

**SR-006:** The system SHALL use Tailscale VPN for remote access

*Priority: High*
*Purpose: Secure Mac Studio access*
*Status: Active - v5.0*

**SR-007:** The system SHALL implement zero-knowledge backup encryption

*Priority: Essential*
*Method: Client-side encryption*
*Status: Active - v5.0*

**SR-008:** The system SHALL detect and prevent injection attacks

*Priority: Essential*
*Status: Active - All Versions*

**SR-009:** The system SHALL implement rate limiting on all endpoints

*Priority: High*
*Status: Active - All Versions*

**SR-010:** The system SHALL comply with GDPR data protection requirements

*Priority: Essential*
*Status: Active - All Versions*

**SR-011:** The system SHALL maintain complete audit trail

*Priority: High*
*Storage: Encrypted and backed up*
*Status: Active - All Versions*

## 3.3 External Interface Requirements

### 3.3.1 User Interfaces

#### 3.3.1.1 Web Upload Interface

**UI-001:** The interface SHALL provide drag-and-drop file upload area
**UI-002:** The interface SHALL display upload progress with percentage
**UI-003:** The interface SHALL show processing status for each file
**UI-004:** The interface SHALL provide download links for results
**UI-005:** The interface SHALL support bulk file selection

*Status: Active - All Versions*

#### 3.3.1.2 Open WebUI Interface (NEW v5.0)

**UI-006:** The interface SHALL provide chat interface for local LLMs

*Technology: Open WebUI*
*Status: Active - v5.0*

**UI-007:** The interface SHALL display model selection (Llama 70B, Qwen-VL)

*Status: Active - v5.0*

**UI-008:** The interface SHALL show token generation speed

*Status: Active - v5.0*

**UI-009:** The interface SHALL support markdown rendering

*Status: Active - v5.0*

**UI-010:** The interface SHALL maintain conversation history

*Status: Active - v5.0*

#### 3.3.1.3 Claude Desktop Interface (v5.0)

**UI-011:** The interface SHALL integrate via MCP protocol

*Status: Active - v5.0*

**UI-012:** The interface SHALL access mem-agent memories

*Status: Active - v5.0*

**UI-013:** The interface SHALL trigger document processing

*Status: Active - v5.0*

### 3.3.2 Hardware Interfaces

**HW-001:** Mac Studio M3 Ultra Interface
- 28-core CPU, 60-core GPU, 32-core Neural Engine
- 96GB unified memory (800 GB/s bandwidth)
- 1TB+ SSD storage
- 10Gb Ethernet
- 6x Thunderbolt 4 ports
- Power consumption: ~65W average

*Status: Active - v5.0*

### 3.3.3 Software Interfaces

#### 3.3.3.1 Local Model Interfaces (v5.0)

**SI-001:** Ollama Model Server Interface
```python
Interface: Ollama API
Protocol: HTTP/REST
Endpoint: http://localhost:11434/api/generate
Method: POST
Request: {
  "model": "llama3.3:70b",
  "prompt": "user query",
  "stream": false,
  "options": {
    "temperature": 0.7,
    "top_p": 0.9
  }
}
Response: {
  "response": "generated text",
  "context": [],
  "total_duration": 1000000000,
  "eval_count": 100,
  "eval_duration": 3125000000  # 32 tokens/second
}
```
*Status: Active - v5.0*

**SI-002:** LiteLLM API Compatibility Layer
```python
Interface: LiteLLM
Protocol: HTTP/REST (OpenAI-compatible)
Endpoint: http://localhost:8000/v1/completions
Authentication: Local API key
Method: POST
Request: OpenAI-compatible format
Response: OpenAI-compatible format
```
*Status: Active - v5.0*

**SI-003:** mem-agent MCP Interface
```python
Interface: mem-agent MCP
Protocol: Model Context Protocol
Operations:
  - store_memory(user_id, content)
  - retrieve_memories(user_id, query, limit=10)
  - update_memory(memory_id, content)
  - delete_memory(memory_id)
Response Time: <500ms (typically <100ms)
```
*Status: Active - v5.0*

#### 3.3.3.2 Cloud Service Interfaces

**SI-004:** MarkItDown MCP Interface
```python
Interface: MarkItDown MCP Server
Protocol: HTTP/REST
Endpoint: http://markitdown-mcp:8080/convert
Method: POST
Request: {
  "content": "base64_encoded_file",
  "filename": "document.docx",
  "options": {
    "preserve_formatting": true,
    "extract_images": true,
    "include_metadata": true
  }
}
```
*Status: Active - All Versions*

**SI-005:** Pinecone Vector Database Interface
```python
Interface: Pinecone API
Protocol: HTTPS/REST
Endpoint: https://api.pinecone.io
Authentication: API Key
Operations:
  - upsert(vectors)
  - query(vector, top_k=10, filter={})
  - delete(ids)
```
*Status: Active - All Versions*

**SI-006:** Supabase PostgreSQL Interface
```python
Interface: Supabase Database
Protocol: PostgreSQL Wire Protocol
Connection: postgres://[user]:[pass]@[project].supabase.co:5432/postgres
Pooling: PgBouncer
Max Connections: 60
```
*Status: Active - All Versions*

**SI-007:** Backblaze B2 Backup Interface
```python
Interface: B2 API
Protocol: HTTPS/REST
Endpoint: https://api.backblazeb2.com
Authentication: Application Key
Encryption: Client-side AES-256
Operations:
  - upload_file(encrypted_data)
  - download_file(file_id)
  - list_file_versions()
```
*Status: Active - All Versions*

**SI-008:** Hyperbolic.ai LLM Interface (Minimal Use)
```python
Interface: Hyperbolic API
Protocol: HTTPS/REST
Endpoint: https://api.hyperbolic.ai/v1/completions
Usage: Edge cases only (<2% of inference)
Models: Backup for complex tasks
Cost: $5-10/month
```
*Status: Active - v5.0 (Minimal)*

### 3.3.4 Communications Interfaces

**CI-001:** The system SHALL use HTTPS for all external communications
**CI-002:** The system SHALL implement WebSocket for real-time updates
**CI-003:** The system SHALL support REST API with JSON payloads
**CI-004:** The system SHALL use MCP for model context protocol
**CI-005:** The system SHALL implement Tailscale VPN for secure remote access
**CI-006:** The system SHALL use SSH for Mac Studio administration

*Status: Active - All Versions*

## 3.4 Deprecated Requirements (Historical Reference)

### 3.4.1 Deprecated in v5.0

#### Zep Memory Service (Replaced by mem-agent)

**DEPRECATED-FR-092:** ~~The system SHALL integrate Zep for user-specific long-term memory~~

*Deprecated: v5.0*
*Replaced by: MEM-001 through MEM-010*
*Reason: Local mem-agent provides better privacy and performance*

**DEPRECATED-FR-093:** ~~The system SHALL create unique user profiles in Zep~~

*Deprecated: v5.0*
*Replaced by: MEM-004*

**DEPRECATED-FR-094:** ~~The system SHALL store user facts and preferences as graph edges~~

*Deprecated: v5.0*
*Replaced by: MEM-003 (Markdown storage)*

**DEPRECATED-FR-095:** ~~The system SHALL retrieve relevant memories from Zep~~

*Deprecated: v5.0*
*Replaced by: MEM-002*

**DEPRECATED-FR-096:** ~~The system SHALL update Zep memories asynchronously~~

*Deprecated: v5.0*
*Replaced by: MEM-006*

#### OpenAI Embeddings (Replaced by nomic-embed)

**DEPRECATED-FR-069:** ~~The system SHALL generate embeddings using OpenAI text-embedding-3-small~~

*Deprecated: v5.0*
*Replaced by: LLR-007 (local nomic-embed-text)*
*Reason: Local embeddings eliminate API costs and latency*

#### Mistral Pixtral Vision API (Replaced by Qwen2.5-VL)

**DEPRECATED-FR-039:** ~~The system SHALL enable direct visual querying using Mistral Pixtral-12B~~

*Deprecated: v5.0*
*Replaced by: VIS-001 (local Qwen2.5-VL-7B)*
*Reason: Local vision processing for privacy and cost*

#### Cohere as Primary Reranking

**DEPRECATED-FR-053:** ~~The system SHALL integrate Cohere reranking API as primary~~

*Deprecated: v5.0*
*Replaced by: LLR-010 (BGE-reranker primary, Cohere fallback)*
*Reason: Local reranking reduces costs and latency*

### 3.4.2 Migration Path

For users migrating from v4.0 to v5.0:

1. **Memory Migration:** Export Zep memories → Convert to Markdown → Import to mem-agent
2. **Embedding Migration:** Re-generate with nomic-embed for better local performance
3. **Vision Migration:** Re-process images with local Qwen2.5-VL
4. **API Migration:** Update to LiteLLM endpoints for compatibility

## 3.5 Performance Metrics Summary

### 3.5.1 v5.0 Target Metrics

| Metric | Target | Method |
|--------|--------|--------|
| LLM Inference Speed | 32 tok/s | Llama 70B on Mac Studio |
| Document Throughput | 500+/day | Parallel processing |
| Memory Retrieval | <100ms | Local mem-agent |
| Vision Processing | <2 sec | Local Qwen-VL |
| Local Processing | 98% | Smart routing |
| Cache Hit Rate | 80%+ | 31GB cache |
| Uptime | 99.5% | Mac Studio reliability |
| Monthly Cost | $100-195 | Reduced cloud usage |
| Backup Success | 100% | Automated B2 sync |
| Recovery Time | 4 hours | Documented procedures |

### 3.5.2 Resource Utilization

| Resource | Usage | Available |
|----------|-------|-----------|
| Memory (Models) | 65GB | 31GB free |
| CPU Average | 40% | 60% headroom |
| GPU Peak | 70% | 30% buffer |
| Storage Models | ~50GB | User defined |
| Network | <50Mbps | 10Gbps capable |
| Power Average | 65W | Well within limits |

## 3.6 Compliance and Standards

**CS-001:** The system SHALL comply with IEEE 830-1998 for documentation
**CS-002:** The system SHALL follow OpenAPI 3.1 for API specification
**CS-003:** The system SHALL implement OAuth 2.0 for authentication
**CS-004:** The system SHALL use ISO 8601 for datetime formats
**CS-005:** The system SHALL follow REST architectural principles
**CS-006:** The system SHALL maintain GDPR compliance
**CS-007:** The system SHALL meet SOC 2 Type II requirements
**CS-008:** The system SHALL implement HIPAA-ready security (when configured)

*Status: Active - All Versions*