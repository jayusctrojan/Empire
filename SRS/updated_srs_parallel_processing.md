# AI Empire File Processing System - Software Requirements Specification (SRS)

**Document Version:** 2.5  
**Date:** September 16, 2025  
**Project:** AI Empire Organizational Intelligence Platform  
**System:** File Processing Workflow V2.5 with Phoenix Observability + DeepEval Testing  

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for the AI Empire File Processing System, an automated workflow that processes course materials, documents, and media files to generate organizational intelligence and AI agent recommendations for business optimization. **Version 2.5 adds comprehensive observability with Arize Phoenix and systematic testing with DeepEval framework for production-ready reliability.**

### 1.2 Scope
The AI Empire File Processing System encompasses:
- Multi-format file processing and conversion
- **Parallel image extraction and vision analysis with session correlation**
- **Enhanced video processing with vision analysis**
- **Audio-only transcription for pure audio files**
- **Session-based correlation tracking for data integrity**
- **Real-time observability with Arize Phoenix**
- **Systematic testing with DeepEval framework**
- Content analysis and chunking via LlamaIndex + LangExtract
- Vector storage in Pinecone for retrieval
- Multi-agent organizational intelligence analysis via CrewAI
- Comprehensive course documentation generation
- Automated storage and audit trail management

### 1.3 Document Conventions
- **Functional Requirements** are prefixed with FR-
- **Non-Functional Requirements** are prefixed with NFR-
- **Business Rules** are prefixed with BR-
- **Technical Constraints** are prefixed with TC-
- **Observability Requirements** are prefixed with OR-
- **Testing Requirements** are prefixed with TR-

### 1.4 Intended Audience
- Development Team
- Product Managers
- System Administrators
- Business Stakeholders
- QA Engineers

---

## 2. Overall Description

### 2.1 Product Perspective
The AI Empire File Processing System is a comprehensive workflow automation platform built on n8n that orchestrates multiple AI services to transform raw course materials into actionable organizational intelligence. **Version 2.5 introduces production-ready observability with Arize Phoenix for real-time debugging and DeepEval for systematic testing, ensuring reliable operation of the parallel processing architecture with session correlation.**

### 2.2 Product Functions
- **Dual Input Processing:** HTML interface uploads and Backblaze file monitoring
- **Format Detection & Conversion:** Support for 40+ file formats including PDF, Office documents, audio, video, and images
- **Parallel Processing Architecture:** Simultaneous text and image extraction with session correlation
- **Comprehensive Image Processing:** Vision analysis for documents, articles, and video content
- **Advanced Video Processing:** Frame extraction and vision analysis for educational content
- **Audio-Only Processing:** Dedicated Soniox transcription for pure audio files
- **Session-Based Data Integrity:** Robust correlation tracking across all processing paths
- **Real-Time Observability:** Phoenix-powered debugging and performance monitoring
- **Systematic Testing:** DeepEval-driven evaluation and regression testing
- **Content Processing:** LlamaIndex + LangExtract for chunking, embedding generation, and structured extraction
- **Vector Storage:** Immediate Pinecone storage for future retrieval
- **AI Analysis:** CrewAI multi-agent analysis for organizational recommendations
- **Documentation Generation:** Automated creation of comprehensive reports with visual content timelines
- **Audit & Compliance:** Complete processing trail and notification system

### 2.3 User Classes and Characteristics
- **Content Processors:** Upload and monitor course materials with rich multimedia content
- **Business Analysts:** Review generated reports including comprehensive visual content analysis
- **Executives:** Receive notifications and approve implementation plans
- **System Administrators:** Monitor workflow performance and troubleshoot issues using Phoenix dashboards
- **QA Engineers:** Create and maintain DeepEval test suites for system validation

### 2.4 Operating Environment
- **Orchestration Platform:** n8n (https://jb-n8n.onrender.com)
- **Cloud Infrastructure:** Render.com services
- **Storage:** Backblaze B2 cloud storage
- **Vector Database:** Pinecone
- **Processing Services:** LlamaIndex, CrewAI, Soniox, MarkItDown MCP, **Hyperbolic Vision AI**
- **Observability:** **Arize Phoenix (embedded in LlamaIndex service)**
- **Testing Framework:** **DeepEval with Confident AI integration**
- **Audit Storage:** Airtable

---

## 3. System Features

### 3.1 Dual Input Processing System

#### 3.1.1 HTML Interface Webhook (Node 1a)
**FR-001:** The system SHALL accept file uploads via HTTP POST requests to `/content-upload` endpoint  
**FR-002:** The system SHALL validate uploaded content type (URL or file)  
**FR-003:** The system SHALL return immediate acknowledgment with processing ID and timestamp  
**FR-004:** The system SHALL support course and module metadata specification  
**FR-005:** The system SHALL generate unique session IDs for correlation tracking  

#### 3.1.2 Backblaze File Monitor (Node 1b)
**FR-006:** The system SHALL monitor Backblaze B2 `pending/` folder every 5 minutes  
**FR-007:** The system SHALL detect new files modified within the last 5 minutes  
**FR-008:** The system SHALL extract course/module information from file path structure  
**FR-009:** The system SHALL handle B2 API authentication and error responses  
**FR-010:** The system SHALL generate unique session IDs for monitored files  

### 3.2 Content Type Processing

#### 3.2.1 Input Type Classification (Node 2)
**FR-011:** The system SHALL distinguish between HTML interface and Backblaze monitor inputs  
**FR-012:** The system SHALL classify URLs as YouTube, Google Workspace, or general articles  
**FR-013:** The system SHALL validate URL formats and reject invalid URLs  
**FR-014:** The system SHALL maintain session correlation throughout classification  
**FR-015:** The system SHALL preserve source metadata in session context  

#### 3.2.2 Processing Route Switch (Node 3)
**FR-016:** The system SHALL route content to appropriate processors based on input type  
**FR-017:** The system SHALL support parallel processing of multiple content types  
**FR-018:** The system SHALL implement fallback routing for unrecognized types  
**FR-019:** The system SHALL distribute session context to all processing paths  

### 3.3 Format-Specific Processing

#### 3.3.1 Backblaze File Download (Node 3a)
**FR-020:** The system SHALL download files from Backblaze using B2 API  
**FR-021:** The system SHALL handle large file downloads up to 300MB  
**FR-022:** The system SHALL implement retry logic for failed downloads  
**FR-023:** The system SHALL maintain session correlation during download  

#### 3.3.2 YouTube Processing with Vision Analysis (Node 3b) - UPDATED
**FR-024:** The system SHALL extract YouTube video metadata and transcripts using three-tier system  
**FR-025:** The system SHALL extract video frames at configurable intervals (default: 30 seconds)  
**FR-026:** The system SHALL analyze frames using Hyperbolic Llama-3.2-11B-Vision-Instruct model  
**FR-027:** The system SHALL identify educational content including diagrams, charts, slides, and code  
**FR-028:** The system SHALL filter out frames with no significant visual content  
**FR-029:** The system SHALL create timestamped visual content descriptions  
**FR-030:** The system SHALL combine transcript and visual analysis in unified markdown output  
**FR-031:** The system SHALL maintain session correlation between transcript and frame analysis  
**FR-032:** The system SHALL generate session-tracked visual timeline for YouTube content  
**FR-033:** The system SHALL ensure video metadata preservation through parallel processing  

#### 3.3.3 Article Processing with Image Extraction (Node 3c) - UPDATED
**FR-034:** The system SHALL extract clean text from web articles  
**FR-035:** The system SHALL preserve article structure and metadata  
**FR-036:** The system SHALL generate markdown output with proper formatting  
**FR-037:** The system SHALL extract images from web articles along with text content  
**FR-038:** The system SHALL analyze extracted article images using Hyperbolic vision AI  
**FR-039:** The system SHALL associate image descriptions with their context in the article  
**FR-040:** The system SHALL preserve image positioning and captions from source articles  
**FR-041:** The system SHALL maintain session correlation for article content and images  

#### 3.3.4 Google Workspace Processing (Node 3d) - UPDATED
**FR-042:** The system SHALL process Google Docs, Sheets, and Slides URLs  
**FR-043:** The system SHALL extract text content while preserving structure  
**FR-044:** The system SHALL handle authentication for accessible documents  
**FR-045:** The system SHALL extract embedded images from Google Workspace documents  
**FR-046:** The system SHALL analyze Google Workspace images using vision processing  
**FR-047:** The system SHALL maintain session correlation for Google Workspace content and images  
**FR-048:** The system SHALL preserve document structure with integrated visual elements  

### 3.4 Enhanced File Type Detection and Format Conversion

#### 3.4.1 Enhanced File Detection with Parallel Processing Support (Node 4) - UPDATED
**FR-049:** The system SHALL detect 40+ file formats including PDF, Office, audio, video, images  
**FR-050:** The system SHALL distinguish between audio-only and video formats  
**FR-051:** The system SHALL classify files into processing categories: MarkItDown, Audio-Only, Video, Direct Text  
**FR-052:** The system SHALL assign confidence scores to detection results  
**FR-053:** The system SHALL provide processing hints for downstream nodes  
**FR-054:** The system SHALL identify files containing embedded images for parallel processing  
**FR-055:** The system SHALL validate session correlation data integrity  

**Supported Audio-Only Formats:** MP3, WAV, FLAC, AAC, OGG, WMA, M4A  
**Supported Video Formats:** MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPG, MPEG, 3GP, OGV  

#### 3.4.2 Enhanced Format Processing Switch (Node 5) - UPDATED
**FR-056:** The system SHALL route files to appropriate format converters  
**FR-057:** The system SHALL implement fallback processing for unknown formats  
**FR-058:** The system SHALL support parallel processing paths: Text Extraction + Image Extraction  
**FR-059:** The system SHALL initiate session-based tracking for multi-path processing  
**FR-060:** The system SHALL distribute session context to all parallel processing nodes  

#### 3.4.3 Parallel Text Processing (Node 5a) - UPDATED
**FR-061:** The system SHALL convert documents to clean markdown using MarkItDown MCP  
**FR-062:** The system SHALL preserve document structure and formatting  
**FR-063:** The system SHALL handle conversion timeouts and errors  
**FR-064:** The system SHALL maintain session ID correlation throughout text processing  
**FR-065:** The system SHALL preserve placeholder markers for image integration  

#### 3.4.4 Parallel Image Extraction and Analysis (Node 5a-img) - NEW
**FR-066:** The system SHALL extract embedded images from documents before format conversion  
**FR-067:** The system SHALL maintain image-to-content positioning relationships using page/section metadata  
**FR-068:** The system SHALL analyze extracted images using Hyperbolic vision AI in parallel with text processing  
**FR-069:** The system SHALL preserve original image quality and metadata  
**FR-070:** The system SHALL correlate images with session ID and source document context  
**FR-071:** The system SHALL support image extraction from PDF, DOCX, PPTX, XLSX formats  
**FR-072:** The system SHALL filter out decorative images and focus on educational content  
**FR-073:** The system SHALL generate timestamped descriptions with document positioning  

#### 3.4.5 Audio-Only Transcription (Node 5b) - UPDATED
**FR-074:** The system SHALL transcribe pure audio files using Soniox API  
**FR-075:** The system SHALL enable speaker diarization for multi-speaker audio content  
**FR-076:** The system SHALL support automatic language detection  
**FR-077:** The system SHALL handle large audio files up to 300MB  
**FR-078:** The system SHALL process only files detected as audio-only formats  
**FR-079:** The system SHALL maintain session correlation throughout audio transcription  
**FR-080:** The system SHALL preserve audio metadata and processing context  
**FR-081:** The system SHALL integrate transcription results with session tracking  

#### 3.4.6 Comprehensive Video Processing (Node 5d) - UPDATED
**FR-082:** The system SHALL process video files with both audio transcription and vision analysis  
**FR-083:** The system SHALL extract video frames at configurable intervals  
**FR-084:** The system SHALL analyze frames using Hyperbolic vision AI for educational content  
**FR-085:** The system SHALL identify diagrams, charts, flowcharts, slides, code, and whiteboard content  
**FR-086:** The system SHALL filter out non-educational frames (speaker-only, low-contrast)  
**FR-087:** The system SHALL combine audio transcription with timestamped visual descriptions  
**FR-088:** The system SHALL support all major video formats  
**FR-089:** The system SHALL provide unified output compatible with downstream processing  
**FR-090:** The system SHALL maintain session correlation between audio and visual processing paths  
**FR-091:** The system SHALL synchronize completion of both transcription and frame analysis  
**FR-092:** The system SHALL merge video content using timestamp-based correlation  
**FR-093:** The system SHALL preserve video metadata through parallel processing  

#### 3.4.7 Direct Text Processing (Node 5c)
**FR-094:** The system SHALL process plain text files without conversion  
**FR-095:** The system SHALL decode base64 encoded text content  
**FR-096:** The system SHALL handle various text encodings (UTF-8, ASCII)  
**FR-097:** The system SHALL maintain session correlation for text processing  

### 3.5 Enhanced Content Processing and Storage

#### 3.5.1 Enhanced Content Merging with Session Validation (Node 6) - UPDATED
**FR-098:** The system SHALL merge all processing paths into unified stream using session correlation  
**FR-099:** The system SHALL verify both processing paths completed for the same session  
**FR-100:** The system SHALL correlate images with their document context using position metadata  
**FR-101:** The system SHALL integrate image descriptions into appropriate content sections  
**FR-102:** The system SHALL reject incomplete processing sessions and trigger retry logic  
**FR-103:** The system SHALL preserve original metadata through merge process  
**FR-104:** The system SHALL combine audio, visual, and text content from all processing paths  
**FR-105:** The system SHALL log correlation failures for debugging and audit purposes  
**FR-106:** The system SHALL validate session data integrity before proceeding  

#### 3.5.2 LlamaIndex + LangExtract Processing (Node 7)
**FR-107:** The system SHALL chunk content using configurable chunk sizes (1000 chars, 200 overlap)  
**FR-108:** The system SHALL generate embeddings using text-embedding-3-small model  
**FR-109:** The system SHALL extract keywords, entities, topics, and questions  
**FR-110:** The system SHALL generate content summaries  
**FR-111:** The system SHALL respect content boundaries (paragraphs, sections, tables)  
**FR-112:** The system SHALL perform structured data extraction with source grounding using LangExtract  
**FR-113:** The system SHALL extract frameworks, processes, action items, and key concepts  
**FR-114:** The system SHALL provide document context for enhanced extraction  
**FR-115:** The system SHALL preserve session correlation through processing  

#### 3.5.3 Enhanced Pinecone Vector Storage (Node 8a)
**FR-116:** The system SHALL store vectors in Pinecone immediately after processing  
**FR-117:** The system SHALL use "course_vectors" namespace for organization  
**FR-118:** The system SHALL batch vector uploads (100 vectors per batch)  
**FR-119:** The system SHALL implement retry logic for storage failures  
**FR-120:** The system SHALL include visual content metadata in vector storage  
**FR-121:** The system SHALL store timestamped visual descriptions as searchable metadata  
**FR-122:** The system SHALL maintain session correlation in vector metadata  

#### 3.5.4 Response Processing (Node 8b)
**FR-123:** The system SHALL process combined responses into structured format  
**FR-124:** The system SHALL extract learning objectives from content  
**FR-125:** The system SHALL identify frameworks and business processes  
**FR-126:** The system SHALL extract timestamps from video content including visual elements  
**FR-127:** The system SHALL map content to department applications  
**FR-128:** The system SHALL preserve session correlation through response processing  

### 3.6 Analysis and Intelligence Generation

#### 3.6.1 Intelligent Analysis Router (Node 9)
**FR-129:** The system SHALL determine analysis complexity based on content characteristics  
**FR-130:** The system SHALL route to quick (1 agent), strategic (2 agents), or comprehensive (5 agents) analysis  
**FR-131:** The system SHALL calculate importance scores using multiple factors including visual content  
**FR-132:** The system SHALL estimate processing duration for each analysis type  

#### 3.6.2 Multi-Agent Analysis (Node 10)
**FR-133:** The system SHALL execute CrewAI analysis using appropriate number of agents  
**FR-134:** The system SHALL provide analysis objectives based on complexity level  
**FR-135:** The system SHALL generate organizational intelligence recommendations  
**FR-136:** The system SHALL implement timeout handling for long-running analysis  
**FR-137:** The system SHALL consider visual content in strategic analysis  

### 3.7 Documentation and Output Generation

#### 3.7.1 Enhanced Results Processing (Node 11)
**FR-138:** The system SHALL create comprehensive course analysis with multiple sections  
**FR-139:** The system SHALL generate agent recommendations with business justification  
**FR-140:** The system SHALL create implementation roadmaps with timelines  
**FR-141:** The system SHALL provide reference guides with timestamps for both audio and visual content  
**FR-142:** The system SHALL include visual content timeline in course documentation  

#### 3.7.2 Documentation Generation (Node 12)
**FR-143:** The system SHALL generate markdown analysis reports including visual content  
**FR-144:** The system SHALL create executive summaries  
**FR-145:** The system SHALL export JSON data for programmatic access  
**FR-146:** The system SHALL generate agent specification files  
**FR-147:** The system SHALL include visual learning elements in documentation  

#### 3.7.3 Backblaze Upload (Node 13a)
**FR-148:** The system SHALL upload documentation to organized folder structure  
**FR-149:** The system SHALL use `processed/[Course]/[Module]/` path structure  
**FR-150:** The system SHALL include date stamps in filenames  
**FR-151:** The system SHALL handle upload failures with retry logic  

### 3.8 Completion and Audit

#### 3.8.1 Final Results Processing (Node 13c)
**FR-152:** The system SHALL create final deliverable packages  
**FR-153:** The system SHALL generate completion audit records  
**FR-154:** The system SHALL provide next steps for manual implementation (V1)  
**FR-155:** The system SHALL prepare data for notification system  

#### 3.8.2 Audit Logging (Node 14)
**FR-156:** The system SHALL log complete processing audit trail to Airtable  
**FR-157:** The system SHALL record processing success/failure status  
**FR-158:** The system SHALL track agent recommendation counts  
**FR-159:** The system SHALL maintain workflow version information  
**FR-160:** The system SHALL log vision processing statistics  
**FR-161:** The system SHALL record session correlation success rates  

#### 3.8.3 Notification System (Node 15)
**FR-162:** The system SHALL send completion notifications  
**FR-163:** The system SHALL include processing summary and recommendations count  
**FR-164:** The system SHALL provide links to generated documentation  
**FR-165:** The system SHALL include visual content processing statistics  

---

## Universal Session Tracking Requirements

### **All Processing Nodes Must Implement:**
**FR-166:** Every processing node SHALL accept and forward session correlation data  
**FR-167:** Every processing node SHALL validate session ID integrity before processing  
**FR-168:** Every processing node SHALL append processing metadata to session context  
**FR-169:** Every processing node SHALL handle session correlation failures gracefully  
**FR-170:** Every processing node SHALL preserve original source metadata through processing  

### **Session Data Flow Validation:**
```
Input (Node 1a/1b) → Generate Session ID
↓
Content Classification (Node 2) → Validate & Forward Session
↓
Route Switch (Node 3) → Distribute Session to Processing Paths
↓
Processing Nodes (3a,3b,3c,3d,5a,5a-img,5b,5d) → Maintain Session Correlation
↓
Content Merge (Node 6) → Validate All Session Paths Complete
↓
Continue Processing → Session Context Preserved Through Completion
```

## Session Tracking Data Structure

### Processing Context Schema:
```json
{
  "sessionId": "proc_YYYYMMDD_HHMMSS_uuid",
  "sourceFile": "filename.ext",
  "sourceType": "document|article|video|audio",
  "courseName": "Course Name",
  "moduleNumber": "Module ID",
  "processingPaths": {
    "textExtraction": "pending|completed|failed",
    "imageExtraction": "pending|completed|failed|not_applicable",
    "audioTranscription": "pending|completed|failed|not_applicable",
    "videoAnalysis": "pending|completed|failed|not_applicable"
  },
  "correlationData": {
    "textContent": "markdown content",
    "extractedImages": [
      {
        "imageId": "img_001",
        "pageNumber": 2,
        "sectionId": "section_3",
        "position": "after_paragraph_5",
        "description": "AI-generated visual description",
        "timestamp": "2025-09-16T14:30:00Z",
        "educationalRelevance": "high|medium|low"
      }
    ],
    "visualTimeline": [...],
    "audioTranscript": "..."
  },
  "metadata": {
    "totalImages": 5,
    "educationalImagesDetected": 3,
    "processingDuration": "00:12:34",
    "qualityScore": 0.87
  }
}
```

---

## 4. Observability and Testing Requirements

### 4.1 Arize Phoenix Observability Integration

#### 4.1.1 Phoenix Deployment and Configuration
**OR-001:** The system SHALL deploy Arize Phoenix embedded within the LlamaIndex service  
**OR-002:** The system SHALL expose Phoenix UI on port 6006 alongside LlamaIndex API on port 8000  
**OR-003:** The system SHALL initialize Phoenix with project name "ai-empire-processing"  
**OR-004:** The system SHALL configure Phoenix to capture all LLM calls and processing workflows  

#### 4.1.2 Observability Instrumentation
**OR-005:** The system SHALL instrument session management operations with @weave.op() decorators  
**OR-006:** The system SHALL trace parallel processing workflows with detailed span information  
**OR-007:** The system SHALL capture session correlation validation events in Phoenix traces  
**OR-008:** The system SHALL track Hyperbolic API calls with performance and cost metrics  
**OR-009:** The system SHALL monitor document processing pipelines with success/failure tracking  
**OR-010:** The system SHALL instrument CrewAI agent interactions for cross-service tracing  

#### 4.1.3 Performance and Debugging Visibility
**OR-011:** The system SHALL provide visual workflow traces showing session correlation flow  
**OR-012:** The system SHALL track processing bottlenecks and performance degradation  
**OR-013:** The system SHALL capture error traces with full context for debugging  
**OR-014:** The system SHALL monitor parallel processing synchronization success rates  
**OR-015:** The system SHALL provide real-time dashboards for operational monitoring  

### 4.2 DeepEval Testing Framework Integration

#### 4.2.1 DeepEval Framework Setup
**TR-001:** The system SHALL integrate DeepEval framework for systematic LLM evaluation  
**TR-002:** The system SHALL configure DeepEval with Confident AI cloud platform integration  
**TR-003:** The system SHALL implement test cases for session correlation validation  
**TR-004:** The system SHALL create evaluation metrics for parallel processing accuracy  
**TR-005:** The system SHALL establish baseline metrics for regression testing  

#### 4.2.2 Core Testing Requirements
**TR-006:** The system SHALL implement unit tests for session manager operations  
**TR-007:** The system SHALL test parallel processing path completion validation  
**TR-008:** The system SHALL evaluate image extraction accuracy using custom metrics  
**TR-009:** The system SHALL test session correlation integrity under failure conditions  
**TR-010:** The system SHALL validate merge logic with synthetic and real data  
**TR-011:** The system SHALL test vision analysis quality with ground truth datasets  

#### 4.2.3 Automated Testing Pipeline
**TR-012:** The system SHALL run DeepEval tests as part of CI/CD pipeline  
**TR-013:** The system SHALL generate test reports for processing quality assessment  
**TR-014:** The system SHALL implement regression testing for session correlation logic  
**TR-015:** The system SHALL perform red team testing for edge case handling  
**TR-016:** The system SHALL validate educational content detection accuracy  

#### 4.2.4 Test Coverage Requirements
**TR-017:** The system SHALL achieve 90% test coverage for session management functions  
**TR-018:** The system SHALL test all parallel processing failure scenarios  
**TR-019:** The system SHALL validate image-to-text correlation accuracy above 95%  
**TR-020:** The system SHALL test processing pipeline with various document types  
**TR-021:** The system SHALL evaluate agent recommendation quality using G-Eval metrics  

---

## 5. Non-Functional Requirements

### 5.1 Performance Requirements

**NFR-001:** The system SHALL process files up to 300MB within 30 minutes  
**NFR-002:** The system SHALL handle concurrent processing of up to 5 files  
**NFR-003:** The system SHALL maintain 99% uptime during business hours  
**NFR-004:** The system SHALL complete vector storage within 2 minutes of processing  
**NFR-005:** Video processing with vision analysis SHALL complete within 45 minutes for 1-hour videos  
**NFR-006:** Audio-only processing SHALL complete within 15 minutes for 1-hour files  
**NFR-007:** Parallel image processing SHALL complete within 10 minutes for documents with 20+ images  
**NFR-008:** Phoenix observability overhead SHALL not exceed 5% of total processing time  
**NFR-009:** DeepEval test execution SHALL complete within 30 seconds per test case  

### 5.2 Scalability Requirements

**NFR-010:** The system SHALL support processing 100+ files per day  
**NFR-011:** The system SHALL handle vector storage of 10,000+ chunks per file  
**NFR-012:** The system SHALL scale analysis complexity based on content characteristics  
**NFR-013:** The system SHALL support up to 20 video frames per file for vision analysis  
**NFR-014:** The system SHALL handle up to 50 images per document for parallel processing  
**NFR-015:** Phoenix SHALL handle 1000+ trace spans per processing session without degradation  

### 5.3 Reliability Requirements

**NFR-016:** The system SHALL implement retry logic for all external API calls  
**NFR-017:** The system SHALL gracefully handle service timeouts and failures  
**NFR-018:** The system SHALL preserve data integrity through processing failures  
**NFR-019:** The system SHALL maintain audit trail for all processing activities  
**NFR-020:** Vision processing failures SHALL NOT prevent audio transcription completion  
**NFR-021:** Image extraction failures SHALL NOT prevent text processing completion  
**NFR-022:** Session correlation validation SHALL achieve 99.9% accuracy  
**NFR-023:** Phoenix observability SHALL maintain 99.9% availability  
**NFR-024:** DeepEval tests SHALL achieve 100% reliability for core validation scenarios  

### 5.4 Security Requirements

**NFR-025:** The system SHALL secure all API communications using HTTPS  
**NFR-026:** The system SHALL authenticate all external service connections  
**NFR-027:** The system SHALL not store sensitive content in workflow memory  
**NFR-028:** The system SHALL implement access controls for generated documentation  
**NFR-029:** Temporary video files SHALL be automatically deleted after processing  
**NFR-030:** Session correlation data SHALL be encrypted during transmission  
**NFR-031:** Phoenix traces SHALL not expose sensitive document content  
**NFR-032:** DeepEval test data SHALL be sanitized and anonymized  

### 5.5 Usability Requirements

**NFR-033:** The system SHALL provide clear error messages for processing failures  
**NFR-034:** The system SHALL generate human-readable documentation and reports  
**NFR-035:** The system SHALL include progress indicators for long-running processes  
**NFR-036:** Visual content descriptions SHALL be clearly timestamped and contextualized  
**NFR-037:** Session correlation failures SHALL provide detailed debugging information  
**NFR-038:** Phoenix dashboards SHALL be accessible via intuitive web interface  
**NFR-039:** DeepEval test results SHALL provide actionable improvement recommendations  

---

## 6. System Interfaces

### 6.1 External Systems Integration

#### 6.1.1 n8n Workflow Platform
- **Interface:** HTTP REST APIs and webhook endpoints
- **Purpose:** Workflow orchestration and execution
- **Data Exchange:** JSON payloads with processing metadata and session correlation

#### 6.1.2 LlamaIndex Service Enhanced with Phoenix
- **Interface:** HTTP REST API (https://jb-llamaindex.onrender.com)
- **Purpose:** Content processing, chunking, embedding generation, vision analysis, and observability
- **Data Exchange:** JSON with content, metadata, processing options, and session context
- **Version:** 2.5.0 with Phoenix observability and session correlation capabilities
- **Phoenix UI:** Available at https://jb-llamaindex.onrender.com:6006

#### 6.1.3 CrewAI Service with Prometheus Metrics
- **Interface:** HTTP REST API (https://jb-crewai.onrender.com)
- **Purpose:** Multi-agent organizational intelligence analysis
- **Data Exchange:** JSON with analysis type, content, requirements, and session context
- **Monitoring:** Prometheus metrics at `/metrics` endpoint

#### 6.1.4 Soniox Speech-to-Text API
- **Interface:** HTTP REST API (https://api.soniox.com/v1/transcribe)
- **Purpose:** Audio transcription with speaker diarization
- **Data Exchange:** JSON with audio data, configuration parameters, and session tracking

#### 6.1.5 Hyperbolic Vision AI
- **Interface:** HTTP REST API (https://api.hyperbolic.xyz/v1)
- **Purpose:** Video frame and document image analysis using Llama-3.2-11B-Vision-Instruct
- **Data Exchange:** JSON with image data, vision analysis prompts, and session correlation

#### 6.1.6 Backblaze B2 Cloud Storage
- **Interface:** B2 REST API
- **Purpose:** File storage, retrieval, and monitoring
- **Data Exchange:** Binary file content with metadata headers and session tracking

#### 6.1.7 Pinecone Vector Database
- **Interface:** HTTP REST API via LlamaIndex service
- **Purpose:** Vector storage and retrieval for semantic search
- **Data Exchange:** Vector embeddings with metadata including visual content and session correlation

#### 6.1.8 Airtable Database
- **Interface:** HTTP REST API (https://api.airtable.com/v0)
- **Purpose:** Audit logging and processing statistics
- **Data Exchange:** JSON records with processing metadata and session correlation data

#### 6.1.9 DeepEval Framework Integration
- **Interface:** Python library with Confident AI cloud platform
- **Purpose:** Systematic LLM evaluation and testing
- **Data Exchange:** Test cases, evaluation results, and performance metrics

### 6.2 Data Formats

#### 6.2.1 Supported Input Formats
- **Documents:** PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS, HTML, RTF, ODT, ODP, ODS
- **Images:** JPG, PNG, GIF, BMP, TIFF, WEBP, SVG, HEIC, HEIF
- **Audio-Only:** MP3, WAV, FLAC, AAC, OGG, WMA, M4A
- **Video:** MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPG, MPEG, 3GP, OGV
- **Text:** TXT, MD, CSV, JSON, XML, YAML
- **URLs:** YouTube, Google Workspace (Docs, Sheets, Slides), Web Articles

#### 6.2.2 Output Formats
- **Documentation:** Markdown (.md) with visual content timelines, JSON (.json)
- **Reports:** Structured markdown with executive summaries and comprehensive visual analysis
- **Specifications:** JSON agent specification files with session metadata
- **Audit:** JSON audit records in Airtable format with session correlation tracking
- **Observability:** Phoenix traces and spans in OpenTelemetry format
- **Testing:** DeepEval test reports and evaluation metrics

---

## 7. Business Rules

**BR-001:** Files must be processed in order of upload/detection timestamp  
**BR-002:** Vector storage must complete before analysis can proceed  
**BR-003:** Agent recommendations are for manual implementation in V1 (no automated deployment)  
**BR-004:** Course documentation must be stored in organized folder hierarchy  
**BR-005:** All processing activities must be logged for audit compliance  
**BR-006:** Processing failures must not result in data loss  
**BR-007:** Generated documentation must include processing metadata and timestamps  
**BR-008:** Audio-only files SHALL route to Soniox transcription only  
**BR-009:** Video files SHALL receive comprehensive processing (audio + vision)  
**BR-010:** Visual content analysis SHALL be included in vector storage metadata  
**BR-011:** Vision processing failures SHALL NOT prevent transcript completion  
**BR-012:** All parallel processing paths must complete successfully before content merging  
**BR-013:** Session correlation data must be validated before proceeding to LlamaIndex processing  
**BR-014:** Image extraction failures SHALL NOT prevent text processing completion  
**BR-015:** Processing sessions must maintain data integrity across all parallel paths  
**BR-016:** Incomplete sessions must be logged and retried with exponential backoff  
**BR-017:** Session correlation must be preserved through all workflow stages  
**BR-018:** Phoenix observability must not interfere with core processing functions  
**BR-019:** DeepEval tests must pass before deploying processing logic changes  
**BR-020:** Observability data must be retained for minimum 30 days for debugging  

---

## 8. Technical Constraints

**TC-001:** The system must operate within Render.com service limitations  
**TC-002:** Node.js execution environment for n8n workflow processing  
**TC-003:** HTTP request timeouts limited to 45 minutes maximum for video processing  
**TC-004:** File size limitations based on service memory constraints  
**TC-005:** API rate limits must be respected for all external services  
**TC-006:** Vector storage limited by Pinecone index capacity and quotas  
**TC-007:** Video frame extraction limited to maximum 20 frames per video  
**TC-008:** Temporary video files must be stored in ephemeral storage only  
**TC-009:** Session tracking data must not exceed 10MB per processing session  
**TC-010:** Parallel processing paths must complete within 45 minutes total  
**TC-011:** Image extraction must respect document security permissions  
**TC-012:** Session correlation must handle up to 50 images per document  
**TC-013:** Phoenix observability must operate within existing service resource limits  
**TC-014:** DeepEval tests must execute within CI/CD time constraints  

---

## 9. Assumptions and Dependencies

### 9.1 Assumptions
- External APIs (LlamaIndex, CrewAI, Soniox, Hyperbolic) maintain stable interfaces
- Backblaze B2 storage provides reliable file access
- n8n platform continues to support required node types and features
- Course content follows generally accepted educational formats
- Video content contains educational material suitable for frame analysis
- Document formats support embedded image extraction
- Session correlation data remains accessible throughout processing
- Phoenix observability maintains minimal performance overhead
- DeepEval framework continues compatibility with current LLM models

### 9.2 Dependencies
- **MarkItDown MCP:** Document format conversion capabilities
- **OpenAI API:** Embedding generation for vector storage
- **Hyperbolic.ai:** LLM processing for analysis tasks and vision processing
- **Network Connectivity:** Stable internet connection for API communications
- **Storage Quotas:** Sufficient Backblaze and Pinecone storage capacity
- **ffmpeg:** Video processing and frame extraction capabilities
- **OpenCV/PIL:** Image processing libraries for frame analysis
- **Document Processing Libraries:** python-docx, PyPDF2, python-pptx for image extraction
- **Arize Phoenix:** Open-source observability platform
- **DeepEval Framework:** LLM evaluation and testing capabilities

---

## 10. Acceptance Criteria

### 10.1 Functional Acceptance
- ✅ Successfully processes all supported file formats including audio and video
- ✅ Generates comprehensive course documentation with visual content timelines
- ✅ Creates actionable agent recommendations
- ✅ Stores vectors in Pinecone for future retrieval including visual metadata
- ✅ Maintains complete audit trail with session correlation
- ✅ Provides executive-ready reports with multimedia analysis
- ✅ Extracts and analyzes educational visual content from videos
- ✅ Properly routes audio-only vs video files to appropriate processors
- ✅ Successfully processes text and images in parallel while maintaining correlation
- ✅ Properly merges content from multiple processing paths using session tracking
- ✅ Maintains document structure with integrated visual content descriptions
- ✅ Handles partial processing failures without data corruption

### 10.2 Performance Acceptance  
- ✅ Processes typical course files (10-50MB) within 15 minutes
- ✅ Processes video files with vision analysis within 45 minutes
- ✅ Handles concurrent processing without degradation
- ✅ Maintains 99% successful processing rate
- ✅ Completes vector storage within defined timeframes
- ✅ Parallel image processing completes within 10 minutes for image-rich documents

### 10.3 Quality Acceptance
- ✅ Generated documentation is comprehensive and actionable
- ✅ Agent recommendations include business justification
- ✅ Processing errors are handled gracefully
- ✅ Audit trail provides complete processing history
- ✅ Visual content descriptions are accurate and educationally relevant
- ✅ Audio and visual content are properly synchronized in output
- ✅ Images are correctly associated with their document context and positioning
- ✅ Session correlation prevents mixing content from different source files
- ✅ Merge validation ensures complete processing before proceeding

### 10.4 Data Integrity Acceptance
- ✅ Session correlation maintains 99.9% accuracy across all processing paths
- ✅ Image-to-text relationships are preserved through parallel processing
- ✅ Content from different sources never gets mixed or corrupted
- ✅ Visual elements maintain proper positioning and context relationships
- ✅ Processing failures in one path do not corrupt other parallel paths

### 10.5 Observability Acceptance
- ✅ Phoenix captures all critical processing workflows with minimal overhead
- ✅ Visual traces clearly show session correlation flow and bottlenecks
- ✅ Real-time dashboards provide actionable operational insights
- ✅ Error traces contain sufficient context for rapid debugging
- ✅ Performance metrics enable proactive optimization

### 10.6 Testing Acceptance
- ✅ DeepEval test suite achieves 90% coverage of session management functions
- ✅ All parallel processing scenarios pass automated testing
- ✅ Image extraction accuracy exceeds 95% in evaluation metrics
- ✅ Session correlation integrity tests pass under all failure conditions
- ✅ Regression tests prevent quality degradation during system updates

---

## 11. Future Enhancements (V3 Scope)

### 11.1 Planned Features
- **Archon Integration:** Automated agent deployment and testing
- **Real-time Monitoring:** Agent performance tracking and optimization
- **Advanced Analytics:** Predictive analysis and ROI measurement
- **Approval Workflows:** Executive decision gates and approval processes
- **Interactive Visual Elements:** Clickable timestamps and visual navigation
- **Advanced Session Analytics:** Processing pattern analysis and optimization
- **Grafana Dashboard Integration:** Infrastructure monitoring with existing Prometheus metrics

### 11.2 Technology Upgrades
- **Enhanced AI Models:** Integration with latest LLM and vision capabilities
- **Advanced Processing:** Real-time streaming and batch processing
- **Expanded Formats:** Additional file type support and conversion
- **Integration APIs:** RESTful APIs for third-party integrations
- **Multi-modal Search:** Search by both text and visual content
- **Distributed Session Management:** Advanced correlation across multiple processing clusters
- **Enterprise Phoenix Features:** Upgrade to Arize AX for enhanced capabilities

---

## 12. Glossary

**Agent:** AI-powered automation system designed to perform specific organizational tasks  
**Chunking:** Process of dividing content into smaller, semantically meaningful segments  
**DeepEval:** Open-source LLM evaluation framework for systematic testing and validation  
**Embedding:** Vector representation of text content for semantic similarity matching  
**Frame Extraction:** Process of extracting individual frames from video content for analysis  
**LangExtract:** Structured data extraction service using LLM capabilities  
**MarkItDown MCP:** Microsoft's format conversion tool for document processing  
**Parallel Processing:** Simultaneous execution of multiple processing paths with correlation tracking  
**Phoenix (Arize):** Open-source observability platform for LLM applications and workflows  
**Pinecone:** Vector database service for storing and querying embeddings  
**Session Correlation:** Data integrity mechanism ensuring content from same source stays together  
**Soniox:** Advanced speech-to-text service with speaker diarization  
**Vector Storage:** Database system optimized for similarity search using vector embeddings  
**Vision Analysis:** AI-powered analysis of visual content in images and video frames  
**Hyperbolic Vision AI:** Llama-3.2-11B-Vision-Instruct model for educational content analysis  

---

**Document Control:**  
- **Author:** AI Empire Development Team  
- **Reviewer:** Product Management  
- **Approval:** Technical Architecture Committee  
- **Distribution:** Development Team, QA Team, Business Stakeholders  
- **Next Review Date:** December 15, 2025  

**Version 2.5 Change Summary:**
- Added comprehensive Arize Phoenix observability integration
- Implemented DeepEval testing framework for systematic validation
- Enhanced session correlation requirements across all processing nodes
- Updated performance and reliability requirements for production readiness
- Added observability and testing requirements sections
- Expanded acceptance criteria to include observability and testing validation
- Updated system interfaces to include Phoenix and DeepEval integration
- Enhanced business rules and technical constraints for observability and testing