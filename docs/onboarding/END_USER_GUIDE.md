# Empire Chat UI - End User Guide

**Welcome to Empire!** This guide will help you get started with Empire's intelligent chat interface in just 5 minutes.

---

## What is Empire?

Empire is an advanced AI-powered knowledge assistant that helps you:
- **Find Information**: Search through your organization's documents and policies
- **Get Answers**: Ask questions in natural language and receive accurate, cited responses
- **Research Topics**: Conduct deep research with external sources when needed
- **Analyze Documents**: Process and understand complex documents automatically

**Key Features**:
- Semantic search across all your documents
- Intelligent caching for instant responses to common questions
- Multi-source answers combining internal knowledge with external research
- Secure, role-based access to ensure data privacy

---

## Getting Started (5 Minutes)

### Step 1: Access the Chat UI (1 minute)

1. Open your browser and navigate to: **https://jb-empire-chat.onrender.com**
2. You'll see the Empire login page

### Step 2: Sign In (1 minute)

1. Click **"Sign In"**
2. Enter your credentials:
   - **Email**: Your work email address
   - **Password**: Your secure password

3. If this is your first time:
   - Click **"Sign Up"** instead
   - Enter your email, create a password
   - Verify your email address
   - You'll be redirected to the chat interface

**Note**: Empire uses Clerk for secure authentication. Your credentials are never stored by Empire directly.

### Step 3: Your First Query (3 minutes)

Once logged in, you'll see the chat interface:

```
┌─────────────────────────────────────────────────────┐
│ Empire Chat                                    [⚙] │
├─────────────────────────────────────────────────────┤
│                                                     │
│                                                     │
│           👋 Welcome to Empire!                     │
│                                                     │
│   Ask me anything about your documents              │
│                                                     │
│                                                     │
├─────────────────────────────────────────────────────┤
│ What would you like to know?            [Send →]   │
└─────────────────────────────────────────────────────┘
```

**Try these sample queries**:

1. **Simple Lookup** (fastest, ~1-2 seconds):
   ```
   What is our refund policy?
   ```

2. **Complex Research** (~5-10 seconds):
   ```
   How do our insurance requirements compare to California state law?
   ```

3. **Document-Specific** (~3-5 seconds):
   ```
   Summarize the key points from the Q4 2024 financial report
   ```

**What Happens Behind the Scenes**:
- Empire checks its cache first (instant if cached)
- Searches your document database using AI
- Retrieves the most relevant information
- Synthesizes a clear answer with source citations

---

## Understanding Your Responses

### Response Format

Every response includes:

```
[Your Answer Here - synthesized from multiple sources]

Sources:
📄 California Insurance Requirements 2025
   Relevance: 95%
   Location: policies/insurance/ca_requirements.pdf

📄 Company Insurance Policy
   Relevance: 88%
   Location: internal/hr/insurance_policy.docx

Processed in: 5.2 seconds
From cache: No
```

**Key Elements**:
- **Answer**: Clear, natural language response
- **Sources**: Documents used with relevance scores
- **Processing Time**: How long the query took
- **Cache Status**: Whether this was a cached result

### Response Types

**1. Simple Answers** (Uncached: ~5s, Cached: ~0.3s)
- Direct lookups from your knowledge base
- Example: "What is our office address?"
- Best for: Factual questions with clear answers

**2. Research-Enhanced Answers** (~10-15s)
- Combines internal knowledge with external research
- Example: "What are the latest trends in our industry?"
- Best for: Questions requiring current information

**3. Multi-Document Analysis** (~30s-2min)
- Analyzes multiple documents to provide comprehensive answers
- Example: "Compare our last 3 quarterly reports"
- Best for: Cross-document insights and trends

---

## Tips for Better Results

### 1. Be Specific

❌ **Vague**: "Tell me about insurance"
✅ **Specific**: "What are the insurance requirements for California employees?"

### 2. Use Natural Language

You don't need to use keywords. Empire understands natural questions:

✅ "What's our policy on remote work?"
✅ "Can I work from home on Fridays?"
✅ "Are there any restrictions on telecommuting?"

All of these will find the same information.

### 3. Ask Follow-Up Questions

Empire maintains conversation context:

```
You: What are California insurance requirements?
Empire: [Provides detailed answer]

You: How does that compare to our current policy?
Empire: [Compares the two, understanding "that" refers to CA requirements]

You: What would we need to change?
Empire: [Suggests specific changes]
```

### 4. Request Different Formats

Ask for information in the format you need:

- "Give me a bulleted list of..."
- "Summarize in 3 sentences..."
- "Provide a detailed explanation of..."
- "Create a table comparing..."

---

## Common Use Cases

### Research & Learning

**Query**: "Explain how our procurement process works"

**Best For**:
- Onboarding new employees
- Understanding company processes
- Learning about policies and procedures

---

### Policy Lookups

**Query**: "What is the PTO accrual rate for employees with 3 years of service?"

**Best For**:
- HR questions
- Benefit inquiries
- Compliance checks

---

### Document Analysis

**Query**: "What are the main risks identified in the Q3 audit report?"

**Best For**:
- Executive summaries
- Risk assessment
- Compliance reviews

---

### Comparison & Analysis

**Query**: "How do our employee benefits compare to industry standards?"

**Best For**:
- Competitive analysis
- Benchmarking
- Strategic planning

---

## Features Explained

### Intelligent Caching

Empire remembers recent queries to provide instant responses:

**First time asking**: "What are California insurance requirements?"
- Processing time: ~8 seconds
- Status: **FRESH** (new search)

**Second time asking** (or very similar question):
- Processing time: ~0.3 seconds
- Status: **CACHED** (instant response)

**Benefits**:
- 96.7% faster for cached queries
- Consistent answers across your team
- Reduced server load

---

### Source Citations

Every answer includes clickable sources:

```
Sources:
📄 California Insurance Requirements 2025
   Relevance: 95%
   Location: policies/insurance/ca_requirements.pdf
   [View Document →]
```

Click **[View Document →]** to see the original source.

**Why This Matters**:
- Verify information accuracy
- Read source material in full context
- Understand where answers come from

---

### Real-Time Streaming

Watch Empire think as it processes your query:

```
🔍 Searching documents...
📊 Found 12 relevant sources...
🤖 Analyzing content...
✍️ Synthesizing answer...

[Response appears here]
```

**Benefits**:
- See progress in real-time
- Cancel queries if needed
- Understand processing steps

---

## Troubleshooting

### "No results found"

**Possible Reasons**:
1. Document hasn't been indexed yet
2. Question too vague
3. Information doesn't exist in knowledge base

**Solutions**:
- Rephrase your question more specifically
- Check if the document was recently uploaded (may take 5-10 minutes to index)
- Try broader keywords first, then narrow down

---

### Slow Responses

**Normal Processing Times**:
- Simple queries: 3-5 seconds
- Research queries: 10-15 seconds
- Multi-document analysis: 30-60 seconds

**If Slower Than Expected**:
- Check your internet connection
- Refresh the page and try again
- Ask a simpler version of your question first

---

### Unexpected Answers

**If the answer seems incorrect**:
1. Check the source citations - is Empire using the right documents?
2. Try rephrasing your question more specifically
3. Add context: "Based on the 2025 policy..." or "According to our latest handbook..."

**If asking about recent changes**:
- Specify the date: "What changed in our policy after January 2025?"
- Empire may be using older cached information for very recent updates

---

## Privacy & Security

### Your Data is Protected

- **Encrypted in Transit**: All communication uses HTTPS/TLS
- **Encrypted at Rest**: Documents stored with AES-256 encryption
- **Access Control**: You only see documents you have permission to access
- **Audit Logs**: All queries are logged for security (admin access only)

### What Empire Knows About You

Empire tracks:
- ✅ Your queries (for improving responses)
- ✅ Documents you access (for access control)
- ❌ Your password (stored securely by Clerk, not Empire)
- ❌ Personal browsing history

### Data Retention

- **Chat Sessions**: Stored for 30 days
- **Query History**: Kept for analytics (anonymized after 90 days)
- **Documents**: Retained per your organization's policy

---

## Keyboard Shortcuts

Make chatting faster with these shortcuts:

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift + Enter` | New line (without sending) |
| `Ctrl/Cmd + K` | Clear chat |
| `Ctrl/Cmd + /` | Focus search box |
| `Esc` | Cancel streaming response |

---

## Settings & Preferences

Click the **⚙ Settings** icon (top-right) to customize:

### Appearance
- **Theme**: Light, Dark, or Auto
- **Font Size**: Small, Medium, Large
- **Compact Mode**: Show more messages on screen

### Behavior
- **Streaming**: Enable/disable real-time response streaming
- **Auto-scroll**: Keep latest message in view
- **Sound**: Enable notification sounds

### Privacy
- **Query History**: Enable/disable saving your queries
- **Analytics**: Opt-in/out of usage analytics
- **Session Timeout**: Auto-logout after inactivity (15/30/60 min)

---

## FAQs

### How accurate are the answers?

Empire provides answers based on your organization's documents. Accuracy depends on:
- Quality of source documents
- Specificity of your question
- Recency of information

**Always verify critical information** using the source citations provided.

---

### Can I upload my own documents?

Currently, document upload is managed by administrators. Contact your IT team to:
- Request new documents be added
- Update existing documents
- Remove outdated information

---

### What happens if I ask something Empire doesn't know?

Empire will:
1. Search your knowledge base
2. Let you know if no relevant information was found
3. Suggest rephrasing or broadening your question

For questions requiring external research, Empire can search the web (if enabled by your admin).

---

### Can I share my chat history?

Yes! Click the **Share** button next to any response to:
- Copy a link to this conversation
- Export as PDF
- Email to colleagues

**Note**: Recipients must have access to the same documents to view source citations.

---

### How do I report incorrect information?

Click the **👎 Feedback** button below any response to:
- Report inaccuracy
- Suggest improvements
- Flag inappropriate content

Your feedback helps improve Empire for everyone.

---

## Getting Help

### Support Channels

**Email**: support@empire.ai
**Response Time**: Within 24 hours

**Slack**: #empire-support (if your organization uses Slack integration)
**Response Time**: Within 2 hours during business hours

**Documentation**: https://jb-empire-api.onrender.com/docs
**API Reference**: /docs/API_REFERENCE.md (for developers)

### Common Issues & Solutions

Visit our **Troubleshooting Guide**: /docs/TROUBLESHOOTING.md (coming soon)

---

## What's Next?

Now that you're familiar with Empire, try:

1. **Explore your knowledge base**: Ask about different departments and policies
2. **Bookmark frequent queries**: Save time by bookmarking common questions
3. **Share insights**: Use the share feature to collaborate with colleagues
4. **Provide feedback**: Help us improve by rating responses

**Advanced Features** (ask your admin about access):
- Direct API access for integrations
- Bulk document upload
- Custom workflows
- Analytics dashboards

---

## Tips from Power Users

### Create a "Cheat Sheet"

Keep a document with your most common queries:
- "What's the process for..."
- "Who do I contact for..."
- "Where can I find..."

### Use Empire for Onboarding

New to the team? Ask Empire:
- "What are the first things I should know?"
- "Where do I find the employee handbook?"
- "What are the key policies I need to understand?"

### Set Up Morning Briefings

Start your day with:
- "Summarize any policy changes this month"
- "What meetings do I have today?" (if calendar integration enabled)
- "Are there any urgent announcements?"

---

## Version History

**v7.3** (Current):
- ✅ Semantic caching for 96.7% faster repeat queries
- ✅ Enhanced LangGraph workflows with external tool support
- ✅ Real-time streaming responses
- ✅ Improved source citations

**v7.2**:
- Dual-database architecture (PostgreSQL + Neo4j)
- Row-level security for data isolation
- Multi-agent document processing

---

**Welcome to Empire!** 🚀

If you have any questions or need assistance, don't hesitate to reach out to our support team. Happy chatting!

---

**Last Updated**: 2025-01-17
**Version**: 7.3
**Audience**: End Users (non-technical)
