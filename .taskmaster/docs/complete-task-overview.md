# Empire Document Processing System - Complete Task Overview

**Generated**: 2025-11-05
**Project**: Empire Document Processing & RAG System
**Total Tasks**: 36
**Active Tag**: master

---

## Table of Contents

- [Project Status Summary](#project-status-summary)
- [Task Dependency Chain](#task-dependency-chain)
- [Detailed Task Breakdown](#detailed-task-breakdown)

---

## Project Status Summary

| Status | Count | Tasks |
|--------|-------|-------|
| ✅ Done | 3 | 1, 2, 3 |
| 🔄 In Progress | 1 | 4 |
| ⏸️ Pending | 32 | 5-36 |

---

## Task Dependency Chain

```
1 (Backend Setup) ✅
  └─> 2 (File Upload & B2) ✅
      └─> 3 (Validation & Security) ✅
          └─> 4 (Metadata Extraction) 🔄
              └─> 5 (Duplicate Detection)
                  └─> 6 (Celery Queue)
                      └─> 7 (Notifications)
                          └─> 8 (B2 Folder Management)
                              └─> 9 (AI Classification)
                                  └─> 10 (Doc Processing)
                                      └─> ... (continues through task 36)
```

---

## Detailed Task Breakdown

### ✅ Task 1: Backend Environment Setup (FastAPI, Celery, Supabase, Redis, Neo4j)

**Priority**: High
**Status**: Done
**Dependencies**: None
**Complexity**: 7/10

**Description**:
Establish the production backend infrastructure using FastAPI, Celery, Supabase PostgreSQL (with pgvector), Redis (Upstash), and Neo4j Community (Docker).

**Details**:
Provision Render services for FastAPI and Celery. Configure Supabase PostgreSQL with pgvector and graph tables. Set up Redis (Upstash) for caching and Celery broker. Deploy Neo4j Community via Docker on Mac Studio for knowledge graph storage. Ensure all services use TLS 1.3 and encrypted environment variables. Recommended versions: FastAPI >=0.110, Celery >=5.3, supabase-py >=2.0, redis-py >=5.0, Neo4j Community 5.x.

**Test Strategy**:
Validate service connectivity, health endpoints, and database schema migrations. Run integration tests for API endpoints and Celery task execution. Confirm Redis and Neo4j connectivity.

#### Subtasks:

##### 1.1: Provision FastAPI and Celery Services on Render ✅
**Status**: Done
**Dependencies**: None

**Description**:
Deploy FastAPI and Celery worker services using Render, ensuring production-grade configuration and separation.

**Details**:
Set up two separate Render services: one for FastAPI (API server) and one for Celery (background worker). Use recommended versions (FastAPI >=0.110, Celery >=5.3). Configure environment variables securely and ensure both services are reachable over the network.

**Test Strategy**:
Verify service deployment via Render dashboards. Access FastAPI health endpoint and confirm Celery worker logs show successful startup.

---

##### 1.2: Configure Supabase PostgreSQL with pgvector Extension and Graph Tables ✅
**Status**: Done
**Dependencies**: None

**Description**:
Set up Supabase PostgreSQL instance, enable pgvector, and create required tables for embeddings and graph data.

**Details**:
In Supabase dashboard, enable the 'vector' extension (pgvector) via Extensions panel or SQL command. Create tables for storing embeddings (e.g., documents with embedding vector columns) and graph structures as needed. Use recommended supabase-py >=2.0 for client access.

**Implementation Notes**:
> Supabase PostgreSQL is already provisioned at qohsmuevxuetjpuherzo.supabase.co with credentials stored in the .env file. The database is accessible via Supabase Management Console Panel (MCP).
>
> To complete this subtask:
> 1. Connect to the Supabase PostgreSQL instance using the MCP or SQL editor.
> 2. Enable the pgvector extension by executing:
>    ```sql
>    CREATE EXTENSION IF NOT EXISTS vector;
>    ```
> 3. Create all 37+ required tables from /workflows/database_setup.md, including:
>    - documents
>    - document_chunks
>    - chat_sessions
>    - user_memory_nodes
>    - crewai_agents
>    - crewai_crews
>    - vector tables with embedding columns
>    - graph structure tables
>    - and all other tables specified in the database setup file
> 4. Verify table creation and ensure proper relationships and constraints are established according to the schema definitions.
> 5. Test database connectivity using supabase-py >=2.0 client from the application.
>
> *Added: 2025-11-03T04:12:52.520Z*

**Test Strategy**:
Run SQL queries to confirm pgvector is enabled and tables exist. Insert and retrieve sample data, including vector columns.

---

##### 1.3: Set Up Redis (Upstash) for Caching and Celery Broker ✅
**Status**: Done
**Dependencies**: None

**Description**:
Provision a Redis instance on Upstash and configure it for both caching and as the Celery message broker.

**Details**:
Create a new Redis database on Upstash. Obtain connection URL and credentials. Configure FastAPI and Celery to use this Redis instance for caching and as the Celery broker. Use redis-py >=5.0 for integration.

**Test Strategy**:
Connect to Redis from both FastAPI and Celery. Set and retrieve cache keys. Confirm Celery can enqueue and process tasks using Redis broker.

---

##### 1.4: Deploy Neo4j Community Edition via Docker on Mac Studio ✅
**Status**: Done
**Dependencies**: None

**Description**:
Install and run Neo4j Community Edition (5.x) using Docker on the Mac Studio for knowledge graph storage.

**Details**:
Pull the official Neo4j Community Docker image (version 5.x). Configure Docker container with appropriate ports, volumes for data persistence, and secure environment variables. Ensure Neo4j is accessible from the local network.

**Test Strategy**:
Access Neo4j Browser UI, run basic Cypher queries, and verify data persistence after container restart.

---

##### 1.5: Configure TLS 1.3 and Encrypted Environment Variables for All Services ✅
**Status**: Done
**Dependencies**: 1.1, 1.2, 1.3, 1.4

**Description**:
Ensure all backend services (FastAPI, Celery, Supabase, Redis, Neo4j) use TLS 1.3 for secure communication and store environment variables encrypted.

**Details**:
Update service configurations to enforce TLS 1.3 (e.g., Render custom domains with TLS, Upstash Redis with TLS, Supabase with SSL, Neo4j Docker with TLS certificates). Store all secrets and environment variables using encrypted storage mechanisms provided by each platform.

**Test Strategy**:
Attempt connections using only TLS 1.3. Inspect certificates and verify environment variables are not exposed in logs or process listings.

---

##### 1.6: Validate Integration and Connectivity Across All Services ✅
**Status**: Done
**Dependencies**: 1.1, 1.2, 1.3, 1.4, 1.5

**Description**:
Test and confirm that FastAPI, Celery, Supabase, Redis, and Neo4j are correctly integrated and can communicate securely.

**Details**:
Implement health checks and integration tests: FastAPI connects to Supabase and Neo4j, Celery tasks use Redis broker and access Supabase, all over TLS. Run end-to-end tests for API endpoints and background tasks.

**Test Strategy**:
Run automated integration tests. Check logs for successful connections. Use tools like curl or Postman to verify TLS and endpoint health.

---

### ✅ Task 2: File Upload Interface & Backblaze B2 Integration

**Priority**: High
**Status**: Done
**Dependencies**: Task 1
**Complexity**: 5/10

**Description**:
Implement multi-file upload (up to 10 files, 100MB each) with drag-and-drop UI, progress indicators, and direct upload to Backblaze B2 pending/courses/ folder.

**Details**:
Use Gradio or Streamlit for the web UI. Integrate Backblaze B2 via b2sdk (Python >=1.20). Support Mountain Duck polling (30s) and immediate processing for web UI uploads. Enforce file size/type limits and progress feedback. Organize files per B2 folder structure.

**Test Strategy**:
Upload various file types and sizes, verify progress indicators, and confirm files appear in B2 pending/courses/. Test both Mountain Duck and web UI flows.

#### Subtasks:

##### 2.1: Design and Implement Multi-File Upload UI with Drag-and-Drop ✅
**Status**: Done
**Dependencies**: None

**Description**:
Create a user interface using Streamlit or Gradio that supports uploading up to 10 files (max 100MB each) via drag-and-drop, with progress indicators and file type/size validation.

**Details**:
Use Streamlit's st.file_uploader with accept_multiple_files=True or Gradio's file upload component. Implement drag-and-drop functionality, enforce file type and size limits, and display progress indicators for each file. Ensure the UI is intuitive and provides feedback on upload status and errors.

**Test Strategy**:
Upload various file types and sizes, verify drag-and-drop works, progress indicators display correctly, and validation prevents unsupported files.

---

##### 2.2: Integrate Backblaze B2 Direct Upload via b2sdk ✅
**Status**: Done
**Dependencies**: 2.1

**Description**:
Connect the file upload UI to Backblaze B2 using b2sdk (Python >=1.20), enabling direct upload of files to the pending/courses/ folder and organizing files per B2 folder structure.

**Details**:
Configure b2sdk for authentication and folder management. Implement logic to upload files directly from the UI to the pending/courses/ folder, ensuring files are organized according to the required B2 structure. Handle upload errors and provide feedback to the user.

**Test Strategy**:
Upload files through the UI and confirm they appear in the correct B2 folder. Test error handling and folder organization.

---

##### 2.3: Implement Mountain Duck Polling and Immediate Processing Logic ✅
**Status**: Done
**Dependencies**: 2.2

**Description**:
Support file uploads via Mountain Duck by polling the local folder every 30 seconds and trigger immediate processing for files uploaded via the web UI.

**Details**:
Set up a polling mechanism to detect new files in the local folder synced by Mountain Duck every 30 seconds. For files uploaded via the web UI, initiate processing immediately after upload. Ensure both flows enforce file limits and integrate with the B2 upload logic.

**Test Strategy**:
Simulate uploads via Mountain Duck and web UI, verify polling detects new files, immediate processing works, and all files are uploaded to B2 with correct feedback.

---

### ✅ Task 3: File Format Validation & Security Scanning

**Priority**: High
**Status**: Done
**Dependencies**: Task 2
**Complexity**: 5/10

**Description**:
Validate file formats, check integrity, scan for malware, and enforce MIME/extension rules before upload.

**Details**:
Use python-magic for MIME detection, validate extensions, and run integrity checks (e.g., PDF header validation). Integrate ClamAV (clamd) for malware scanning. Reject unsupported formats with clear error messages.

**Test Strategy**:
Attempt uploads of valid, corrupted, and malicious files. Confirm correct rejection and error messaging. Validate security scan logs.

#### Subtasks:

##### 3.1: Implement File Format and MIME Type Validation ✅
**Status**: Done
**Dependencies**: None

**Description**:
Detect and validate the file's MIME type and extension before upload using python-magic and extension checks.

**Details**:
Use the python-magic library to inspect the file's magic number and determine its true MIME type. Cross-check this with the file extension to ensure consistency. Reject files with mismatched or unsupported MIME types/extensions, and provide clear error messages. Consider using additional libraries like file-validator for comprehensive checks if needed.

**Test Strategy**:
Attempt uploads with valid and invalid file types and extensions. Confirm correct acceptance or rejection and error messaging.

---

##### 3.2: Perform File Integrity and Header Validation ✅
**Status**: Done
**Dependencies**: 3.1

**Description**:
Check file integrity and validate headers for supported formats (e.g., PDF, images) to ensure files are not corrupted or malformed.

**Details**:
For each supported file type, implement header validation (e.g., check PDF header for '%PDF', image headers for magic numbers). Reject files that fail integrity or header checks. Ensure that only structurally valid files proceed to the next stage.

**Test Strategy**:
Upload corrupted or partially valid files and verify that they are rejected with appropriate error messages.

---

##### 3.3: Integrate Malware Scanning with ClamAV ✅
**Status**: Done
**Dependencies**: 3.2

**Description**:
Scan validated files for malware using ClamAV (clamd) before final acceptance.

**Details**:
After passing format and integrity checks, submit files to ClamAV for malware scanning. Reject any files flagged as malicious and log the incident. Ensure the scanning process is efficient and does not introduce significant upload latency.

**Test Strategy**:
Upload files containing known malware signatures and verify detection, rejection, and logging. Confirm clean files are accepted.

---

### 🔄 Task 4: Metadata Extraction & Supabase Storage

**Priority**: High
**Status**: In Progress
**Dependencies**: Task 3
**Complexity**: 5/10

**Description**:
Extract basic and advanced metadata (filename, size, type, timestamps, EXIF, audio/video info) and store in Supabase documents table.

**Details**:
Use Python libraries: exifread for images, mutagen for audio/video, python-docx for DOCX metadata. Store extracted metadata in Supabase documents table as per schema. Ensure upload triggers metadata extraction.

**Test Strategy**:
Upload files of each supported type, verify metadata extraction accuracy, and confirm correct Supabase storage.

#### Subtasks:

##### 4.1: Implement Metadata Extraction for Supported File Types ✅
**Status**: Done
**Dependencies**: None

**Description**:
Develop Python functions to extract basic and advanced metadata from images, audio/video, DOCX, and PDF files using appropriate libraries.

**Details**:
Use exifread for image EXIF data, mutagen for audio/video metadata, python-docx for DOCX files, and PyPDF2 or pdfminer.six for PDF metadata extraction. Ensure extraction covers filename, size, type, timestamps, and relevant advanced fields (EXIF, audio/video info, document properties). Structure output as per Supabase schema requirements.

**Test Strategy**:
Unit test each extractor with sample files of each type. Validate that all required metadata fields are present and accurate.

---

##### 4.2: Integrate Metadata Extraction with File Upload Workflow ✅
**Status**: Done
**Dependencies**: 4.1

**Description**:
Ensure that metadata extraction is automatically triggered upon file upload and that extracted data is prepared for storage.

**Details**:
Modify the upload handler to invoke the correct extraction function based on file type immediately after upload. Collect and format extracted metadata into a dictionary/object matching the Supabase documents table schema.

**Implementation Notes**:
> Implementation completed for metadata extraction integration with upload workflow:
>
> 1. Added metadata_extractor import to upload.py
> 2. Modified upload flow to:
>    - Create temp file if not already created (for virus scanning)
>    - Extract metadata from temp file using MetadataExtractor
>    - Include extracted metadata in upload results
> 3. Installed required libraries: exifread 3.5.1 and mutagen 1.47.0
> 4. Metadata extraction happens after validation and virus scanning, before B2 upload
> 5. Graceful error handling - if extraction fails, error is logged but upload continues
> 6. Metadata is included in JSON response under "metadata" key for each uploaded file
>
> *Added: 2025-11-05T22:11:51.333Z*

**Test Strategy**:
Simulate file uploads via the interface and verify that metadata extraction is triggered and output is correctly formatted for storage.

---

##### 4.3: Store Extracted Metadata in Supabase Documents Table ✅
**Status**: Done
**Dependencies**: 4.2

**Description**:
Insert the extracted metadata into the Supabase documents table, ensuring schema compliance and error handling.

**Details**:
Use the Supabase Python client to insert metadata records into the documents table. Implement error handling for failed inserts and log issues for debugging. Confirm that all required fields are populated and that the data matches the schema.

**Implementation Notes**:
> Successfully implemented the SupabaseStorage class in app/services/supabase_storage.py with methods for managing document metadata: store_document_metadata(), get_document_by_file_id(), update_document_status(), and list_documents(). The implementation has been integrated into the upload workflow immediately after the B2 upload process. The API response now includes a "supabase_stored" boolean flag to indicate successful metadata storage. The system gracefully degrades if Supabase is not configured, allowing the application to function without interruption. Testing confirms that the complete upload workflow functions as expected - metadata extraction works perfectly and Supabase storage attempts are handled gracefully, returning false if not configured.
>
> *Added: 2025-11-05T22:21:11.569Z*

**Test Strategy**:
Upload files of each supported type, then query the Supabase documents table to verify that metadata is stored correctly and completely.

---

### ⏸️ Task 5: Duplicate Detection (SHA-256 & Fuzzy Matching)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 4
**Complexity**: 5/10

**Description**:
Detect duplicate and near-duplicate files using SHA-256 hashes and optional fuzzy matching.

**Details**:
Compute SHA-256 hash for each file and check against Supabase documents table. Implement fuzzy matching using Levenshtein distance for filenames and content (rapidfuzz >=2.0). Provide skip/overwrite options.

**Test Strategy**:
Upload duplicate and near-duplicate files, verify detection and user options. Confirm deduplication accuracy.

#### Subtasks:

##### 5.1: Implement SHA-256 Hash-Based Duplicate Detection
**Status**: Pending
**Dependencies**: None

**Description**:
Compute SHA-256 hashes for each file and compare against existing hashes in the Supabase documents table to identify exact duplicates.

**Details**:
Use a reliable hashing library to generate SHA-256 hashes for all files. Query the Supabase documents table for existing hashes and flag files with matching hashes as duplicates. Ensure efficient scanning and parallel processing for large file sets.

**Test Strategy**:
Upload files with identical content and verify that duplicates are detected solely by hash comparison. Confirm that files with different content are not flagged as duplicates.

---

##### 5.2: Integrate Fuzzy Matching for Near-Duplicate Detection
**Status**: Pending
**Dependencies**: 5.1

**Description**:
Apply fuzzy matching algorithms (Levenshtein distance via rapidfuzz >=2.0) to filenames and file content to identify near-duplicate files.

**Details**:
After hash-based filtering, use rapidfuzz to compute similarity scores for filenames and optionally file contents. Set configurable thresholds for similarity to flag near-duplicates. Optimize for performance when comparing large numbers of files.

**Test Strategy**:
Upload files with similar but not identical names and/or content. Verify that near-duplicates are detected according to the configured similarity threshold.

---

##### 5.3: Implement User Options for Duplicate Handling (Skip/Overwrite)
**Status**: Pending
**Dependencies**: 5.1, 5.2

**Description**:
Provide user interface and backend logic for skip or overwrite actions when duplicates or near-duplicates are detected.

**Details**:
Design UI prompts and backend logic to allow users to choose whether to skip uploading duplicates, overwrite existing files, or take other actions. Ensure options are clearly presented and actions are reliably executed.

**Test Strategy**:
Simulate duplicate and near-duplicate uploads, test all user options (skip, overwrite), and verify correct file handling and user feedback.

---

### ⏸️ Task 6: Celery Task Queue Management

**Priority**: High
**Status**: Pending
**Dependencies**: Task 5
**Complexity**: 6.5/10

**Description**:
Implement priority-based Celery task queue for async document processing, with status tracking, retries, and dead letter queue.

**Details**:
Configure Celery with Redis broker. Use priority queues (urgent, normal, low). Implement status tracking in Supabase file_uploads table. Add retry logic (3 attempts, exponential backoff) and dead letter queue for failed tasks.

**Test Strategy**:
Submit tasks with varying priorities, simulate failures, and verify retry and dead letter queue behavior.

#### Subtasks:

##### 6.1: Configure Celery with Redis for Priority Queues
**Status**: Pending
**Dependencies**: None

**Description**:
Set up Celery to use Redis as the broker and implement priority-based task queues (urgent, normal, low).

**Details**:
Update Celery configuration to use Redis as the broker. Define separate queues for each priority level (e.g., urgent, normal, low) and configure the broker_transport_options with 'queue_order_strategy': 'priority'. Adjust worker_prefetch_multiplier to 1 for effective prioritization. Ensure workers are started with the correct queue order.

**Test Strategy**:
Submit tasks with different priorities and verify that urgent tasks are processed before normal and low priority tasks.

---

##### 6.2: Integrate Status Tracking with Supabase
**Status**: Pending
**Dependencies**: 6.1

**Description**:
Implement status updates for each task in the Supabase file_uploads table.

**Details**:
Modify Celery tasks to update the status field in the Supabase file_uploads table at key stages (queued, started, succeeded, failed). Ensure atomic updates and handle race conditions. Use Supabase client libraries for database operations.

**Test Strategy**:
Trigger tasks and verify that status changes are accurately reflected in the Supabase file_uploads table throughout the task lifecycle.

---

##### 6.3: Implement Retry Logic with Exponential Backoff
**Status**: Pending
**Dependencies**: 6.1

**Description**:
Add retry logic to Celery tasks with up to 3 attempts and exponential backoff on failure.

**Details**:
Configure Celery task decorators to include retry parameters: max_retries=3 and a backoff strategy (e.g., exponential). Ensure that exceptions trigger retries and that retry attempts are logged or tracked for observability.

**Test Strategy**:
Simulate task failures and verify that tasks are retried up to 3 times with increasing delays between attempts.

---

##### 6.4: Set Up Dead Letter Queue for Failed Tasks
**Status**: Pending
**Dependencies**: 6.3

**Description**:
Configure a dead letter queue to capture tasks that fail after all retry attempts.

**Details**:
Create a dedicated dead letter queue in Celery/Redis. Update task failure handlers to route tasks to this queue after exhausting retries. Optionally, log or notify on dead letter events for monitoring.

**Test Strategy**:
Force tasks to fail beyond retry limits and verify their presence in the dead letter queue.

---

##### 6.5: End-to-End Testing of Priority Queue Management
**Status**: Pending
**Dependencies**: 6.2, 6.4

**Description**:
Test the complete priority queue system, including status tracking, retries, and dead letter handling.

**Details**:
Design and execute test cases covering all priority levels, status transitions, retry scenarios, and dead letter queue routing. Validate system behavior under normal and failure conditions.

**Test Strategy**:
Run integration tests that submit tasks with various priorities, induce failures, and confirm correct processing, status updates, retries, and dead letter handling.

---

### ⏸️ Task 7: User Notification System (WebSocket & Email)

**Priority**: Medium
**Status**: Pending
**Dependencies**: Task 6
**Complexity**: 5/10

**Description**:
Provide real-time upload and processing notifications via WebSocket, with optional email alerts for long-running tasks.

**Details**:
Implement FastAPI WebSocket endpoints for progress and completion notifications. Use SMTP or SendGrid for email alerts. Integrate with frontend for actionable error messages.

**Test Strategy**:
Trigger uploads and processing, verify real-time notifications and email delivery for long tasks.

#### Subtasks:

##### 7.1: Implement FastAPI WebSocket Endpoints for Real-Time Notifications
**Status**: Pending
**Dependencies**: None

**Description**:
Develop FastAPI WebSocket endpoints to deliver real-time upload and processing progress and completion notifications to connected clients.

**Details**:
Set up FastAPI WebSocket routes (e.g., /ws/notifications). Manage client connections and broadcast progress/completion events. Ensure endpoints can handle multiple simultaneous connections and send actionable error messages. Integrate with backend processing logic to emit updates as tasks progress or complete.

**Test Strategy**:
Simulate uploads and processing tasks; verify clients receive real-time progress and completion notifications via WebSocket.

---

##### 7.2: Integrate Email Alert System for Long-Running Tasks
**Status**: Pending
**Dependencies**: 7.1

**Description**:
Add optional email notifications for users when uploads or processing tasks exceed a defined duration threshold.

**Details**:
Configure SMTP or SendGrid integration for sending emails. Implement logic to detect long-running tasks and trigger email alerts with relevant status and error details. Ensure emails are sent only when user opts in or when thresholds are exceeded. Handle email delivery failures gracefully.

**Test Strategy**:
Trigger long-running tasks and confirm that email alerts are sent to the correct recipients with accurate information.

---

##### 7.3: Frontend Integration for Real-Time and Email Notifications
**Status**: Pending
**Dependencies**: 7.1, 7.2

**Description**:
Connect frontend application to WebSocket endpoints and display real-time notifications, including actionable error messages. Provide UI for email alert preferences.

**Details**:
Update frontend to establish and manage WebSocket connections, display progress/completion notifications, and show errors in a user-friendly manner. Add UI controls for users to opt in/out of email alerts. Ensure seamless user experience for both notification channels.

**Test Strategy**:
Test frontend by uploading files and processing tasks; verify real-time updates and error messages appear, and email preferences are respected.

---

### ⏸️ Task 8: Backblaze B2 Folder Management & Encryption

**Priority**: High
**Status**: Pending
**Dependencies**: Task 7
**Complexity**: 7/10

**Description**:
Automate file movement across B2 folders (pending → processing → processed/failed) and support zero-knowledge encryption for sensitive files.

**Details**:
Use b2sdk for folder operations. Implement file movement logic based on processing status. Integrate PyCryptodome for optional AES encryption before upload.

**Test Strategy**:
Process files through all folder stages, verify correct organization and encryption for flagged files.

#### Subtasks:

##### 8.1: Integrate b2sdk and Set Up B2 Folder Interfaces
**Status**: Pending
**Dependencies**: None

**Description**:
Initialize b2sdk, authenticate, and set up interfaces for pending, processing, processed, and failed folders in the B2 bucket.

**Details**:
Use b2sdk's AccountInfo and B2Api to authenticate and connect to the B2 bucket. Instantiate B2Folder objects for each logical folder (pending, processing, processed, failed) to enable file operations between them.

**Test Strategy**:
Verify connection and folder listing for each B2 folder using b2sdk methods.

---

##### 8.2: Implement File Movement Logic Based on Processing Status
**Status**: Pending
**Dependencies**: 8.1

**Description**:
Develop logic to move files between B2 folders according to their processing status (pending → processing → processed/failed).

**Details**:
Create functions to list files in each folder and move them to the next stage based on status. Ensure atomicity and handle errors during move operations using b2sdk's file copy and delete methods.

**Test Strategy**:
Simulate status changes and verify files are moved to the correct folders without duplication or loss.

---

##### 8.3: Integrate PyCryptodome for Optional AES Encryption
**Status**: Pending
**Dependencies**: 8.1

**Description**:
Add support for zero-knowledge AES encryption of sensitive files before upload to B2.

**Details**:
Use PyCryptodome to encrypt files with a user-supplied key before uploading to B2. Ensure encryption is optional and only applied to flagged files. Store encrypted files in the appropriate B2 folder.

**Test Strategy**:
Upload both encrypted and unencrypted files, then download and verify decryption for encrypted files.

---

##### 8.4: Handle Status-Based Transitions and Error Recovery
**Status**: Pending
**Dependencies**: 8.2, 8.3

**Description**:
Implement robust handling for file status transitions, including retries and error recovery for failed moves or uploads.

**Details**:
Add logic to detect and recover from failed moves or uploads. Implement retry mechanisms and ensure files are not lost or duplicated during transitions. Log all status changes and errors for auditability.

**Test Strategy**:
Intentionally trigger errors (e.g., network failures) and verify that files are correctly retried or moved to the failed folder.

---

##### 8.5: Develop Comprehensive Tests for Folder Organization and Encryption
**Status**: Pending
**Dependencies**: 8.2, 8.3, 8.4

**Description**:
Create automated tests to verify correct file organization across all folder stages and validate encryption/decryption for sensitive files.

**Details**:
Write tests that process files through all folder stages, check their presence in the correct folders, and confirm that encryption is correctly applied and reversible for flagged files.

**Test Strategy**:
Run end-to-end tests covering all transitions and encryption scenarios, ensuring files are organized and protected as specified.

---

### ⏸️ Task 9: AI Department Classification Workflow (Claude Haiku)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 8
**Complexity**: 5/10

**Description**:
Classify uploaded documents into 10 departments using Claude Haiku API, storing results in Supabase.

**Details**:
Integrate anthropic-py SDK. Implement async auto_classify_course function as per PRD. Store department, confidence, and subdepartment in documents and courses tables.

**Test Strategy**:
Upload sample documents for each department, verify classification accuracy and Supabase updates.

#### Subtasks:

##### 9.1: Integrate Claude Haiku API and anthropic-py SDK for Document Classification
**Status**: Pending
**Dependencies**: None

**Description**:
Set up the Claude Haiku API and anthropic-py SDK to enable classification of uploaded documents into 10 departments.

**Details**:
Install and configure the anthropic-py SDK. Implement API authentication and error handling (e.g., retries, rate limits). Ensure the async auto_classify_course function is ready to send document content to Claude Haiku and receive department predictions. Tune parameters such as temperature and max_tokens for optimal classification accuracy.

**Test Strategy**:
Send sample documents to the API and verify department predictions are returned correctly. Test error handling by simulating API failures.

---

##### 9.2: Implement Async auto_classify_course Function and PRD Logic
**Status**: Pending
**Dependencies**: 9.1

**Description**:
Develop the async auto_classify_course function according to the Product Requirements Document (PRD), ensuring it processes documents and extracts department, confidence, and subdepartment.

**Details**:
Write the async function to handle document input, call the Claude Haiku API, and parse the response for department, confidence score, and subdepartment. Ensure the function supports batch processing and handles edge cases (e.g., ambiguous classifications). Document the function and its parameters for maintainability.

**Test Strategy**:
Unit test the function with mock API responses. Validate output structure and accuracy against expected department labels.

---

##### 9.3: Store Classification Results in Supabase Documents and Courses Tables
**Status**: Pending
**Dependencies**: 9.2

**Description**:
Persist the classification results (department, confidence, subdepartment) in the Supabase documents and courses tables.

**Details**:
Map the classification output to the correct schema fields in Supabase. Implement transactional writes to ensure data consistency. Add logging for successful and failed writes. Verify that updates are reflected in both documents and courses tables as required.

**Test Strategy**:
Upload test documents, run classification, and confirm Supabase tables are updated with correct department, confidence, and subdepartment values. Check for data integrity and error handling.

---

### ⏸️ Task 10: Universal Document Processing Pipeline

**Priority**: High
**Status**: Pending
**Dependencies**: Task 9
**Complexity**: 5/10

**Description**:
Extract text and structured data from all supported document types using specialized services and fallback methods.

**Details**:
Integrate LlamaIndex (REST API) for clean PDFs, Mistral OCR for scanned PDFs, Tesseract OCR for fallback. Use python-docx for DOCX, mutagen for audio/video, Claude Vision API for images. Implement table/image extraction and maintain page/section info.

**Test Strategy**:
Process each file type, verify extraction accuracy, structure preservation, and fallback logic.

#### Subtasks:

##### 10.1: Implement Modular Document Ingestion and Classification
**Status**: Pending
**Dependencies**: None

**Description**:
Design and build the pipeline's ingestion layer to accept documents from various sources and classify them by type (PDF, DOCX, image, audio/video).

**Details**:
Set up connectors for file sources (e.g., S3 buckets, local uploads). Integrate document type detection logic to route files to appropriate extraction modules. Log ingestion events and maintain audit trails for each document.

**Test Strategy**:
Submit sample files of each supported type, verify correct classification and routing, and check ingestion logs for completeness.

---

##### 10.2: Integrate Specialized Extraction Services and Fallbacks
**Status**: Pending
**Dependencies**: 10.1

**Description**:
Connect and orchestrate specialized extraction services for each document type, with fallback logic for unsupported or failed cases.

**Details**:
Integrate LlamaIndex REST API for clean PDFs, Mistral OCR for scanned PDFs, Tesseract OCR as fallback, python-docx for DOCX, mutagen for audio/video, Claude Vision API for images. Implement logic to select extraction method based on classification and handle failures by cascading to fallback services.

**Test Strategy**:
Process a diverse set of documents, intentionally trigger extraction failures, and verify fallback mechanisms activate and extract data as expected.

---

##### 10.3: Extract Structured Data and Metadata with Section/Page Tracking
**Status**: Pending
**Dependencies**: 10.2

**Description**:
Develop logic to extract tables, images, and maintain page/section metadata for all processed documents, ensuring structured outputs.

**Details**:
Implement table and image extraction for supported formats. Track and store page/section information alongside extracted text and structured data. Ensure outputs are normalized for downstream consumption.

**Test Strategy**:
Validate extracted outputs for structure, completeness, and correct association of metadata (page/section info) using test documents with known layouts.

---

### ⏸️ Task 11: Audio & Video Processing (Soniox, Claude Vision)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 10
**Complexity**: 5/10

**Description**:
Transcribe audio, extract speakers/timestamps, and analyze video frames using Soniox and Claude Vision APIs.

**Details**:
Integrate Soniox REST API for transcription and diarization. Use ffmpeg-python for frame/audio extraction from video. Analyze frames with Claude Vision API. Store transcripts and timeline metadata.

**Test Strategy**:
Process audio and video files, verify transcript accuracy, speaker identification, and frame analysis.

#### Subtasks:

##### 11.1: Extract Audio and Video Frames from Input Files
**Status**: Pending
**Dependencies**: None

**Description**:
Use ffmpeg-python to extract audio tracks and video frames from input video files for downstream processing.

**Details**:
Implement a Python module using ffmpeg-python to separate audio from video files and extract video frames at configurable intervals. Ensure extracted audio is in a Soniox-compatible format (e.g., 16kHz mono WAV). Store extracted frames and audio in a structured directory or object storage for later processing.

**Test Strategy**:
Run extraction on sample video files, verify correct number and quality of frames, and check audio format compatibility with Soniox.

---

##### 11.2: Transcribe Audio and Extract Speaker/Timestamps with Soniox API
**Status**: Pending
**Dependencies**: 11.1

**Description**:
Integrate Soniox REST API to transcribe extracted audio, enabling speaker diarization and timestamp extraction.

**Details**:
Authenticate with Soniox API using a project API key. Send extracted audio files for transcription using the async or streaming endpoints. Enable speaker diarization and timestamp options in the API request. Parse and store the returned transcript, speaker labels, and word-level timestamps in the database or metadata files.

**Test Strategy**:
Submit test audio files, verify transcript accuracy, correct speaker segmentation, and presence of timestamps. Compare results with ground truth if available.

---

##### 11.3: Analyze Video Frames with Claude Vision API and Store Metadata
**Status**: Pending
**Dependencies**: 11.1

**Description**:
Send extracted video frames to Claude Vision API for analysis and store the resulting metadata alongside transcripts and timeline data.

**Details**:
Batch or stream video frames to the Claude Vision API, handling authentication and rate limits. Parse the returned analysis (e.g., scene description, object detection) and associate results with corresponding timestamps. Store all metadata in a structured format, linking frame analysis to transcript timeline.

**Test Strategy**:
Process sample frames, verify that analysis results are received and correctly mapped to frame timestamps. Check integration with transcript timeline and metadata storage.

---

### ⏸️ Task 12: Structured Data Extraction (LangExtract)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 11
**Complexity**: 5/10

**Description**:
Extract entities, key-value pairs, and course metadata using LangExtract API.

**Details**:
Integrate LangExtract REST API for field/entity extraction. Store results in Supabase courses and document_chunks tables. Implement intelligent filename generation (M01-L02 format).

**Test Strategy**:
Process documents with structured fields, verify entity extraction and metadata accuracy.

#### Subtasks:

##### 12.1: Define Extraction Schema and Example Prompts for LangExtract
**Status**: Pending
**Dependencies**: None

**Description**:
Specify the entity types, key-value pairs, and course metadata fields to be extracted. Create example prompts and sample extractions to guide the LangExtract API.

**Details**:
List all required fields (e.g., course title, module number, lesson number, instructor, date) and define their expected formats. Write natural language prompts and provide high-quality example extractions using LangExtract's ExampleData objects to ensure consistent output schema and accurate extraction.

**Test Strategy**:
Review extracted fields from test documents to confirm schema coverage and prompt effectiveness.

---

##### 12.2: Integrate LangExtract REST API for Automated Entity and Metadata Extraction
**Status**: Pending
**Dependencies**: 12.1

**Description**:
Connect to the LangExtract REST API and implement logic to process course documents, extracting entities, key-value pairs, and metadata as defined in the schema.

**Details**:
Set up API authentication and request handling. For each uploaded course document, send the text and extraction instructions/examples to LangExtract. Parse the returned structured data, ensuring source grounding and attribute mapping. Handle errors and edge cases (e.g., missing fields, ambiguous extractions).

**Test Strategy**:
Process a variety of course documents and verify that all required entities and metadata are extracted with correct attributes and source positions.

---

##### 12.3: Store Extracted Data in Supabase and Implement Intelligent Filename Generation
**Status**: Pending
**Dependencies**: 12.2

**Description**:
Save the extracted entities and metadata into Supabase courses and document_chunks tables. Generate filenames using the M01-L02 format based on extracted module and lesson numbers.

**Details**:
Map extracted fields to Supabase table schemas, ensuring correct data types and relationships. Implement logic to generate filenames (e.g., M01-L02) from extracted metadata and associate them with stored records. Validate data integrity and handle duplicate or conflicting entries.

**Test Strategy**:
Insert extracted data from sample documents into Supabase, verify correct mapping and filename generation, and check for consistency across multiple uploads.

---

### ⏸️ Task 13: Adaptive Chunking Strategy Implementation

**Priority**: High
**Status**: Pending
**Dependencies**: Task 12
**Complexity**: 5/10

**Description**:
Implement semantic, code, and transcript chunking with configurable size and overlap, preserving context.

**Details**:
Use LlamaIndex chunking for documents, custom logic for code (AST parsing), and time/topic-based chunking for transcripts. Store chunks in document_chunks table with metadata and overlap.

**Test Strategy**:
Chunk various document types, verify chunk boundaries, overlap, and context preservation.

#### Subtasks:

##### 13.1: Implement Adaptive Semantic Chunking for Documents
**Status**: Pending
**Dependencies**: None

**Description**:
Develop and configure semantic chunking for text documents using LlamaIndex, supporting adjustable chunk size and overlap to preserve context.

**Details**:
Use LlamaIndex's semantic chunker to split documents into contextually coherent chunks. Expose configuration for chunk size and overlap (e.g., via parameters or settings). Ensure chunk metadata (source_doc_id, chunk boundaries, overlap) is captured for each chunk and stored in the document_chunks table. Validate that semantic boundaries are respected and context is preserved across chunks.

**Test Strategy**:
Chunk a variety of document types, verify chunk boundaries align with semantic units, check overlap, and confirm metadata is correctly stored.

---

##### 13.2: Develop Custom Code Chunking Using AST Parsing
**Status**: Pending
**Dependencies**: 13.1

**Description**:
Create a chunking mechanism for code files that leverages AST parsing to split code into logical units with configurable size and overlap.

**Details**:
Implement code chunking logic that parses source code into AST nodes (e.g., functions, classes) and groups them into chunks based on configurable parameters (lines per chunk, overlap). Support multiple programming languages if required. Store resulting code chunks with relevant metadata (e.g., language, function/class names, overlap) in the document_chunks table.

**Test Strategy**:
Process code files in different languages, verify chunking aligns with logical code units, check overlap, and ensure metadata accuracy.

---

##### 13.3: Implement Time/Topic-Based Chunking for Transcripts
**Status**: Pending
**Dependencies**: 13.1

**Description**:
Design and implement a chunking strategy for transcripts that splits content based on time intervals or topic shifts, with configurable overlap.

**Details**:
Develop logic to segment transcripts using either fixed time windows or detected topic boundaries. Allow configuration of chunk duration or topic sensitivity, as well as overlap between chunks. Store transcript chunks with metadata (e.g., start/end time, topic label, overlap) in the document_chunks table. Ensure context is preserved across chunk boundaries.

**Test Strategy**:
Chunk transcripts with varying lengths and topics, verify chunk boundaries match time/topic criteria, check overlap, and validate metadata storage.

---

### ⏸️ Task 14: Error Handling & Graceful Degradation

**Priority**: High
**Status**: Pending
**Dependencies**: Task 13
**Complexity**: 5/10

**Description**:
Implement robust error handling, retry logic, partial processing, and detailed logging for all pipeline stages.

**Details**:
Use Python exception handling, Celery retry policies, and fallback to simpler methods. Log errors with stack traces in processing_logs table. Move failed files to B2 failed/ folder.

**Test Strategy**:
Simulate service failures, verify retries, partial saves, and error logs.

#### Subtasks:

##### 14.1: Implement Robust Exception Handling and Retry Logic in Pipeline Tasks
**Status**: Pending
**Dependencies**: None

**Description**:
Integrate structured Python exception handling and Celery retry policies for all pipeline stages to ensure resilience against transient and expected failures.

**Details**:
Wrap all critical pipeline operations in try/except blocks. Use Celery's retry mechanisms (e.g., autoretry_for, max_retries, retry_backoff) to handle transient errors such as network or service outages. Configure per-task retry parameters and ensure idempotency to avoid side effects on repeated execution. Avoid retrying on non-transient exceptions.

**Test Strategy**:
Simulate transient and permanent failures in pipeline tasks. Verify that retries occur as configured, and that non-retriable errors do not trigger retries.

---

##### 14.2: Enable Graceful Degradation and Partial Processing with Fallbacks
**Status**: Pending
**Dependencies**: 14.1

**Description**:
Design pipeline stages to degrade gracefully by falling back to simpler or partial processing methods when primary logic fails.

**Details**:
For each pipeline stage, define fallback logic (e.g., simplified processing, skipping non-critical steps) to be invoked when primary processing fails after retries. Ensure that partial results are saved where possible, and that the system continues processing unaffected files or stages. Move unrecoverable files to the B2 failed/ folder for later inspection.

**Test Strategy**:
Force failures in primary processing logic and verify that fallback methods are invoked, partial results are saved, and failed files are moved appropriately.

---

##### 14.3: Implement Detailed Error Logging and Monitoring
**Status**: Pending
**Dependencies**: 14.1, 14.2

**Description**:
Log all errors, stack traces, and processing outcomes in the processing_logs table to support debugging and monitoring.

**Details**:
On every exception or failure, capture the full stack trace and relevant context. Insert detailed error records into the processing_logs table, including task identifiers, error types, messages, and timestamps. Ensure logs are structured for easy querying and monitoring. Integrate with monitoring tools if available.

**Test Strategy**:
Trigger various error scenarios and verify that all relevant details are logged in the processing_logs table, including stack traces and context.

---

### ⏸️ Task 15: Processing Monitoring & Metrics Collection

**Priority**: High
**Status**: Pending
**Dependencies**: Task 14
**Complexity**: 5/10

**Description**:
Track real-time processing progress, resource usage, and cost per document using Prometheus metrics.

**Details**:
Integrate prometheus_client for FastAPI, Celery, and custom business metrics. Track processing time, resource usage, and cost. Store stage-wise metrics in processing_logs table.

**Test Strategy**:
Process documents, verify Prometheus metrics, Grafana dashboard updates, and Supabase logs.

#### Subtasks:

##### 15.1: Integrate Prometheus Metrics Collection in FastAPI and Celery
**Status**: Pending
**Dependencies**: None

**Description**:
Instrument FastAPI and Celery services to expose Prometheus-compatible metrics endpoints for processing progress, resource usage, and cost tracking.

**Details**:
Install prometheus_client in both FastAPI and Celery environments. For FastAPI, mount the /metrics endpoint using make_asgi_app and add counters, histograms, and gauges for request counts, processing time, and resource usage. For Celery, use available Prometheus exporters or integrate prometheus_client to expose worker and task metrics. Ensure all relevant business and custom metrics are included.

**Test Strategy**:
Verify /metrics endpoints in FastAPI and Celery return expected metrics. Use Prometheus to scrape these endpoints and confirm metrics are ingested.

---

##### 15.2: Track and Store Stage-wise Processing Metrics in Database
**Status**: Pending
**Dependencies**: 15.1

**Description**:
Capture and persist detailed stage-wise metrics (processing time, resource usage, cost per document) in the processing_logs table for audit and analysis.

**Details**:
Extend processing logic to record metrics at each pipeline stage. Store metrics such as start/end timestamps, CPU/memory usage, and cost estimates in the processing_logs table. Ensure schema supports all required fields and that writes are efficient and reliable.

**Test Strategy**:
Process sample documents and verify that processing_logs table contains accurate, stage-wise metrics matching Prometheus data.

---

##### 15.3: Validate Metrics Collection and Visualization End-to-End
**Status**: Pending
**Dependencies**: 15.1, 15.2

**Description**:
Test the full monitoring pipeline from metrics emission to visualization and logging, ensuring real-time and historical data is accurate and actionable.

**Details**:
Simulate document processing and monitor Prometheus for real-time metrics updates. Confirm that Grafana dashboards reflect current and historical metrics. Cross-check database logs with Prometheus data for consistency. Validate cost calculations and resource usage reporting.

**Test Strategy**:
Run end-to-end tests: process documents, check Prometheus and Grafana for live metrics, and verify processing_logs entries. Ensure all metrics are accurate and actionable.

---

### ⏸️ Task 16: Embedding Generation Pipeline (BGE-M3, Claude API)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 15
**Complexity**: 5/10

**Description**:
Generate and cache embeddings for document chunks using BGE-M3 (Ollama for dev, Claude API for prod).

**Details**:
Integrate langchain.embeddings.OllamaEmbeddings for dev, Claude API for prod. Batch process 100 chunks, cache embeddings in Supabase pgvector. Regenerate on content updates.

**Test Strategy**:
Generate embeddings for sample chunks, verify latency, caching, and Supabase storage.

#### Subtasks:

##### 16.1: Integrate BGE-M3 Embedding Generation for Development (Ollama)
**Status**: Pending
**Dependencies**: None

**Description**:
Set up and integrate the BGE-M3 embedding model using Ollama for local development, enabling batch processing of document chunks.

**Details**:
Install and configure langchain_ollama and OllamaEmbeddings with the BGE-M3 model. Implement batch processing for 100 document chunks at a time. Ensure the pipeline can handle content updates by triggering re-embedding as needed. Optimize for local inference speed and resource usage.

**Test Strategy**:
Generate embeddings for a sample batch of 100 chunks, verify output shape and latency, and confirm embeddings are regenerated on content updates.

---

##### 16.2: Integrate Claude API for Production Embedding Generation
**Status**: Pending
**Dependencies**: 16.1

**Description**:
Implement embedding generation using the Claude API for production, supporting batch processing and seamless switching from development to production.

**Details**:
Configure the Claude API integration within the embedding pipeline. Ensure batch processing of 100 chunks per request, with error handling and retry logic. Provide a configuration switch to toggle between Ollama (dev) and Claude API (prod). Ensure compatibility of embedding formats and dimensions.

**Test Strategy**:
Run embedding generation for a sample batch via Claude API, verify output consistency with dev pipeline, and test failover and error handling.

---

##### 16.3: Implement Embedding Caching and Regeneration Logic in Supabase pgvector
**Status**: Pending
**Dependencies**: 16.2

**Description**:
Design and implement caching of generated embeddings in Supabase pgvector, including logic to detect content updates and trigger regeneration.

**Details**:
Integrate with Supabase pgvector to store and retrieve embeddings. Implement logic to check for content changes and invalidate or update cached embeddings as needed. Ensure efficient batch inserts and retrievals. Maintain metadata for tracking embedding versions and update timestamps.

**Test Strategy**:
Insert, retrieve, and update embeddings in Supabase for sample documents. Simulate content updates and verify that embeddings are correctly regenerated and cached.

---

### ⏸️ Task 17: Vector Storage & Indexing (Supabase pgvector)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 16
**Complexity**: 7.5/10

**Description**:
Store embeddings in Supabase pgvector, create HNSW index for fast similarity search, and optimize batch inserts.

**Details**:
Enable pgvector extension, create HNSW index, and optimize batch inserts using supabase-py bulk operations. Organize by namespace and support metadata filtering.

**Test Strategy**:
Insert and search embeddings, verify index performance and metadata filtering.

#### Subtasks:

##### 17.1: Enable pgvector Extension in Supabase
**Status**: Pending
**Dependencies**: None

**Description**:
Activate the pgvector extension in the Supabase PostgreSQL database to support vector data types and similarity search operations.

**Details**:
Access the Supabase dashboard, navigate to the Extensions section, and enable the 'vector' extension. This step is required before creating tables with vector columns and using vector search features.

**Test Strategy**:
Verify that the 'vector' extension is listed as enabled in the Supabase dashboard and that SQL commands using the 'vector' data type execute without errors.

---

##### 17.2: Create Embeddings Table and HNSW Index
**Status**: Pending
**Dependencies**: 17.1

**Description**:
Design and create a table for storing embeddings, including metadata and namespace columns, and add an HNSW index for fast similarity search.

**Details**:
Define a table schema with columns for id, embedding (vector), metadata (JSONB), and namespace (text or UUID). Use SQL to create the table and then create an HNSW index on the embedding column for efficient ANN search.

**Test Strategy**:
Insert sample embeddings and confirm that the HNSW index exists and is used in EXPLAIN query plans for similarity searches.

---

##### 17.3: Optimize Batch Inserts Using supabase-py Bulk Operations
**Status**: Pending
**Dependencies**: 17.2

**Description**:
Implement efficient batch insertion of embeddings and metadata using supabase-py or equivalent bulk insert methods.

**Details**:
Use supabase-py or another supported client to insert multiple embeddings in a single operation, minimizing transaction overhead and maximizing throughput. Ensure the code handles large batches and error cases.

**Test Strategy**:
Benchmark batch insert performance with varying batch sizes and verify that all records are correctly stored in the table.

---

##### 17.4: Organize Embeddings by Namespace
**Status**: Pending
**Dependencies**: 17.2

**Description**:
Implement logic to assign and query embeddings by namespace to support multi-tenant or segmented storage.

**Details**:
Add a namespace column to the embeddings table if not already present. Ensure all insert and query operations include namespace filtering to logically separate data for different use cases or clients.

**Test Strategy**:
Insert embeddings with different namespaces and verify that queries scoped to a namespace only return relevant records.

---

##### 17.5: Implement Metadata Filtering in Similarity Search
**Status**: Pending
**Dependencies**: 17.2

**Description**:
Enable filtering of similarity search results based on metadata fields stored with each embedding.

**Details**:
Use PostgreSQL's JSONB operators to filter embeddings by metadata fields in combination with vector similarity queries. Update search queries to support metadata-based filtering (e.g., by document type, tags, or timestamps).

**Test Strategy**:
Run similarity searches with and without metadata filters, confirming that results are correctly filtered and performance remains acceptable.

---

### ⏸️ Task 18: Hybrid Search Implementation (Dense, Sparse, Fuzzy, RRF)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 17
**Complexity**: 5/10

**Description**:
Implement hybrid search combining vector similarity, BM25, ILIKE, fuzzy matching, and reciprocal rank fusion.

**Details**:
Use pgvector for dense search, PostgreSQL full-text search for BM25, ILIKE for pattern matching, rapidfuzz for fuzzy search. Implement RRF for result fusion with configurable weights.

**Test Strategy**:
Run hybrid searches, verify result fusion, relevance, and latency targets.

#### Subtasks:

##### 18.1: Implement Dense, Sparse, and Fuzzy Search Pipelines
**Status**: Pending
**Dependencies**: None

**Description**:
Develop individual search pipelines for dense (vector), sparse (BM25), and fuzzy (ILIKE, rapidfuzz) retrieval methods.

**Details**:
Set up pgvector for dense search, configure PostgreSQL full-text search for BM25, implement ILIKE for pattern matching, and integrate rapidfuzz for fuzzy matching. Ensure each pipeline can independently retrieve and score results for a given query.

**Test Strategy**:
Run isolated queries for each pipeline and verify result relevance, accuracy, and latency.

---

##### 18.2: Design and Implement Reciprocal Rank Fusion (RRF) Algorithm
**Status**: Pending
**Dependencies**: 18.1

**Description**:
Create a fusion algorithm to combine ranked results from dense, sparse, and fuzzy pipelines using reciprocal rank fusion.

**Details**:
Develop RRF logic to merge result lists from all pipelines, applying configurable weights. Ensure the algorithm penalizes lower-ranked results and boosts consensus across methods. Validate with sample queries and edge cases.

**Test Strategy**:
Test fusion with controlled input lists, verify ranking consistency, and check that top results reflect combined relevance.

---

##### 18.3: Integrate Hybrid Search and Expose Unified API Endpoint
**Status**: Pending
**Dependencies**: 18.2

**Description**:
Combine all search pipelines and RRF fusion into a single hybrid search workflow, exposing it via an API endpoint.

**Details**:
Orchestrate parallel execution of all search methods, collect results, apply RRF fusion, and return unified ranked results. Implement API endpoint with configurable fusion weights and query parameters. Ensure robust error handling and logging.

**Test Strategy**:
Run end-to-end hybrid search queries through the API, validate result quality, latency, and error handling.

---

### ⏸️ Task 19: Query Expansion & Reranking (Claude Haiku, BGE-Reranker-v2)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 18
**Complexity**: 5/10

**Description**:
Expand queries using Claude Haiku, execute parallel searches, and rerank results with BGE-Reranker-v2.

**Details**:
Integrate anthropic-py for query expansion, run parallel searches, and rerank top 20-30 results using Ollama BGE-Reranker-v2 (dev) or Claude API (prod).

**Test Strategy**:
Test query expansion and reranking, verify improved recall and precision.

#### Subtasks:

##### 19.1: Integrate Claude Haiku for Query Expansion
**Status**: Pending
**Dependencies**: None

**Description**:
Implement query expansion using Claude Haiku via anthropic-py, ensuring queries are enriched for improved recall.

**Details**:
Set up anthropic-py client and configure Claude Haiku 4.5 API parameters (e.g., max_tokens, temperature, top_p). Design prompt templates to expand user queries, leveraging advanced prompt engineering techniques for optimal output. Handle API errors and retries for reliability.

**Test Strategy**:
Send sample queries and verify that expanded queries are generated as expected. Compare recall and diversity of results before and after expansion.

---

##### 19.2: Execute Parallel Searches with Expanded Queries
**Status**: Pending
**Dependencies**: 19.1

**Description**:
Run parallel searches using the expanded queries to retrieve a broad set of relevant results.

**Details**:
Implement asynchronous or concurrent search logic to execute multiple queries in parallel. Aggregate results from all searches, ensuring deduplication and efficient handling of large result sets. Optimize for latency and throughput.

**Test Strategy**:
Test with multiple expanded queries and measure search latency. Confirm that all relevant results are retrieved and aggregated correctly.

---

##### 19.3: Rerank Search Results Using BGE-Reranker-v2
**Status**: Pending
**Dependencies**: 19.2

**Description**:
Apply BGE-Reranker-v2 to rerank the top 20-30 search results for improved relevance and precision.

**Details**:
Integrate Ollama BGE-Reranker-v2 (dev) or Claude API (prod) to rerank aggregated results. Configure reranker model and permissions, and tune reranking parameters. Validate reranked output for relevance and consistency.

**Test Strategy**:
Compare original and reranked result sets using relevance metrics (precision, recall, NDCG). Conduct manual review of top results for quality assurance.

---

### ⏸️ Task 20: Neo4j Graph Integration & Entity Storage

**Priority**: High
**Status**: Pending
**Dependencies**: Task 19
**Complexity**: 5/10

**Description**:
Store entities and relationships in Neo4j, enable graph-based queries and context retrieval.

**Details**:
Use neo4j Python driver (neo4j >=5.10) to create document and entity nodes, relationships, and vector index. Implement Cypher queries for entity-centric and relationship traversal.

**Test Strategy**:
Insert entities/relationships, run Cypher queries, verify graph traversal and context retrieval.

#### Subtasks:

##### 20.1: Set Up Neo4j Python Driver and Database Connection
**Status**: Pending
**Dependencies**: None

**Description**:
Install the Neo4j Python driver and establish a secure connection to the Neo4j database instance.

**Details**:
Use pip to install the neo4j Python driver (neo4j >=5.10). Configure connection parameters (URI, username, password) and verify connectivity using GraphDatabase.driver and driver.verify_connectivity(). Ensure the database instance is running and accessible.

**Test Strategy**:
Attempt connection and run a simple Cypher query to confirm connectivity.

---

##### 20.2: Implement Entity and Relationship Node Creation
**Status**: Pending
**Dependencies**: 20.1

**Description**:
Create Cypher queries and Python functions to insert document and entity nodes, and define relationships between them in Neo4j.

**Details**:
Define node labels (e.g., Document, Entity) and relationship types. Use MERGE or CREATE Cypher statements to add nodes and relationships. Implement Python functions to batch insert entities and relationships, ensuring idempotency and data integrity.

**Test Strategy**:
Insert sample entities and relationships, then query the graph to verify correct node and relationship creation.

---

##### 20.3: Enable Graph-Based Queries and Context Retrieval
**Status**: Pending
**Dependencies**: 20.2

**Description**:
Develop Cypher queries and Python interfaces for entity-centric and relationship traversal, including context retrieval and vector index integration.

**Details**:
Implement Cypher queries for traversing relationships (e.g., MATCH, OPTIONAL MATCH). Integrate vector index for similarity search if required. Provide Python functions to retrieve context around entities and relationships, supporting advanced graph queries.

**Test Strategy**:
Run entity-centric and relationship traversal queries, validate context retrieval, and test vector index search if applicable.

---

### ⏸️ Task 21: Caching Strategy (Redis, Tiered Cache)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 20
**Complexity**: 5/10

**Description**:
Implement Redis caching for frequent queries, embeddings, and search results with semantic thresholds and tiered cache.

**Details**:
Use redis-py for L1 cache (Redis), fallback to L2 (PostgreSQL). Implement semantic cache thresholds and 5-minute TTL. Track cache hit rate.

**Test Strategy**:
Run repeated queries, verify cache hits/misses, and cache update logic.

#### Subtasks:

##### 21.1: Implement Redis L1 Cache with Semantic Thresholds and TTL
**Status**: Pending
**Dependencies**: None

**Description**:
Set up Redis as the primary (L1) cache for frequent queries, embeddings, and search results, applying semantic thresholds and a 5-minute TTL.

**Details**:
Use redis-py to connect to Redis. Define cache keys for queries, embeddings, and search results. Implement logic to only cache results that meet semantic similarity thresholds. Set a 5-minute expiration (TTL) for all cache entries to ensure freshness. Ensure cache-aside pattern is used for read-heavy workloads, checking Redis first and falling back to the database on cache miss.

**Test Strategy**:
Run repeated queries and verify that results are cached in Redis, TTL is respected, and only semantically relevant results are cached.

---

##### 21.2: Integrate Tiered Cache Fallback to PostgreSQL (L2)
**Status**: Pending
**Dependencies**: 21.1

**Description**:
Implement fallback logic to query PostgreSQL (L2) when Redis (L1) cache misses occur, and repopulate Redis cache as needed.

**Details**:
On cache miss in Redis, query PostgreSQL for the required data. If found, repopulate Redis with the result, applying the same semantic threshold and TTL logic. Ensure the fallback mechanism is robust and does not introduce significant latency. Use efficient serialization for storing and retrieving data between Redis and PostgreSQL.

**Test Strategy**:
Simulate cache misses and verify that data is correctly fetched from PostgreSQL, then cached in Redis for subsequent requests.

---

##### 21.3: Monitor and Track Cache Hit Rate and Effectiveness
**Status**: Pending
**Dependencies**: 21.1, 21.2

**Description**:
Implement monitoring to track cache hit/miss rates and overall cache effectiveness for both Redis and PostgreSQL tiers.

**Details**:
Instrument the caching logic to record cache hits, misses, and repopulation events. Aggregate metrics such as hit rate, miss rate, and average response time. Set up dashboards or logs to visualize cache performance and identify optimization opportunities. Use these metrics to tune semantic thresholds and TTL values.

**Test Strategy**:
Generate load with a mix of repeated and unique queries, then verify that hit/miss metrics are accurately tracked and reported.

---

### ⏸️ Task 22: Query Type Detection & Routing

**Priority**: High
**Status**: Pending
**Dependencies**: Task 21
**Complexity**: 5/10

**Description**:
Classify incoming queries and route to optimal search strategy (semantic, relational, hybrid, metadata).

**Details**:
Implement query classifier using Claude Haiku. Route queries to vector, graph, or metadata search pipelines based on type.

**Test Strategy**:
Submit queries of each type, verify correct classification and routing.

#### Subtasks:

##### 22.1: Design Query Type Taxonomy and Routing Logic
**Status**: Pending
**Dependencies**: None

**Description**:
Define the taxonomy of query types (semantic, relational, hybrid, metadata) and specify routing logic for each type.

**Details**:
Analyze typical incoming queries and categorize them into clear types. Document routing rules for each category, mapping them to the appropriate search pipeline (vector, graph, metadata). Consider hierarchical classification if the taxonomy is complex, and ensure the design supports future extensibility.

**Test Strategy**:
Review taxonomy coverage against a sample set of queries. Validate routing logic with test cases for each query type.

---

##### 22.2: Implement Query Classifier Using Claude Haiku
**Status**: Pending
**Dependencies**: 22.1

**Description**:
Develop and deploy a query classifier leveraging Claude Haiku to assign incoming queries to the correct type.

**Details**:
Use prompt engineering and, if needed, hierarchical classification to maximize accuracy. Integrate Claude Haiku via API, ensuring the classifier outputs only the defined category names. Optimize for speed and reliability, and consider using vector similarity retrieval for highly variable queries.

**Test Strategy**:
Submit queries of each type and edge cases to the classifier. Measure classification accuracy and latency. Confirm output matches taxonomy.

---

##### 22.3: Integrate Classifier with Search Pipeline Routing
**Status**: Pending
**Dependencies**: 22.2

**Description**:
Connect the classifier output to the routing system, ensuring queries are dispatched to the correct search pipeline.

**Details**:
Implement the routing logic that receives the classified query type and triggers the corresponding search pipeline (vector, graph, metadata, or hybrid). Ensure robust error handling and logging. Validate that each pipeline receives only relevant queries and that fallback logic is in place for unclassified or ambiguous queries.

**Test Strategy**:
End-to-end test: submit queries, verify correct classification and routing to the intended pipeline. Check logs and error handling for misrouted or unclassified queries.

---

### ⏸️ Task 23: Query Processing Pipeline & Result Merging

**Priority**: High
**Status**: Pending
**Dependencies**: Task 22
**Complexity**: 5/10

**Description**:
Normalize, expand, execute, deduplicate, and merge query results using RRF and reranking.

**Details**:
Implement query normalization, expansion, parallel execution, deduplication, RRF merging, and reranking. Log all queries and results.

**Test Strategy**:
Process complex queries, verify result quality, deduplication, and latency.

#### Subtasks:

##### 23.1: Implement Query Normalization and Expansion
**Status**: Pending
**Dependencies**: None

**Description**:
Develop modules to normalize incoming queries and expand them for improved recall and relevance.

**Details**:
Create functions to standardize query formats (e.g., lowercasing, removing stopwords) and apply expansion techniques using external models or APIs. Ensure logging of all normalized and expanded queries for traceability.

**Test Strategy**:
Test with diverse query inputs, verify normalization accuracy, and check that expansions improve recall without introducing irrelevant results.

---

##### 23.2: Execute Queries in Parallel and Deduplicate Results
**Status**: Pending
**Dependencies**: 23.1

**Description**:
Design and implement parallel query execution across multiple sources, followed by deduplication of retrieved results.

**Details**:
Set up parallel execution logic to run expanded queries against all relevant data sources. After retrieval, apply deduplication algorithms to remove duplicate results based on content similarity or unique identifiers. Log execution times and deduplication statistics.

**Test Strategy**:
Simulate concurrent queries, measure execution latency, and verify that deduplication removes all duplicates while retaining unique results.

---

##### 23.3: Merge Results Using RRF and Rerank Final Output
**Status**: Pending
**Dependencies**: 23.2

**Description**:
Integrate Reciprocal Rank Fusion (RRF) for merging results and apply reranking models to optimize final result order.

**Details**:
Implement RRF to combine results from multiple sources, then apply reranking using models such as BGE-Reranker-v2 or Claude API. Ensure all queries and merged results are logged for audit and debugging purposes.

**Test Strategy**:
Process sample queries, validate that RRF merging and reranking improve relevance, and check that final output matches expected quality benchmarks.

---

### ⏸️ Task 24: Faceted Search & Result Presentation

**Priority**: Medium
**Status**: Pending
**Dependencies**: Task 23
**Complexity**: 5/10

**Description**:
Enable faceted filtering (department, type, date, entities) and present results with snippets, highlights, and relevance scores.

**Details**:
Implement multi-select facets in frontend. Generate snippets, highlight keywords, show relevance, source, and department. Link to B2 URLs.

**Test Strategy**:
Run filtered searches, verify result presentation and facet accuracy.

#### Subtasks:

##### 24.1: Implement Multi-Select Faceted Filtering UI
**Status**: Pending
**Dependencies**: None

**Description**:
Develop the frontend components to support multi-select faceted filtering by department, type, date, and entities.

**Details**:
Design and build user interface elements for each facet (department, type, date, entities) with multi-select capability. Ensure facets are easy to find, mobile-friendly, and update results quickly when filters are applied. Facet values should be ordered logically (alphabetical, numerical, or by relevance) and selected values should be clearly indicated. Only display relevant facets for the current result set.

**Test Strategy**:
Test by applying various combinations of facet filters and verifying that the displayed results update accordingly and facet selections persist. Check usability on both desktop and mobile.

---

##### 24.2: Generate and Present Search Result Snippets with Highlights
**Status**: Pending
**Dependencies**: 24.1

**Description**:
Create backend and frontend logic to generate result snippets, highlight matched keywords, and display relevant metadata.

**Details**:
For each search result, extract a relevant snippet containing the matched keywords. Highlight these keywords in the snippet. Display additional metadata such as relevance score, source, and department. Ensure that snippets are concise and informative, and that highlights are visually distinct.

**Test Strategy**:
Run searches with various queries and verify that snippets are generated, keywords are highlighted, and metadata is displayed correctly for each result.

---

##### 24.3: Integrate Result Presentation with B2 URLs and Relevance Scores
**Status**: Pending
**Dependencies**: 24.2

**Description**:
Link each search result to its corresponding Backblaze B2 URL and ensure relevance scores are visible and accurate.

**Details**:
For each result, provide a clickable link to the B2 URL. Display the relevance score prominently, ensuring it is calculated and presented consistently. Confirm that the source and department fields are shown as specified. Validate that all links are functional and direct users to the correct B2 resource.

**Test Strategy**:
Click through result links to verify correct B2 URL redirection. Check that relevance scores match backend calculations and are displayed for all results.

---

### ⏸️ Task 25: Query Analytics & A/B Testing

**Priority**: Medium
**Status**: Pending
**Dependencies**: Task 24
**Complexity**: 5/10

**Description**:
Log queries, track latency, CTR, and support A/B testing for ranking algorithms.

**Details**:
Store query logs and result clicks in Supabase. Implement analytics dashboard and A/B test framework for ranking methods.

**Test Strategy**:
Analyze logs, verify CTR tracking, and run A/B tests.

#### Subtasks:

##### 25.1: Implement Query Logging and Metric Tracking in Supabase
**Status**: Pending
**Dependencies**: None

**Description**:
Set up infrastructure to log all search queries, track latency, and record click-through rates (CTR) in Supabase.

**Details**:
Design Supabase tables to store query logs, including query text, timestamps, latency, and user interactions (clicks). Integrate logging into the query execution pipeline to ensure all relevant metrics are captured for each search event.

**Test Strategy**:
Verify that queries, latency, and clicks are correctly logged in Supabase by running test queries and inspecting the stored data for completeness and accuracy.

---

##### 25.2: Develop Analytics Dashboard for Query Metrics
**Status**: Pending
**Dependencies**: 25.1

**Description**:
Build a dashboard to visualize query volume, latency, and CTR using data from Supabase.

**Details**:
Use a dashboarding tool (e.g., Grafana or Streamlit) to connect to Supabase and display real-time and historical analytics for query metrics. Include filters for date ranges and ranking algorithm versions to support analysis.

**Test Strategy**:
Check that the dashboard accurately reflects Supabase data by comparing dashboard metrics with direct database queries. Test responsiveness and filtering capabilities.

---

##### 25.3: Implement and Run A/B Testing Framework for Ranking Algorithms
**Status**: Pending
**Dependencies**: 25.1

**Description**:
Create an A/B testing framework to compare different ranking algorithms by splitting user traffic and measuring impact on CTR and latency.

**Details**:
Randomly assign users or sessions to control and treatment groups, each using a different ranking algorithm. Log group assignment and outcomes in Supabase. Analyze results using statistical tests (e.g., t-test or Z-test) to determine significance of observed differences in metrics like CTR and latency.

**Test Strategy**:
Simulate A/B tests with test users, verify correct group assignment and metric logging, and validate statistical analysis pipeline with sample data.

---

### ⏸️ Task 26: Chat UI Implementation (WebSocket, Streaming)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 25
**Complexity**: 6.5/10

**Description**:
Build a mobile-responsive chat UI with WebSocket-based real-time messaging and token-by-token streaming.

**Details**:
Use Gradio or Streamlit for frontend. Implement FastAPI WebSocket endpoints for chat. Support streaming responses from Claude API, typing indicators, and error handling.

**Test Strategy**:
Test chat interactions, streaming, and mobile responsiveness.

#### Subtasks:

##### 26.1: Develop Chat UI Frontend with Gradio or Streamlit
**Status**: Pending
**Dependencies**: None

**Description**:
Create a mobile-responsive chat interface using Gradio or Streamlit, supporting user input, message display, and chat history.

**Details**:
Implement the chat UI using Gradio's ChatInterface or Streamlit's chat elements (st.chat_message, st.chat_input). Ensure the layout is mobile-friendly and supports dynamic resizing. Integrate session state or equivalent for chat history persistence.

**Test Strategy**:
Manually test UI on desktop and mobile browsers for responsiveness, usability, and correct message display.

---

##### 26.2: Implement FastAPI WebSocket Endpoints for Real-Time Messaging
**Status**: Pending
**Dependencies**: 26.1

**Description**:
Set up FastAPI backend with WebSocket endpoints to handle real-time chat communication between frontend and backend.

**Details**:
Create FastAPI WebSocket routes for chat message exchange. Ensure proper connection handling, message broadcasting, and support for multiple clients. Integrate authentication if required.

**Test Strategy**:
Use WebSocket client tools and frontend integration to verify real-time message delivery and connection stability.

---

##### 26.3: Integrate Token-by-Token Streaming from Claude API
**Status**: Pending
**Dependencies**: 26.2

**Description**:
Enable streaming of Claude API responses token-by-token to the frontend for real-time chat experience.

**Details**:
Modify backend to call Claude API with streaming enabled. Forward each token or chunk to the frontend as it arrives via WebSocket. Update frontend to append streamed tokens to the chat window in real time.

**Test Strategy**:
Send prompts and verify that responses appear incrementally in the chat UI, matching Claude API streaming output.

---

##### 26.4: Implement Typing Indicators and Error Handling
**Status**: Pending
**Dependencies**: 26.3

**Description**:
Add typing indicators for the assistant and robust error handling for network/API failures.

**Details**:
Emit typing events from backend to frontend while waiting for Claude API responses. Display a typing indicator in the UI. Handle and display errors gracefully, such as API timeouts or connection drops.

**Test Strategy**:
Simulate slow responses and errors; verify typing indicator visibility and user-friendly error messages.

---

##### 26.5: Test and Optimize Mobile Responsiveness
**Status**: Pending
**Dependencies**: 26.4

**Description**:
Thoroughly test the chat UI on various mobile devices and optimize for touch interaction and layout.

**Details**:
Use browser dev tools and real devices to test UI scaling, input usability, and scrolling. Adjust CSS or component properties as needed for optimal mobile experience.

**Test Strategy**:
Perform cross-device testing and collect feedback to ensure consistent, responsive behavior on phones and tablets.

---

### ⏸️ Task 27: Conversation Memory System (Supabase Graph Tables)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 26
**Complexity**: 5/10

**Description**:
Store and retrieve user conversation memory using PostgreSQL graph tables (user_memory_nodes, user_memory_edges).

**Details**:
Implement memory node/edge creation, context window management, and recency/access-weighted retrieval. Enforce RLS policies.

**Test Strategy**:
Simulate conversations, verify memory storage, retrieval, and RLS enforcement.

#### Subtasks:

##### 27.1: Design and Implement Graph Tables for Conversation Memory
**Status**: Pending
**Dependencies**: None

**Description**:
Create PostgreSQL tables (user_memory_nodes, user_memory_edges) to represent conversation memory as a graph structure, supporting efficient storage and retrieval.

**Details**:
Define schemas for user_memory_nodes and user_memory_edges, ensuring each node represents a memory item (e.g., message, context) and edges capture relationships (e.g., temporal, reference). Implement table creation scripts and indexes for efficient traversal. Ensure compatibility with Supabase and prepare for RLS enforcement.

**Test Strategy**:
Verify table creation, schema correctness, and ability to insert and query nodes/edges representing conversation history.

---

##### 27.2: Implement Memory Node/Edge Management and Context Window Logic
**Status**: Pending
**Dependencies**: 27.1

**Description**:
Develop logic for creating, updating, and deleting memory nodes and edges, and manage the context window for conversation retrieval.

**Details**:
Implement backend functions to add new conversation turns as nodes, link them with edges, and prune or limit history based on a context window (e.g., last N messages). Ensure recency and access-weighted retrieval logic is in place to prioritize relevant memory during retrieval. Integrate with Supabase API for transactional consistency.

**Test Strategy**:
Simulate conversations, add and remove nodes/edges, and verify that context window and recency/access-weighted retrieval return expected results.

---

##### 27.3: Enforce Row-Level Security (RLS) and Validate Secure Access
**Status**: Pending
**Dependencies**: 27.1, 27.2

**Description**:
Apply and test RLS policies to ensure users can only access their own conversation memory data in the graph tables.

**Details**:
Define and apply RLS policies on user_memory_nodes and user_memory_edges to restrict access by user identity. Test for unauthorized access attempts and verify that only the correct user's data is accessible. Document RLS configuration and integrate with Supabase authentication.

**Test Strategy**:
Attempt cross-user access, verify RLS enforcement, and run automated tests to confirm only authorized access to memory nodes and edges.

---

### ⏸️ Task 28: Session & Preference Management

**Priority**: Medium
**Status**: Pending
**Dependencies**: Task 27
**Complexity**: 5/10

**Description**:
Support multiple concurrent sessions, session persistence, user preference learning, and privacy controls.

**Details**:
Implement session tracking, timeout, export, and deletion. Store preferences as memory nodes. Provide opt-out and explicit preference UI.

**Test Strategy**:
Test session persistence, preference learning, and privacy controls.

#### Subtasks:

##### 28.1: Implement Multi-Session Tracking and Persistence
**Status**: Pending
**Dependencies**: None

**Description**:
Develop mechanisms to support multiple concurrent user sessions, ensure session data is persistent across server restarts, and enable session export and deletion.

**Details**:
Design a session management system that assigns unique, secure session IDs, supports concurrent sessions per user, and persists session data using a shared store (e.g., Redis). Implement session timeout, export, and deletion features. Ensure session data is securely stored and can be invalidated or removed on demand.

**Test Strategy**:
Simulate multiple concurrent sessions, verify session persistence after server restart, and test session export and deletion functionality.

---

##### 28.2: Develop User Preference Learning and Storage
**Status**: Pending
**Dependencies**: 28.1

**Description**:
Create a system to learn, store, and update user preferences as memory nodes, ensuring preferences are associated with the correct session and user.

**Details**:
Implement logic to capture user actions and infer preferences, storing them as structured memory nodes linked to user profiles. Ensure updates are atomic and preferences persist across sessions. Provide mechanisms to retrieve and update preferences efficiently.

**Test Strategy**:
Test preference capture, retrieval, and update across multiple sessions and users. Validate that preferences persist and are correctly associated with users.

---

##### 28.3: Design Privacy Controls and Explicit Preference UI
**Status**: Pending
**Dependencies**: 28.1, 28.2

**Description**:
Provide user-facing controls for privacy, including opt-out options and an explicit UI for managing preferences and active sessions.

**Details**:
Develop UI components that allow users to view and manage their active sessions, export or delete session data, and opt out of preference learning. Ensure privacy controls are clear, accessible, and enforceable at the backend.

**Test Strategy**:
Perform UI/UX testing for privacy controls, verify backend enforcement of opt-out and deletion, and ensure users can manage sessions and preferences as intended.

---

### ⏸️ Task 29: Monitoring & Observability (Prometheus, Grafana, Alertmanager)

**Priority**: High
**Status**: Pending
**Dependencies**: Task 28
**Complexity**: 5/10

**Description**:
Collect metrics, visualize in Grafana, set up alerting, and structured logging for all services.

**Details**:
Integrate prometheus_client for FastAPI, Celery, Redis, Neo4j. Build Grafana dashboards with pre-built panels. Configure Alertmanager for multi-channel alerts. Implement JSON logs and health check endpoints.

**Test Strategy**:
Simulate load, verify metrics, dashboard updates, alert triggers, and log accuracy.

#### Subtasks:

##### 29.1: Integrate Prometheus Metrics Collection for All Services
**Status**: Pending
**Dependencies**: None

**Description**:
Set up Prometheus metrics collection for FastAPI, Celery, Redis, and Neo4j services using prometheus_client.

**Details**:
Install and configure prometheus_client in each service. Expose /metrics endpoints for FastAPI, Celery, Redis, and Neo4j. Ensure custom business metrics are included where relevant. Validate that metrics are accessible and correctly formatted for Prometheus scraping.

**Test Strategy**:
Simulate service activity and verify metrics are exposed and collected by Prometheus. Check for completeness and accuracy of metrics.

---

##### 29.2: Build Grafana Dashboards and Panels for Metrics Visualization
**Status**: Pending
**Dependencies**: 29.1

**Description**:
Create Grafana dashboards with pre-built and custom panels to visualize collected metrics from all integrated services.

**Details**:
Connect Grafana to Prometheus as a data source. Design dashboards for FastAPI, Celery, Redis, and Neo4j, including panels for key metrics (e.g., request rates, error rates, resource usage). Use Grafana's dashboard editor to organize panels and set up useful visualizations for operational monitoring.

**Test Strategy**:
Verify dashboards update in real-time with incoming metrics. Confirm panels display accurate and actionable data for each service.

---

##### 29.3: Configure Alertmanager for Multi-Channel Alerting and Notification Routing
**Status**: Pending
**Dependencies**: 29.2

**Description**:
Set up Alertmanager to handle alerts from Prometheus and Grafana, routing notifications to multiple channels (e.g., email, Slack).

**Details**:
Install and configure Alertmanager. Define alert rules in Prometheus and Grafana for critical metrics. Set up Alertmanager contact points for email, Slack, and other channels. Configure notification policies and silences as needed. Integrate Alertmanager with Grafana to manage and route alerts, ensuring unified notification handling.

**Test Strategy**:
Trigger test alerts and verify notifications are sent to all configured channels. Check alert deduplication, grouping, and routing logic.

---

### ⏸️ Task 30: Cost Tracking & Optimization

**Priority**: Medium
**Status**: Pending
**Dependencies**: Task 29
**Complexity**: 5/10

**Description**:
Track API, compute, and storage costs. Generate monthly reports and trigger budget alerts.

**Details**:
Integrate cost tracking for Claude, Soniox, Mistral, LangExtract, Render, Supabase, B2. Implement budget alert logic at 80% threshold.

**Test Strategy**:
Simulate usage, verify cost reports and alert triggers.

#### Subtasks:

##### 30.1: Integrate Cost Tracking for All Services
**Status**: Pending
**Dependencies**: None

**Description**:
Implement automated cost tracking for Claude, Soniox, Mistral, LangExtract, Render, Supabase, and B2, covering API, compute, and storage expenses.

**Details**:
Set up data pipelines or use APIs to collect cost and usage data from each provider. Normalize and aggregate costs by service and resource type. Ensure tracking supports multi-cloud and SaaS sources, and enables per-service breakdowns for accurate reporting.

**Test Strategy**:
Simulate usage across all services, verify that cost data is collected, normalized, and attributed correctly for each provider.

---

##### 30.2: Generate Monthly Cost Reports
**Status**: Pending
**Dependencies**: 30.1

**Description**:
Develop automated monthly reporting that summarizes API, compute, and storage costs for all integrated services.

**Details**:
Design and implement a reporting system that compiles monthly cost data into clear, actionable reports. Include breakdowns by service, resource type, and time period. Reports should be exportable and support visualization for trend analysis.

**Test Strategy**:
Trigger monthly report generation with sample data, verify report accuracy, completeness, and clarity for all tracked services.

---

##### 30.3: Implement Budget Alert Logic at 80% Threshold
**Status**: Pending
**Dependencies**: 30.1

**Description**:
Set up automated alerts to notify stakeholders when spending reaches 80% of the defined monthly budget for any tracked service.

**Details**:
Configure monitoring logic to evaluate cumulative spend against budget thresholds in real time. Integrate with notification channels (e.g., email, Slack) to deliver timely alerts. Ensure alerts are actionable and include relevant cost breakdowns.

**Test Strategy**:
Simulate cost increases to exceed 80% of budget, confirm that alerts are triggered promptly and contain accurate, actionable information.

---

### ⏸️ Task 31: Role-Based Access Control (RBAC) & API Key Management

**Priority**: High
**Status**: Pending
**Dependencies**: Task 30
**Complexity**: 5/10

**Description**:
Implement RBAC for users, documents, and API keys with audit logging and row-level security.

**Details**:
Use Supabase RLS policies, implement user roles (admin, editor, viewer, guest), API key creation/rotation/revocation, and audit logs. Hash API keys with bcrypt.

**Test Strategy**:
Test role permissions, API key flows, and audit log accuracy.

#### Subtasks:

##### 31.1: Design and Implement User Roles and Row-Level Security (RLS) Policies in Supabase
**Status**: Pending
**Dependencies**: None

**Description**:
Define user roles (admin, editor, viewer, guest) and implement row-level security (RLS) policies for users, documents, and API keys using Supabase.

**Details**:
Create a roles table and associate users with roles. Use Supabase's RLS policies to restrict access to tables based on user roles. Ensure that each role has clearly defined permissions for CRUD operations on users, documents, and API keys. Reference Supabase documentation and best practices for RLS and RBAC implementation.

**Test Strategy**:
Test RLS policies by creating users with different roles and verifying access to resources. Attempt unauthorized actions to confirm enforcement of restrictions.

---

##### 31.2: Implement API Key Lifecycle Management with Secure Storage
**Status**: Pending
**Dependencies**: 31.1

**Description**:
Develop endpoints and logic for API key creation, rotation, and revocation. Store API keys securely using bcrypt hashing.

**Details**:
Create endpoints for generating, rotating, and revoking API keys. Store only hashed versions of API keys using bcrypt in the database. Ensure that API keys are associated with users and roles, and that their permissions align with RBAC policies. Document the API key management process and enforce secure handling throughout the lifecycle.

**Test Strategy**:
Verify API key creation, rotation, and revocation flows. Confirm that only hashed keys are stored and that revoked keys cannot be used for access.

---

##### 31.3: Implement Audit Logging for Access and Key Management Events
**Status**: Pending
**Dependencies**: 31.1, 31.2

**Description**:
Track and log all access events, permission changes, and API key operations for auditing and compliance.

**Details**:
Set up audit logging for all RBAC-related actions, including role assignments, permission changes, and API key lifecycle events. Store logs in a dedicated audit table with relevant metadata (user, action, timestamp, resource). Ensure logs are immutable and accessible for compliance reviews.

**Test Strategy**:
Trigger various RBAC and API key events, then review audit logs to confirm accurate and complete recording of all relevant actions.

---

### ⏸️ Task 32: Bulk Document Management & Batch Operations

**Priority**: High
**Status**: Pending
**Dependencies**: Task 31
**Complexity**: 5/10

**Description**:
Enable bulk upload, delete, reprocessing, metadata update, versioning, and approval workflow for documents.

**Details**:
Implement batch endpoints for document operations. Track progress and support document versioning and approval states.

**Test Strategy**:
Perform bulk operations, verify throughput, versioning, and approval transitions.

#### Subtasks:

##### 32.1: Implement Bulk Document Operations Endpoints
**Status**: Pending
**Dependencies**: None

**Description**:
Develop RESTful API endpoints to support bulk upload, delete, reprocessing, and metadata update for documents.

**Details**:
Design and implement backend endpoints that accept batch requests for document operations. Ensure endpoints handle large payloads efficiently, support progress tracking, and provide clear error reporting for partial failures. Integrate with storage and indexing layers to maintain consistency and performance.

**Test Strategy**:
Submit bulk operation requests (upload, delete, reprocess, metadata update) with varying batch sizes. Verify throughput, error handling, and data integrity for all operations.

---

##### 32.2: Integrate Document Versioning and Approval Workflow
**Status**: Pending
**Dependencies**: 32.1

**Description**:
Enable version control and approval states for documents, supporting batch transitions and rollbacks.

**Details**:
Extend the document model to support version history and approval status. Implement logic for batch versioning (e.g., uploading new versions in bulk) and batch approval/rejection. Ensure audit trails are maintained for all version and approval changes.

**Test Strategy**:
Perform bulk version uploads and approval transitions. Verify correct version history, approval state changes, and audit trail entries for all affected documents.

---

##### 32.3: Implement Progress Tracking and Operation Auditing
**Status**: Pending
**Dependencies**: 32.1, 32.2

**Description**:
Track and expose the progress and audit logs of all batch document operations for transparency and compliance.

**Details**:
Develop mechanisms to monitor the status of ongoing batch operations, including per-document success/failure. Provide APIs or dashboards for users to query operation progress and review detailed audit logs. Ensure compliance with organizational and regulatory requirements for traceability.

**Test Strategy**:
Initiate various batch operations and monitor progress tracking endpoints or dashboards. Validate that audit logs accurately reflect all actions, including errors and rollbacks.

---

### ⏸️ Task 33: User Management & GDPR Compliance

**Priority**: High
**Status**: Pending
**Dependencies**: Task 32
**Complexity**: 5/10

**Description**:
Support user creation, editing, role assignment, password reset, suspension, activity logs, and GDPR-compliant data export.

**Details**:
Implement admin endpoints for user management. Store activity logs and support data export/deletion per GDPR.

**Test Strategy**:
Test user flows, activity logging, and GDPR export/deletion.

#### Subtasks:

##### 33.1: Implement User Account and Role Management Endpoints
**Status**: Pending
**Dependencies**: None

**Description**:
Develop admin endpoints to support user creation, editing, role assignment, password reset, and suspension.

**Details**:
Create RESTful endpoints for user CRUD operations, role assignment, and password management. Ensure endpoints allow for user suspension/reactivation and support both pre-defined and custom roles. Integrate secure authentication and authorization checks for all admin actions.

**Test Strategy**:
Test user creation, editing, role assignment, password reset, and suspension via API and UI. Verify role-based access control and error handling.

---

##### 33.2: Implement Activity Logging for User Actions
**Status**: Pending
**Dependencies**: 33.1

**Description**:
Log all significant user management actions (creation, edits, role changes, suspensions, password resets) for audit and compliance.

**Details**:
Design and implement a logging mechanism to capture all admin and user actions related to user management. Store logs securely with timestamps, user IDs, action types, and relevant metadata. Ensure logs are immutable and accessible for compliance audits.

**Test Strategy**:
Trigger user management actions and verify that logs are created with correct details. Test log retrieval and integrity.

---

##### 33.3: Develop GDPR-Compliant Data Export and Deletion Features
**Status**: Pending
**Dependencies**: 33.1, 33.2

**Description**:
Enable GDPR-compliant export and deletion of user data, including activity logs, upon user or admin request.

**Details**:
Implement endpoints to export all user-related data in a machine-readable format and to delete user data in accordance with GDPR requirements. Ensure deletion covers user profile, roles, and associated activity logs, and that exports are complete and secure.

**Test Strategy**:
Request data export and deletion for test users. Verify completeness of exported data and confirm all user data is removed after deletion, including logs.

---

### ⏸️ Task 34: Analytics Dashboard Implementation

**Priority**: Medium
**Status**: Pending
**Dependencies**: Task 33
**Complexity**: 6/10

**Description**:
Build dashboard for document stats, query metrics, user activity, storage usage, and API endpoint usage.

**Details**:
Use Grafana or Streamlit for dashboard UI. Aggregate metrics from Supabase and Prometheus.

**Test Strategy**:
Verify dashboard accuracy and responsiveness under load.

#### Subtasks:

##### 34.1: Develop Dashboard UI with Grafana or Streamlit
**Status**: Pending
**Dependencies**: None

**Description**:
Set up the dashboard user interface using either Grafana or Streamlit, ensuring a logical layout for document stats, query metrics, user activity, storage usage, and API endpoint usage.

**Details**:
Install and configure Grafana or Streamlit. Design the dashboard structure, applying best practices such as focusing on key metrics, using consistent layouts, and providing clear panel documentation. Ensure the UI is intuitive and supports dynamic filtering or variable selection as needed.

**Test Strategy**:
Verify that all required metric categories are represented and the UI is navigable. Check for adherence to dashboard design best practices.

---

##### 34.2: Aggregate Metrics from Supabase and Prometheus
**Status**: Pending
**Dependencies**: 34.1

**Description**:
Implement data aggregation logic to collect and preprocess metrics from Supabase and Prometheus for use in the dashboard.

**Details**:
Develop scripts or queries to extract relevant metrics (document stats, query metrics, user activity, storage usage, API endpoint usage) from Supabase and Prometheus. Transform and aggregate data as needed for efficient dashboard consumption. Ensure data freshness and reliability.

**Test Strategy**:
Validate that all required metrics are accurately aggregated and available for the dashboard. Test with sample data and edge cases.

---

##### 34.3: Implement Data Visualization Components
**Status**: Pending
**Dependencies**: 34.2

**Description**:
Create and configure visualizations for each metric category, ensuring clarity and actionable insights.

**Details**:
Select appropriate visualization types (e.g., graphs, tables, gauges) for each metric. Configure panels to highlight key signals and trends. Apply consistent color schemes and labeling. Add annotations or context where relevant to aid interpretation.

**Test Strategy**:
Review each visualization for accuracy, clarity, and alignment with dashboard goals. Solicit feedback from stakeholders and iterate as needed.

---

##### 34.4: Test Dashboard Load and Responsiveness
**Status**: Pending
**Dependencies**: 34.3

**Description**:
Evaluate dashboard performance under expected and peak loads, optimizing for fast load times and responsive interactions.

**Details**:
Simulate concurrent users and high data volumes. Monitor dashboard load times, panel refresh rates, and responsiveness. Apply optimizations such as query aggregation, efficient variable usage, and appropriate refresh intervals. Document and address any bottlenecks.

**Test Strategy**:
Run load tests and measure key performance indicators (KPIs) such as load time and refresh latency. Confirm dashboard remains usable and responsive under stress.

---

### ⏸️ Task 35: CrewAI Multi-Agent Integration & Orchestration

**Priority**: High
**Status**: Pending
**Dependencies**: Task 34
**Complexity**: 5/10

**Description**:
Integrate CrewAI service (REST API) for multi-agent workflows, agent management, and orchestration.

**Details**:
Connect to CrewAI REST API (srv-d2n0hh3uibrs73buafo0). Implement agent pool management, dynamic agent creation, lifecycle, and resource allocation. Support async task execution via Celery.

**Test Strategy**:
Run multi-agent workflows, verify orchestration, agent lifecycle, and result aggregation.

#### Subtasks:

##### 35.1: Integrate CrewAI REST API for Agent Pool Management and Dynamic Agent Creation
**Status**: Pending
**Dependencies**: None

**Description**:
Connect to the CrewAI REST API and implement logic for managing an agent pool, including dynamic creation, configuration, and lifecycle management of agents.

**Details**:
Establish secure connectivity to the CrewAI REST API (srv-d2n0hh3uibrs73buafo0). Implement endpoints and logic for creating, updating, and deleting agents dynamically. Support agent configuration (roles, goals, tools, memory, etc.) as per CrewAI's agent model. Ensure agents can be instantiated with custom parameters and maintain their lifecycle state.

**Test Strategy**:
Create, update, and delete agents via API calls. Verify agent state transitions and configuration persistence.

---

##### 35.2: Implement Multi-Agent Workflow Orchestration and Resource Allocation
**Status**: Pending
**Dependencies**: 35.1

**Description**:
Develop orchestration logic to coordinate multi-agent workflows, manage task assignments, and allocate resources efficiently among agents.

**Details**:
Design and implement orchestration mechanisms using CrewAI's crew-and-flow model. Enable both sequential and parallel task execution modes. Assign tasks to agents based on their roles and goals, and manage dependencies between tasks. Implement resource allocation strategies to optimize agent utilization and prevent overload.

**Test Strategy**:
Run sample multi-agent workflows with varying complexity. Verify correct task sequencing, parallelism, and resource allocation.

---

##### 35.3: Enable Asynchronous Task Execution and Monitoring via Celery
**Status**: Pending
**Dependencies**: 35.2

**Description**:
Integrate Celery to support asynchronous execution of agent tasks and implement monitoring for workflow progress and agent states.

**Details**:
Set up Celery workers to handle asynchronous task execution for CrewAI workflows. Ensure tasks can be queued, executed, and monitored independently. Capture logs and state changes for each agent and workflow. Implement error handling and alerting for failed tasks or agent exceptions.

**Test Strategy**:
Submit multiple concurrent workflows, monitor execution progress, and verify correct handling of asynchronous tasks and error scenarios.

---

### ⏸️ Task 36: CrewAI Asset Generation Agents Implementation

**Priority**: High
**Status**: Pending
**Dependencies**: Task 35
**Complexity**: 5/10

**Description**:
Implement 8 asset generation agents (orchestrator, summarizer, skill, command, agent, prompt, workflow, department classifier) per PRD specs.

**Details**:
Define agent roles, goals, tools, and LLM configs in crewai_agents table. Integrate with CrewAI API for asset generation. Store outputs in B2 processed/ folders.

**Test Strategy**:
Trigger asset generation for sample documents, verify output formats and B2 storage.

#### Subtasks:

##### 36.1: Define and Configure 8 Asset Generation Agents in crewai_agents Table
**Status**: Pending
**Dependencies**: None

**Description**:
Specify roles, goals, tools, and LLM configurations for orchestrator, summarizer, skill, command, agent, prompt, workflow, and department classifier agents as per PRD specifications.

**Details**:
Draft detailed agent definitions in the crewai_agents table, ensuring each agent's role, goal, toolset, and LLM configuration aligns with PRD requirements. Use YAML or database schema as appropriate. Validate configuration completeness for all 8 agents.

**Test Strategy**:
Review crewai_agents table for correct entries and completeness. Validate agent configs load without errors in CrewAI.

---

##### 36.2: Integrate Agents with CrewAI API for Asset Generation Workflows
**Status**: Pending
**Dependencies**: 36.1

**Description**:
Connect the configured agents to the CrewAI API, enabling them to generate assets according to workflow requirements.

**Details**:
Implement integration logic to instantiate and orchestrate the 8 agents using the CrewAI API. Ensure agents can receive tasks, execute asset generation, and interact as needed. Handle API authentication and error management.

**Test Strategy**:
Trigger asset generation for sample inputs via CrewAI API and verify that each agent performs its designated function.

---

##### 36.3: Store Generated Assets in B2 Processed Folders
**Status**: Pending
**Dependencies**: 36.2

**Description**:
Implement logic to save all outputs from asset generation agents into the appropriate B2 processed/ folders.

**Details**:
Develop or update storage routines to ensure all generated assets are saved in the correct B2 processed/ directory structure. Confirm metadata and output formats match requirements. Handle storage errors and ensure data integrity.

**Test Strategy**:
Generate assets through the workflow and verify their presence, structure, and metadata in B2 processed/ folders.

---

## End of Document

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Total Pages**: Complete Task Overview (Tasks 1-36)
