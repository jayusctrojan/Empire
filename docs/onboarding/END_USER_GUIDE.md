# Empire v7.5 - End User Guide

**Welcome to Empire!** This guide will help you get started with Empire's intelligent knowledge assistant in just 5 minutes.

---

## What is Empire?

Empire is an advanced AI-powered knowledge assistant that helps you:
- **Find Information**: Search through your organization's documents and policies
- **Get Answers**: Ask questions in natural language and receive accurate, cited responses
- **Generate Documents**: Create reports, spreadsheets, and presentations from AI responses
- **Research Topics**: Conduct deep research combining your knowledge base with AI reasoning
- **Analyze Documents**: Process images, audio, and video files automatically

**Key Features**:
- Multi-model AI pipeline for high-quality answers
- Document generation (DOCX, XLSX, PPTX, PDF)
- Unified search across chats, projects, knowledge base, and artifacts
- Organization-based data isolation and access control
- Desktop application with artifact preview and download

---

## Getting Started (5 Minutes)

### Step 1: Launch the Empire Desktop App (1 minute)

1. Open the **Empire Desktop** application
2. You'll see the login screen

### Step 2: Sign In (1 minute)

1. Click **"Sign In"**
2. Enter your credentials:
   - **Email**: Your work email address
   - **Password**: Your secure password

3. If this is your first time:
   - Click **"Sign Up"** instead
   - Enter your email, create a password
   - Verify your email address

**Note**: Empire uses Clerk for secure authentication. Your credentials are never stored by Empire directly.

### Step 3: Select Your Organization (30 seconds)

If you belong to multiple organizations:
1. You'll see the **Organization Picker** screen
2. Select your company/team from the list
3. You can switch organizations later using the dropdown in the sidebar

If you belong to only one organization, you'll skip this step automatically.

### Step 4: Your First Query (3 minutes)

Once logged in, you'll see the chat interface with the sidebar on the left.

**Try these sample queries**:

1. **Simple Lookup** (~5-8 seconds):
   ```
   What is our refund policy?
   ```

2. **Complex Analysis** (~8-13 seconds):
   ```
   How do our insurance requirements compare to California state law?
   ```

3. **Document Generation** (~10-15 seconds):
   ```
   Create a spreadsheet comparing our quarterly revenue for the last 3 quarters
   ```

**What You'll See During Processing**:

As your query is processed, you'll see phase indicators:
1. **"Analyzing..."** - AI is understanding your question
2. **"Searching..."** - Searching your knowledge base
3. **"Thinking..."** - AI is reasoning about the answer
4. **"Formatting..."** - AI is structuring the response

Then the formatted answer streams in token-by-token.

---

## Understanding Your Responses

### Response Format

Every response includes:
- **Formatted Answer**: Clear, structured response with headings, tables, and lists
- **Inline Citations**: [1], [2], [3] referencing source documents
- **Artifact Card**: If a document was generated, an inline card appears with download button

### Response Types

**1. Text Answers** (~5-13s)
- Direct answers from your knowledge base
- Example: "What is our office address?"
- Includes source citations

**2. Document Artifacts** (~10-15s)
- AI-generated files you can download
- Formats: DOCX (reports), XLSX (spreadsheets), PPTX (presentations), PDF
- Example: "Create a budget template for Q2"
- Appears as an artifact card in chat with preview and download

**3. Research-Enhanced Answers** (~10-15s)
- Combines internal knowledge with deep AI reasoning
- Example: "What are the latest trends in our industry?"
- Best for questions requiring analysis

---

## Key Features

### Unified Search (Cmd+K)

Press **Cmd+K** (or Ctrl+K on Windows) to open the search modal:

- Search across **Chats**, **Projects**, **Knowledge Base**, and **Artifacts**
- Use filter tabs to narrow results by type
- Results show relevance-ranked matches with highlighted text
- Click any result to navigate directly to it

### Document Generation

Ask Empire to create documents and they'll appear as downloadable artifacts:

- **"Create a report on..."** → DOCX document
- **"Make a spreadsheet of..."** → XLSX spreadsheet
- **"Build a presentation about..."** → PPTX slide deck

When a document is generated:
1. An **ArtifactCard** appears inline in the chat
2. Click **"Open"** to view a preview in the side panel
3. Click **"Download"** to save the file to your computer

### Quality Weights

Choose your preferred balance of speed vs. depth:

| Preset | Speed | Best For |
|--------|-------|----------|
| **Speed** | Fastest (~3-5s) | Quick lookups, simple questions |
| **Balanced** | Medium (~6-10s) | General queries (default) |
| **Quality** | Slowest (~10-15s) | Deep analysis, complex reasoning |

### File Uploads

You can upload files directly in chat:

- **Images** (PNG, JPG): AI analyzes the image content
- **Audio** (MP3, WAV, M4A): Automatically transcribed and analyzed
- **Video** (MP4, MOV): Key frames extracted and analyzed
- **Documents** (PDF, DOCX): Added to conversation context

### Organization Switching

If you belong to multiple organizations:
1. Click the org dropdown in the sidebar header
2. Select a different organization
3. All data (chats, projects, KB, artifacts) switches to that org's scope

---

## Tips for Better Results

### 1. Be Specific

- **Vague**: "Tell me about insurance"
- **Specific**: "What are the insurance requirements for California employees?"

### 2. Use Natural Language

You don't need keywords. Empire understands natural questions:
- "What's our policy on remote work?"
- "Can I work from home on Fridays?"
- "Are there any restrictions on telecommuting?"

All of these will find the same information.

### 3. Ask Follow-Up Questions

Empire maintains conversation context:

```
You: What are California insurance requirements?
Empire: [Provides detailed answer with citations]

You: How does that compare to our current policy?
Empire: [Compares the two, understanding "that" refers to CA requirements]
```

### 4. Request Specific Formats

Ask for information in the format you need:
- "Give me a bulleted list of..."
- "Summarize in 3 sentences..."
- "Create a table comparing..."
- "Generate a spreadsheet with..."
- "Make a presentation about..."

### 5. Use Quality Weights

- Switch to **Speed** for quick factual lookups
- Use **Quality** when you need thorough analysis
- **Balanced** works well for most queries

---

## Common Use Cases

### Research & Learning
**Query**: "Explain how our procurement process works"
- Great for onboarding, understanding processes, learning policies

### Policy Lookups
**Query**: "What is the PTO accrual rate for employees with 3 years of service?"
- HR questions, benefit inquiries, compliance checks

### Document Generation
**Query**: "Create a quarterly report template with revenue, expenses, and profit sections"
- Reports, spreadsheets, presentations, templates

### Comparison & Analysis
**Query**: "Compare our employee benefits to industry standards"
- Competitive analysis, benchmarking, strategic planning

### Document Analysis
**Query**: "What are the main risks identified in the Q3 audit report?"
- Executive summaries, risk assessment, compliance reviews

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + K` | Open unified search |
| `Enter` | Send message |
| `Shift + Enter` | New line (without sending) |
| `Esc` | Close search modal / Cancel streaming |
| Arrow keys | Navigate search results |

---

## Troubleshooting

### "No results found"

**Solutions**:
- Rephrase your question more specifically
- Check if the document was recently uploaded (may take a few minutes to index)
- Try broader keywords first, then narrow down
- Make sure you're in the correct organization

### Slow Responses

**Normal Processing Times**:
- Speed mode: 3-5 seconds
- Balanced mode: 6-10 seconds
- Quality mode: 10-15 seconds

**If Slower Than Expected**:
- Check your internet connection
- The AI pipeline involves 3 model calls — some latency is normal
- Try Speed mode for faster responses

### Unexpected Answers

1. Check the source citations — is Empire using the right documents?
2. Try rephrasing your question more specifically
3. Add context: "Based on the 2025 policy..." or "According to our latest handbook..."

### Artifact Not Downloading

1. Ensure the desktop app has permission to access your Downloads folder
2. Try clicking "Download" again
3. Check the artifact panel (click "Open" on the artifact card)

---

## Privacy & Security

### Your Data is Protected

- **Encrypted in Transit**: All communication uses HTTPS/TLS
- **Encrypted at Rest**: Documents stored with AES-256 encryption
- **Organization Isolation**: You only see data within your current organization
- **Role-Based Access**: Owners, Admins, Members, and Viewers have different permissions
- **Audit Logs**: All queries are logged for security (admin access only)

---

## Version History

**v7.5** (Current):
- Multi-model AI pipeline (Sonnet 4.5 + Kimi K2.5 Thinking)
- Desktop application (Tauri 2.x + React)
- Document generation (DOCX, XLSX, PPTX, PDF)
- Inline artifact preview and download
- Multi-tenant organizations with role-based access
- Unified search across all content types (Cmd+K)
- Multimodal processing (images, audio, video)
- Phase indicators during query processing

**v7.3**:
- Semantic caching for faster repeat queries
- Real-time streaming responses
- Enhanced source citations
- 15 specialized AI agents

**v7.2**:
- Dual-database architecture (PostgreSQL + Neo4j)
- Row-level security for data isolation
- Multi-agent document processing

---

**Welcome to Empire!**

If you have any questions or need assistance, don't hesitate to reach out to your admin or the support team.

---

**Last Updated**: 2026-02-19
**Version**: 7.5
**Audience**: End Users (non-technical)
