# 3. Specific Requirements

## 3.0 v7.2 NEW - Graph Database & Dual-Interface Requirements

### 3.0.1 Neo4j Graph Database Requirements

**FR-NEO-001:** The system SHALL run Neo4j Graph Database locally on Mac Studio via Docker

*Priority: Critical*
*Cost Benefit: Eliminates ~$100+/month cloud GraphDB costs*
*Status: v7.2 NEW*

**FR-NEO-002:** The system SHALL support natural language to Cypher query translation

*Priority: Critical*
*Description: Convert user natural language queries to Cypher via Claude Sonnet*
*Accuracy Target: >90% correct Cypher generation*
*Status: v7.2 NEW*

**FR-NEO-003:** The system SHALL provide Neo4j MCP Server for Claude Desktop/Code integration

*Priority: Critical*
*Interface: Claude Desktop + Claude Code direct graph access*
*Response Latency: <100ms for simple queries, <500ms for complex traversal*
*Status: v7.2 NEW*

**FR-NEO-004:** The system SHALL implement bi-directional Supabase ↔ Neo4j synchronization

*Priority: High*
*Description: Automatic sync of entities and relationships between relational and graph databases*
*Sync Latency: <5 minutes for eventual consistency*
*Status: v7.2 NEW*

**FR-NEO-005:** The system SHALL support advanced graph traversal capabilities

*Priority: High*
*Features: Multi-hop pathfinding, community detection, centrality analysis*
*Max Hops: 5 levels with configurable depth*
*Status: v7.2 NEW*

**FR-NEO-006:** The system SHALL implement semantic entity resolution

*Priority: Medium*
*Description: ML-based entity matching and deduplication across graphs*
*Accuracy Target: >95% entity consolidation*
*Status: v7.2 NEW*

### 3.0.2 Chat UI Requirements

**FR-CHAT-001:** The system SHALL provide a Gradio/Streamlit Chat UI interface

*Priority: Critical*
*Deployment: Render cloud platform*
*Cost: $15-20/month*
*Availability: 24/7 public access*
*Status: v7.2 NEW*

**FR-CHAT-002:** The system SHALL support both vector search AND graph queries through Chat UI

*Priority: High*
*Description: Unified query interface supporting hybrid searches*
*Status: v7.2 NEW*

**FR-CHAT-003:** The system SHALL display search results with relevance scores and source citations

*Priority: High*
*Status: v7.2 NEW*

### 3.0.3 MCP Requirements

**FR-MCP-001:** The system SHALL provide Neo4j MCP tools for Claude agents

*Priority: Critical*
*Tools: neo4j_query, entity_search, graph_traverse, path_find*
*Status: v7.2 NEW*

**FR-MCP-002:** The system SHALL enable natural language graph analysis in Claude Code

*Priority: High*
*Description: Direct Cypher generation from user intent*
*Status: v7.2 NEW*

## 3.1 Functional Requirements

### 3.1.1 Document Processing Requirements (Core - All Versions)

#### 3.1.1.1 Unified MarkItDown Processing

**FR-001:** The system SHALL accept documents in 40+ supported formats

*Priority: Essential*
*Description: Universal document conversion to standardized Markdown*
*Input: Documents in supported formats (PDF, DOCX, XLSX, PPTX, HTML, TXT, CSV, etc.)*
*Output: Standardized Markdown with preserved structure and content*
*Validation: Format detection accuracy >99%*
*Source: Product Management*
*Verification: Integration Testing*
*Status: Active - All Versions*

**FR-002:** The system SHALL convert all supported formats to clean Markdown using MarkItDown MCP

*Priority: Essential*
*Processing: Via MarkItDown MCP Server*
*Dependencies: TC-003*
*Status: Active - All Versions*

**FR-003:** The system SHALL preserve document structure including headings, lists, and paragraphs

*Priority: Essential*
*Success Rate: >95% structure preservation*
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
*Description: Intelligent routing based on PDF complexity*
*Status: Active - All Versions*

**FR-008:** The system SHALL route simple text-based PDFs to MarkItDown MCP

*Priority: Essential*
*Processing: Direct MarkItDown processing for simple PDFs*
*Status: Active - All Versions*

**FR-009:** The system SHALL route complex PDFs to Mistral OCR when:
- Document contains complex tables or layouts
- Document contains diagrams or flowcharts
- Document contains mathematical formulas
- File size exceeds 10MB
- MarkItDown processing fails

*Priority: Essential*
*Note: v5.0 - Only complex PDFs use cloud OCR, simple PDFs processed locally*
*Success Rate: >95% successful extraction*
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

#### 3.1.1.3b LlamaCloud/LlamaParse OCR (NEW - v7.1)

**FR-015C:** The system SHALL use LlamaCloud/LlamaParse for OCR processing

*Priority: Essential*
*Provider: LlamaCloud (free tier)*
*Capacity: 10,000 pages/month free tier*
*Cost: $0 for standard volume (replaces $20/month Mistral OCR)*
*Formats: PDF, PNG, JPG, BMP, GIF*
*Routing: Primary OCR provider, fallback to Mistral if needed*
*Status: Active - v7.1*

**FR-015D:** The system SHALL automatically route PDFs to LlamaParse when > 5MB or complex

*Priority: High*
*Method: File size + complexity detection*
*Performance: 10-30s per document*
*Status: Active - v7.1*

#### 3.1.1.4 LangExtract Integration (NEW - v7.0)

**FR-015A:** The system SHALL integrate LangExtract for precise information extraction alongside LlamaIndex

*Priority: High*
*Description: Gemini-powered extraction library for precise grounding*
*Status: Active - v7.1+*

**FR-015B:** The system SHALL use LangExtract for structured data extraction from documents

*Priority: High*
*Processing: Gemini-powered extraction with schema validation*
*Accuracy: >95% extraction accuracy for structured fields*
*Status: Active - v7.1+*

**FR-015C:** The system SHALL validate extracted information against LlamaIndex document processing

*Priority: High*
*Description: Cross-validation between LangExtract and LlamaIndex for grounding precision*
*Status: Active - v7.1+*

**FR-015D:** The system SHALL support custom extraction schemas for domain-specific needs

*Priority: Medium*
*Configuration: YAML/JSON schema definitions*
*Status: Active - v7.1+*

**FR-015E:** The system SHALL provide extraction confidence scores for validation

*Priority: Medium*
*Threshold: >0.85 confidence for auto-acceptance*
*Status: Active - v7.1+*

**LangExtract Use Cases:**
- **Entity Extraction:** Precise identification of people, organizations, dates, locations
- **Relationship Mapping:** Extract relationships between entities
- **Structured Fields:** Pull specific fields (dates, amounts, IDs) with high precision
- **Citation Grounding:** Validate extracted information against source documents
- **Schema Compliance:** Ensure extracted data matches expected formats

### 3.1.2 Multimedia Processing Requirements (All Versions)

#### 3.1.2.1 YouTube Content Extraction

**FR-016:** The system SHALL extract YouTube video metadata including:
- Title, description, duration
- Channel information
- Upload date, view count
- Tags and categories

*Priority: High*
*Processing: Automated metadata retrieval*
*Status: Active - All Versions*

**FR-017:** The system SHALL retrieve video transcripts using three-tier hierarchy:
1. Official YouTube captions (highest priority)
2. Auto-generated captions (medium priority)
3. Soniox transcription of audio (fallback)

*Priority: Essential*
*Accuracy: >90% transcription accuracy*
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
*Description: Professional transcription with speaker diarization*
*Processing: Via Soniox API*
*Formats: MP3, WAV, MP4, MOV, WebM*
*Features: Speaker identification, timestamp preservation*
*Accuracy: >90% transcription accuracy*
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
*Description: Extract content from web resources*
*Processing: Via Firecrawl API*
*Features: JavaScript rendering, dynamic content handling*
*Output: Clean Markdown with preserved structure*
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
*Description: Vision and image analysis*
*Processing: Local on Mac Studio*
*Features: Object detection, scene description, text extraction*
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
*Output: Structured image metadata and descriptions*
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

#### 3.1.5.1 Vector Search Integration

**HR-001:** The system SHALL perform semantic vector searches

*Priority: Essential*
*Backend: Supabase pgvector database*
*Embeddings: BGE-M3 1024-dim vectors with built-in sparse vectors (v7.1)*
*Features: Similarity search, filtering, metadata queries*
*Performance: <50ms dense, <100ms sparse query response time*
*Status: Active - v7.1*

**HR-002:** The system SHALL maintain and query knowledge graphs

*Priority: High*
*Backend: LightRAG API*
*Features: Entity relationships, graph traversal, pattern detection*
*Updates: Real-time graph updates on document ingestion*
*Status: Active - All Versions*

**HR-003:** The system SHALL execute SQL queries on structured data

*Priority: High*
*Backend: Supabase PostgreSQL*
*Features: Complex joins, aggregations, window functions*
*Interface: Standard SQL syntax support*
*Status: Active - All Versions*

**HR-004:** The system SHALL combine multiple search strategies with reranking

*Priority: Essential*
*Components: Dense Vector + Sparse + ILIKE + Fuzzy search*
*Reranking: BGE-Reranker-v2 on Mac Studio (v7.1, replaces Cohere)*
*Fusion: Reciprocal Rank Fusion (RRF) for result combining*
*Optimization: Dynamic weight adjustment based on query type*
*Status: Active - v7.1*

#### 3.1.5.2 Hash-Based Change Detection

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

#### 3.1.5.3 Adaptive Chunking Strategy (NEW - v7.1)

**CHK-001:** The system SHALL implement adaptive document-type-aware chunking

*Priority: Essential*
*Description: Optimize chunk size based on document type*
*Status: Active - v7.1*

**CHK-002:** The system SHALL detect document type via Claude Vision

*Priority: High*
*Method: Analyze document structure and format*
*Types: Contract, Policy, Technical, Narrative, Mixed*
*Status: Active - v7.1*

**CHK-003:** The system SHALL apply document-type-specific chunk sizes

*Priority: Essential*
*Chunk Sizes (v7.1 - NEW):*
  - *Contracts: 300 tokens, 25% overlap (precision focus)*
  - *Policies: 400 tokens, 20% overlap (balanced)*
  - *Technical: 512 tokens, 20% overlap (context focus)*
  - *Transcripts: 300 tokens, speaker-aware*
  - *Default: 400 tokens, semantic boundaries*
*Status: Active - v7.1*

**CHK-004:** The system SHALL preserve document structure during chunking

*Priority: High*
*Method: Semantic boundary detection*
*Preservation: Tables, images, code blocks, sections*
*Impact: 15-25% better semantic coherence*
*Status: Active - v7.1*

**CHK-005:** The system SHALL provide one-time preprocessing for chunking

*Priority: Medium*
*Execution: During document ingestion*
*Caching: Results reused for query processing*
*Status: Active - v7.1*

### 3.1.6 Content Intelligence Requirements (UPDATED v5.0)

#### 3.1.6.1 Named Entity Recognition

**FR-008:** The system SHALL identify and extract named entities

*Priority: High*
*Categories: People, Organizations, Locations, Dates, Products*
*Processing: Local Llama 70B with confidence scoring (v5.0)*
*Storage: Entity catalog with relationships*
*Status: Active - All Versions*

**FR-009:** The system SHALL generate rich metadata for documents

*Priority: Medium*
*Components: Tags, categories, summaries, key points*
*Processing: AI-powered classification and summarization*
*Quality: Confidence scores for all generated metadata*
*Status: Active - All Versions*

#### 3.1.6.2 Semantic Processing

**FR-068:** The system SHALL chunk content using configurable parameters:
- Default chunk size: 1000 characters
- Default overlap: 200 characters
- Sentence boundary respect: enabled
- Optimal chunk size: 512-2048 tokens

*Priority: Essential*
*Method: Context-aware chunking with overlap*
*Quality: Chunk coherence scoring*
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

#### 3.1.6.3 Contextual Embeddings

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

#### 3.1.6.4 Tabular Data Processing

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

### 3.1.7 Memory and Agent Architecture Requirements

#### 3.1.7.1 Long-term Memory Management (v5.0)

**IMPORTANT NOTE:** This section describes **mem-agent MCP**, which is a **developer-only tool** for local development and testing. It runs on the Mac Studio, integrates with Claude Desktop via Model Context Protocol, and is **NOT used in production n8n workflows**. For production end-user memory requirements, see Section 3.1.13: Memory System Requirements.

**MEM-001:** The system SHALL use mem-agent MCP for persistent memory management (DEVELOPER ONLY)

*Priority: Essential*
*Description: Maintains persistent developer context during local development*
*Backend: mem-agent (4B model) on Mac Studio*
*Features: Context retrieval, memory updates, relevance scoring*
*Performance: <100ms local retrieval time*
*Model: 4B parameters, 3GB memory usage*
*Location: Mac Studio local*
*Usage: Developer tool for Claude Desktop integration, NOT for production workflows*
*Replaces: Zep cloud service (for developer use)*
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

#### 3.1.7.2 Multi-Agent Orchestration

**FR-012:** The system SHALL coordinate multiple AI agents

*Priority: High*
*Description: Multi-agent orchestration for complex tasks*
*Framework: CrewAI on Render*
*Agents: Research, Analysis, Writing, Review agents*
*Coordination: Task delegation and result aggregation*
*Status: Active - All Versions*

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

### 3.1.8 Processing Optimization Requirements

#### 3.1.8.1 Parallel Processing

**PFR-001:** The system SHALL process multiple documents concurrently

*Priority: Essential*
*Description: Parallel document processing for improved throughput*
*Capacity: Up to 10 workflows simultaneously (v5.0, up from 5)*
*Load Balancing: Dynamic allocation based on complexity*
*Resource Management: CPU and memory optimization*
*Status: Enhanced - v5.0*

#### 3.1.8.2 Fast Track Pipeline

**PFR-002:** The system SHALL provide expedited processing for simple documents

*Priority: High*
*Description: Fast track for simple documents*
*Criteria: Documents <10 pages, standard formats, no OCR needed*
*Performance: 70% faster than standard pipeline*
*Routing: Automatic detection and routing*
*Status: Active - All Versions*

### 3.1.9 Vector Storage Requirements (Cloud-Based)

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

### 3.1.10 Privacy and Security Requirements (ENHANCED v5.0)

#### 3.1.10.1 Local-First Processing

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

#### 3.1.10.2 Zero-Knowledge Backup

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

### 3.1.11 Advanced Search Requirements (NEW - v7.0)

#### 3.1.11.1 Hybrid Search Implementation

**SRC-001:** The system SHALL implement dynamic hybrid search combining multiple retrieval methods

*Priority: Essential*
*Description: Four-method hybrid search for superior relevance*
*Methods: Dense (vector), Sparse (full-text), ILIKE (pattern), Fuzzy (trigram)*
*Fusion: Reciprocal Rank Fusion (RRF)*
*Impact: 40-60% improvement in search relevance*
*Status: Active - v7.1*

**SRC-002:** The system SHALL support dense vector search using BGE-M3 embeddings

*Priority: Essential*
*Dimensions: 1024*
*Similarity: Cosine distance*
*Index: HNSW with m=16, ef_construction=64*
*Status: Active - v7.1*

**SRC-003:** The system SHALL support sparse full-text search using BGE-M3 built-in sparse vectors

*Priority: Essential*
*Method: BGE-M3 native sparse vectors (superior to traditional BM25)*
*Index: GIN index on JSONB sparse vector column*
*Ranking: Sparse relevance scoring*
*Status: Active - v7.1*

**SRC-004:** The system SHALL support pattern matching search (ILIKE)

*Priority: High*
*Use Case: Exact phrase matching, wildcards*
*Scoring: Frequency-based relevance*
*Status: Active - v7.1*

**SRC-005:** The system SHALL support fuzzy search using trigram similarity

*Priority: High*
*Extension: pg_trgm*
*Use Case: Typo tolerance, approximate matching*
*Threshold: Configurable (default 0.3)*
*Status: Active - v7.1*

**SRC-006:** The system SHALL combine search results using Reciprocal Rank Fusion

*Priority: Essential*
*Algorithm: RRF with configurable k parameter (default 60)*
*Weights: Configurable per method (dense: 0.4, sparse: 0.3, ilike: 0.15, fuzzy: 0.15)*
*Output: Unified ranking with individual method scores*
*Status: Active - v7.1*

**SRC-007:** The system SHALL support advanced metadata filtering in hybrid search

*Priority: Essential*
*Operators: =, !=, >, <, >=, <=, IN, NOT IN*
*Logic: $and, $or operators*
*Types: Text, numeric, timestamp, array*
*Status: Active - v7.1*

#### 3.1.11.2 Reranking Requirements

**RRK-001:** The system SHALL implement BGE-Reranker-v2 for result optimization

*Priority: High*
*Model: BGE-Reranker-v2 (299M parameters, ~1.5GB RAM)*
*Deployment: Mac Studio via Tailscale secure connection*
*Application: Applied after hybrid search, before context expansion*
*Impact: 25-35% improvement in result ordering*
*Cost: $0 (self-hosted on Mac Studio, saved $30-50/month vs Cohere)*
*Latency: 10-20ms per batch*
*Status: Active - v7.1*

**RRK-002:** The system SHALL rerank top N results based on query relevance

*Priority: High*
*Default: Rerank top 20, return top 10*
*Threshold: Configurable relevance threshold (default 0.7)*
*Status: Active - v7.1*

**RRK-003:** The system SHALL preserve diversity in reranked results

*Priority: Medium*
*Method: Maximum marginal relevance (MMR)*
*Balance: Relevance vs diversity*
*Status: Active - v7.1*

#### 3.1.11.3 Query Enhancement Requirements

**QRY-001:** The system SHALL enhance queries before search execution

*Priority: High*
*Pipeline: Query expansion → Spell correction → Entity extraction → Intent classification*
*Impact: 15-30% better recall with query expansion*
*Status: Active - v7.1*

**QRY-001a:** The system SHALL generate query variations using Claude Haiku (NEW - v7.1)

*Priority: Essential*
*Method: Claude Haiku API generates 4-5 semantic variations*
*Execution: Parallel expansion before hybrid search*
*Cost: ~$1.50-9/month*
*Latency: Sub-100ms expansion time*
*UI: Toggle for "Enhanced Search" mode*
*Strategies: Synonym expansion, step variations, concept expansion*
*Status: Active - v7.1*

**QRY-002:** The system SHALL perform spell correction on user queries

*Priority: Medium*
*Method: Claude API-based correction*
*Fallback: User confirmation for significant changes*
*Status: Active - v7.1*

**QRY-003:** The system SHALL expand queries with relevant synonyms

*Priority: Medium*
*Source: Claude Haiku API semantic understanding*
*Limit: 4-5 variations total*
*Status: Active - v7.1*

**QRY-004:** The system SHALL extract entities from queries

*Priority: High*
*Types: Person, Organization, Location, Date, Technology, Concept*
*Use: Entity-based filtering and graph traversal*
*Status: Active - v7.1*

**QRY-005:** The system SHALL classify query intent

*Priority: High*
*Categories: Factual, Analytical, Comparative, Multi-hop, Ambiguous*
*Use: Adaptive search strategy selection*
*Status: Active - v7.1*

#### 3.1.11.4 Semantic Caching Requirements (OPTIMIZED - v7.1)

**CHE-001:** The system SHALL implement tiered semantic caching for query results

*Priority: High*
*Method: BGE-M3 embedding-based similarity matching*
*Tiered Thresholds (v7.1 - NEW):*
  - *0.98+: Direct cache hit (return cached result)*
  - *0.93-0.97: Return with "similar answer found" note*
  - *0.88-0.92: Show as suggestion, allow bypass*
  - *<0.88: Execute full pipeline*
*Storage: Upstash Redis with adaptive TTL*
*Impact: 60-80% cache hit rate for common queries*
*Status: Active - v7.1*

**CHE-002:** The system SHALL cache query embeddings for similarity comparison

*Priority: High*
*Storage: Redis hash with BGE-M3 1024-dim embedding vectors*
*TTL: 1 hour for query cache, 24 hours for result cache*
*Adaptive: Document-type-aware TTL (policies 24h, real-time 5m)*
*Status: Active - v7.1*

**CHE-003:** The system SHALL invalidate cache on document updates

*Priority: Essential*
*Strategy: Document-based invalidation*
*Granularity: Per-document or global flush*
*UI: Manual refresh button to bypass cache*
*Status: Active - v7.1*

### 3.1.12 Knowledge Graph Requirements (NEW - v7.0)

#### 3.1.12.1 LightRAG Integration

**KG-001:** The system SHALL integrate LightRAG for knowledge graph capabilities

*Priority: High*
*API: LightRAG HTTP API*
*Cost: $15-30/month*
*Impact: 20-40% better context understanding for entity-rich queries*
*Status: Active - v7.1*

**KG-002:** The system SHALL extract entities and relationships from documents

*Priority: High*
*Extraction: During document ingestion*
*Types: Entities (Person, Organization, Technology, Concept, Event)*
*Relationships: (uses, created_by, related_to, part_of, occurred_at)*
*Status: Active - v7.1*

**KG-003:** The system SHALL store knowledge graph data in Supabase

*Priority: Essential*
*Tables: knowledge_entities, knowledge_relationships*
*Indexing: B-tree on entity values, JSONB GIN on properties*
*Status: Active - v7.1*

**KG-004:** The system SHALL support graph traversal queries

*Priority: High*
*Max Hops: Configurable (default 3)*
*Filtering: By entity type and relationship type*
*Scoring: Path relevance based on relationship strength*
*Status: Active - v7.1*

**KG-005:** The system SHALL combine graph results with vector search

*Priority: High*
*Integration: Graph traversal → Expand to related documents → Hybrid search*
*Weighting: Graph results boosted by relationship proximity*
*Status: Active - v7.1*

#### 3.1.12.2 Entity Management

**ENT-001:** The system SHALL maintain entity embeddings for similarity search

*Priority: High*
*Model: BGE-M3 (1024 dimensions with built-in sparse vectors)*
*Use: Entity disambiguation and linking*
*Status: Active - v7.1*

**ENT-002:** The system SHALL deduplicate entities automatically

*Priority: Medium*
*Method: Embedding similarity + name matching*
*Threshold: 0.9 similarity for merge*
*Status: Active - v7.1*

**ENT-003:** The system SHALL track entity confidence scores

*Priority: Medium*
*Range: 0.0-1.0*
*Use: Filtering low-confidence entities*
*Status: Active - v7.1*

### 3.1.13 Production User Memory System Requirements (NEW - v7.0)

**IMPORTANT NOTE:** This section describes the **production user memory system** using Supabase graph-based architecture. This is distinct from mem-agent MCP (Section 3.1.7.1), which is a developer-only tool. Production user memory is implemented in n8n workflows and provides graph-based memory with relationships for all end users.

#### 3.1.13.1 Graph-Based User Memory

**MEM-001:** The system SHALL implement graph-based user memory storage in Supabase

*Priority: Essential*
*Architecture: Three-layer graph (User Memory, Document Knowledge, Hybrid)*
*Storage: Supabase PostgreSQL with pgvector extension*
*Tables: user_memory_nodes, user_memory_edges, user_document_connections*
*Purpose: Production user memory with graph relationships*
*Status: Active - v7.1*

**MEM-002:** The system SHALL store user memory nodes with embeddings

*Priority: Essential*
*Node Types: fact, preference, goal, context, skill, interest*
*Embeddings: 1024-dim BGE-M3 vectors (upgraded from 768-dim)*
*Metadata: confidence_score, importance_score, source_type*
*Lifecycle: Active/inactive status, optional expiration*
*Status: Active - v7.1*

**MEM-003:** The system SHALL maintain graph edges between memory nodes

*Priority: Essential*
*Relationship Types: causes, relates_to, contradicts, supports, precedes, enables*
*Edge Metadata: strength (0.0-1.0), directionality, observation_count*
*Purpose: Multi-hop graph traversal for context enrichment*
*Status: Active - v7.1*

**MEM-004:** The system SHALL extract user facts using Claude API

*Priority: High*
*Extraction: Automatic from conversation context (last 10 messages)*
*Types: Facts, preferences, goals, context, skills, interests*
*Confidence: 0.0-1.0 confidence scoring per memory*
*Trigger: After each user message in chat interface*
*Status: Active - v7.1*

**MEM-005:** The system SHALL retrieve user memory context with graph traversal

*Priority: Essential*
*Retrieval: SQL function get_user_memory_context() with recursive CTEs*
*Traversal Depth: 2 hops (configurable 1-3)*
*Performance: <100ms for graph traversal*
*Similarity: Vector similarity threshold 0.7 for seed nodes*
*Status: Active - v7.1*

**MEM-006:** The system SHALL create hybrid graph connections to LightRAG entities

*Priority: High*
*Purpose: Link user memories to document knowledge graph entities*
*Connection Types: related_to, expert_in, interested_in, worked_on*
*Benefits: Personalized document recommendations, expertise matching*
*Storage: user_document_connections table*
*Status: Active - v7.1*

**MEM-007:** The system SHALL enrich queries with personalized user context

*Priority: Essential*
*Integration: Before RAG pipeline execution*
*Context: Top 10 relevant memories with relationship paths*
*Personalization: Related LightRAG entities based on user interests*
*Performance: <300ms total for memory retrieval and enrichment*
*Status: Active - v7.1*

**MEM-008:** The system SHALL implement memory decay for stale information

*Priority: Medium*
*Function: decay_user_memories() executed daily*
*Threshold: 30 days of inactivity*
*Decay Rate: 10% confidence reduction per period*
*Purpose: Prevent outdated information from polluting context*
*Status: Active - v7.1*

**MEM-009:** The system SHALL detect contradicting memories

*Priority: Medium*
*Detection: High embedding similarity (>0.85) with contradictory patterns*
*Function: detect_contradicting_memories() during extraction*
*Resolution: Flag for review, prefer higher confidence scores*
*Purpose: Maintain memory consistency*
*Status: Active - v7.1*

**MEM-010:** The system SHALL enforce row-level security on memory tables

*Priority: Essential*
*Security: User-specific memory isolation*
*Implementation: PostgreSQL RLS policies*
*Privacy: User memories not visible across accounts*
*GDPR: Support for full memory deletion on request*
*Status: Active - v7.1*

**MEM-011:** The system SHALL support personalized document entity recommendations

*Priority: High*
*Function: get_personalized_document_entities() with relevance scoring*
*Scoring: Combines user memory connections, access frequency, relevance*
*Use Case: "Show documents related to my expertise/interests"*
*Performance: <50ms for entity retrieval*
*Status: Active - v7.1*

**MEM-012:** The system SHALL maintain temporal tracking for memories

*Priority: Medium*
*Tracking: first_mentioned_at, last_mentioned_at, mention_count*
*Purpose: Identify frequently referenced vs. one-time facts*
*Decay: Used for automatic confidence decay of stale information*
*Analytics: Memory usage patterns and user engagement*
*Status: Active - v7.1*

**MEM-013:** The system SHALL support memory importance and confidence scoring

*Priority: High*
*Importance: 0.0-1.0 score for prioritization (explicit vs. casual mentions)*
*Confidence: 0.0-1.0 score for reliability (explicit vs. inferred)*
*Source Types: explicit (directly stated), inferred (implied), conversation*
*Ranking: Combined scoring for context retrieval prioritization*
*Status: Active - v7.1*

**MEM-014:** The system SHALL implement multi-hop graph traversal for context

*Priority: Essential*
*Algorithm: Recursive CTEs in PostgreSQL*
*Depth Control: Configurable 1-3 hops (default 2)*
*Cycle Prevention: Track visited nodes, prevent infinite loops*
*Scoring: Decay similarity by edge strength at each hop*
*Performance: <100ms for 2-hop traversal with 10 seed nodes*
*Status: Active - v7.1*

#### 3.1.13.2 Session Management

**SES-001:** The system SHALL maintain session-based chat history

*Priority: Essential*
*Storage: Supabase n8n_chat_histories table*
*Retention: 90 days*
*Status: Active - v7.1*

**SES-002:** The system SHALL support multi-session management per user

*Priority: High*
*Sessions: Unlimited concurrent sessions*
*Isolation: Complete session isolation*
*Status: Active - v7.1*

**SES-003:** The system SHALL preserve context within sessions

*Priority: Essential*
*Window: Last 10 messages or 8000 tokens*
*Compression: Automatic summarization for long conversations*
*Status: Active - v7.1*

### 3.1.14 Structured Data Requirements (NEW - v7.0)

#### 3.1.14.1 Tabular Data Processing

**TAB-001:** The system SHALL process CSV and Excel files as structured data

*Priority: High*
*Formats: CSV, TSV, XLSX, XLS*
*Preservation: Column headers, data types, relationships*
*Status: Active - v7.1*

**TAB-002:** The system SHALL store tabular data in dedicated schema

*Priority: High*
*Table: tabular_document_rows*
*Format: JSONB for flexible schema*
*Indexing: GIN index on row_data*
*Status: Active - v7.1*

**TAB-003:** The system SHALL support structured queries on tabular data

*Priority: Medium*
*Query Types: Filter, aggregate, join*
*Interface: Natural language to SQL translation*
*Status: Active - v7.1*

**TAB-004:** The system SHALL preserve table relationships and metadata

*Priority: Medium*
*Metadata: Column names, types, statistics*
*Relationships: Foreign key detection*
*Status: Active - v7.1*

#### 3.1.14.2 Schema Inference

**SCH-001:** The system SHALL automatically infer schema from structured data

*Priority: High*
*Detection: Column types (string, number, date, boolean)*
*Validation: Sample-based validation*
*Status: Active - v7.1*

**SCH-002:** The system SHALL detect and preserve data relationships

*Priority: Medium*
*Detection: Foreign key patterns, hierarchical structures*
*Use: Enhanced query planning*
*Status: Active - v7.1*

#### 3.1.14.3 Metadata Fields Management (NEW - v7.0)

**MDF-001:** The system SHALL maintain a metadata_fields table for dynamic schema management

*Priority: High*
*Purpose: Track available metadata fields, types, and validation rules*
*Schema: field_name, field_type, allowed_values, validation_regex, description*
*Status: New - v7.0*

**MDF-002:** The system SHALL support multiple field types:
- `string`: Text fields with optional regex validation
- `number`: Numeric fields with range validation
- `date`: ISO8601 date/timestamp fields
- `boolean`: True/false fields
- `enum`: Restricted value set from allowed_values array
- `array`: Multi-value fields

*Priority: High*
*Validation: Type checking enforced at ingestion*
*Status: New - v7.0*

**MDF-003:** The system SHALL enforce field validation rules:
- Required fields must be present
- Enum fields must match allowed_values
- Regex patterns must match for validated fields
- Type coercion with error handling

*Priority: Medium*
*Error Handling: Graceful degradation with warnings*
*Status: New - v7.0*

**MDF-004:** The system SHALL support field ordering and display configuration:
- display_order integer for UI rendering
- is_searchable flag for search index inclusion
- is_required flag for validation
- default_value for missing fields

*Priority: Medium*
*Use Case: Dynamic form generation, search filtering*
*Status: New - v7.0*

**MDF-005:** The system SHALL allow runtime metadata field registration:
- Add new fields without schema migration
- Update field definitions dynamically
- Backwards compatible with existing documents

*Priority: Medium*
*Flexibility: Schema evolution without downtime*
*Status: New - v7.0*

### 3.1.15 Multi-Modal Processing Requirements (NEW - v7.0)

#### 3.1.15.1 Image Processing

**IMG-001:** The system SHALL process images using Claude Vision API

*Priority: High*
*Formats: JPG, PNG, GIF, BMP, TIFF, WEBP*
*Extraction: Text (OCR), objects, descriptions, captions*
*Status: Active - v7.1*

**IMG-002:** The system SHALL generate descriptive embeddings for images

*Priority: High*
*Method: Text description → nomic-embed-text*
*Storage: Standard vector storage with image metadata*
*Status: Active - v7.1*

**IMG-003:** The system SHALL support image-text cross-modal search

*Priority: Medium*
*Query: Text query retrieves relevant images*
*Ranking: Semantic similarity of descriptions*
*Status: Active - v7.1*

#### 3.1.15.2 Audio Processing

**AUD-001:** The system SHALL transcribe audio files using Soniox API

*Priority: Medium*
*Formats: MP3, WAV, M4A, FLAC*
*Features: Speaker diarization, timestamps*
*Cost: $0.005 per minute*
*Status: Active - v7.1*

**AUD-002:** The system SHALL process transcriptions as text documents

*Priority: Medium*
*Enrichment: Speaker labels, timing metadata*
*Chunking: By speaker turns or time segments*
*Status: Active - v7.1*

#### 3.1.15.3 Video Processing

**VID-001:** The system SHALL extract keyframes from video files

*Priority: Low*
*Method: 1 frame per 10 seconds*
*Processing: Each frame as image (Claude Vision)*
*Status: Future - v8.0*

**VID-002:** The system SHALL extract audio tracks for transcription

*Priority: Low*
*Method: FFmpeg audio extraction → Soniox*
*Integration: Synchronized transcript with keyframes*
*Status: Future - v8.0*

### 3.1.16 Advanced Context Expansion Requirements (NEW - v7.0)

#### 3.1.16.1 Chunk Expansion

**CTX-001:** The system SHALL expand retrieved chunks with neighboring context

*Priority: High*
*Range: Configurable (default ±2 chunks)*
*Limit: Maximum 8000 tokens total*
*Status: Active - v7.1*

**CTX-002:** The system SHALL merge overlapping expanded chunks

*Priority: High*
*Method: Deduplication by chunk ID*
*Ordering: Document order preservation*
*Status: Active - v7.1*

**CTX-003:** The system SHALL prioritize expansion based on relevance scores

*Priority: Medium*
*Strategy: Expand high-scoring chunks more than low-scoring*
*Weighting: Score-based expansion radius*
*Status: Active - v7.1*

#### 3.1.16.2 Hierarchical Context

**CTX-004:** The system SHALL maintain hierarchical document structure

*Priority: Medium*
*Hierarchy: Document → Section → Subsection → Chunk*
*Storage: Metadata fields for parent/child relationships*
*Status: Active - v7.1*

**CTX-005:** The system SHALL expand to parent context when relevant

*Priority: Medium*
*Trigger: High relevance score or missing context*
*Expansion: Include section headers and summaries*
*Status: Active - v7.1*

**CTX-006:** The system SHALL provide batch context expansion via get_chunks_by_ranges() function

*Priority: High*
*Input: JSON array of range specifications [{doc_id, start, end}]*
*Output: Chunks with hierarchical_context and graph_entities*
*Performance: <300ms for ≤10 ranges*
*Status: New - v7.0*

**CTX-007:** The system SHALL include knowledge graph entity references in expanded context

*Priority: Medium*
*Integration: LightRAG knowledge_entities table*
*Enrichment: Entity names linked to retrieved chunks*
*Use: Graph-enhanced RAG traversal*
*Status: New - v7.0*

### 3.1.17 Observability Requirements (NEW - v7.0)

#### 3.1.17.1 Metrics and Monitoring

**OBS-001:** The system SHALL track and expose key performance metrics

*Priority: High*
*Metrics: Query latency, search quality, token usage, cost per query, error rate*
*Collection: Prometheus metrics*
*Visualization: Grafana dashboards*
*Status: Active - v7.1*

**OBS-002:** The system SHALL log all API calls and searches

*Priority: Essential*
*Format: Structured JSON logs*
*Storage: Elasticsearch or file-based*
*Retention: 90 days*
*Status: Active - v7.1*

**OBS-003:** The system SHALL implement distributed tracing

*Priority: Medium*
*Framework: OpenTelemetry*
*Tracing: Request flow through all components*
*Storage: Jaeger*
*Status: Active - v7.1*

#### 3.1.17.2 Alerting

**ALT-001:** The system SHALL alert on error rate thresholds

*Priority: High*
*Threshold: >5% error rate for 5 minutes*
*Delivery: Email, Slack, PagerDuty*
*Status: Active - v7.1*

**ALT-002:** The system SHALL alert on performance degradation

*Priority: High*
*Thresholds: P95 latency >3s, search quality <70%*
*Status: Active - v7.1*

**ALT-003:** The system SHALL alert on cost anomalies

*Priority: Medium*
*Threshold: >$10/hour token usage*
*Status: Active - v7.1*

### 3.1.18 Edge Functions and API Requirements (NEW - v7.0)

**API-001:** The system SHALL provide HTTP-accessible Edge Functions for all core database operations

*Implementation: Supabase Edge Functions (TypeScript/Deno)*
*Integration: n8n HTTP Request nodes, web clients, mobile apps*
*Status: New - v7.0*

**API-002:** The system SHALL implement Edge Function for hybrid search with the following capabilities:
- Accept JSON payload: `{query, top_k, rerank_enabled, user_id}`
- Return structured results with metadata
- Support CORS for browser access
- Validate JWT authentication
- Handle errors gracefully

*Endpoint: `/functions/v1/hybrid-search`*
*Response Time: <500ms for cached, <2s for new queries*
*Status: New - v7.0*

**API-003:** The system SHALL implement Edge Function for context expansion:
- Accept range specifications: `{ranges: [{doc_id, start, end}]}`
- Return chunks with hierarchical context
- Include knowledge graph entity references
- Support batch processing of multiple ranges

*Endpoint: `/functions/v1/context-expansion`*
*Response Time: <300ms for ≤10 ranges*
*Status: New - v7.0*

**API-004:** The system SHALL implement Edge Function for knowledge graph queries:
- Entity lookup by name
- Relationship traversal
- Support filtering by relationship type
- Return graph structure as JSON

*Endpoint: `/functions/v1/graph-query`*
*Response Time: <400ms*
*Status: New - v7.0*

**API-005:** All Edge Functions SHALL implement CORS headers for web client access:
- `Access-Control-Allow-Origin: *` (or specific domains for production)
- `Access-Control-Allow-Headers: authorization, x-client-info, apikey, content-type`
- Handle OPTIONS preflight requests

*Security: RLS enforced, JWT validation automatic*
*Status: New - v7.0*

**API-006:** Edge Functions SHALL use Supabase Service Role Key for internal operations:
- Full database access within Edge Function context
- Automatic RLS bypass when needed
- Secure secret management via Supabase CLI

*Security Level: Service role key accessible only server-side*
*Status: New - v7.0*

**API-007:** The system SHALL support three authentication levels:
1. **Anon Key**: Rate-limited, RLS enforced, client-safe
2. **Service Role Key**: Full access, Edge Functions only
3. **User JWT**: Per-user authentication, automatic RLS

*Implementation: Supabase Auth integration*
*Status: New - v7.0*

**API-008:** Edge Functions SHALL return standardized JSON responses:
```json
{
  "success": true|false,
  "data": {...},
  "error": "error message if applicable",
  "metadata": {
    "count": N,
    "query_time_ms": N
  }
}
```

*Consistency: All endpoints follow same pattern*
*Status: New - v7.0*

**API-009:** The system SHALL support local Edge Function testing via Supabase CLI:
- `supabase functions serve` for local development
- Hot reload during development
- Local database connection

*Developer Experience: <5 minute setup*
*Status: New - v7.0*

**API-010:** Edge Functions SHALL be deployable with single command:
- `supabase functions deploy [name]`
- Automatic TypeScript compilation
- Environment variable management via `supabase secrets`

*Deployment Time: <2 minutes per function*
*Status: New - v7.0*

**API-011:** The system SHALL implement RLS policies for all user-accessible tables:
- Users can only access their own documents
- Service role bypasses RLS for system operations
- Automatic auth.uid() filtering

*Security: Zero-trust model, policy enforcement at database level*
*Status: New - v7.0*

**API-012:** Edge Functions SHALL log all errors with structured format:
```typescript
{
  timestamp: ISO8601,
  function_name: string,
  error_type: string,
  error_message: string,
  request_payload: object,
  user_id: string
}
```

*Monitoring: Integrated with Supabase Logs*
*Status: New - v7.0*

## 3.2 Non-Functional Requirements

### 3.2.1 Performance Requirements (ENHANCED v5.0)

**NFR-001: Response Time**
- Query Response: <2 seconds for 95% of requests
- Document Processing: <5 minutes for standard documents
- Fast Track: <90 seconds for simple documents
- Memory Retrieval: <100ms for local, <500ms for cloud
- LLM Inference: 32 tokens/second for Llama 70B

*Priority: Essential*
*Measurement: Response time monitoring*
*Status: Active - v5.0*

**NFR-002: Throughput**
- Document Processing: 500+ documents per day (v5.0, up from 200+)
- Concurrent Users: Support for 10+ simultaneous users
- Concurrent Workflows: 10 parallel (v5.0, up from 5)
- API Calls: 10,000+ requests per day
- Storage Operations: 1,000+ read/write operations per hour

*Priority: Essential*
*Measurement: System throughput metrics*
*Status: Enhanced - v5.0*

**NFR-003: Resource Utilization**
- CPU Usage: <60% average (28-core Mac Studio)
- GPU Usage: <70% during inference (60-core GPU)
- Memory Usage: ~65GB for models, 31GB free
- Network Bandwidth: <100 Mbps average
- Storage Growth: <10GB per day

*Priority: High*
*Measurement: Resource monitoring*
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

**NFR-011:** The system SHALL maintain 98% local processing ratio

*Measurement: Local vs cloud processing metrics*
*Status: Active - v5.0*

**NFR-012:** The system SHALL achieve 80%+ cache hit rate

*Measurement: Cache effectiveness*
*Status: Active - All Versions*

### 3.2.2 Security Requirements (ENHANCED v5.0)

**SR-001: Data Encryption**
- At Rest: AES-256 encryption for all stored data
- In Transit: TLS 1.3 for all communications
- Backup: Client-side encryption before upload
- Keys: Secure key management with rotation

*Priority: Essential*
*Status: Active - All Versions*

**SR-002: Authentication and Authorization**
- Method: OAuth 2.0 / JWT tokens
- MFA: Support for multi-factor authentication
- RBAC: Role-based access control
- Session: Secure session management with timeout

*Priority: Essential*
*Status: Active - All Versions*

**SR-003: Audit Logging**
- Coverage: All data access and modifications
- Details: User, timestamp, action, resource
- Storage: Immutable audit log storage
- Retention: 90-day minimum retention

*Priority: High*
*Status: Active - All Versions*

**SR-004: Privacy Compliance**
- GDPR: Full compliance with data protection
- PII: Automatic detection and handling
- Right to Delete: Support for data deletion requests
- Consent: Explicit consent management

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

### 3.2.3 Reliability Requirements

**NFR-004: Availability**
- Uptime: 99.5% availability (excluding planned maintenance)
- Failover: Automatic failover between local and cloud
- Recovery: 4-hour RTO, 1-hour RPO
- Redundancy: All critical components redundant

*Priority: Essential*
*Measurement: Monthly uptime percentage*
*Status: Enhanced - v5.0*

**NFR-005: Error Handling**
- Detection: Automatic error detection and classification
- Recovery: Intelligent retry with exponential backoff
- Circuit Breaker: Prevent cascade failures
- Notification: Real-time error alerting

*Priority: Essential*
*Status: Active - All Versions*

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

### 3.2.4 Scalability Requirements

**NFR-006: Horizontal Scaling**
- Cloud Services: Auto-scaling based on load
- Processing: Dynamic worker allocation
- Storage: Unlimited storage via Backblaze B2
- Database: Connection pooling and read replicas

*Priority: High*
*Status: Active - All Versions*

**NFR-007: Vertical Scaling**
- Mac Studio: Support for model expansion up to 96GB
- Models: Ability to host larger models (up to 70B)
- Cache: Expandable cache storage (31GB available)
- Processing: GPU acceleration fully utilized

*Priority: Medium*
*Status: Active - v5.0*

**NFR-030:** The system SHALL scale to handle 100,000+ documents in storage

*Measurement: Storage performance at scale*
*Note: v5.0 - Increased capacity*
*Status: Enhanced - v5.0*

**NFR-031:** The system SHALL support up to 10M vectors with maintained performance

*Measurement: Vector search latency at scale*
*Note: v5.0 - Increased from 1M*
*Status: Enhanced - v5.0*

**NFR-033:** The system SHALL support incremental capacity increases

*Measurement: Scaling without downtime*
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

*Integration: Via MCP protocol*
*Features: Document upload, query interface, result display*
*Response: Real-time streaming responses*
*Visualization: Rich media support*
*Status: Active - v5.0*

**UI-012:** The interface SHALL access mem-agent memories

*Status: Active - v5.0*

**UI-013:** The interface SHALL trigger document processing

*Status: Active - v5.0*

#### 3.3.1.4 Web Dashboard

**UI-014:** The interface SHALL provide browser-based management

*Access: Browser-based management interface*
*Features: System monitoring, cost tracking, configuration*
*Responsive: Mobile and desktop compatible*
*Security: Secure authentication required*
*Status: Active - All Versions*

### 3.3.2 Hardware Interfaces

**HW-001:** Mac Studio M3 Ultra Interface
- 28-core CPU, 60-core GPU, 32-core Neural Engine
- 96GB unified memory (800 GB/s bandwidth)
- 1TB+ SSD storage recommended
- 10Gb Ethernet connection
- 6x Thunderbolt 4 ports
- 2x USB-A, HDMI 2.1
- Power consumption: ~65W average during inference
- Cooling: Adequate ventilation required for 24/7 operation
- Optional: External storage via Thunderbolt
- Optional: Monitoring display for maintenance

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

#### 3.3.3.3 API Interfaces

**SI-009:** RESTful API Interface
- Protocol: RESTful API with OpenAPI specification
- Format: JSON request/response
- Authentication: API key or OAuth token
- Rate Limiting: Configurable per client
- Versioning: URI-based versioning (/api/v1/)

*Status: Active - All Versions*

### 3.3.4 Communications Interfaces

**CI-001:** The system SHALL use HTTPS for all external communications
**CI-002:** The system SHALL implement WebSocket for real-time updates
**CI-003:** The system SHALL support REST API with JSON payloads
**CI-004:** The system SHALL use MCP for model context protocol
**CI-005:** The system SHALL implement Tailscale VPN for secure remote access
**CI-006:** The system SHALL use SSH for Mac Studio administration
**CI-007:** The system SHALL support gRPC for high-performance local communication

*Status: Active - All Versions*

### 3.3.5 Context Expansion Requirements (NEW)

**CER-001: Hierarchical Document Structure Extraction**
*Priority: Essential*
*Description: Extract and store document hierarchy with heading levels*
*Processing: During ingestion after chunking*
*Storage: PostgreSQL hierarchical_index in record_manager*
*Output: JSON structure with H1-H6 mappings to chunk IDs*
*Dependencies: Smart markdown chunking*
*Status: Active - v5.0*

**CER-002: Neighbor Chunk Retrieval**
*Priority: High*
*Description: Support retrieval of adjacent chunks (±1 position)*
*Method: Line number-based lookup in PostgreSQL*
*Performance: <100ms retrieval time*
*Use Case: Expanding context for boundary chunks*
*Status: Active - v5.0*

**CER-003: Section-Based Expansion**
*Priority: Essential*
*Description: Retrieve all chunks within a document section*
*Method: Chunk range queries based on hierarchy*
*Metadata: Include parent_range and child_range in chunks*
*Performance: <500ms for section retrieval*
*Status: Active - v5.0*

**CER-004: Document Hierarchy Mapping**
*Priority: Essential*
*Description: Create and maintain chunk-to-section mappings*
*Storage: Supabase edge function for retrieval*
*Format: Hierarchical index with chunk ranges*
*Update: Automatic on document ingestion*
*Status: Active - v5.0*

**CER-005: Smart Chunk Merging**
*Priority: High*
*Description: Merge tiny chunks (<100 tokens) intelligently*
*Method: Combine with adjacent chunks while preserving boundaries*
*Threshold: Configurable minimum chunk size*
*Quality: Maintain semantic coherence*
*Status: Active - v5.0*

## 3.4 System Features

### 3.4.1 Intelligent Document Router

**Description:** Automatically routes documents to optimal processing pipeline
**Priority:** Critical
**Stimulus:** Document upload or URL submission
**Response:** Document routed to appropriate processor

**Functional Requirements:**
- Analyze document complexity and type
- Assess privacy requirements for local vs cloud routing
- Select optimal processing pipeline (local first for v5.0)
- Route to local or cloud based on privacy needs
- Track routing decisions for optimization
- Maintain routing metrics for analysis

*Status: Active - v5.0*

### 3.4.2 Smart Cost Optimizer

**Description:** Minimizes API costs through intelligent routing
**Priority:** High
**Stimulus:** Processing request received
**Response:** Cost-optimized processing path selected

**Functional Requirements:**
- Track API costs in real-time
- Prioritize local processing (98% target)
- Cache frequently accessed data (80%+ hit rate)
- Batch API calls when possible
- Use local processing when cost-effective
- Generate cost reports and projections

*Status: Active - v5.0*

### 3.4.3 Memory Context System

**Description:** Maintains persistent context across interactions
**Priority:** High
**Stimulus:** User query or document processing
**Response:** Relevant context retrieved and applied

**Functional Requirements:**
- Store interaction history locally (mem-agent)
- Retrieve relevant context for queries (<100ms)
- Update memory with new information
- Manage memory size and relevance
- Backup memories to encrypted storage
- Support memory versioning

*Status: Active - v5.0*

### 3.4.4 Adaptive Processing Pipeline

**Description:** Dynamically adjusts processing based on content characteristics
**Priority:** High
**Stimulus:** Document characteristics detected
**Response:** Optimal processing pipeline selected

**Functional Requirements:**
- Detect document type and complexity
- Identify sensitive content for local processing
- Select appropriate AI models
- Configure chunking parameters
- Optimize for quality vs speed
- Monitor pipeline performance

*Status: Active - v5.0*

## 3.5 Performance Requirements

### 3.5.1 Static Performance Requirements

**SPR-001: System Capacity**
- Maximum Documents: 500+ per day (v5.0, up from 200+)
- Maximum Users: 10 concurrent
- Maximum Storage: 100TB active data (via B2)
- Maximum Memory: 96GB (Mac Studio M3 Ultra)
- Maximum Models: 65GB model storage, 31GB operational

*Priority: Essential*
*Status: Active - v5.0*

**SPR-002: Response Times**
- P50 Latency: <1 second
- P95 Latency: <2 seconds
- P99 Latency: <5 seconds
- Maximum: 30 seconds timeout
- LLM Generation: 32 tokens/second

*Priority: Essential*
*Status: Active - v5.0*

### 3.5.2 Dynamic Performance Requirements

**DPR-001: Load Adaptation**
- Auto-scaling: Based on queue depth
- Throttling: Graceful degradation under load
- Priority: Fast track for simple documents
- Backpressure: Queue management for overload
- Resource Allocation: Dynamic based on workload

*Priority: High*
*Status: Active - v5.0*

**DPR-002: Intelligent Caching**
- Cache Hit Rate: >80% target
- Cache Size: 31GB memory + 100GB SSD
- TTL Management: Adaptive based on usage
- Prefetching: Predictive cache warming
- Invalidation: Smart cache invalidation

*Priority: High*
*Status: Active - v5.0*

## 3.6 Design Constraints

### 3.6.1 Hardware Constraints

- **Mac Studio M3 Ultra:** 96GB unified memory limit
- **Storage:** 1TB+ SSD recommended for models and cache
- **Network:** 10Gb Ethernet for optimal performance
- **Power:** Continuous 65W average draw capability
- **Cooling:** Adequate ventilation for 24/7 operation
- **GPU:** 60-core GPU shared between inference tasks
- **Location:** Secure physical location required

*Status: Active - v5.0*

### 3.6.2 Software Constraints

- **Operating System:** macOS 15.0+ (Sequoia) required
- **Python:** 3.11+ requirement
- **Docker:** Docker Desktop for Mac compatibility
- **MCP Protocol:** Anthropic MCP protocol limitations
- **Model Formats:** GGUF format for efficient storage
- **API Compatibility:** LiteLLM for OpenAI compatibility
- **Memory Management:** mem-agent MCP constraints

*Status: Active - v5.0*

### 3.6.3 Regulatory Constraints

- **GDPR:** Compliance mandatory for EU users
- **SOC 2:** Type II audit requirements
- **HIPAA:** Ready architecture (requires configuration)
- **Data Residency:** Restrictions on data location
- **Privacy Laws:** State and country-specific requirements
- **Industry Regulations:** Sector-specific compliance
- **Encryption Standards:** AES-256 minimum

*Status: Active - All Versions*

### 3.6.4 Architectural Constraints

- **Local First:** 98% processing must be local
- **Cloud Dependency:** Minimal cloud service usage
- **Backup Strategy:** Zero-knowledge encryption required
- **Network Latency:** <50ms to cloud services
- **Model Size:** Limited by 96GB total memory
- **Concurrent Processing:** Hardware-limited parallelism

*Status: Active - v5.0*

## 3.7 Software System Attributes

### 3.7.1 Reliability

- **Mean Time Between Failures:** >720 hours
- **Mean Time To Recovery:** <4 hours
- **Error Rate:** <0.1% of operations
- **Data Integrity:** 99.999% accuracy
- **Backup Success Rate:** 100% target
- **Service Availability:** 99.5% uptime

*Priority: Essential*
*Status: Active - v5.0*

### 3.7.2 Maintainability

- **Code Coverage:** >80% test coverage
- **Documentation:** Complete API documentation
- **Logging:** Comprehensive operational logs
- **Monitoring:** Real-time system metrics
- **Debugging:** Remote debugging capability
- **Updates:** Zero-downtime deployments

*Priority: High*
*Status: Active - All Versions*

### 3.7.3 Portability

- **Platform:** macOS and Linux support
- **Database:** PostgreSQL standard compliance
- **APIs:** OpenAPI 3.1 specification
- **Data Formats:** Standard format exports (JSON, CSV, Markdown)
- **Model Formats:** GGUF for model portability
- **Container Support:** Docker compatibility

*Priority: Medium*
*Status: Active - All Versions*

### 3.7.4 Security

- **Encryption:** AES-256 minimum for all sensitive data
- **Authentication:** Industry standard protocols (OAuth 2.0, JWT)
- **Authorization:** Fine-grained permissions (RBAC)
- **Audit:** Complete audit trail with immutable logs
- **Vulnerability Management:** Regular security updates
- **Penetration Testing:** Annual security audits

*Priority: Essential*
*Status: Active - All Versions*

### 3.7.5 Usability

- **Learning Curve:** <2 hours for basic operations
- **Documentation:** Comprehensive user guides
- **Error Messages:** Clear and actionable
- **Accessibility:** WCAG 2.1 AA compliance
- **Localization:** Multi-language support ready
- **User Feedback:** In-app feedback mechanisms

*Priority: High*
*Status: Active - All Versions*

### 3.7.6 Performance

- **Responsiveness:** <2 second response for 95% of queries
- **Throughput:** 500+ documents per day
- **Efficiency:** 98% local processing ratio
- **Resource Usage:** <60% CPU, <70% GPU average
- **Scalability:** Linear scaling with resources
- **Optimization:** Continuous performance tuning

*Priority: Essential*
*Status: Active - v5.0*

### 3.1.22 Sub-Workflow Architecture Requirements (NEW - v7.0)

**SWF-001:** The system SHALL implement modular sub-workflows for complex processing tasks

*Priority: High*
*Purpose: Improve maintainability, testability, and reusability*
*Patterns: Multimodal processing, knowledge graph operations, memory management*
*Status: New - v7.0*

**SWF-002:** The system SHALL implement a dedicated multimodal processing sub-workflow with:
- Image processing via Claude Vision API
- Audio transcription via Soniox
- Binary data handling
- Result format standardization

*Priority: High*
*Workflow Name: Empire - Multimodal Processing Sub-Workflow*
*Trigger: HTTP POST /multimodal-process*
*Status: New - v7.0*

**SWF-003:** The system SHALL implement a knowledge graph sub-workflow with:
- LightRAG API integration
- Async processing with wait/poll patterns
- Status checking and retry logic
- Graph ID mapping to documents table

*Priority: High*
*Workflow Name: Empire - Knowledge Graph Sub-Workflow*
*Trigger: HTTP POST /kg-process*
*Max Retries: 10*
*Status: New - v7.0*

**SWF-004:** Sub-workflows SHALL be callable from main workflows via Execute Workflow nodes

*Priority: Medium*
*Benefits: Modularity, independent testing, parallel execution*
*Status: New - v7.0*

**SWF-005:** Sub-workflows SHALL return standardized result objects with:
- status (success/error/timeout)
- data (processed results)
- error (error details if applicable)
- metadata (processing metrics)

*Priority: Medium*
*Format: JSON*
*Status: New - v7.0*

### 3.1.23 Document Lifecycle Management Requirements (NEW - v7.0)

**DLC-001:** The system SHALL support complete document deletion with cascade operations

*Priority: High*
*Cascade Targets: Vector embeddings, tabular data, knowledge graph, object storage*
*Audit: All deletions logged to audit_log table*
*Status: New - v7.0*

**DLC-002:** The system SHALL implement document versioning with:
- version_number (integer, auto-increment)
- previous_version_id (UUID reference)
- is_current_version (boolean flag)

*Priority: Medium*
*Trigger: Content hash change detection*
*Retention: All versions preserved unless manually purged*
*Status: New - v7.0*

**DLC-003:** The system SHALL support document update detection via content hash comparison

*Priority: High*
*Method: SHA-256 hash comparison*
*Action: Create new version, archive old version*
*Status: New - v7.0*

**DLC-004:** Document deletion SHALL be exposed via DELETE /document/:id webhook

*Priority: Medium*
*Authentication: Required*
*Authorization: User must own document or have admin role*
*Status: New - v7.0*

**DLC-005:** The system SHALL preserve deleted document metadata for compliance:
- deletion timestamp
- deleted_by user ID
- retention period (configurable, default 90 days)

*Priority: Medium*
*Compliance: GDPR right to be forgotten with audit trail*
*Status: New - v7.0*

### 3.1.24 Asynchronous Processing Pattern Requirements (NEW - v7.0)

**ASY-001:** The system SHALL implement wait/poll patterns for long-running operations

*Priority: High*
*Use Cases: LightRAG processing, OCR jobs, batch operations*
*Pattern: Initialize → Wait → Poll → Check Status → Continue/Complete*
*Status: New - v7.0*

**ASY-002:** Async polling SHALL use exponential backoff with:
- Initial interval: 5 seconds
- Max interval: 30 seconds
- Backoff factor: 1.5x
- Max retries: 20

*Priority: High*
*Purpose: Reduce API load, improve reliability*
*Status: New - v7.0*

**ASY-003:** The system SHALL implement timeout handling for async operations:
- Default timeout: 10 minutes (configurable)
- Graceful degradation on timeout
- Error logging with context

*Priority: Medium*
*Timeout Action: Mark as failed, notify user, log for manual review*
*Status: New - v7.0*

**ASY-004:** Async job status SHALL be tracked with states:
- pending (initial state)
- processing (in progress)
- complete (successfully finished)
- error (failed with details)
- timeout (exceeded max wait time)

*Priority: High*
*Storage: Workflow variables + database status field*
*Status: New - v7.0*

**ASY-005:** The system SHALL support async result retrieval via status endpoints

*Priority: Medium*
*Pattern: GET /jobs/:id/status*
*Response: {status, progress, result, error}*
*Status: New - v7.0*

### 3.1.25 Error Handling and Retry Requirements (NEW - v7.0)

**ERR-001:** Critical HTTP request nodes SHALL implement retry configuration:
- retryOnFail: true
- maxTries: 3
- waitBetweenTries: 2000ms
- backoffFactor: 2

*Priority: High*
*Applies To: External API calls, database operations, file operations*
*Status: New - v7.0*

**ERR-002:** The system SHALL distinguish between retryable and non-retryable errors:
- Retryable: ETIMEDOUT, ECONNRESET, 502, 503, 504
- Non-retryable: 400, 401, 403, 404, 422

*Priority: High*
*Action: Retry retryable errors, fail immediately on non-retryable*
*Status: New - v7.0*

**ERR-003:** Nodes that may return empty results SHALL set alwaysOutputData: true

*Priority: Medium*
*Purpose: Prevent workflow halts on empty query results*
*Examples: Database lookups, API searches, filter operations*
*Status: New - v7.0*

**ERR-004:** The system SHALL log all errors with structured format:
- timestamp (ISO8601)
- error_type (code/status)
- error_message (detailed description)
- context (workflow, node, input data)
- stack_trace (for debugging)

*Priority: High*
*Storage: error_logs table in Supabase*
*Retention: 90 days*
*Status: New - v7.0*

**ERR-005:** Critical errors SHALL trigger notifications via:
- n8n error workflow
- Email alerts (configurable)
- Webhook to monitoring system

*Priority: Medium*
*Threshold: 5 errors in 10 minutes*
*Status: New - v7.0*

## 3.8 Deprecated Requirements (Historical Reference)

### 3.8.1 Deprecated in v5.0

#### Zep Memory Service (Replaced by mem-agent)

**DEPRECATED-FR-092:** ~~The system SHALL integrate Zep for user-specific long-term memory~~

*Deprecated: v5.0*
*Replaced by: MEM-001 through MEM-010*
*Reason: Local mem-agent provides better privacy and performance*

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

### 3.8.2 Migration Path

For users migrating from v4.0 to v5.0:

1. **Memory Migration:** Export Zep memories → Convert to Markdown → Import to mem-agent
2. **Embedding Migration:** Re-generate with nomic-embed for better local performance
3. **Vision Migration:** Re-process images with local Qwen2.5-VL
4. **API Migration:** Update to LiteLLM endpoints for compatibility
5. **Hardware Migration:** Transition from Mac Mini M4 to Mac Studio M3 Ultra

## 3.9 Performance Metrics Summary

### 3.9.1 v5.0 Target Metrics

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

### 3.9.2 Resource Utilization

| Resource | Usage | Available |
|----------|-------|-----------|
| Memory (Models) | 65GB | 31GB free |
| CPU Average | 40% | 60% headroom |
| GPU Peak | 70% | 30% buffer |
| Storage Models | ~50GB | User defined |
| Network | <50Mbps | 10Gbps capable |
| Power Average | 65W | Well within limits |

## 3.10 Compliance and Standards

**CS-001:** The system SHALL comply with IEEE 830-1998 for documentation
**CS-002:** The system SHALL follow OpenAPI 3.1 for API specification
**CS-003:** The system SHALL implement OAuth 2.0 for authentication
**CS-004:** The system SHALL use ISO 8601 for datetime formats
**CS-005:** The system SHALL follow REST architectural principles
**CS-006:** The system SHALL maintain GDPR compliance
**CS-007:** The system SHALL meet SOC 2 Type II requirements
**CS-008:** The system SHALL implement HIPAA-ready security (when configured)

*Status: Active - All Versions*