## 10.8 Milestone 7: CrewAI Multi-Agent Integration via HTTP

### 10.8.1 Objectives
- Implement HTTP wrapper for CrewAI API
- Configure specialized agents
- Create multi-agent workflows
- Handle agent coordination
- Process agent outputs
- Integrate with main pipeline

### 10.8.2 Complete CrewAI HTTP Integration

```json
{
  "name": "CrewAI_Integration_v7_Complete",
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "https://crewai-api.example.com/v1/crews/create",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-API-Key",
              "value": "{{ $credentials.crewaiApiKey }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {\n  \"name\": \"Document Analysis Crew\",\n  \"agents\": [\n    {\n      \"name\": \"Research Analyst\",\n      \"role\": \"Senior Research Analyst\",\n      \"goal\": \"Analyze documents and extract key insights\",\n      \"backstory\": \"Expert analyst with 15 years of experience in document analysis and research\",\n      \"tools\": [\"document_search\", \"fact_checker\", \"summarizer\"],\n      \"llm_config\": {\n        \"model\": \"claude-3-sonnet\",\n        \"temperature\": 0.5\n      }\n    },\n    {\n      \"name\": \"Content Strategist\",\n      \"role\": \"Content Strategy Expert\",\n      \"goal\": \"Identify content patterns and strategic themes\",\n      \"backstory\": \"Seasoned strategist specializing in content organization and taxonomy\",\n      \"tools\": [\"pattern_analyzer\", \"theme_extractor\", \"categorizer\"],\n      \"llm_config\": {\n        \"model\": \"claude-3-sonnet\",\n        \"temperature\": 0.7\n      }\n    },\n    {\n      \"name\": \"Fact Checker\",\n      \"role\": \"Senior Fact Verification Specialist\",\n      \"goal\": \"Verify claims and validate information accuracy\",\n      \"backstory\": \"Meticulous fact-checker with expertise in verification methodologies\",\n      \"tools\": [\"web_search\", \"database_query\", \"citation_validator\"],\n      \"llm_config\": {\n        \"model\": \"claude-3-sonnet\",\n        \"temperature\": 0.3\n      }\n    }\n  ],\n  \"process\": \"sequential\",\n  \"memory\": true,\n  \"verbose\": true\n} }}"
      },
      "name": "Create CrewAI Team",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [450, 300],
      "id": "create_crew_601"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://crewai-api.example.com/v1/tasks/create",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {\n  \"crew_id\": $json.crew_id,\n  \"tasks\": [\n    {\n      \"description\": \"Analyze the uploaded document and extract key information including main topics, entities, dates, and important facts\",\n      \"agent\": \"Research Analyst\",\n      \"expected_output\": \"Structured analysis with key findings, entities, and facts\",\n      \"context\": {\n        \"document_id\": $json.document_id,\n        \"document_content\": $json.content\n      }\n    },\n    {\n      \"description\": \"Based on the analysis, identify strategic themes and categorize content into a hierarchical taxonomy\",\n      \"agent\": \"Content Strategist\",\n      \"expected_output\": \"Content taxonomy with themes, categories, and relationships\",\n      \"context_from_previous\": true\n    },\n    {\n      \"description\": \"Verify all factual claims and provide confidence scores for each piece of information\",\n      \"agent\": \"Fact Checker\",\n      \"expected_output\": \"Fact verification report with confidence scores and citations\",\n      \"context_from_previous\": true\n    }\n  ],\n  \"execution_mode\": \"sequential\",\n  \"max_iterations\": 5,\n  \"timeout\": 300\n} }}"
      },
      "name": "Define Tasks",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [650, 300],
      "id": "define_tasks_602"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://crewai-api.example.com/v1/crews/execute",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {\n  \"crew_id\": $json.crew_id,\n  \"task_ids\": $json.task_ids,\n  \"inputs\": {\n    \"document_id\": $json.document_id,\n    \"content\": $json.content,\n    \"metadata\": $json.metadata\n  },\n  \"stream\": false,\n  \"return_intermediate\": true\n} }}",
        "options": {
          "timeout": 300000
        }
      },
      "name": "Execute Crew Tasks",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [850, 300],
      "id": "execute_crew_603"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Process CrewAI execution results\nconst execution = $json;\nconst documentId = $node['Previous'].json.document_id;\n\n// Parse agent outputs\nconst agentResults = execution.results || [];\nconst processedResults = [];\n\nfor (const result of agentResults) {\n  const processed = {\n    agent: result.agent_name,\n    task: result.task_description,\n    status: result.status,\n    output: parseAgentOutput(result.output),\n    execution_time: result.execution_time_ms,\n    iterations: result.iterations,\n    confidence: result.confidence || 0.8\n  };\n  \n  processedResults.push(processed);\n}\n\n// Extract structured data from agent outputs\nfunction parseAgentOutput(output) {\n  try {\n    // Try to parse as JSON first\n    return JSON.parse(output);\n  } catch (e) {\n    // Otherwise, extract structured information\n    return extractStructuredData(output);\n  }\n}\n\nfunction extractStructuredData(text) {\n  const structured = {\n    summary: extractSection(text, 'SUMMARY'),\n    key_findings: extractBulletPoints(text, 'KEY FINDINGS'),\n    entities: extractBulletPoints(text, 'ENTITIES'),\n    themes: extractBulletPoints(text, 'THEMES'),\n    facts: extractBulletPoints(text, 'FACTS'),\n    recommendations: extractBulletPoints(text, 'RECOMMENDATIONS'),\n    raw_text: text\n  };\n  \n  return structured;\n}\n\nfunction extractSection(text, sectionName) {\n  const regex = new RegExp(`${sectionName}:?\\s*([^\\n]+(?:\\n(?!\\n|[A-Z]+:)[^\\n]+)*)`, 'i');\n  const match = text.match(regex);\n  return match ? match[1].trim() : '';\n}\n\nfunction extractBulletPoints(text, sectionName) {\n  const sectionText = extractSection(text, sectionName);\n  if (!sectionText) return [];\n  \n  const points = sectionText\n    .split(/\\n/)\n    .map(line => line.replace(/^[-*•]\\s*/, '').trim())\n    .filter(line => line.length > 0);\n  \n  return points;\n}\n\n// Combine results from all agents\nconst combinedAnalysis = {\n  document_id: documentId,\n  crew_execution_id: execution.execution_id,\n  status: execution.status,\n  total_execution_time_ms: execution.total_time_ms,\n  agent_results: processedResults,\n  consolidated_findings: consolidateFindings(processedResults),\n  metadata: {\n    crew_id: execution.crew_id,\n    task_count: agentResults.length,\n    success_rate: agentResults.filter(r => r.status === 'success').length / agentResults.length,\n    timestamp: new Date().toISOString()\n  }\n};\n\nfunction consolidateFindings(results) {\n  const consolidated = {\n    all_entities: [],\n    all_themes: [],\n    all_facts: [],\n    consensus_items: [],\n    conflicting_items: []\n  };\n  \n  // Collect all findings\n  for (const result of results) {\n    if (result.output.entities) {\n      consolidated.all_entities.push(...result.output.entities);\n    }\n    if (result.output.themes) {\n      consolidated.all_themes.push(...result.output.themes);\n    }\n    if (result.output.facts) {\n      consolidated.all_facts.push(...result.output.facts);\n    }\n  }\n  \n  // Remove duplicates\n  consolidated.all_entities = [...new Set(consolidated.all_entities)];\n  consolidated.all_themes = [...new Set(consolidated.all_themes)];\n  consolidated.all_facts = [...new Set(consolidated.all_facts)];\n  \n  return consolidated;\n}\n\nreturn [{\n  json: combinedAnalysis\n}];"
      },
      "name": "Process Agent Results",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1050, 300],
      "id": "process_agent_results_604"
    }
  ]
}
```

## 10.9 Advanced Features and Optimization

### 10.9.1 Batch Processing for Cost Optimization

```javascript
// Batch processing implementation for 90% cost savings
class BatchProcessor {
  constructor(config = {}) {
    this.batchSize = config.batchSize || 20;
    this.maxWaitTime = config.maxWaitTime || 5000; // 5 seconds
    this.queue = [];
    this.processing = false;
    this.timer = null;
  }
  
  async addToQueue(item) {
    this.queue.push({
      id: crypto.randomUUID(),
      item: item,
      timestamp: Date.now(),
      promise: null
    });
    
    // Start timer if not already running
    if (!this.timer) {
      this.timer = setTimeout(() => this.processBatch(), this.maxWaitTime);
    }
    
    // Process immediately if batch is full
    if (this.queue.length >= this.batchSize) {
      clearTimeout(this.timer);
      this.timer = null;
      await this.processBatch();
    }
  }
  
  async processBatch() {
    if (this.processing || this.queue.length === 0) return;
    
    this.processing = true;
    const batch = this.queue.splice(0, this.batchSize);
    
    try {
      // Process batch with Claude API
      const results = await this.callClaudeAPI(batch);
      
      // Distribute results back
      for (let i = 0; i < batch.length; i++) {
        batch[i].result = results[i];
        batch[i].completed = true;
      }
      
      // Calculate cost savings
      const individualCost = batch.length * 0.003; // Per request
      const batchCost = 0.003; // Single batch request
      const savings = ((individualCost - batchCost) / individualCost) * 100;
      
      console.log(`Batch processed: ${batch.length} items, ${savings.toFixed(1)}% cost savings`);
      
    } catch (error) {
      console.error('Batch processing error:', error);
      // Mark all items as failed
      for (const item of batch) {
        item.error = error;
        item.completed = true;
      }
    } finally {
      this.processing = false;
      
      // Process remaining items if any
      if (this.queue.length > 0) {
        this.timer = setTimeout(() => this.processBatch(), this.maxWaitTime);
      }
    }
  }
  
  async callClaudeAPI(batch) {
    // Combine all prompts into a single request
    const combinedPrompt = batch.map((item, index) => 
      `[Request ${index + 1}]\\n${item.item.prompt}\\n[End Request ${index + 1}]`
    ).join('\\n\\n');
    
    // Make single API call
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-3-sonnet-20240229',
        max_tokens: 4096,
        messages: [{
          role: 'user',
          content: `Process the following ${batch.length} requests and provide separate responses for each:\\n\\n${combinedPrompt}`
        }],
        metadata: {
          batch_id: crypto.randomUUID(),
          batch_size: batch.length
        }
      })
    });
    
    const result = await response.json();
    
    // Parse individual responses
    const responses = this.parseResponses(result.content[0].text, batch.length);
    return responses;
  }
  
  parseResponses(text, count) {
    const responses = [];
    const regex = /\\[Response (\\d+)\\]([\\s\\S]*?)\\[End Response \\d+\\]/g;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
      responses.push(match[2].trim());
    }
    
    // Ensure we have responses for all items
    while (responses.length < count) {
      responses.push('Processing error - no response generated');
    }
    
    return responses;
  }
}

// Usage in n8n
const batchProcessor = new BatchProcessor({
  batchSize: 20,
  maxWaitTime: 5000
});

// Add items to batch
for (const document of documents) {
  await batchProcessor.addToQueue({
    prompt: `Analyze this document: ${document.content}`,
    document_id: document.id
  });
}
```

### 10.9.2 Prompt Caching Implementation

```javascript
// Prompt caching for 90% cost reduction on repeated queries
class PromptCache {
  constructor(redisClient) {
    this.redis = redisClient;
    this.cachePrefix = 'prompt_cache:';
    this.ttl = 3600; // 1 hour
    this.stats = {
      hits: 0,
      misses: 0,
      savings: 0
    };
  }
  
  generateCacheKey(prompt, params = {}) {
    const normalized = this.normalizePrompt(prompt);
    const paramString = JSON.stringify(params, Object.keys(params).sort());
    const hash = crypto.createHash('sha256')
      .update(normalized + paramString)
      .digest('hex')
      .substring(0, 16);
    return `${this.cachePrefix}${hash}`;
  }
  
  normalizePrompt(prompt) {
    // Remove extra whitespace and normalize
    return prompt
      .toLowerCase()
      .replace(/\\s+/g, ' ')
      .trim();
  }
  
  async get(prompt, params = {}) {
    const key = this.generateCacheKey(prompt, params);
    
    try {
      const cached = await this.redis.get(key);
      
      if (cached) {
        this.stats.hits++;
        this.stats.savings += this.calculateSavings(prompt);
        
        return {
          response: JSON.parse(cached),
          cached: true,
          cache_key: key,
          savings: this.stats.savings
        };
      }
    } catch (error) {
      console.error('Cache get error:', error);
    }
    
    this.stats.misses++;
    return null;
  }
  
  async set(prompt, params, response) {
    const key = this.generateCacheKey(prompt, params);
    
    try {
      await this.redis.setex(
        key,
        this.ttl,
        JSON.stringify(response)
      );
      
      // Also cache with semantic similarity for fuzzy matching
      await this.setSemantic(prompt, key);
      
    } catch (error) {
      console.error('Cache set error:', error);
    }
  }
  
  async setSemantic(prompt, cacheKey) {
    // Generate embedding for prompt
    const embedding = await this.generateEmbedding(prompt);
    
    // Store in vector database for semantic search
    await this.storeVector(embedding, cacheKey);
  }
  
  async findSimilar(prompt, threshold = 0.9) {
    const embedding = await this.generateEmbedding(prompt);
    
    // Search for similar prompts
    const similar = await this.searchVectors(embedding, threshold);
    
    if (similar.length > 0) {
      // Return the most similar cached response
      const cacheKey = similar[0].cache_key;
      const cached = await this.redis.get(cacheKey);
      
      if (cached) {
        this.stats.hits++;
        return {
          response: JSON.parse(cached),
          cached: true,
          similarity: similar[0].similarity,
          cache_key: cacheKey
        };
      }
    }
    
    return null;
  }
  
  calculateSavings(prompt) {
    // Estimate token count
    const tokens = Math.ceil(prompt.length / 4);
    const costPerToken = 0.00002; // $0.02 per 1K tokens
    return tokens * costPerToken;
  }
  
  getStats() {
    const hitRate = this.stats.hits / (this.stats.hits + this.stats.misses);
    return {
      ...this.stats,
      hit_rate: hitRate,
      total_requests: this.stats.hits + this.stats.misses,
      estimated_savings_usd: this.stats.savings.toFixed(4)
    };
  }
}
```
