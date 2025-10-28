# 1. Introduction

## 1.1 Purpose

This Software Requirements Specification (SRS) document provides a complete description of all functions and specifications for the AI Empire File Processing System, version 7.0 Advanced RAG Production Edition. This document is intended for all project stakeholders including developers, system architects, quality assurance teams, project managers, and business stakeholders involved in the development, deployment, and maintenance of the AI Empire intelligent document processing and retrieval-augmented generation platform.

Version 7.0 represents a production-grade RAG architecture with hybrid search, knowledge graphs, and advanced observability, leveraging Claude Sonnet 4.5 API for core intelligence while maintaining the Mac Studio M3 Ultra for development and mem-agent MCP hosting.

### Document Objectives

- **Define** all functional and non-functional requirements for AI Empire v7.0
- **Establish** the basis for agreement between customers and contractors
- **Reduce** development effort and project risks through clear specification
- **Provide** a basis for estimating costs and schedules
- **Facilitate** transfer to new personnel or teams
- **Serve** as a basis for future enhancements
- **Document** the production-grade RAG architecture with hybrid search and knowledge graphs
- **Specify** 4-method hybrid search with RRF fusion and Cohere reranking
- **Detail** sub-workflow architecture patterns for modular n8n implementations
- **Outline** asynchronous processing patterns with exponential backoff
- **Define** complete document lifecycle management with versioning and cascade deletion
- **Ensure** SOC 2 Type II compliance for all cloud service vendors
- **Demonstrate** 30-50% search quality improvement over traditional RAG
- **Enable** <500ms query latency with 60-80% semantic cache hit rate

## 1.2 Scope

### Product Name
**AI Empire File Processing System**

### Product Version
**7.0 - Advanced RAG Production Edition**

### Product Description

The AI Empire File Processing System v7.0 is a production-grade RAG platform that processes diverse document formats, multimedia content, and web resources using Claude Sonnet 4.5 API with hybrid search, knowledge graphs, and full observability. The system combines 4-method hybrid search (dense, sparse, ILIKE, fuzzy) with Cohere reranking, achieving 30-50% better relevance than traditional RAG. It leverages modular sub-workflows for multimodal processing, asynchronous patterns for long-running operations, and comprehensive lifecycle management for documents.

### Core Capabilities

#### Version 7.0 NEW - Production-Grade RAG Features
- **Hybrid Search** - 4-method search (dense, sparse, ILIKE, fuzzy) with RRF fusion
- **Cohere Reranking** - 20-30% better result ordering with v3.5 model
- **LightRAG Knowledge Graph** - Entity relationships and graph traversal
- **Sub-Workflow Architecture** - Modular n8n workflows for multimodal, KG, memory
- **Asynchronous Processing** - Wait/poll patterns with exponential backoff
- **Document Lifecycle** - Complete CRUD with versioning, cascade deletion, audit trails
- **Hash-Based Deduplication** - SHA-256 content hashing prevents redundant processing
- **Error Handling & Retry** - Configurable retry with retryable vs non-retryable classification
- **Semantic Caching** - 60-80% hit rate, <50ms cached queries via Redis
- **mem-agent MCP** - Persistent conversation memory (<500ms retrieval)
- **Multi-Modal Support** - Images (Claude Vision), audio (Soniox), structured data
- **Dynamic Metadata** - Flexible schema management with metadata_fields table
- **500+ documents/day** processing capacity with batch optimization
- **<500ms query latency** with semantic caching
- **30-50% search quality improvement** over traditional RAG

#### From Version 2.9-4.0 (All Capabilities Maintained)
- Unified document processing supporting 40+ file formats via MarkItDown MCP
- Intelligent PDF routing with OCR fallback for complex documents
- YouTube content extraction with transcript and frame analysis
- Audio/video transcription with speaker diarization via Soniox
- Hash-based change detection for efficient reprocessing
- Contextual embeddings for enhanced retrieval accuracy
- Dynamic metadata enrichment using AI classification
- Hybrid search with Cohere reranking for optimal relevance
- Vector storage with Pinecone and graph storage with LightRAG API
- SQL querying capabilities for tabular data analysis
- Multi-agent organizational intelligence analysis via CrewAI
- Web scraping capabilities via Firecrawl
- Dual storage architecture with SQL performance layer
- Parallel processing of up to 5 documents simultaneously
- Semantic chunking with quality scoring
- Three-tier caching architecture (Memory, Redis, Disk)
- Fast track processing for simple documents (70% faster)
- Real-time API cost tracking and optimization
- Comprehensive backup to Backblaze B2
- Disaster recovery with 4-hour RTO and 1-hour RPO
- SOC 2 Type II compliant cloud services only

### System Objectives

1. **Achieve** 30-50% better search quality through hybrid search and reranking
2. **Enable** <500ms query latency with 60-80% semantic cache hit rate
3. **Process** 500+ documents daily with hash-based deduplication
4. **Maintain** <500ms memory retrieval through mem-agent MCP
5. **Implement** modular sub-workflows for multimodal, knowledge graph, and memory operations
6. **Support** asynchronous processing with wait/poll patterns and exponential backoff
7. **Provide** complete document lifecycle management with versioning and cascade deletion
8. **Ensure** robust error handling with configurable retry logic
9. **Enable** 4-method hybrid search with RRF fusion
10. **Integrate** LightRAG knowledge graphs for entity relationships
11. **Deliver** multi-modal support (text, images, audio, structured data)
12. **Maintain** 99.9% uptime through production-grade infrastructure
13. **Support** 1000+ queries/day with semantic caching
14. **Provide** full observability with Prometheus, Grafana, OpenTelemetry
15. **Ensure** SOC 2 Type II compliance for all cloud services
16. **Optimize** costs to $375-550/month for production features
17. **Enable** dynamic metadata management with flexible schemas
18. **Implement** batch processing with splitInBatches patterns
19. **Provide** Supabase Edge Functions for HTTP API access
20. **Execute** comprehensive testing and validation for all workflows
21. **Maintain** Infrastructure as Code for automated deployment
22. **Ensure** all cloud vendors maintain SOC 2 Type II compliance
23. **Deliver** 14-20 month ROI with 5-year savings of $10,000-15,000

## 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|------|------------|
| **Mac Studio** | Apple Mac Studio M3 Ultra with 96GB unified memory, 32-core Neural Engine, 800 GB/s bandwidth |
| **Llama 3.3 70B** | Meta's 70-billion parameter LLM, GPT-4 quality, runs locally at 32 tok/s |
| **Local-First** | Architecture prioritizing on-device processing (98% local inference) |
| **Neural Engine** | 32-core ML accelerator in M3 Ultra for optimized AI operations |
| **Ollama** | Model distribution and management platform for local LLM deployment |
| **HuggingFace** | Model repository and community platform, backup source for models |
| **GitHub LFS** | Large File Storage for versioned model weight backups |
| **IaC** | Infrastructure as Code - automated deployment and recovery scripts |
| **SOC 2 Type II** | Security compliance standard required for all cloud vendors |
| **RAG** | Retrieval-Augmented Generation - AI technique combining retrieval with generation |
| **MCP** | Model Context Protocol - Protocol for AI model interaction and memory management |
| **mem-agent** | 4B parameter memory management model running locally on Mac Studio |
| **Open WebUI** | Local web interface for interacting with on-device LLMs |
| **LiteLLM** | API compatibility layer for local models |
| **GGUF** | Model format for efficient local LLM storage and inference |
| **Qwen2.5-VL** | 7B parameter vision-language model for image analysis |
| **nomic-embed** | Local embedding model for semantic vector generation |
| **BGE-reranker** | Local model for search result reranking |
| **Zero-Knowledge** | Encryption where service provider cannot decrypt user data |
| **Tailscale** | VPN for secure remote access to Mac Studio |
| **tok/s** | Tokens per second - LLM inference speed metric |
| **FileVault** | macOS full-disk encryption system |
| **B2** | Backblaze B2 cloud storage for encrypted backups |
| **n8n** | Workflow automation platform (minimal cloud use) |
| **CrewAI** | Multi-agent AI collaboration framework |
| **Hyperbolic.ai** | Backup LLM provider for edge cases only ($5-10/month) |
| **RTO** | Recovery Time Objective - 4 hours for v5.0 |
| **RPO** | Recovery Point Objective - 1 hour for v5.0 |
| **API Replacement Value** | Equivalent cloud API cost for local processing (~$200-300/month) |
| **Memory Bandwidth** | 800 GB/s unified memory bandwidth in Mac Studio M3 Ultra |
| **ROI** | Return on Investment - 14-20 months payback period |

## 1.4 References

1. **IEEE Std 830-1998:** IEEE Recommended Practice for Software Requirements Specifications
2. **Apple Mac Studio Documentation:** M3 Ultra Technical Specifications
3. **Apple Neural Engine:** Machine Learning Acceleration Guide
4. **Llama 3.3 Model Card:** Meta's 70B parameter model documentation
5. **Ollama Documentation:** Local LLM serving and distribution platform guide
6. **HuggingFace Model Hub:** Community model repository and documentation
7. **GitHub LFS Documentation:** Large File Storage for model versioning
8. **Infrastructure as Code:** Best practices for automated deployment
9. **SOC 2 Type II Framework:** Security compliance requirements
10. **Open WebUI Documentation:** Local LLM interface specifications
11. **LiteLLM Documentation:** API compatibility layer guide
12. **mem-agent Documentation:** Local memory management protocol
13. **Qwen2.5-VL Documentation:** Vision-language model specifications
14. **Microsoft MarkItDown Documentation:** Universal document converter
15. **Pinecone Documentation:** Vector database best practices
16. **CrewAI Framework Guide:** Multi-agent system architecture
17. **n8n Workflow Documentation:** Automation platform guidelines
18. **Backblaze B2 API:** Zero-knowledge backup specifications
19. **Tailscale Documentation:** Secure VPN configuration
20. **FileVault Documentation:** macOS encryption guide
21. **GGUF Format Specification:** Efficient model storage format
22. **nomic-embed Documentation:** Local embedding generation
23. **BGE-reranker Documentation:** Local search optimization
24. **Hyperbolic.ai Documentation:** Backup LLM service (minimal use)
25. **Metal Performance Shaders:** Apple GPU optimization guide
26. **macOS Sequoia Documentation:** Operating system requirements
27. **Docker Desktop for Mac:** Container runtime specifications
28. **Homebrew Documentation:** Package management for macOS
29. **Disaster Recovery Best Practices:** Quarterly drill procedures
30. **Performance Benchmarking:** Cloud API comparison metrics

## 1.5 Overview

This document follows the IEEE Std 830-1998 structure and is organized as follows:

- **Section 1** (this section) provides introductory information about the SRS document
- **Section 2** presents the v5.0 Mac Studio architecture and system overview
- **Section 3** contains all specific requirements from the base platform
- **Section 4** details v3.0 performance enhancement features
- **Section 5** describes v3.1 solopreneur optimization features  
- **Section 6** specifies v4.0 unified architecture (superseded by v5.0)
- **Section 7** covers performance and scaling enhancements
- **Section 8** defines advanced video processing with Qwen2.5-VL
- **Section 9** addresses orchestrator and scheduler requirements
- **Section 10** provides Appendix A - Business Rules
- **Section 11** provides Appendix B - Technical Specifications
- **Section 12** provides Appendix C - Glossary and Additional Documentation

### Requirement Identification Convention

Each requirement is uniquely identified using the following convention:

**Core Platform Requirements:**
- **FR-XXX:** Functional Requirements
- **NFR-XXX:** Non-Functional Requirements
- **SR-XXX:** Security Requirements
- **OR-XXX:** Observability Requirements

**Version 5.0 Mac Studio Requirements:**
- **MSR-XXX:** Mac Studio Requirements
- **LLR-XXX:** Local LLM Requirements
- **MEM-XXX:** Memory Management Requirements
- **VIS-XXX:** Vision Processing Requirements
- **PRV-XXX:** Privacy Requirements
- **LOC-XXX:** Local Processing Requirements
- **BKP-XXX:** Backup Requirements
- **DRR-XXX:** Disaster Recovery Requirements
- **IaC-XXX:** Infrastructure as Code Requirements

**Previous Version Requirements (Maintained):**
- **PFR-XXX:** Performance Functional (v3.0)
- **CMR-XXX:** Cost Management (v3.1)
- **UAR-XXX:** Unified Architecture (v4.0)
- **HYB-XXX:** Hybrid Processing (v4.0)
- **VPR-XXX:** Video Processing
- **OCR-XXX:** Orchestration Requirements

**Supplementary:**
- **BR-XXX:** Business Rules
- **TC-XXX:** Technical Constraints
- **TR-XXX:** Testing Requirements
- **SOC-XXX:** SOC 2 Compliance Requirements

### Key Architecture Changes in v5.0

**From Cloud-Heavy to Local-First:**
- v4.0: Hybrid with significant cloud dependency
- v5.0: 98% local processing on Mac Studio

**From Mac Mini to Mac Studio:**
- v4.0: Mac Mini M4 with 24GB RAM
- v5.0: Mac Studio M3 Ultra with 96GB RAM, 800 GB/s bandwidth

**From API Dependence to Local Models:**
- v4.0: $50-100/month in LLM API costs
- v5.0: $5-10/month (edge cases only)

**Performance Improvements:**
- v4.0: Variable cloud latency (5-15 seconds)
- v5.0: Consistent 32 tokens/second locally (1-3 seconds end-to-end)
- 2-5x faster than typical cloud APIs

**Cost Reduction:**
- v4.0: $125-255/month operating costs
- v5.0: $100-195/month (40% reduction)
- API replacement value: $200-300/month
- ROI: 14-20 months payback
- 5-year savings: $10,000-15,000

### Document Usage Guidelines

This SRS is intended for:

1. **System Owners** - Understanding the Mac Studio investment and capabilities
2. **Privacy-Conscious Users** - Validating data sovereignty features
3. **Development Teams** - Implementation of local-first architecture
4. **System Administrators** - Mac Studio deployment and maintenance
5. **Security Teams** - Zero-knowledge encryption and SOC 2 compliance
6. **DevOps Engineers** - Infrastructure as Code automation and backup procedures
7. **Support Teams** - Troubleshooting local and minimal cloud components
8. **Business Stakeholders** - ROI analysis and cost optimization validation
9. **Compliance Officers** - SOC 2 Type II vendor verification

### Implementation Timeline

**October 14, 2025:** Mac Studio M3 Ultra delivery and deployment begins
- Day 1: Hardware setup, Ollama installation, model deployment
- Week 1: Core services, performance benchmarking
- Week 2: Integration testing, disaster recovery setup
- Week 3-4: Optimization, quarterly drill preparation

### Operational Procedures

**Quarterly Disaster Recovery Drills:**
- Q1: Full system rebuild from Infrastructure as Code
- Q2: Backup restoration and validation
- Q3: Failover testing and manual operations
- Q4: Complete disaster simulation
- Document lessons learned and update procedures

**Model Management:**
- Primary source: Ollama model registry
- Backup source: HuggingFace repository
- Version control: GitHub LFS for model weights
- Rollback procedures documented in IaC

### Change Management

All changes to this document must be:
- Tracked in the revision history
- Approved by the technical lead
- Reflected in the implementation timeline
- Version controlled in the GitHub repository
- Aligned with the Mac Studio deployment schedule
- Validated against SOC 2 compliance requirements
- Tested in quarterly disaster recovery drills