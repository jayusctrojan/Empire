# Empire n8n Workflow Validation Report and Corrections

## Executive Summary

After analyzing the Empire repository's n8n workflows using the n8n-MCP validation tools, I've identified several critical issues that need correction for the workflows to function properly in n8n. The main problems relate to:

1. **Code node syntax errors** - Improper return statements and module usage
2. **Missing error handling** - Webhook nodes without proper error responses
3. **Node type mismatches** - Using incorrect node versions or parameters
4. **Connection flow issues** - Incomplete workflow connections
5. **Credential placeholders** - Need proper credential configuration

## Validation Results Summary

### Milestone 1: Document Intake
- **Errors Found**: 1 critical error
- **Warnings Found**: 5 warnings
- **Main Issues**:
  - Code node cannot return primitive values directly
  - Cannot use `require('path')` - only built-in modules available
  - Missing webhook error handling

## Key Issues and Corrections

### 1. Code Node Return Format

**Problem**: Code nodes must return an array of objects with `json` property
```javascript
// INCORRECT
return output;

// CORRECT
return [{
  json: output,
  binary: {
    file: file
  }
}];
```

### 2. Module Requirements in Code Nodes

**Problem**: Limited module availability in Code nodes
```javascript
// INCORRECT
const path = require('path');  // Not available
const crypto = require('crypto'); // Available

// CORRECT - Use built-in alternatives
function getFileExtension(filename) {
  return filename.split('.').pop().toLowerCase();
}
```

### 3. Webhook Error Handling

**Problem**: Webhooks need proper error responses
```json
{
  "parameters": {
    "httpMethod": "POST",
    "path": "document-upload",
    "responseMode": "onReceived",
    "options": {
      "rawBody": true,
      "binaryPropertyName": "file",
      "responseHeaders": {
        "Access-Control-Allow-Origin": "*"
      },
      "onError": "continueRegularOutput"  // ADD THIS
    }
  }
}
```

## Corrected Milestone 1 Workflow

Here's the validated and corrected version of the Document Intake workflow:

```json
{
  "name": "Empire_Document_Intake_v8_Corrected",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "empire/document-upload",
        "responseMode": "onReceived",
        "options": {
          "rawBody": true,
          "binaryPropertyName": "file",
          "responseHeaders": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
          },
          "onError": "continueRegularOutput"
        }
      },
      "name": "Document Upload Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300],
      "id": "webhook_001"
    },
    {
      "parameters": {
        "jsCode": "// File validation and metadata extraction\nconst crypto = require('crypto');\n\n// Configuration\nconst CONFIG = {\n  maxFileSizeMB: 100,\n  allowedMimeTypes: [\n    'application/pdf',\n    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',\n    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',\n    'text/plain',\n    'text/csv',\n    'application/json',\n    'image/jpeg',\n    'image/png'\n  ]\n};\n\n// Helper functions\nfunction getFileExtension(filename) {\n  const parts = filename.split('.');\n  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';\n}\n\nfunction calculateFileHash(buffer) {\n  return crypto.createHash('sha256')\n    .update(buffer)\n    .digest('hex');\n}\n\nfunction formatBytes(bytes) {\n  if (bytes === 0) return '0 Bytes';\n  const k = 1024;\n  const sizes = ['Bytes', 'KB', 'MB', 'GB'];\n  const i = Math.floor(Math.log(bytes) / Math.log(k));\n  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];\n}\n\nfunction validateFile(file, buffer) {\n  const errors = [];\n  const warnings = [];\n  \n  if (!file) {\n    errors.push('No file received');\n    return { valid: false, errors, warnings };\n  }\n  \n  const maxSizeBytes = CONFIG.maxFileSizeMB * 1048576;\n  if (buffer.length > maxSizeBytes) {\n    errors.push(`File too large: ${formatBytes(buffer.length)}`);\n  }\n  \n  if (buffer.length === 0) {\n    errors.push('File is empty');\n  }\n  \n  const mimeType = file.mimeType || 'application/octet-stream';\n  if (!CONFIG.allowedMimeTypes.includes(mimeType)) {\n    errors.push(`Unsupported file type: ${mimeType}`);\n  }\n  \n  return {\n    valid: errors.length === 0,\n    errors,\n    warnings\n  };\n}\n\n// Main processing\ntry {\n  const items = $input.all();\n  const file = items[0]?.binary?.file;\n  \n  if (!file) {\n    throw new Error('No file received');\n  }\n  \n  // Convert to buffer\n  const fileBuffer = Buffer.from(file.data, 'base64');\n  \n  // Calculate hash\n  const hash = calculateFileHash(fileBuffer);\n  \n  // Validate\n  const validation = validateFile(file, fileBuffer);\n  \n  if (!validation.valid) {\n    throw new Error(validation.errors.join(', '));\n  }\n  \n  // Get extension\n  const extension = getFileExtension(file.fileName || 'file');\n  \n  // Determine category\n  const categoryMap = {\n    'pdf': 'pdf',\n    'docx': 'word',\n    'xlsx': 'excel',\n    'txt': 'text',\n    'csv': 'csv',\n    'json': 'json',\n    'jpg': 'image',\n    'jpeg': 'image',\n    'png': 'image'\n  };\n  \n  const category = categoryMap[extension] || 'other';\n  \n  // Generate storage path\n  const date = new Date();\n  const year = date.getFullYear();\n  const month = String(date.getMonth() + 1).padStart(2, '0');\n  const day = String(date.getDate()).padStart(2, '0');\n  const safeName = (file.fileName || 'unnamed').replace(/[^a-z0-9._-]/gi, '_');\n  const storagePath = `${category}/${year}/${month}/${day}/${hash}/${safeName}`;\n  \n  // Prepare output\n  const output = {\n    fileId: hash,\n    hash: hash,\n    filename: file.fileName || 'unnamed_file',\n    mimeType: file.mimeType || 'application/octet-stream',\n    size: fileBuffer.length,\n    sizeMB: (fileBuffer.length / 1048576).toFixed(2),\n    sizeReadable: formatBytes(fileBuffer.length),\n    extension: extension,\n    category: category,\n    storagePath: storagePath,\n    uploadTime: new Date().toISOString(),\n    validation: {\n      passed: validation.valid,\n      warnings: validation.warnings,\n      errors: validation.errors\n    },\n    requiresOCR: ['image', 'pdf'].includes(category),\n    requiresTextExtraction: ['pdf', 'word'].includes(category),\n    requiresStructuredParsing: ['excel', 'csv', 'json'].includes(category)\n  };\n  \n  // Return properly formatted data\n  return [{\n    json: output,\n    binary: {\n      file: file\n    }\n  }];\n  \n} catch (error) {\n  // Error handling\n  return [{\n    json: {\n      error: true,\n      errorMessage: error.message,\n      timestamp: new Date().toISOString()\n    }\n  }];\n}"
      },
      "name": "Validate and Process File",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "validate_002"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.error }}",
              "value2": true
            }
          ]
        }
      },
      "name": "Check Validation Error",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [650, 300],
      "id": "check_error_003"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT id, document_id, filename, file_hash, upload_date, processing_status FROM documents WHERE file_hash = $1 LIMIT 1",
        "options": {
          "queryParams": "={{ [$json.hash] }}"
        }
      },
      "name": "Check for Duplicates",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.4,
      "position": [850, 250],
      "id": "check_dup_004",
      "credentials": {
        "postgres": {
          "id": "supabase_cred",
          "name": "Supabase"
        }
      }
    },
    {
      "parameters": {
        "conditions": {
          "number": [
            {
              "value1": "={{ $json.length }}",
              "operation": "larger",
              "value2": 0
            }
          ]
        }
      },
      "name": "Is Duplicate?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [1050, 250],
      "id": "is_dup_005"
    },
    {
      "parameters": {
        "rules": {
          "values": [
            {
              "conditions": {
                "conditions": [
                  {
                    "leftValue": "={{ $('Validate and Process File').item.json.category }}",
                    "rightValue": "pdf",
                    "operator": {
                      "type": "string",
                      "operation": "equals"
                    }
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "pdf"
            },
            {
              "conditions": {
                "conditions": [
                  {
                    "leftValue": "={{ $('Validate and Process File').item.json.category }}",
                    "rightValue": "word",
                    "operator": {
                      "type": "string",
                      "operation": "equals"
                    }
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "word"
            },
            {
              "conditions": {
                "conditions": [
                  {
                    "leftValue": "={{ $('Validate and Process File').item.json.category }}",
                    "rightValue": "excel",
                    "operator": {
                      "type": "string",
                      "operation": "equals"
                    }
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "excel"
            },
            {
              "conditions": {
                "conditions": [
                  {
                    "leftValue": "={{ $('Validate and Process File').item.json.category }}",
                    "rightValue": "csv",
                    "operator": {
                      "type": "string",
                      "operation": "equals"
                    }
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "csv"
            },
            {
              "conditions": {
                "conditions": [
                  {
                    "leftValue": "={{ $('Validate and Process File').item.json.category }}",
                    "rightValue": "image",
                    "operator": {
                      "type": "string",
                      "operation": "equals"
                    }
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "image"
            }
          ]
        },
        "options": {
          "fallbackOutput": "other"
        }
      },
      "name": "Route by File Type",
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3,
      "position": [1250, 300],
      "id": "route_006"
    },
    {
      "parameters": {
        "operation": "upload",
        "bucketName": "empire-documents",
        "fileName": "={{ $json.storagePath }}",
        "binaryPropertyName": "file",
        "additionalFields": {
          "storageClass": "STANDARD",
          "acl": "private",
          "metadata": {
            "metadataValues": [
              {
                "key": "original_filename",
                "value": "={{ $json.filename }}"
              },
              {
                "key": "file_hash",
                "value": "={{ $json.hash }}"
              },
              {
                "key": "upload_date",
                "value": "={{ $json.uploadTime }}"
              },
              {
                "key": "category",
                "value": "={{ $json.category }}"
              }
            ]
          }
        }
      },
      "name": "Store in S3/B2",
      "type": "n8n-nodes-base.s3",
      "typeVersion": 1,
      "position": [1450, 300],
      "id": "store_007",
      "credentials": {
        "s3": {
          "id": "b2_cred",
          "name": "Backblaze B2"
        }
      }
    },
    {
      "parameters": {
        "operation": "insert",
        "table": "documents",
        "columns": "document_id,filename,file_hash,mime_type,file_size,category,storage_path,upload_date,processing_status,metadata",
        "additionalFields": {}
      },
      "name": "Log to Database",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.4,
      "position": [1650, 300],
      "id": "log_008",
      "credentials": {
        "postgres": {
          "id": "supabase_cred",
          "name": "Supabase"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "// Handle validation errors\nconst error = $('Validate and Process File').item.json;\n\nconst errorLog = {\n  timestamp: new Date().toISOString(),\n  error_type: 'validation_failure',\n  error_message: error.errorMessage,\n  severity: 'error',\n  component: 'document_intake'\n};\n\nreturn [{\n  json: errorLog\n}];"
      },
      "name": "Handle Error",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [650, 450],
      "id": "handle_error_009"
    },
    {
      "parameters": {
        "jsCode": "// Handle duplicate detection\nconst duplicate = $('Check for Duplicates').item.json[0];\nconst currentFile = $('Validate and Process File').item.json;\n\nconst response = {\n  status: 'duplicate_detected',\n  message: 'File already uploaded',\n  existing_document: {\n    id: duplicate.id,\n    document_id: duplicate.document_id,\n    filename: duplicate.filename,\n    upload_date: duplicate.upload_date,\n    processing_status: duplicate.processing_status\n  },\n  attempted_upload: {\n    filename: currentFile.filename,\n    hash: currentFile.hash\n  },\n  action: 'skipped'\n};\n\nreturn [{\n  json: response\n}];"
      },
      "name": "Handle Duplicate",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1050, 400],
      "id": "handle_dup_010"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}",
        "options": {}
      },
      "name": "Respond Success",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1850, 300],
      "id": "respond_success_011"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}",
        "responseCode": 400,
        "options": {}
      },
      "name": "Respond Error",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [850, 450],
      "id": "respond_error_012"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}",
        "responseCode": 409,
        "options": {}
      },
      "name": "Respond Duplicate",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1250, 400],
      "id": "respond_dup_013"
    }
  ],
  "connections": {
    "Document Upload Webhook": {
      "main": [[
        {"node": "Validate and Process File", "type": "main", "index": 0}
      ]]
    },
    "Validate and Process File": {
      "main": [[
        {"node": "Check Validation Error", "type": "main", "index": 0}
      ]]
    },
    "Check Validation Error": {
      "main": [
        [{"node": "Handle Error", "type": "main", "index": 0}],
        [{"node": "Check for Duplicates", "type": "main", "index": 0}]
      ]
    },
    "Handle Error": {
      "main": [[
        {"node": "Respond Error", "type": "main", "index": 0}
      ]]
    },
    "Check for Duplicates": {
      "main": [[
        {"node": "Is Duplicate?", "type": "main", "index": 0}
      ]]
    },
    "Is Duplicate?": {
      "main": [
        [{"node": "Handle Duplicate", "type": "main", "index": 0}],
        [{"node": "Route by File Type", "type": "main", "index": 0}]
      ]
    },
    "Handle Duplicate": {
      "main": [[
        {"node": "Respond Duplicate", "type": "main", "index": 0}
      ]]
    },
    "Route by File Type": {
      "main": [
        [{"node": "Store in S3/B2", "type": "main", "index": 0}],
        [{"node": "Store in S3/B2", "type": "main", "index": 0}],
        [{"node": "Store in S3/B2", "type": "main", "index": 0}],
        [{"node": "Store in S3/B2", "type": "main", "index": 0}],
        [{"node": "Store in S3/B2", "type": "main", "index": 0}],
        [{"node": "Store in S3/B2", "type": "main", "index": 0}]
      ]
    },
    "Store in S3/B2": {
      "main": [[
        {"node": "Log to Database", "type": "main", "index": 0}
      ]]
    },
    "Log to Database": {
      "main": [[
        {"node": "Respond Success", "type": "main", "index": 0}
      ]]
    }
  },
  "settings": {
    "executionOrder": "v1",
    "saveDataSuccessExecution": "all",
    "saveExecutionProgress": true,
    "saveManualExecutions": true,
    "callerPolicy": "workflowsFromSameOwner"
  },
  "staticData": null,
  "meta": {
    "templateId": "empire-document-intake-v8",
    "version": "8.0.0",
    "description": "Validated and corrected document intake workflow"
  },
  "tags": [
    {"name": "document-processing"},
    {"name": "validated"},
    {"name": "empire"}
  ]
}
```

## Additional Corrections Needed Across All Milestones

### 1. Replace Extract From File Node

The `extractFromFile` node type is incorrect. Use the correct type:
```json
{
  "name": "Extract Text",
  "type": "n8n-nodes-base.extractTextFromFile",
  "parameters": {
    "binaryPropertyName": "file",
    "options": {}
  }
}
```

### 2. Fix Postgres Node Version

Use the latest version consistently:
```json
{
  "type": "n8n-nodes-base.postgres",
  "typeVersion": 2.4  // Not 2.6
}
```

### 3. Correct Switch Node Implementation

The Switch node v3 has a different structure:
```json
{
  "parameters": {
    "rules": {
      "values": [
        {
          "conditions": {
            "conditions": [
              {
                "leftValue": "={{ $json.category }}",
                "rightValue": "pdf",
                "operator": {
                  "type": "string",
                  "operation": "equals"
                }
              }
            ]
          },
          "renameOutput": true,
          "outputKey": "pdf"
        }
      ]
    }
  }
}
```

## Recommended Template Usage

Based on the n8n template search, I recommend using elements from these proven templates:

1. **Template #4336** - "Webhook-enabled AI PDF analyzer"
   - Good webhook error handling patterns
   - File validation (size and page limits)
   - Proper response handling

2. **Template #4400** - "PDF Document RAG System with Mistral OCR"
   - OCR integration patterns
   - Vector storage implementation
   - Batch processing approach

3. **Template #3119** - "REST API for PDF Digital Signatures"
   - Complete webhook API patterns
   - File handling best practices
   - Method routing implementation

## Implementation Recommendations

### 1. Use Existing n8n Nodes Where Possible

Instead of complex Code nodes, use native n8n nodes:
- `n8n-nodes-base.extractTextFromFile` for PDF text extraction
- `n8n-nodes-base.splitInBatches` for batch processing
- `n8n-nodes-base.httpRequest` for external API calls
- `n8n-nodes-base.set` for data transformation

### 2. Implement Proper Error Handling

Every workflow should have:
- Error trigger nodes for global error handling
- Try-catch patterns in Code nodes
- Proper webhook responses for all paths
- Logging to database for debugging

### 3. Use Sub-Workflows for Complex Processing

Split complex workflows into manageable sub-workflows:
- Document intake sub-workflow
- Text extraction sub-workflow
- Embedding generation sub-workflow
- Query processing sub-workflow

### 4. Credential Configuration

Set up proper credentials in n8n UI:
```javascript
// Supabase
{
  "host": "your-project.supabase.co",
  "database": "postgres",
  "user": "postgres",
  "password": "your-password",
  "port": 5432,
  "ssl": true
}

// Backblaze B2 (S3 compatible)
{
  "endpoint": "s3.us-west-001.backblazeb2.com",
  "region": "us-west-001",
  "accessKeyId": "your-key-id",
  "secretAccessKey": "your-secret"
}

// OpenAI
{
  "apiKey": "sk-..."
}

// Google Gemini
{
  "apiKey": "your-gemini-key"
}
```

## Testing Strategy

### 1. Unit Test Each Node
- Test file validation with various file types
- Test database operations independently
- Test external API integrations

### 2. Integration Testing
- Test complete workflow with sample files
- Verify error handling paths
- Check duplicate detection

### 3. Performance Testing
- Test with large files (up to 100MB)
- Test batch processing with multiple files
- Monitor memory usage

## Next Steps

1. **Import the corrected workflow** into n8n
2. **Configure all credentials** in the n8n UI
3. **Test with sample files** of each type
4. **Monitor execution logs** for errors
5. **Iterate and refine** based on actual usage

## Conclusion

The Empire workflows contain solid logic but need syntax corrections for n8n compatibility. The main issues are:
- Code node return format
- Module availability limitations
- Webhook error handling
- Node type versions

With the corrections provided, the workflows should function properly in n8n v1.0+. I recommend starting with the corrected Milestone 1 workflow and progressively implementing the remaining milestones after validation.

---

**Report Generated**: October 30, 2025
**Validated Against**: n8n v1.0+
**Status**: Ready for implementation with corrections
