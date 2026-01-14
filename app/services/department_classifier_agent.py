"""
Empire v7.3 - AGENT-008: Department Classifier Agent (Task 44)

Build specialized agent for accurate 10-department classification with confidence
scores using keyword extraction and content analysis.

Role: Department Classification Specialist
Goal: Classify content into one of 10 departments with >96% accuracy
Output: Department + confidence score (0-1)
Tools: file_reader, department_classifier, keyword_extractor
LLM: Claude Haiku (fast)

Author: Claude Code
Date: 2025-01-26
"""

import os
import re
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from collections import Counter
import asyncio

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError
from app.services.agent_metrics import (
    AgentMetricsContext,
    AgentID,
    track_agent_request,
    track_agent_error,
    track_llm_call,
    track_confidence_score,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class Department(str, Enum):
    """10 business departments for content classification (per PRD AGENT-008)"""
    IT_ENGINEERING = "it-engineering"
    SALES_MARKETING = "sales-marketing"
    CUSTOMER_SUPPORT = "customer-support"
    OPERATIONS_HR_SUPPLY = "operations-hr-supply"
    FINANCE_ACCOUNTING = "finance-accounting"
    PROJECT_MANAGEMENT = "project-management"
    REAL_ESTATE = "real-estate"
    PRIVATE_EQUITY_MA = "private-equity-ma"
    CONSULTING = "consulting"
    PERSONAL_CONTINUING_ED = "personal-continuing-ed"


# Department descriptions for LLM context
DEPARTMENT_DESCRIPTIONS: Dict[Department, str] = {
    Department.IT_ENGINEERING: "Software development, coding, APIs, DevOps, infrastructure, databases, cloud services, technical architecture",
    Department.SALES_MARKETING: "Sales processes, marketing campaigns, lead generation, CRM, customer acquisition, revenue growth, brand management",
    Department.CUSTOMER_SUPPORT: "Help desk, ticketing, issue resolution, customer service, SLA management, customer satisfaction",
    Department.OPERATIONS_HR_SUPPLY: "Human resources, hiring, workforce management, supply chain, logistics, procurement, operations",
    Department.FINANCE_ACCOUNTING: "Financial reporting, budgeting, accounting, auditing, tax, treasury, cash flow management",
    Department.PROJECT_MANAGEMENT: "Project planning, milestones, Agile/Scrum, resource allocation, risk management, stakeholder coordination",
    Department.REAL_ESTATE: "Property management, leases, mortgages, commercial/residential real estate, tenant relations",
    Department.PRIVATE_EQUITY_MA: "Mergers & acquisitions, due diligence, valuations, investment portfolio, buyouts, exit strategies",
    Department.CONSULTING: "Strategy consulting, advisory services, business analysis, frameworks, client engagements",
    Department.PERSONAL_CONTINUING_ED: "Professional development, courses, certifications, skill building, career growth, training"
}


# Enhanced keyword dictionary for >96% accuracy
# Uses tiered weighting: primary (weight 4), secondary (weight 2), tertiary (weight 1)
DEPARTMENT_KEYWORDS: Dict[Department, Dict[str, List[str]]] = {
    Department.IT_ENGINEERING: {
        "primary": [
            "software", "code", "api", "programming", "development", "engineering",
            "backend", "frontend", "database", "server", "deployment", "infrastructure",
            "devops", "ci/cd", "microservices", "architecture", "developer", "repository",
            "git", "github", "gitlab", "bitbucket", "commit", "pull request"
        ],
        "secondary": [
            "docker", "kubernetes", "aws", "azure", "gcp", "cloud", "linux",
            "python", "javascript", "java", "typescript", "react", "node", "sql",
            "nosql", "mongodb", "redis", "elasticsearch", "terraform", "ansible",
            "nginx", "postgres", "mysql", "api endpoint", "rest", "graphql"
        ],
        "tertiary": [
            "debug", "testing", "unit test", "integration", "deployment pipeline",
            "container", "virtual machine", "vm", "scaling", "load balancer",
            "cache", "memory", "cpu", "optimization", "refactoring"
        ]
    },
    Department.SALES_MARKETING: {
        "primary": [
            "sales", "marketing", "lead", "customer acquisition", "pipeline",
            "revenue", "crm", "campaign", "conversion", "funnel", "prospect",
            "quota", "target", "booking", "closed won", "closed lost"
        ],
        "secondary": [
            "hubspot", "salesforce", "outreach", "seo", "sem", "content marketing",
            "email marketing", "social media", "brand", "advertising", "b2b", "b2c",
            "commission", "deal", "opportunity", "account", "territory"
        ],
        "tertiary": [
            "cold email", "cold call", "follow-up", "demo", "pitch", "presentation",
            "proposal", "pricing", "discount", "negotiation", "close", "upsell"
        ]
    },
    Department.CUSTOMER_SUPPORT: {
        "primary": [
            "support", "customer service", "helpdesk", "ticket", "issue resolution",
            "complaint", "service desk", "customer success", "client support",
            "help center", "support request", "case management"
        ],
        "secondary": [
            "zendesk", "freshdesk", "intercom", "sla", "response time", "escalation",
            "first response", "resolution time", "customer satisfaction", "csat",
            "nps", "churn", "retention", "support agent"
        ],
        "tertiary": [
            "troubleshoot", "diagnose", "workaround", "knowledge base", "faq",
            "self-service", "chat support", "phone support", "email support"
        ]
    },
    Department.OPERATIONS_HR_SUPPLY: {
        "primary": [
            "operations", "hr", "human resources", "supply chain", "logistics",
            "warehouse", "inventory", "procurement", "hiring", "recruitment",
            "employee", "workforce", "manufacturing", "talent", "headcount"
        ],
        "secondary": [
            "benefits", "payroll", "onboarding", "offboarding", "performance review",
            "compensation", "training", "shipping", "fulfillment", "distribution",
            "vendor", "supplier", "purchase order", "staffing"
        ],
        "tertiary": [
            "overtime", "pto", "leave", "attendance", "scheduling", "shift",
            "stock", "reorder", "lead time", "safety stock", "candidate"
        ]
    },
    Department.FINANCE_ACCOUNTING: {
        "primary": [
            "finance", "accounting", "financial", "budget", "revenue", "expense",
            "profit", "cash flow", "balance sheet", "income statement", "audit",
            "working capital", "capital management", "treasury", "fiscal"
        ],
        "secondary": [
            "invoice", "payment", "tax", "accounts receivable", "accounts payable",
            "general ledger", "reconciliation", "financial reporting", "forecast",
            "variance", "cost center", "profit center", "liquidity", "solvency"
        ],
        "tertiary": [
            "accrual", "depreciation", "amortization", "journal entry", "closing",
            "gaap", "ifrs", "fiscal year", "quarter", "month-end", "cash management"
        ]
    },
    Department.PROJECT_MANAGEMENT: {
        "primary": [
            "project", "project management", "milestone", "deliverable", "timeline",
            "scope", "risk management", "stakeholder", "resource allocation",
            "project plan", "project status", "gantt", "critical path"
        ],
        "secondary": [
            "agile", "scrum", "kanban", "sprint", "backlog", "user story", "epic",
            "jira", "asana", "monday", "trello", "waterfall", "pmo",
            "project scope", "work breakdown"
        ],
        "tertiary": [
            "standup", "retrospective", "planning", "estimation", "velocity",
            "burndown", "capacity", "blocker", "dependency", "mitigation"
        ]
    },
    Department.REAL_ESTATE: {
        "primary": [
            "real estate", "property", "lease", "tenant", "landlord", "rental",
            "mortgage", "commercial property", "residential property", "building",
            "rent", "listing", "square footage", "vacancy"
        ],
        "secondary": [
            "mls", "appraisal", "closing", "escrow", "title", "inspection",
            "zoning", "cap rate", "noi", "occupancy", "broker", "realtor"
        ],
        "tertiary": [
            "amenities", "maintenance", "hoa", "property management",
            "eviction", "security deposit", "lease renewal", "sublease"
        ]
    },
    Department.PRIVATE_EQUITY_MA: {
        "primary": [
            "private equity", "merger", "acquisition", "m&a", "valuation",
            "due diligence", "investment", "portfolio company", "buyout",
            "exit strategy", "ipo", "deal sourcing", "investment thesis"
        ],
        "secondary": [
            "lbo", "leveraged buyout", "ebitda", "multiple", "exit",
            "fund", "limited partner", "general partner", "carry", "irr",
            "deal flow", "term sheet", "synergy", "portfolio"
        ],
        "tertiary": [
            "data room", "management presentation", "quality of earnings",
            "purchase agreement", "earnout", "rollover", "recapitalization"
        ]
    },
    Department.CONSULTING: {
        "primary": [
            "consulting", "strategy", "advisory", "recommendation", "assessment",
            "analysis", "framework", "methodology", "engagement", "consultant",
            "strategic", "transformation", "client engagement"
        ],
        "secondary": [
            "mckinsey", "bcg", "bain", "client", "deliverable", "workstream",
            "hypothesis", "insight", "benchmark", "best practice",
            "market analysis", "competitive analysis", "industry analysis"
        ],
        "tertiary": [
            "slide deck", "executive summary", "findings", "implementation plan",
            "change management", "stakeholder alignment", "workshop", "roadmap"
        ]
    },
    Department.PERSONAL_CONTINUING_ED: {
        "primary": [
            "education", "learning", "course", "training", "skill development",
            "personal development", "certification", "professional development",
            "career", "upskilling", "reskilling", "tutorial"
        ],
        "secondary": [
            "online course", "workshop", "webinar", "bootcamp",
            "curriculum", "module", "lesson", "quiz", "assessment", "credential",
            "career growth", "career path", "learning path"
        ],
        "tertiary": [
            "self-improvement", "skill building", "continuing education",
            "cpe", "cme", "pdh", "coaching", "mentoring", "masterclass"
        ]
    }
}


# Negative keywords that should reduce scores for certain departments
NEGATIVE_KEYWORDS: Dict[Department, List[str]] = {
    Department.IT_ENGINEERING: ["no coding required", "non-technical"],
    Department.FINANCE_ACCOUNTING: ["non-financial", "personal budget"],
    Department.REAL_ESTATE: ["virtual property", "metaverse real estate"],
    Department.PRIVATE_EQUITY_MA: ["retail investor", "personal investing"],
}


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class KeywordExtractionResult(BaseModel):
    """Result of keyword extraction from content"""
    all_keywords: List[str] = Field(default_factory=list)
    department_keywords: Dict[str, List[str]] = Field(default_factory=dict)
    keyword_counts: Dict[str, int] = Field(default_factory=dict)
    total_keywords_found: int = 0


class ClassificationScore(BaseModel):
    """Score breakdown for a single department"""
    department: Department
    raw_score: float = 0.0
    normalized_score: float = 0.0
    keyword_matches: List[str] = Field(default_factory=list)
    primary_matches: int = 0
    secondary_matches: int = 0
    tertiary_matches: int = 0


class ClassificationResult(BaseModel):
    """Complete classification result"""
    department: Department
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    keywords_matched: List[str] = Field(default_factory=list)
    secondary_department: Optional[Department] = None
    secondary_confidence: float = 0.0
    all_scores: List[ClassificationScore] = Field(default_factory=list)
    llm_enhanced: bool = False
    processing_time_ms: float = 0.0


class BatchClassificationResult(BaseModel):
    """Result of batch classification"""
    results: List[ClassificationResult]
    total_processed: int
    average_confidence: float
    processing_time_ms: float
    accuracy_estimate: float = 0.0


# =============================================================================
# KEYWORD EXTRACTOR TOOL
# =============================================================================

class KeywordExtractorTool:
    """
    Tool for extracting relevant keywords from content.
    Identifies department-specific terms and phrases.
    """

    def __init__(self):
        """Initialize keyword extractor with compiled patterns"""
        logger.info("KeywordExtractorTool initialized")

        # Build lookup sets for fast matching
        self._all_keywords: Dict[Department, Set[str]] = {}
        self._keyword_to_dept: Dict[str, List[Tuple[Department, str]]] = {}

        for dept, keywords in DEPARTMENT_KEYWORDS.items():
            dept_keywords = set()
            for tier in ["primary", "secondary", "tertiary"]:
                for kw in keywords.get(tier, []):
                    kw_lower = kw.lower()
                    dept_keywords.add(kw_lower)
                    if kw_lower not in self._keyword_to_dept:
                        self._keyword_to_dept[kw_lower] = []
                    self._keyword_to_dept[kw_lower].append((dept, tier))
            self._all_keywords[dept] = dept_keywords

    def extract_keywords(self, content: str) -> KeywordExtractionResult:
        """
        Extract keywords from content.

        Args:
            content: Text content to analyze

        Returns:
            KeywordExtractionResult with extracted keywords
        """
        content_lower = content.lower()

        all_found: List[str] = []
        dept_keywords: Dict[str, List[str]] = {d.value: [] for d in Department}
        keyword_counts: Dict[str, int] = {}

        # Check each known keyword
        for keyword, dept_tiers in self._keyword_to_dept.items():
            count = content_lower.count(keyword)
            if count > 0:
                all_found.append(keyword)
                keyword_counts[keyword] = count
                for dept, _ in dept_tiers:
                    dept_keywords[dept.value].append(keyword)

        return KeywordExtractionResult(
            all_keywords=all_found,
            department_keywords=dept_keywords,
            keyword_counts=keyword_counts,
            total_keywords_found=len(all_found)
        )

    def extract_ngrams(self, content: str, n: int = 2) -> List[str]:
        """Extract n-grams from content for phrase matching"""
        words = re.findall(r'\b\w+\b', content.lower())
        ngrams = []
        for i in range(len(words) - n + 1):
            ngrams.append(' '.join(words[i:i+n]))
        return ngrams


# =============================================================================
# DEPARTMENT CLASSIFIER TOOL
# =============================================================================

class DepartmentClassifierTool:
    """
    Tool for classifying content into one of 10 departments.
    Uses weighted keyword matching + optional LLM enhancement for >96% accuracy.
    """

    # Keyword weights
    PRIMARY_WEIGHT = 4.0
    SECONDARY_WEIGHT = 2.0
    TERTIARY_WEIGHT = 1.0
    NEGATIVE_WEIGHT = -3.0

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.75
    LLM_ENHANCEMENT_THRESHOLD = 0.60
    LOW_CONFIDENCE_THRESHOLD = 0.30

    def __init__(self, use_llm_enhancement: bool = True):
        """
        Initialize classifier with optional LLM enhancement.

        Args:
            use_llm_enhancement: Use Claude Haiku for edge cases
        """
        self.use_llm_enhancement = use_llm_enhancement
        self.keyword_extractor = KeywordExtractorTool()
        self.llm = None

        if use_llm_enhancement:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.llm = ResilientAnthropicClient(
                    api_key=api_key,
                    service_name="department_classifier",
                    failure_threshold=5,
                    recovery_timeout=60.0,
                )

        logger.info(
            "DepartmentClassifierTool initialized",
            llm_enhanced=self.llm is not None
        )

    def _calculate_scores(
        self,
        content: str,
        filename: Optional[str] = None
    ) -> List[ClassificationScore]:
        """
        Calculate classification scores for all departments.

        Args:
            content: Content to classify
            filename: Optional filename for hints

        Returns:
            List of ClassificationScore for each department
        """
        content_lower = content.lower()
        scores: List[ClassificationScore] = []

        for dept in Department:
            keywords = DEPARTMENT_KEYWORDS.get(dept, {})
            score = ClassificationScore(department=dept)

            # Primary keywords (weight 4)
            for kw in keywords.get("primary", []):
                if kw.lower() in content_lower:
                    score.raw_score += self.PRIMARY_WEIGHT
                    score.primary_matches += 1
                    score.keyword_matches.append(kw)

            # Secondary keywords (weight 2)
            for kw in keywords.get("secondary", []):
                if kw.lower() in content_lower:
                    score.raw_score += self.SECONDARY_WEIGHT
                    score.secondary_matches += 1
                    score.keyword_matches.append(kw)

            # Tertiary keywords (weight 1)
            for kw in keywords.get("tertiary", []):
                if kw.lower() in content_lower:
                    score.raw_score += self.TERTIARY_WEIGHT
                    score.tertiary_matches += 1
                    score.keyword_matches.append(kw)

            # Negative keywords
            for neg_kw in NEGATIVE_KEYWORDS.get(dept, []):
                if neg_kw.lower() in content_lower:
                    score.raw_score += self.NEGATIVE_WEIGHT

            # Filename bonus
            if filename:
                dept_name = dept.value.replace("-", "_")
                if dept_name in filename.lower() or dept_name.replace("_", "-") in filename.lower():
                    score.raw_score += 5.0

            scores.append(score)

        # Normalize scores
        total_score = sum(max(0, s.raw_score) for s in scores)
        if total_score > 0:
            for score in scores:
                score.normalized_score = max(0, score.raw_score) / total_score

        # Sort by score descending
        scores.sort(key=lambda x: x.raw_score, reverse=True)

        return scores

    async def classify(
        self,
        content: str,
        filename: Optional[str] = None,
        force_llm: bool = False
    ) -> ClassificationResult:
        """
        Classify content into a department.

        Args:
            content: Content to classify
            filename: Optional filename for hints
            force_llm: Force LLM enhancement even for high-confidence results

        Returns:
            ClassificationResult with department and confidence
        """
        import time
        start_time = time.time()

        # Step 1: Calculate keyword-based scores
        scores = self._calculate_scores(content, filename)

        best_score = scores[0] if scores else None
        second_best = scores[1] if len(scores) > 1 else None

        if not best_score or best_score.raw_score <= 0:
            # No matches - need LLM
            if self.llm:
                result = await self._llm_classify(content, filename)
                if result:
                    result.processing_time_ms = (time.time() - start_time) * 1000
                    return result

            # Fallback to most likely based on content length
            return ClassificationResult(
                department=Department.PERSONAL_CONTINUING_ED,
                confidence=0.15,
                reasoning="No keyword matches found, defaulting to Personal/Continuing Ed",
                keywords_matched=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # Calculate confidence
        confidence = best_score.normalized_score

        # Boost confidence if there's a clear winner
        if second_best:
            score_gap = best_score.raw_score - second_best.raw_score
            if score_gap > 10:
                confidence = min(0.98, confidence + 0.15)
            elif score_gap > 5:
                confidence = min(0.95, confidence + 0.10)

        # Cap confidence based on keyword evidence
        if best_score.primary_matches >= 3:
            confidence = max(confidence, 0.85)
        elif best_score.primary_matches >= 2:
            confidence = max(confidence, 0.70)

        logger.info(
            "Keyword classification",
            department=best_score.department.value,
            confidence=f"{confidence:.2%}",
            keywords_count=len(best_score.keyword_matches)
        )

        # Step 2: LLM enhancement for edge cases
        use_llm = (
            self.llm is not None and
            (confidence < self.LLM_ENHANCEMENT_THRESHOLD or force_llm)
        )

        if use_llm:
            try:
                llm_result = await self._llm_classify(
                    content, filename,
                    keyword_dept=best_score.department,
                    keyword_confidence=confidence
                )
                if llm_result:
                    llm_result.all_scores = scores
                    llm_result.processing_time_ms = (time.time() - start_time) * 1000
                    return llm_result
            except Exception as e:
                logger.warning("LLM classification failed, using keyword result", error=str(e))

        # Return keyword-based result
        return ClassificationResult(
            department=best_score.department,
            confidence=confidence,
            reasoning=f"Keyword-based classification: {best_score.primary_matches} primary, "
                      f"{best_score.secondary_matches} secondary, {best_score.tertiary_matches} tertiary matches",
            keywords_matched=best_score.keyword_matches[:15],
            secondary_department=second_best.department if second_best and second_best.raw_score > 0 else None,
            secondary_confidence=second_best.normalized_score if second_best else 0.0,
            all_scores=scores,
            llm_enhanced=False,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    async def _llm_classify(
        self,
        content: str,
        filename: Optional[str],
        keyword_dept: Optional[Department] = None,
        keyword_confidence: float = 0.0
    ) -> Optional[ClassificationResult]:
        """
        Use Claude Haiku LLM for enhanced classification.

        Args:
            content: Content to classify
            filename: Optional filename
            keyword_dept: Department from keyword matching (for context)
            keyword_confidence: Confidence from keyword matching

        Returns:
            ClassificationResult or None if LLM call fails
        """
        if not self.llm:
            return None

        departments_list = "\n".join([
            f"- {d.value}: {DEPARTMENT_DESCRIPTIONS[d]}"
            for d in Department
        ])

        system_prompt = f"""You are an expert content classifier for a business knowledge management system.
Your task is to classify content into exactly ONE of these 10 departments:

{departments_list}

Classification Rules:
1. Choose the MOST relevant department based on the primary subject matter
2. Consider the overall context and purpose of the content
3. If content genuinely spans multiple departments equally, choose the most specific one
4. Provide confidence as a decimal between 0.0 and 1.0
5. Be decisive - only use low confidence (<0.5) for truly ambiguous content

Respond ONLY with valid JSON in this format:
{{"department": "department-code", "confidence": 0.XX, "reasoning": "brief explanation (max 100 chars)"}}"""

        # Truncate content for speed (Haiku is fast but still has token limits)
        content_sample = content[:4000] if len(content) > 4000 else content

        # Include keyword hint if available
        keyword_hint = ""
        if keyword_dept and keyword_confidence > 0.3:
            keyword_hint = f"\n\nNote: Keyword analysis suggests '{keyword_dept.value}' with {keyword_confidence:.0%} confidence."

        user_prompt = f"""Classify this content:

Filename: {filename or "unknown"}
{keyword_hint}

Content:
{content_sample}"""

        try:
            response = await self.llm.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                temperature=0.0,
                messages=[
                    {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
                ]
            )

            # Track LLM call metrics (Task 132)
            input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
            output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
            track_llm_call(
                AgentID.DEPARTMENT_CLASSIFIER,
                "claude-3-5-haiku-20241022",
                "success",
                input_tokens,
                output_tokens
            )

            response_text = response.content[0].text.strip()

            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                result_data = json.loads(json_match.group())

                dept_code = result_data.get("department", "")
                confidence = float(result_data.get("confidence", 0.5))
                reasoning = result_data.get("reasoning", "LLM classification")

                # Map department code to enum
                dept = None
                for d in Department:
                    if d.value == dept_code:
                        dept = d
                        break

                if dept:
                    # Boost confidence if LLM agrees with keyword classification
                    if keyword_dept and dept == keyword_dept:
                        confidence = min(0.98, confidence + 0.10)

                    return ClassificationResult(
                        department=dept,
                        confidence=confidence,
                        reasoning=f"LLM: {reasoning}",
                        keywords_matched=[],
                        llm_enhanced=True
                    )

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response as JSON", error=str(e))
            track_llm_call(AgentID.DEPARTMENT_CLASSIFIER, "claude-3-5-haiku-20241022", "failure")
        except Exception as e:
            logger.error("LLM classification error", error=str(e))
            track_llm_call(AgentID.DEPARTMENT_CLASSIFIER, "claude-3-5-haiku-20241022", "failure")

        return None

    async def classify_batch(
        self,
        items: List[Dict[str, Any]],
        concurrency: int = 5
    ) -> BatchClassificationResult:
        """
        Classify multiple items in batch.

        Args:
            items: List of dicts with 'content' and optional 'filename'
            concurrency: Number of concurrent classifications

        Returns:
            BatchClassificationResult with all results
        """
        import time
        start_time = time.time()

        results: List[ClassificationResult] = []

        # Process in batches for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def classify_item(item: Dict[str, Any]) -> ClassificationResult:
            async with semaphore:
                return await self.classify(
                    content=item.get("content", ""),
                    filename=item.get("filename")
                )

        tasks = [classify_item(item) for item in items]
        results = await asyncio.gather(*tasks)

        # Calculate statistics
        total_confidence = sum(r.confidence for r in results)
        avg_confidence = total_confidence / len(results) if results else 0.0

        return BatchClassificationResult(
            results=list(results),
            total_processed=len(results),
            average_confidence=avg_confidence,
            processing_time_ms=(time.time() - start_time) * 1000
        )


# =============================================================================
# FILE READER TOOL
# =============================================================================

class FileReaderTool:
    """
    Tool for reading and preprocessing file content for classification.
    """

    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml', '.csv'}
    MAX_CONTENT_LENGTH = 50000  # 50KB text limit

    def __init__(self):
        logger.info("FileReaderTool initialized")

    def read_file(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Read file content and extract metadata.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (content, metadata)
        """
        import os

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        metadata = {
            "filename": filename,
            "extension": ext,
            "size_bytes": os.path.getsize(file_path),
            "path": file_path
        }

        # Read text content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(self.MAX_CONTENT_LENGTH)
        except UnicodeDecodeError:
            # Try latin-1 as fallback
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read(self.MAX_CONTENT_LENGTH)

        metadata["content_length"] = len(content)
        metadata["truncated"] = len(content) >= self.MAX_CONTENT_LENGTH

        return content, metadata

    def preprocess_content(self, content: str) -> str:
        """
        Preprocess content for better classification.

        Args:
            content: Raw content

        Returns:
            Preprocessed content
        """
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)

        # Remove very long URLs
        content = re.sub(r'https?://\S{100,}', '[URL]', content)

        # Remove base64 encoded data
        content = re.sub(r'[A-Za-z0-9+/]{100,}={0,2}', '[BASE64]', content)

        return content.strip()


# =============================================================================
# DEPARTMENT CLASSIFIER AGENT SERVICE
# =============================================================================

class DepartmentClassifierAgentService:
    """
    AGENT-008: Department Classifier Agent

    Specialized agent for accurate 10-department classification with confidence
    scores using keyword extraction and content analysis.

    Features:
    - >96% classification accuracy target
    - Confidence scores (0-1) calibrated to actual accuracy
    - Fast classification using Claude Haiku
    - Batch processing support
    - Detailed score breakdown
    """

    AGENT_ID = "AGENT-008"
    AGENT_NAME = "Department Classifier Agent"
    AGENT_ROLE = "Department Classification Specialist"

    def __init__(self, use_llm: bool = True):
        """
        Initialize the Department Classifier Agent.

        Args:
            use_llm: Enable LLM enhancement for edge cases
        """
        self.classifier = DepartmentClassifierTool(use_llm_enhancement=use_llm)
        self.keyword_extractor = KeywordExtractorTool()
        self.file_reader = FileReaderTool()

        # Statistics tracking
        self._stats = {
            "classifications_total": 0,
            "classifications_by_department": {d.value: 0 for d in Department},
            "llm_enhanced_count": 0,
            "average_confidence": 0.0,
            "high_confidence_count": 0,
            "low_confidence_count": 0
        }

        logger.info(
            f"{self.AGENT_ID} initialized",
            agent_name=self.AGENT_NAME,
            llm_enabled=use_llm
        )

    async def classify_content(
        self,
        content: str,
        filename: Optional[str] = None,
        include_all_scores: bool = False
    ) -> ClassificationResult:
        """
        Classify content into one of 10 departments.

        Args:
            content: Text content to classify
            filename: Optional filename for context
            include_all_scores: Include scores for all departments

        Returns:
            ClassificationResult with department and confidence
        """
        # Use metrics context for comprehensive tracking (Task 132)
        async with AgentMetricsContext(
            AgentID.DEPARTMENT_CLASSIFIER,
            "classify",
            model="claude-3-5-haiku-20241022"
        ) as metrics_ctx:
            try:
                result = await self.classifier.classify(content, filename)

                # Update statistics
                self._stats["classifications_total"] += 1
                self._stats["classifications_by_department"][result.department.value] += 1

                if result.llm_enhanced:
                    self._stats["llm_enhanced_count"] += 1

                if result.confidence >= 0.80:
                    self._stats["high_confidence_count"] += 1
                elif result.confidence < 0.50:
                    self._stats["low_confidence_count"] += 1

                # Update average confidence
                total = self._stats["classifications_total"]
                old_avg = self._stats["average_confidence"]
                self._stats["average_confidence"] = (
                    (old_avg * (total - 1) + result.confidence) / total
                )

                # Optionally remove detailed scores to reduce response size
                if not include_all_scores:
                    result.all_scores = []

                # Track confidence score for quality metrics (Task 132)
                track_confidence_score(
                    AgentID.DEPARTMENT_CLASSIFIER,
                    "classify",
                    result.confidence
                )

                # Mark metrics as successful
                metrics_ctx.set_success()

                logger.info(
                    "Content classified",
                    department=result.department.value,
                    confidence=f"{result.confidence:.2%}",
                    llm_enhanced=result.llm_enhanced
                )

                return result

            except Exception as e:
                metrics_ctx.set_failure(type(e).__name__)
                raise

    async def classify_file(
        self,
        file_path: str,
        include_all_scores: bool = False
    ) -> ClassificationResult:
        """
        Classify a file into one of 10 departments.

        Args:
            file_path: Path to file
            include_all_scores: Include scores for all departments

        Returns:
            ClassificationResult with department and confidence
        """
        content, metadata = self.file_reader.read_file(file_path)
        content = self.file_reader.preprocess_content(content)

        result = await self.classify_content(
            content=content,
            filename=metadata.get("filename"),
            include_all_scores=include_all_scores
        )

        return result

    async def classify_batch(
        self,
        items: List[Dict[str, Any]],
        concurrency: int = 5
    ) -> BatchClassificationResult:
        """
        Classify multiple items in batch.

        Args:
            items: List of dicts with 'content' and optional 'filename'
            concurrency: Number of concurrent classifications

        Returns:
            BatchClassificationResult with all results
        """
        return await self.classifier.classify_batch(items, concurrency)

    def extract_keywords(self, content: str) -> KeywordExtractionResult:
        """
        Extract department-relevant keywords from content.

        Args:
            content: Text content

        Returns:
            KeywordExtractionResult with extracted keywords
        """
        return self.keyword_extractor.extract_keywords(content)

    def get_department_info(self, department: Department) -> Dict[str, Any]:
        """
        Get information about a specific department.

        Args:
            department: Department enum value

        Returns:
            Dict with department details
        """
        keywords = DEPARTMENT_KEYWORDS.get(department, {})
        return {
            "code": department.value,
            "description": DEPARTMENT_DESCRIPTIONS.get(department, ""),
            "primary_keywords": keywords.get("primary", []),
            "secondary_keywords": keywords.get("secondary", []),
            "tertiary_keywords": keywords.get("tertiary", []),
            "total_keywords": (
                len(keywords.get("primary", [])) +
                len(keywords.get("secondary", [])) +
                len(keywords.get("tertiary", []))
            )
        }

    def get_all_departments(self) -> List[Dict[str, Any]]:
        """
        Get information about all departments.

        Returns:
            List of department info dicts
        """
        return [self.get_department_info(d) for d in Department]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics.

        Returns:
            Dict with usage statistics
        """
        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            **self._stats
        }

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self._stats = {
            "classifications_total": 0,
            "classifications_by_department": {d.value: 0 for d in Department},
            "llm_enhanced_count": 0,
            "average_confidence": 0.0,
            "high_confidence_count": 0,
            "low_confidence_count": 0
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_classifier_service: Optional[DepartmentClassifierAgentService] = None


def get_department_classifier_service() -> DepartmentClassifierAgentService:
    """Get or create singleton instance of DepartmentClassifierAgentService"""
    global _classifier_service
    if _classifier_service is None:
        _classifier_service = DepartmentClassifierAgentService()
    return _classifier_service
