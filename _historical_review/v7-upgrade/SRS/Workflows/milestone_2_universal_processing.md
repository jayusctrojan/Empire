## 10.3 Milestone 2: Text Extraction and Chunking

### 10.3.1 Objectives
- Extract text from various document formats
- Implement intelligent chunking strategies
- Handle OCR for scanned documents
- Process structured data from spreadsheets
- Maintain document structure and metadata
- Prepare content for embedding generation

### 10.3.2 Complete Text Extraction Workflow

```json
{
  "name": "Text_Extraction_Chunking_v7_Complete",
  "nodes": [
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_next_from_queue('text_extraction')",
        "options": {}
      },
      "name": "Get Next Document",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [250, 300],
      "id": "get_next_doc_101",
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
              "value1": "={{ $json.queue_id }}",
              "value2": "={{ undefined }}",
              "operation": "notEqual"
            }
          ]
        }
      },
      "name": "Has Document?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "has_document_102"
    },
    {
      "parameters": {
        "operation": "download",
        "bucketName": "ai-empire-documents",
        "fileName": "={{ $json.metadata.storage_path }}"
      },
      "name": "Download from B2",
      "type": "n8n-nodes-base.s3",
      "typeVersion": 1,
      "position": [650, 250],
      "id": "download_from_b2_103",
      "credentials": {
        "s3": {
          "id": "{{B2_CREDENTIALS_ID}}",
          "name": "Backblaze B2"
        }
      }
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
                    "leftValue": "={{ $json.metadata.category }}",
                    "rightValue": "pdf"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "pdf",
              "outputName": "PDF Extraction"
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
                    "leftValue": "={{ $json.metadata.category }}",
                    "rightValue": "word"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "word",
              "outputName": "Word Extraction"
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
                    "leftValue": "={{ $json.metadata.category }}",
                    "rightValue": "text"
                  },
                  {
                    "operator": {
                      "name": "equals",
                      "type": "string"
                    },
                    "leftValue": "={{ $json.metadata.category }}",
                    "rightValue": "markdown"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "text",
              "outputName": "Text Extraction"
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
                    "leftValue": "={{ $json.metadata.category }}",
                    "rightValue": "image"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "ocr",
              "outputName": "OCR Processing"
            }
          ]
        },
        "options": {
          "fallbackOutput": "other",
          "renameFallbackOutput": "Other Processing"
        }
      },
      "name": "Route by Type",
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3.3,
      "position": [850, 300],
      "id": "route_by_type_104"
    },
    {
      "parameters": {
        "language": "python",
        "pythonCode": "import PyPDF2\nimport json\nimport hashlib\nfrom io import BytesIO\nimport base64\nfrom datetime import datetime\n\n# Initialize metadata variable before try block\ndocument_metadata = {'document_id': 'unknown'}\n\n# Configuration\nCONFIG = {\n    'chunk_size': 1000,  # characters\n    'chunk_overlap': 200,  # characters\n    'min_chunk_size': 100,\n    'max_chunk_size': 2000,\n    'preserve_sentences': True,\n    'preserve_paragraphs': False\n}\n\ndef extract_text_from_pdf(pdf_data):\n    \"\"\"Extract text from PDF with page tracking\"\"\"\n    pdf_buffer = BytesIO(base64.b64decode(pdf_data))\n    pdf_reader = PyPDF2.PdfReader(pdf_buffer)\n    \n    pages = []\n    full_text = \"\"\n    \n    for page_num, page in enumerate(pdf_reader.pages, 1):\n        text = page.extract_text()\n        pages.append({\n            'page_number': page_num,\n            'text': text,\n            'char_count': len(text),\n            'word_count': len(text.split())\n        })\n        full_text += f\"\\n[Page {page_num}]\\n{text}\\n\"\n    \n    return {\n        'full_text': full_text,\n        'pages': pages,\n        'total_pages': len(pages),\n        'total_characters': len(full_text),\n        'total_words': len(full_text.split())\n    }\n\ndef intelligent_chunking(text, config=CONFIG):\n    \"\"\"Intelligently chunk text while preserving context\"\"\"\n    chunks = []\n    \n    if config['preserve_sentences']:\n        # Split by sentences\n        import re\n        sentences = re.split(r'(?<=[.!?])\\s+', text)\n        \n        current_chunk = \"\"\n        current_size = 0\n        chunk_index = 0\n        \n        for sentence in sentences:\n            sentence_size = len(sentence)\n            \n            if current_size + sentence_size <= config['chunk_size']:\n                current_chunk += \" \" + sentence\n                current_size += sentence_size\n            else:\n                if current_chunk:\n                    chunks.append({\n                        'index': chunk_index,\n                        'content': current_chunk.strip(),\n                        'size': len(current_chunk.strip()),\n                        'word_count': len(current_chunk.split()),\n                        'hash': hashlib.md5(current_chunk.encode()).hexdigest()\n                    })\n                    chunk_index += 1\n                \n                # Start new chunk with overlap\n                if config['chunk_overlap'] > 0 and chunks:\n                    overlap_text = chunks[-1]['content'][-config['chunk_overlap']:]\n                    current_chunk = overlap_text + \" \" + sentence\n                    current_size = len(current_chunk)\n                else:\n                    current_chunk = sentence\n                    current_size = sentence_size\n        \n        # Add remaining chunk\n        if current_chunk:\n            chunks.append({\n                'index': chunk_index,\n                'content': current_chunk.strip(),\n                'size': len(current_chunk.strip()),\n                'word_count': len(current_chunk.split()),\n                'hash': hashlib.md5(current_chunk.encode()).hexdigest()\n            })\n    \n    else:\n        # Simple character-based chunking\n        for i in range(0, len(text), config['chunk_size'] - config['chunk_overlap']):\n            chunk = text[i:i + config['chunk_size']]\n            if len(chunk) >= config['min_chunk_size']:\n                chunks.append({\n                    'index': len(chunks),\n                    'content': chunk,\n                    'size': len(chunk),\n                    'word_count': len(chunk.split()),\n                    'hash': hashlib.md5(chunk.encode()).hexdigest()\n                })\n    \n    return chunks\n\n# Main processing\ntry:\n    # Get PDF data from input\n    pdf_data = _input[0]['binary']['file']['data']\n    document_metadata = _input[0]['json']\n    \n    # Extract text from PDF\n    extraction_result = extract_text_from_pdf(pdf_data)\n    \n    # Perform intelligent chunking\n    chunks = intelligent_chunking(extraction_result['full_text'])\n    \n    # Prepare output\n    output = {\n        'document_id': document_metadata['document_id'],\n        'extraction_stats': {\n            'total_pages': extraction_result['total_pages'],\n            'total_characters': extraction_result['total_characters'],\n            'total_words': extraction_result['total_words'],\n            'chunk_count': len(chunks)\n        },\n        'chunks': chunks,\n        'metadata': {\n            'extraction_method': 'PyPDF2',\n            'chunking_config': CONFIG,\n            'timestamp': datetime.now().isoformat()\n        }\n    }\n    \n    return output\n    \nexcept Exception as e:\n    return {\n        'error': True,\n        'error_message': str(e),\n        'document_id': document_metadata.get('document_id', 'unknown')\n    }"
      },
      "name": "Extract PDF Text",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1050, 200],
      "id": "extract_pdf_105"
    },
    {
      "parameters": {
        "url": "https://api.mistral.ai/v1/ocr",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Authorization",
              "value": "Bearer {{ $credentials.apiKey }}"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "image",
              "value": "={{ $binary.file.data }}"
            },
            {
              "name": "model",
              "value": "pixtral-12b-2024-09-04"
            },
            {
              "name": "extract_text",
              "value": "={{ true }}"
            },
            {
              "name": "extract_tables",
              "value": "={{ true }}"
            },
            {
              "name": "extract_layout",
              "value": "={{ true }}"
            }
          ]
        },
        "options": {
          "timeout": 30000,
          "batching": {
            "batch": {
              "batchSize": 10,
              "batchInterval": 1000
            }
          }
        }
      },
      "name": "Mistral OCR",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1050, 500],
      "id": "mistral_ocr_106",
      "notes": "HTTP wrapper for Mistral OCR API - handles scanned documents and images"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Advanced chunking strategy implementation\nconst documents = $input.all();\n\n// Chunking configuration based on document type\nconst chunkingConfigs = {\n  default: {\n    maxChunkSize: 1000,\n    overlap: 200,\n    preserveSentences: true,\n    preserveParagraphs: false,\n    minChunkSize: 100\n  },\n  technical: {\n    maxChunkSize: 1500,\n    overlap: 300,\n    preserveSentences: true,\n    preserveParagraphs: true,\n    minChunkSize: 200,\n    preserveCodeBlocks: true\n  },\n  narrative: {\n    maxChunkSize: 2000,\n    overlap: 400,\n    preserveSentences: true,\n    preserveParagraphs: true,\n    minChunkSize: 500\n  },\n  structured: {\n    maxChunkSize: 800,\n    overlap: 100,\n    preserveSentences: false,\n    preserveParagraphs: false,\n    minChunkSize: 50,\n    preserveTables: true\n  }\n};\n\n/**\n * Intelligent chunking with multiple strategies\n */\nfunction createChunks(text, documentType = 'default') {\n  let config = chunkingConfigs[documentType] || chunkingConfigs.default;\n  const chunks = [];\n  \n  // Detect document type if not specified\n  if (documentType === 'default') {\n    documentType = detectDocumentType(text);\n    config = chunkingConfigs[documentType];\n  }\n  \n  // Pre-process text\n  let processedText = text;\n  \n  // Preserve code blocks if needed\n  const codeBlocks = [];\n  if (config.preserveCodeBlocks) {\n    processedText = processedText.replace(/```[\\s\\S]*?```/g, (match, index) => {\n      codeBlocks.push(match);\n      return `[CODE_BLOCK_${codeBlocks.length - 1}]`;\n    });\n  }\n  \n  // Preserve tables if needed\n  const tables = [];\n  if (config.preserveTables) {\n    processedText = processedText.replace(/\\|[^\\n]+\\|/g, (match, index) => {\n      if (match.includes('|') && match.split('|').length > 3) {\n        tables.push(match);\n        return `[TABLE_${tables.length - 1}]`;\n      }\n      return match;\n    });\n  }\n  \n  // Split into segments\n  let segments = [];\n  \n  if (config.preserveParagraphs) {\n    segments = processedText.split(/\\n\\n+/);\n  } else if (config.preserveSentences) {\n    segments = processedText.match(/[^.!?]+[.!?]+/g) || [processedText];\n  } else {\n    segments = [processedText];\n  }\n  \n  // Create chunks from segments\n  let currentChunk = '';\n  let currentSize = 0;\n  let chunkIndex = 0;\n  \n  for (const segment of segments) {\n    const segmentSize = segment.length;\n    \n    if (currentSize + segmentSize <= config.maxChunkSize) {\n      currentChunk += (currentChunk ? ' ' : '') + segment;\n      currentSize += segmentSize;\n    } else {\n      // Save current chunk\n      if (currentChunk && currentSize >= config.minChunkSize) {\n        chunks.push(createChunkObject(\n          currentChunk,\n          chunkIndex++,\n          codeBlocks,\n          tables\n        ));\n      }\n      \n      // Start new chunk with overlap\n      if (config.overlap > 0 && chunks.length > 0) {\n        const lastChunk = chunks[chunks.length - 1].content;\n        const overlapText = lastChunk.slice(-config.overlap);\n        currentChunk = overlapText + ' ' + segment;\n        currentSize = currentChunk.length;\n      } else {\n        currentChunk = segment;\n        currentSize = segmentSize;\n      }\n    }\n  }\n  \n  // Add final chunk\n  if (currentChunk && currentSize >= config.minChunkSize) {\n    chunks.push(createChunkObject(\n      currentChunk,\n      chunkIndex++,\n      codeBlocks,\n      tables\n    ));\n  }\n  \n  return {\n    chunks: chunks,\n    metadata: {\n      documentType: documentType,\n      config: config,\n      totalChunks: chunks.length,\n      averageChunkSize: chunks.length > 0 ? chunks.reduce((sum, c) => sum + c.size, 0) / chunks.length : 0,\n      processingTime: new Date().toISOString()\n    }\n  };\n}\n\n/**\n * Create chunk object with metadata\n */\nfunction createChunkObject(content, index, codeBlocks, tables) {\n  // Restore code blocks and tables\n  let finalContent = content;\n  \n  finalContent = finalContent.replace(/\\[CODE_BLOCK_(\\d+)\\]/g, (match, idx) => {\n    return codeBlocks[parseInt(idx)] || match;\n  });\n  \n  finalContent = finalContent.replace(/\\[TABLE_(\\d+)\\]/g, (match, idx) => {\n    return tables[parseInt(idx)] || match;\n  });\n  \n  // Calculate hash\n  const crypto = require('crypto');\n  const hash = crypto.createHash('sha256')\n    .update(finalContent)\n    .digest('hex')\n    .substring(0, 16);\n  \n  return {\n    index: index,\n    content: finalContent,\n    size: finalContent.length,\n    wordCount: finalContent.split(/\\s+/).length,\n    hash: hash,\n    metadata: {\n      hasCode: finalContent.includes('```'),\n      hasTable: finalContent.includes('|'),\n      hasList: /^[\\s]*[-*+\\d]+\\.?\\s/m.test(finalContent),\n      hasQuote: finalContent.includes('>'),\n      sentiment: analyzeSentiment(finalContent),\n      keyPhrases: extractKeyPhrases(finalContent)\n    }\n  };\n}\n\n/**\n * Detect document type based on content\n */\nfunction detectDocumentType(text) {\n  const codePatterns = /```|function|class|import|export|const|let|var/gi;\n  const technicalPatterns = /API|SDK|HTTP|JSON|XML|database|server|client/gi;\n  const narrativePatterns = /chapter|section|paragraph|story|narrative/gi;\n  const structuredPatterns = /\\||\\t|,{3,}|;{3,}/g;\n  \n  const codeMatches = (text.match(codePatterns) || []).length;\n  const technicalMatches = (text.match(technicalPatterns) || []).length;\n  const narrativeMatches = (text.match(narrativePatterns) || []).length;\n  const structuredMatches = (text.match(structuredPatterns) || []).length;\n  \n  const scores = {\n    technical: codeMatches + technicalMatches,\n    narrative: narrativeMatches,\n    structured: structuredMatches,\n    default: 1\n  };\n  \n  return Object.keys(scores).reduce((a, b) => \n    scores[a] > scores[b] ? a : b\n  );\n}\n\n/**\n * Simple sentiment analysis\n */\nfunction analyzeSentiment(text) {\n  const positiveWords = /good|great|excellent|amazing|wonderful|fantastic|positive|success|happy|joy/gi;\n  const negativeWords = /bad|terrible|awful|horrible|negative|failure|sad|angry|hate|wrong/gi;\n  \n  const positiveCount = (text.match(positiveWords) || []).length;\n  const negativeCount = (text.match(negativeWords) || []).length;\n  \n  if (positiveCount > negativeCount * 1.5) return 'positive';\n  if (negativeCount > positiveCount * 1.5) return 'negative';\n  return 'neutral';\n}\n\n/**\n * Extract key phrases using simple heuristics\n */\nfunction extractKeyPhrases(text) {\n  // Extract capitalized phrases (likely important)\n  const capitalizedPhrases = text.match(/[A-Z][a-z]+(\\s+[A-Z][a-z]+)*/g) || [];\n  \n  // Extract phrases in quotes\n  const quotedPhrases = text.match(/[\"'][^\"']+[\"']/g) || [];\n  \n  // Extract technical terms\n  const technicalTerms = text.match(/[A-Z]+[a-z]*|[a-z]+[A-Z]+[a-z]*/g) || [];\n  \n  // Combine and deduplicate\n  const allPhrases = [...new Set([\n    ...capitalizedPhrases.slice(0, 5),\n    ...quotedPhrases.slice(0, 3),\n    ...technicalTerms.slice(0, 5)\n  ])];\n  \n  return allPhrases.slice(0, 10);\n}\n\n// Process all input documents\nconst results = [];\n\nfor (const doc of documents) {\n  try {\n    const text = doc.json.extracted_text || doc.json.content || '';\n    const documentId = doc.json.document_id;\n    \n    const chunkingResult = createChunks(text);\n    \n    results.push({\n      json: {\n        document_id: documentId,\n        chunks: chunkingResult.chunks,\n        metadata: chunkingResult.metadata,\n        success: true\n      }\n    });\n  } catch (error) {\n    results.push({\n      json: {\n        document_id: doc.json.document_id || 'unknown',\n        error: true,\n        error_message: error.message,\n        error_stack: error.stack\n      }\n    });\n  }\n}\n\nreturn results;"
      },
      "name": "Advanced Chunking",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1250, 300],
      "id": "advanced_chunking_107"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO document_chunks (\n  document_id,\n  chunk_index,\n  content,\n  content_length,\n  content_hash,\n  metadata\n) VALUES (\n  $1, $2, $3, $4, $5, $6::jsonb\n) ON CONFLICT (document_id, chunk_index) \nDO UPDATE SET \n  content = EXCLUDED.content,\n  content_length = EXCLUDED.content_length,\n  content_hash = EXCLUDED.content_hash,\n  metadata = EXCLUDED.metadata,\n  created_at = NOW()\nRETURNING id, document_id, chunk_index",
        "options": {
          "queryParams": "={{ [\n  $json.document_id,\n  $json.chunk_index,\n  $json.content,\n  $json.size,\n  $json.hash,\n  JSON.stringify($json.metadata)\n] }}",
          "queryBatching": {
            "mode": "independently",
            "batchSize": 100
          }
        }
      },
      "name": "Save Chunks",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1450, 300],
      "id": "save_chunks_108",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "operation": "update",
        "table": "processing_queue",
        "updateKey": "id",
        "columns": [
          {
            "column": "status",
            "value": "completed"
          },
          {
            "column": "updated_at",
            "value": "={{ new Date().toISOString() }}"
          }
        ],
        "options": {
          "queryParams": "={{ [$node['Get Next Document'].json.queue_id] }}"
        }
      },
      "name": "Update Queue Status",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1650, 300],
      "id": "update_queue_109"
    }
  ],
  "connections": {
    "Get Next Document": {
      "main": [
        [
          {
            "node": "Has Document?",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Has Document?": {
      "main": [
        [
          {
            "node": "Download from B2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Wait for Next Run",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Download from B2": {
      "main": [
        [
          {
            "node": "Route by Type",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Route by Type": {
      "main": [
        [
          {
            "node": "Extract PDF Text",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Extract Word Text",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Process Text File",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Mistral OCR",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Generic Extraction",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Extract PDF Text": {
      "main": [
        [
          {
            "node": "Advanced Chunking",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Mistral OCR": {
      "main": [
        [
          {
            "node": "Advanced Chunking",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Advanced Chunking": {
      "main": [
        [
          {
            "node": "Save Chunks",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Save Chunks": {
      "main": [
        [
          {
            "node": "Update Queue Status",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```
