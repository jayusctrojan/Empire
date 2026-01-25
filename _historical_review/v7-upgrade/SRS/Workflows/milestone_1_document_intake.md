## 10.2 Milestone 1: Document Intake and Classification

### 10.2.1 Objectives
- Set up document intake webhook with proper multipart handling
- Implement comprehensive file validation using Code node
- Create intelligent routing with corrected Switch node syntax
- Store documents in Backblaze B2 with proper metadata
- Log all operations to Supabase for tracking
- Handle errors gracefully with retry logic

### 10.2.2 Complete Workflow JSON - Document Intake

```json
{
  "name": "Document_Intake_Classification_v7_Complete",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "document-upload",
        "responseMode": "onReceived",
        "options": {
          "rawBody": true,
          "binaryPropertyName": "file",
          "responseHeaders": {
            "Access-Control-Allow-Origin": "https://empire-chat.onrender.com",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
          }
        }
      },
      "name": "Document Upload Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [250, 300],
      "id": "webhook_trigger_001",
      "webhookId": "document-upload-v7",
      "notes": "Entry point for all document uploads. Handles multipart/form-data with binary files."
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Comprehensive file validation and metadata extraction\nconst crypto = require('crypto');\nconst path = require('path');\n\n// Configuration\nconst CONFIG = {\n  maxFileSizeMB: 100,\n  allowedMimeTypes: [\n    'application/pdf',\n    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',\n    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',\n    'application/vnd.openxmlformats-officedocument.presentationml.presentation',\n    'text/plain',\n    'text/markdown',\n    'text/html',\n    'text/csv',\n    'application/json',\n    'application/xml',\n    'application/rtf',\n    'application/vnd.oasis.opendocument.text',\n    'application/vnd.oasis.opendocument.spreadsheet',\n    'image/jpeg',\n    'image/png',\n    'image/tiff',\n    'audio/mpeg',\n    'audio/wav',\n    'audio/ogg',\n    'video/mp4',\n    'video/mpeg'\n  ],\n  categoryMapping: {\n    'application/pdf': 'pdf',\n    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'word',\n    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel',\n    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'powerpoint',\n    'text/plain': 'text',\n    'text/markdown': 'markdown',\n    'text/html': 'html',\n    'text/csv': 'csv',\n    'application/json': 'json',\n    'application/xml': 'xml',\n    'image/jpeg': 'image',\n    'image/png': 'image',\n    'image/tiff': 'image',\n    'audio/mpeg': 'audio',\n    'audio/wav': 'audio',\n    'audio/ogg': 'audio',\n    'video/mp4': 'video',\n    'video/mpeg': 'video'\n  },\n  processingPriority: {\n    'pdf': 1,\n    'word': 2,\n    'excel': 3,\n    'powerpoint': 4,\n    'text': 5,\n    'markdown': 5,\n    'csv': 6,\n    'json': 7,\n    'html': 8,\n    'xml': 9,\n    'image': 10,\n    'audio': 11,\n    'video': 12\n  }\n};\n\n// Helper functions\nfunction calculateFileHash(buffer) {\n  return crypto.createHash('sha256')\n    .update(buffer)\n    .digest('hex');\n}\n\nfunction extractMetadata(file, buffer) {\n  const stats = {\n    originalName: file.fileName || 'unnamed_file',\n    mimeType: file.mimeType || 'application/octet-stream',\n    size: buffer.length,\n    sizeMB: (buffer.length / 1048576).toFixed(2),\n    sizeReadable: formatBytes(buffer.length),\n    extension: path.extname(file.fileName || '').toLowerCase().replace('.', ''),\n    uploadTime: new Date().toISOString(),\n    processingPriority: CONFIG.processingPriority[CONFIG.categoryMapping[file.mimeType]] || 99\n  };\n  \n  return stats;\n}\n\nfunction formatBytes(bytes) {\n  if (bytes === 0) return '0 Bytes';\n  const k = 1024;\n  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];\n  const i = Math.floor(Math.log(bytes) / Math.log(k));\n  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];\n}\n\nfunction validateFile(file, buffer) {\n  const errors = [];\n  const warnings = [];\n  \n  // Check if file exists\n  if (!file) {\n    errors.push('No file received in request');\n    return { valid: false, errors, warnings };\n  }\n  \n  // Validate file size\n  const maxSizeBytes = CONFIG.maxFileSizeMB * 1048576;\n  if (buffer.length > maxSizeBytes) {\n    errors.push(`File too large: ${formatBytes(buffer.length)} (max: ${CONFIG.maxFileSizeMB}MB)`);\n  }\n  \n  if (buffer.length === 0) {\n    errors.push('File is empty');\n  }\n  \n  // Validate MIME type\n  const mimeType = file.mimeType || 'application/octet-stream';\n  if (!CONFIG.allowedMimeTypes.includes(mimeType)) {\n    errors.push(`Unsupported file type: ${mimeType}`);\n  }\n  \n  // Check for suspicious patterns\n  const fileName = file.fileName || '';\n  const suspiciousPatterns = [\n    /\\.exe$/i,\n    /\\.dll$/i,\n    /\\.bat$/i,\n    /\\.sh$/i,\n    /\\.cmd$/i,\n    /\\.com$/i,\n    /\\.scr$/i,\n    /\\.vbs$/i,\n    /\\.js$/i,\n    /\\.jar$/i\n  ];\n  \n  for (const pattern of suspiciousPatterns) {\n    if (pattern.test(fileName)) {\n      warnings.push(`Potentially dangerous file extension detected: ${fileName}`);\n    }\n  }\n  \n  // Check filename length\n  if (fileName.length > 255) {\n    warnings.push('Filename exceeds 255 characters');\n  }\n  \n  // Check for special characters in filename\n  if (/[<>:\"|?*\\/\\\\]/.test(fileName)) {\n    warnings.push('Filename contains special characters that may cause issues');\n  }\n  \n  return {\n    valid: errors.length === 0,\n    errors,\n    warnings\n  };\n}\n\nfunction generateStoragePath(hash, fileName, category) {\n  const date = new Date();\n  const year = date.getFullYear();\n  const month = String(date.getMonth() + 1).padStart(2, '0');\n  const day = String(date.getDate()).padStart(2, '0');\n  \n  // Structure: /category/year/month/day/hash/filename\n  const safeName = fileName.replace(/[^a-z0-9._-]/gi, '_');\n  return `${category}/${year}/${month}/${day}/${hash}/${safeName}`;\n}\n\n// Main processing\ntry {\n  // Get file from binary data\n  const file = items[0].binary?.file;\n  if (!file) {\n    throw new Error('No file received in request');\n  }\n  \n  // Convert base64 to buffer\n  const fileBuffer = Buffer.from(file.data, 'base64');\n  \n  // Calculate hash\n  const hash = calculateFileHash(fileBuffer);\n  \n  // Validate file\n  const validation = validateFile(file, fileBuffer);\n  \n  if (!validation.valid) {\n    throw new Error(`File validation failed: ${validation.errors.join(', ')}`);\n  }\n  \n  // Extract metadata\n  const metadata = extractMetadata(file, fileBuffer);\n  \n  // Determine category\n  const category = CONFIG.categoryMapping[metadata.mimeType] || 'other';\n  \n  // Generate storage path\n  const storagePath = generateStoragePath(hash, metadata.originalName, category);\n  \n  // Prepare output\n  const output = {\n    // File identification\n    fileId: hash,\n    hash: hash,\n    \n    // File metadata\n    filename: metadata.originalName,\n    mimeType: metadata.mimeType,\n    size: metadata.size,\n    sizeMB: metadata.sizeMB,\n    sizeReadable: metadata.sizeReadable,\n    extension: metadata.extension,\n    \n    // Processing metadata\n    category: category,\n    processingPriority: metadata.processingPriority,\n    storagePath: storagePath,\n    \n    // Timestamps\n    uploadTime: metadata.uploadTime,\n    processingStartTime: new Date().toISOString(),\n    \n    // Validation results\n    validation: {\n      passed: validation.valid,\n      warnings: validation.warnings,\n      errors: validation.errors\n    },\n    \n    // Processing flags\n    requiresOCR: ['image', 'pdf'].includes(category),\n    requiresTranscription: ['audio', 'video'].includes(category),\n    requiresTextExtraction: ['pdf', 'word', 'powerpoint'].includes(category),\n    requiresStructuredParsing: ['excel', 'csv', 'json', 'xml'].includes(category),\n    \n    // Routing information\n    nextStep: determineNextStep(category),\n    \n    // Additional metadata for specific file types\n    typeSpecificMetadata: extractTypeSpecificMetadata(file, category)\n  };\n  \n  // Return both JSON and binary data\n  return [{\n    json: output,\n    binary: {\n      file: file\n    }\n  }];\n  \n} catch (error) {\n  // Error handling with detailed information\n  return [{\n    json: {\n      error: true,\n      errorMessage: error.message,\n      errorStack: error.stack,\n      timestamp: new Date().toISOString(),\n      requestInfo: {\n        hasFile: !!items[0].binary?.file,\n        itemCount: items.length\n      }\n    }\n  }];\n}\n\n// Helper function to determine next processing step\nfunction determineNextStep(category) {\n  const stepMapping = {\n    'pdf': 'pdf_processing',\n    'word': 'docx_processing',\n    'excel': 'spreadsheet_processing',\n    'powerpoint': 'presentation_processing',\n    'text': 'text_processing',\n    'markdown': 'markdown_processing',\n    'html': 'html_processing',\n    'csv': 'csv_processing',\n    'json': 'json_processing',\n    'xml': 'xml_processing',\n    'image': 'ocr_processing',\n    'audio': 'transcription_processing',\n    'video': 'video_processing',\n    'other': 'generic_processing'\n  };\n  \n  return stepMapping[category] || 'error_handling';\n}\n\n// Extract type-specific metadata\nfunction extractTypeSpecificMetadata(file, category) {\n  const metadata = {};\n  \n  switch(category) {\n    case 'pdf':\n      metadata.estimatedPages = Math.ceil(file.data.length / 3000);\n      metadata.requiresOCR = true;\n      break;\n    case 'excel':\n    case 'csv':\n      metadata.estimatedRows = Math.ceil(file.data.length / 100);\n      metadata.requiresStructuredParsing = true;\n      break;\n    case 'image':\n      metadata.requiresOCR = true;\n      metadata.imageAnalysis = 'pending';\n      break;\n    case 'audio':\n    case 'video':\n      metadata.requiresTranscription = true;\n      metadata.estimatedDuration = 'unknown';\n      break;\n    default:\n      metadata.processingType = 'standard';\n  }\n  \n  return metadata;\n}"
      },
      "name": "Advanced File Validation",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "validate_file_002"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.error }}",
              "value2": "={{ true }}"
            }
          ]
        }
      },
      "name": "Has Validation Error?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [650, 300],
      "id": "check_validation_error_003"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT \n  id, \n  document_id,\n  filename, \n  file_hash,\n  upload_date,\n  processing_status,\n  processing_complete,\n  vector_count,\n  metadata\nFROM documents \nWHERE file_hash = $1 \nLIMIT 1",
        "options": {
          "queryParams": "={{ [$json.hash] }}"
        },
        "continueOnFail": true
      },
      "name": "Check for Duplicates",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [850, 250],
      "id": "check_duplicates_004",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.length > 0 }}",
              "value2": "={{ true }}"
            }
          ]
        }
      },
      "name": "Is Duplicate?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [1050, 250],
      "id": "is_duplicate_005"
    },
    {
      "parameters": {
        "mode": "rules",
        "rules": {
          "values": [
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "pdf"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "pdf_processing",
              "outputName": "PDF Files"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "word"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "word_processing",
              "outputName": "Word Documents"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "excel"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "excel_processing",
              "outputName": "Excel Spreadsheets"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "text"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "text_processing",
              "outputName": "Text Files"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "csv"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "csv_processing",
              "outputName": "CSV Files"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "json"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "json_processing",
              "outputName": "JSON Files"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "image"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "image_processing",
              "outputName": "Image Files"
            },
            {
              "conditions": {
                "options": {
                  "leftValue": "",
                  "caseSensitive": true,
                  "typeValidation": "strict"
                },
                "combinator": "or",
                "conditions": [
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "audio"
                  },
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $node['Advanced File Validation'].json.category }}",
                    "rightValue": "video"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "media_processing",
              "outputName": "Audio/Video Files"
            }
          ]
        },
        "options": {
          "fallbackOutput": "other",
          "renameFallbackOutput": "Other Files"
        }
      },
      "name": "Route by File Type",
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3.3,
      "position": [1250, 300],
      "id": "route_file_type_006"
    },
    {
      "parameters": {
        "operation": "upload",
        "bucketName": "ai-empire-documents",
        "fileName": "={{ $json.storagePath }}",
        "binaryPropertyName": "file",
        "additionalFields": {
          "storageClass": "STANDARD",
          "serverSideEncryption": "AES256",
          "acl": "private",
          "metadata": {
            "metadataValues": [
              {
                "key": "original_filename",
                "value": "={{ $json.filename }}"
              },
              {
                "key": "upload_date",
                "value": "={{ $json.uploadTime }}"
              },
              {
                "key": "mime_type",
                "value": "={{ $json.mimeType }}"
              },
              {
                "key": "file_hash",
                "value": "={{ $json.hash }}"
              },
              {
                "key": "file_size",
                "value": "={{ $json.size }}"
              },
              {
                "key": "category",
                "value": "={{ $json.category }}"
              },
              {
                "key": "processing_priority",
                "value": "={{ $json.processingPriority }}"
              }
            ]
          }
        }
      },
      "name": "Save to Backblaze B2",
      "type": "n8n-nodes-base.s3",
      "typeVersion": 1,
      "position": [1450, 300],
      "id": "save_to_b2_007",
      "credentials": {
        "s3": {
          "id": "{{B2_CREDENTIALS_ID}}",
          "name": "Backblaze B2"
        }
      },
      "continueOnFail": true
    },
    {
      "parameters": {
        "operation": "insert",
        "table": "documents",
        "columns": [
          {
            "column": "document_id",
            "value": "={{ $json.fileId }}"
          },
          {
            "column": "filename",
            "value": "={{ $json.filename }}"
          },
          {
            "column": "file_hash",
            "value": "={{ $json.hash }}"
          },
          {
            "column": "mime_type",
            "value": "={{ $json.mimeType }}"
          },
          {
            "column": "file_size",
            "value": "={{ $json.size }}"
          },
          {
            "column": "category",
            "value": "={{ $json.category }}"
          },
          {
            "column": "storage_path",
            "value": "={{ $json.storagePath }}"
          },
          {
            "column": "upload_date",
            "value": "={{ $json.uploadTime }}"
          },
          {
            "column": "processing_status",
            "value": "uploaded"
          },
          {
            "column": "processing_complete",
            "value": "={{ false }}"
          },
          {
            "column": "metadata",
            "value": "={{ JSON.stringify($json) }}"
          }
        ],
        "options": {
          "returnFields": ["id", "document_id", "created_at"]
        }
      },
      "name": "Log to Supabase",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1650, 300],
      "id": "log_to_supabase_008",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Error handler for failed validations\nconst error = $node['Advanced File Validation'].json;\n\n// Log error to database\nconst errorLog = {\n  timestamp: new Date().toISOString(),\n  error_type: 'validation_failure',\n  error_message: error.errorMessage,\n  error_stack: error.errorStack,\n  request_info: error.requestInfo,\n  severity: 'error',\n  component: 'document_intake',\n  action_taken: 'rejected_upload'\n};\n\n// Send notification if needed\nconst shouldNotify = error.errorMessage.includes('File too large') || \n                     error.errorMessage.includes('dangerous file');\n\nif (shouldNotify) {\n  errorLog.notification_sent = true;\n  errorLog.notification_channel = 'slack';\n}\n\nreturn [{\n  json: errorLog\n}];"
      },
      "name": "Handle Validation Error",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [650, 450],
      "id": "handle_validation_error_009"
    },
    {
      "parameters": {
        "operation": "insert",
        "table": "error_logs",
        "columns": [
          {
            "column": "timestamp",
            "value": "={{ $json.timestamp }}"
          },
          {
            "column": "error_type",
            "value": "={{ $json.error_type }}"
          },
          {
            "column": "error_message",
            "value": "={{ $json.error_message }}"
          },
          {
            "column": "error_stack",
            "value": "={{ $json.error_stack }}"
          },
          {
            "column": "severity",
            "value": "={{ $json.severity }}"
          },
          {
            "column": "component",
            "value": "={{ $json.component }}"
          },
          {
            "column": "metadata",
            "value": "={{ JSON.stringify($json) }}"
          }
        ]
      },
      "name": "Log Error to Database",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [850, 450],
      "id": "log_error_010",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Handle duplicate file detection\nconst duplicate = $node['Check for Duplicates'].json[0];\nconst currentFile = $node['Advanced File Validation'].json;\n\nconst response = {\n  status: 'duplicate_detected',\n  message: 'This file has already been uploaded and processed',\n  existing_document: {\n    id: duplicate.id,\n    document_id: duplicate.document_id,\n    filename: duplicate.filename,\n    upload_date: duplicate.upload_date,\n    processing_status: duplicate.processing_status,\n    processing_complete: duplicate.processing_complete,\n    vector_count: duplicate.vector_count\n  },\n  attempted_upload: {\n    filename: currentFile.filename,\n    hash: currentFile.hash,\n    upload_time: currentFile.uploadTime\n  },\n  action: 'skipped',\n  recommendation: duplicate.processing_complete ? \n    'File is fully processed and ready for queries' : \n    'File is still being processed, please check back later'\n};\n\nreturn [{\n  json: response\n}];"
      },
      "name": "Handle Duplicate",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1050, 400],
      "id": "handle_duplicate_011"
    }
  ],
  "connections": {
    "Document Upload Webhook": {
      "main": [
        [
          {
            "node": "Advanced File Validation",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Advanced File Validation": {
      "main": [
        [
          {
            "node": "Has Validation Error?",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Has Validation Error?": {
      "main": [
        [
          {
            "node": "Handle Validation Error",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Check for Duplicates",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Handle Validation Error": {
      "main": [
        [
          {
            "node": "Log Error to Database",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Check for Duplicates": {
      "main": [
        [
          {
            "node": "Is Duplicate?",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Is Duplicate?": {
      "main": [
        [
          {
            "node": "Handle Duplicate",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Route by File Type",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Route by File Type": {
      "main": [
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Save to Backblaze B2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Save to Backblaze B2": {
      "main": [
        [
          {
            "node": "Log to Supabase",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1",
    "saveDataSuccessExecution": "all",
    "saveExecutionProgress": true,
    "saveManualExecutions": true,
    "callerPolicy": "workflowsFromSameOwner",
    "errorWorkflow": "error-handler-workflow"
  },
  "staticData": null,
  "meta": {
    "templateId": "document-intake-v7",
    "version": "7.0.0",
    "description": "Complete document intake and classification workflow with advanced validation",
    "author": "AI Empire v6.0 Implementation Team"
  },
  "tags": [
    {
      "name": "document-processing",
      "createdAt": "2024-10-25T00:00:00.000Z"
    },
    {
      "name": "milestone-1",
      "createdAt": "2024-10-25T00:00:00.000Z"
    }
  ]
}
```

#### Hash-Based Deduplication Implementation (CRITICAL - Gap 1.10)

Add the following nodes to the Document Intake workflow after file upload but before processing:

```json
{
  "nodes": [
    {
      "parameters": {
        "functionCode": "// Generate SHA-256 hash of document content\nconst crypto = require('crypto');\n\nconst content = $input.item.content || $input.item.text || '';\nconst metadata = $input.item.metadata || {};\n\n// Create composite hash from content + key metadata\nconst hashInput = content + JSON.stringify({\n  filename: metadata.filename,\n  file_size: metadata.file_size,\n  modified_date: metadata.modified_date\n});\n\nconst hash = crypto.createHash('sha256').update(hashInput).digest('hex');\n\nreturn {\n  ...($input.item),\n  content_hash: hash\n};"
      },
      "name": "Generate Content Hash",
      "type": "n8n-nodes-base.code",
      "position": [550, 300]
    },
    {
      "parameters": {
        "operation": "select",
        "schema": "public",
        "table": "documents",
        "limit": 1,
        "where": {
          "content_hash": "={{ $json.content_hash }}"
        }
      },
      "name": "Check for Duplicate",
      "type": "n8n-nodes-base.postgres",
      "position": [750, 300]
    },
    {
      "parameters": {
        "conditions": {
          "number": [
            {
              "value1": "={{ $json.length }}",
              "operation": "equal",
              "value2": 0
            }
          ]
        }
      },
      "name": "Is New Document?",
      "type": "n8n-nodes-base.if",
      "position": [950, 300]
    },
    {
      "parameters": {
        "functionCode": "// Document is duplicate - skip processing\nreturn {\n  action: 'skip',\n  reason: 'duplicate_content',\n  existing_hash: $input.item.content_hash,\n  message: 'Document with identical content already exists'\n};"
      },
      "name": "Skip Duplicate",
      "type": "n8n-nodes-base.code",
      "position": [1150, 400],
      "continueOnFail": true
    }
  ]
}
```

Also update the documents table schema to include the hash field:

```sql
-- Add hash column to documents table if it doesn't exist
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);

-- Add processing status tracking (Gap 1.11)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMPTZ;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_duration_ms INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_error TEXT;

-- Status values: 'pending', 'processing', 'complete', 'error', 'duplicate'
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
```

### 10.2.3 Database Schema for Document Management

```sql
-- Complete Supabase Schema for Document Management
-- This schema supports all document processing features

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Main documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash
    filename TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    category VARCHAR(50) NOT NULL,
    storage_path TEXT NOT NULL,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_status VARCHAR(50) DEFAULT 'uploaded',
    processing_complete BOOLEAN DEFAULT FALSE,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_duration_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    vector_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for documents table
CREATE INDEX idx_documents_document_id ON documents(document_id);
CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_processing_status ON documents(processing_status);
CREATE INDEX idx_documents_upload_date ON documents(upload_date DESC);
CREATE INDEX idx_documents_metadata ON documents USING gin(metadata);
CREATE INDEX idx_documents_tags ON documents USING gin(tags);
CREATE INDEX idx_documents_filename_trgm ON documents USING gin(filename gin_trgm_ops);

-- Document chunks table for text extraction
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536), -- OpenAI embedding dimension
    embedding_model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Create indexes for chunks table
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_content_hash ON document_chunks(content_hash);
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_chunks_content_trgm ON document_chunks USING gin(content gin_trgm_ops);

-- Error logs table
CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_stack TEXT,
    severity VARCHAR(20) NOT NULL DEFAULT 'error',
    component VARCHAR(100) NOT NULL,
    document_id VARCHAR(64),
    workflow_id VARCHAR(100),
    execution_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for error logs
CREATE INDEX idx_error_logs_timestamp ON error_logs(timestamp DESC);
CREATE INDEX idx_error_logs_error_type ON error_logs(error_type);
CREATE INDEX idx_error_logs_severity ON error_logs(severity);
CREATE INDEX idx_error_logs_component ON error_logs(component);
CREATE INDEX idx_error_logs_document_id ON error_logs(document_id);
CREATE INDEX idx_error_logs_resolved ON error_logs(resolved);

-- Processing queue table
CREATE TABLE IF NOT EXISTS processing_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    processor_type VARCHAR(50) NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for processing queue
CREATE INDEX idx_queue_status ON processing_queue(status);
CREATE INDEX idx_queue_priority ON processing_queue(priority DESC, created_at ASC);
CREATE INDEX idx_queue_document_id ON processing_queue(document_id);
CREATE INDEX idx_queue_next_attempt ON processing_queue(next_attempt_at);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for audit log
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);

-- Create update trigger for documents
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_queue_updated_at
    BEFORE UPDATE ON processing_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Function to update document access stats
CREATE OR REPLACE FUNCTION update_document_access(p_document_id VARCHAR(64))
RETURNS VOID AS $$
BEGIN
    UPDATE documents 
    SET 
        last_accessed = NOW(),
        access_count = COALESCE(access_count, 0) + 1
    WHERE document_id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- Function to add document to processing queue
CREATE OR REPLACE FUNCTION add_to_processing_queue(
    p_document_id VARCHAR(64),
    p_processor_type VARCHAR(50),
    p_priority INTEGER DEFAULT 5
)
RETURNS UUID AS $$
DECLARE
    v_queue_id UUID;
BEGIN
    INSERT INTO processing_queue (
        document_id,
        processor_type,
        priority,
        status,
        next_attempt_at
    ) VALUES (
        p_document_id,
        p_processor_type,
        p_priority,
        'pending',
        NOW()
    ) RETURNING id INTO v_queue_id;
    
    RETURN v_queue_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get next item from processing queue
CREATE OR REPLACE FUNCTION get_next_from_queue(p_processor_type VARCHAR(50))
RETURNS TABLE (
    queue_id UUID,
    document_id VARCHAR(64),
    priority INTEGER,
    attempts INTEGER,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    UPDATE processing_queue q
    SET 
        status = 'processing',
        attempts = attempts + 1,
        last_attempt_at = NOW(),
        next_attempt_at = CASE 
            WHEN attempts + 1 >= max_attempts THEN NULL
            ELSE NOW() + INTERVAL '5 minutes' * (attempts + 1)
        END
    WHERE q.id = (
        SELECT id 
        FROM processing_queue 
        WHERE status = 'pending' 
        AND processor_type = p_processor_type
        AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING q.id, q.document_id, q.priority, q.attempts, q.metadata;
END;
$$ LANGUAGE plpgsql;
```

### 10.2.4 Tabular Data Processing (NEW - Gap 1.3)

**Purpose**: Handle CSV, Excel, and structured data with dedicated storage and processing pipelines.

#### Database Schema for Tabular Data

```sql
-- Table for storing structured/tabular document rows
CREATE TABLE IF NOT EXISTS public.tabular_document_rows (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  row_number INTEGER NOT NULL,
  row_data JSONB NOT NULL,
  row_hash TEXT GENERATED ALWAYS AS (encode(sha256(row_data::text::bytea), 'hex')) STORED,
  schema_metadata JSONB, -- Stores inferred schema information
  inferred_relationships JSONB, -- Stores detected foreign keys and relationships
  search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', row_data::text)) STORED,
  CONSTRAINT unique_document_row UNIQUE(document_id, row_number)
);

-- Indexes for performance
CREATE INDEX idx_tabular_rows_document ON tabular_document_rows(document_id);
CREATE INDEX idx_tabular_rows_data_gin ON tabular_document_rows USING gin(row_data);
CREATE INDEX idx_tabular_rows_search ON tabular_document_rows USING gin(search_vector);
CREATE INDEX idx_tabular_rows_hash ON tabular_document_rows(row_hash);

-- Schema inference metadata table
CREATE TABLE IF NOT EXISTS public.tabular_schemas (
  id BIGSERIAL PRIMARY KEY,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  schema_definition JSONB NOT NULL,
  column_types JSONB NOT NULL,
  inferred_at TIMESTAMPTZ DEFAULT NOW(),
  confidence_scores JSONB,
  sample_size INTEGER,
  CONSTRAINT unique_document_schema UNIQUE(document_id)
);
```

#### n8n Workflow: Tabular Data Processing

```json
{
  "name": "Empire - Tabular Data Processor",
  "nodes": [
    {
      "parameters": {
        "operation": "text",
        "destinationKey": "csv_content"
      },
      "name": "Extract CSV/Excel Content",
      "type": "n8n-nodes-base.extractFromFile",
      "position": [450, 300]
    },
    {
      "parameters": {
        "functionCode": "// Parse CSV and infer schema\nconst Papa = require('papaparse');\nconst parsed = Papa.parse($input.item.csv_content, {\n  header: true,\n  dynamicTyping: true,\n  skipEmptyLines: true\n});\n\n// Infer column types\nconst schema = {};\nif (parsed.data.length > 0) {\n  const sample = parsed.data.slice(0, 100); // Sample first 100 rows\n  \n  Object.keys(parsed.data[0]).forEach(column => {\n    const values = sample.map(row => row[column]).filter(v => v !== null);\n    \n    // Determine type\n    let columnType = 'string';\n    if (values.every(v => typeof v === 'number')) {\n      columnType = 'number';\n    } else if (values.every(v => v instanceof Date)) {\n      columnType = 'date';\n    } else if (values.every(v => typeof v === 'boolean')) {\n      columnType = 'boolean';\n    }\n    \n    schema[column] = {\n      type: columnType,\n      nullable: values.length < sample.length,\n      unique_count: new Set(values).size,\n      sample_values: [...new Set(values)].slice(0, 5)\n    };\n  });\n}\n\nreturn {\n  rows: parsed.data,\n  schema: schema,\n  row_count: parsed.data.length,\n  column_count: Object.keys(schema).length\n};"
      },
      "name": "Parse and Infer Schema",
      "type": "n8n-nodes-base.code",
      "position": [650, 300]
    },
    {
      "parameters": {
        "batchSize": 100,
        "options": {}
      },
      "name": "Batch Rows",
      "type": "n8n-nodes-base.splitInBatches",
      "position": [850, 300]
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "tabular_document_rows",
        "columns": "document_id,row_number,row_data,schema_metadata",
        "additionalFields": {}
      },
      "name": "Insert Rows to Database",
      "type": "n8n-nodes-base.postgres",
      "position": [1050, 300]
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "tabular_schemas",
        "columns": "document_id,schema_definition,column_types,sample_size"
      },
      "name": "Store Schema Metadata",
      "type": "n8n-nodes-base.postgres",
      "position": [1050, 450]
    }
  ]
}
```

### 10.2.5 Metadata Fields Management (NEW - Gap 1.5)

**Purpose**: Provide controlled vocabularies and metadata validation for advanced filtering.

#### Database Schema

```sql
-- Metadata field definitions for controlled vocabularies
CREATE TABLE IF NOT EXISTS public.metadata_fields (
  id BIGSERIAL PRIMARY KEY,
  field_name TEXT NOT NULL UNIQUE,
  field_type VARCHAR(50) NOT NULL CHECK (field_type IN ('string', 'number', 'date', 'enum', 'boolean')),
  allowed_values TEXT[], -- For enum types only
  validation_regex TEXT, -- For string types
  min_value NUMERIC, -- For number types
  max_value NUMERIC, -- For number types
  description TEXT,
  is_required BOOLEAN DEFAULT FALSE,
  is_searchable BOOLEAN DEFAULT TRUE,
  is_facetable BOOLEAN DEFAULT TRUE,
  display_order INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default metadata fields
INSERT INTO public.metadata_fields (field_name, field_type, allowed_values, description, is_required, display_order) VALUES
  ('department', 'enum', ARRAY['HR', 'Engineering', 'Sales', 'Marketing', 'Operations', 'Legal', 'Finance'], 'Document department', false, 1),
  ('document_type', 'enum', ARRAY['Policy', 'Procedure', 'Report', 'Memo', 'Contract', 'Invoice', 'Manual'], 'Type of document', true, 2),
  ('confidentiality', 'enum', ARRAY['Public', 'Internal', 'Confidential', 'Secret'], 'Confidentiality level', true, 3),
  ('document_date', 'date', NULL, 'Date of document creation', false, 4),
  ('expiry_date', 'date', NULL, 'Document expiration date', false, 5),
  ('author', 'string', NULL, 'Document author name', false, 6),
  ('version', 'string', NULL, 'Document version', false, 7),
  ('tags', 'string', NULL, 'Comma-separated tags', false, 8),
  ('review_status', 'enum', ARRAY['Draft', 'Under Review', 'Approved', 'Archived'], 'Review status', false, 9),
  ('language', 'enum', ARRAY['en', 'es', 'fr', 'de', 'zh', 'ja'], 'Document language', false, 10)
ON CONFLICT (field_name) DO NOTHING;

-- Function to validate metadata against field definitions
CREATE OR REPLACE FUNCTION validate_document_metadata(metadata JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  field RECORD;
  field_value TEXT;
  validation_errors JSONB := '[]'::JSONB;
  validated_metadata JSONB := '{}'::JSONB;
BEGIN
  -- Check each defined field
  FOR field IN SELECT * FROM metadata_fields WHERE is_required = true
  LOOP
    IF NOT metadata ? field.field_name THEN
      validation_errors := validation_errors || jsonb_build_object(
        'field', field.field_name,
        'error', 'Required field missing'
      );
    END IF;
  END LOOP;

  -- Validate present fields
  FOR field IN SELECT * FROM metadata_fields
  LOOP
    IF metadata ? field.field_name THEN
      field_value := metadata->>field.field_name;

      -- Validate based on type
      CASE field.field_type
        WHEN 'enum' THEN
          IF NOT field_value = ANY(field.allowed_values) THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', format('Value must be one of: %s', array_to_string(field.allowed_values, ', '))
            );
          ELSE
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value);
          END IF;

        WHEN 'date' THEN
          BEGIN
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value::date);
          EXCEPTION WHEN OTHERS THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', 'Invalid date format'
            );
          END;

        WHEN 'number' THEN
          BEGIN
            IF field.min_value IS NOT NULL AND field_value::numeric < field.min_value THEN
              RAISE EXCEPTION 'Below minimum';
            END IF;
            IF field.max_value IS NOT NULL AND field_value::numeric > field.max_value THEN
              RAISE EXCEPTION 'Above maximum';
            END IF;
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value::numeric);
          EXCEPTION WHEN OTHERS THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', format('Must be a number between %s and %s', field.min_value, field.max_value)
            );
          END;

        WHEN 'string' THEN
          IF field.validation_regex IS NOT NULL AND NOT field_value ~ field.validation_regex THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', 'Invalid format'
            );
          ELSE
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value);
          END IF;

        ELSE
          validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value);
      END CASE;
    END IF;
  END LOOP;

  -- Return result
  IF jsonb_array_length(validation_errors) > 0 THEN
    RETURN jsonb_build_object(
      'valid', false,
      'errors', validation_errors,
      'metadata', metadata
    );
  ELSE
    RETURN jsonb_build_object(
      'valid', true,
      'errors', '[]'::jsonb,
      'metadata', validated_metadata
    );
  END IF;
END;
$$;
```
