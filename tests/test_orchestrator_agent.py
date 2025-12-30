"""
Tests for AGENT-001: Master Content Analyzer & Asset Orchestrator (Task 41)

Target: >96% department classification accuracy
"""

import pytest
import asyncio
from typing import Dict, List, Tuple

# Import the service directly
import sys
sys.path.insert(0, '/Users/jaybajaj/Library/Mobile Documents/com~apple~CloudDocs/Documents/ai/Empire')

from app.services.orchestrator_agent_service import (
    OrchestratorAgentService,
    DepartmentClassifierTool,
    PatternAnalyzerTool,
    AssetTypeDeciderTool,
    Department,
    AssetType,
    ContentAnalysis
)


# =============================================================================
# TEST DATA: 100+ test cases for >96% accuracy validation
# =============================================================================

TEST_CASES: List[Dict] = [
    # IT-ENGINEERING (15 cases)
    {
        "content": "Building a REST API with FastAPI and PostgreSQL database integration",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "Docker container orchestration using Kubernetes for microservices deployment",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "CI/CD pipeline setup with GitHub Actions for automated testing and deployment",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "Python backend development best practices for scalable web applications",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "AWS Lambda serverless functions with API Gateway integration",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "React frontend component architecture with TypeScript",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "Database optimization and SQL query performance tuning for MySQL",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "Git branching strategies and code review best practices for team collaboration",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "Redis caching implementation for high-performance web applications",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },
    {
        "content": "Terraform infrastructure as code for cloud resource provisioning",
        "expected": Department.IT_ENGINEERING,
        "category": "it-engineering"
    },

    # SALES-MARKETING (15 cases)
    {
        "content": "B2B sales pipeline management and lead scoring methodologies",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "HubSpot CRM configuration for marketing automation and email campaigns",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Cold email outreach strategies for enterprise prospect engagement",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Sales forecasting models and quota management for sales teams",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "SEO optimization and content marketing strategy for brand visibility",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Lead generation funnel optimization and conversion rate analysis",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Salesforce implementation guide for enterprise sales teams",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Social media marketing campaign planning and ROI tracking",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Customer acquisition cost analysis and marketing budget allocation",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },
    {
        "content": "Account-based marketing strategy for high-value B2B prospects",
        "expected": Department.SALES_MARKETING,
        "category": "sales-marketing"
    },

    # CUSTOMER-SUPPORT (10 cases)
    {
        "content": "Zendesk ticket management workflow for customer service teams",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "SLA management and escalation procedures for support tickets",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Customer satisfaction survey analysis and CSAT improvement strategies",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Helpdesk knowledge base creation for self-service support",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Issue resolution time optimization and first response metrics",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Customer complaint handling procedures and resolution tracking",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Support team training materials for product troubleshooting",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Live chat support best practices and response templates",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "NPS score tracking and customer retention strategies",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },
    {
        "content": "Intercom chatbot configuration for automated customer support",
        "expected": Department.CUSTOMER_SUPPORT,
        "category": "customer-support"
    },

    # OPERATIONS-HR-SUPPLY (10 cases)
    {
        "content": "Employee onboarding checklist and HR documentation requirements",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Supply chain optimization and inventory management strategies",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Warehouse logistics workflow and order fulfillment process",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Recruitment and hiring process documentation for HR teams",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Performance review templates and employee evaluation criteria",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Vendor management and procurement process optimization",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Employee benefits administration and payroll processing",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Shipping and distribution logistics for e-commerce operations",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Human resources policy documentation and compliance requirements",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },
    {
        "content": "Workforce scheduling and shift management procedures",
        "expected": Department.OPERATIONS_HR_SUPPLY,
        "category": "operations-hr-supply"
    },

    # FINANCE-ACCOUNTING (10 cases)
    {
        "content": "Financial statement analysis and monthly reporting procedures",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Budget planning and expense forecasting for fiscal year",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Accounts receivable management and invoice processing workflow",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Tax compliance checklist and quarterly filing requirements",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Cash flow management and working capital optimization",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "General ledger reconciliation procedures and month-end close",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Revenue recognition guidelines and GAAP compliance",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Internal audit procedures and financial controls documentation",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Accounts payable workflow and vendor payment processing",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },
    {
        "content": "Financial modeling and variance analysis for profit centers",
        "expected": Department.FINANCE_ACCOUNTING,
        "category": "finance-accounting"
    },

    # PROJECT-MANAGEMENT (10 cases)
    {
        "content": "Agile sprint planning and user story estimation techniques",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Project milestone tracking and Gantt chart creation",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Scrum ceremony facilitation and daily standup best practices",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Resource allocation and capacity planning for project teams",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Project risk assessment and mitigation strategy development",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Stakeholder communication plan and project status reporting",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Jira workflow configuration for agile project management",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Sprint retrospective facilitation and continuous improvement",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Project scope management and change request process",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },
    {
        "content": "Kanban board setup and workflow visualization techniques",
        "expected": Department.PROJECT_MANAGEMENT,
        "category": "project-management"
    },

    # REAL-ESTATE (10 cases)
    {
        "content": "Commercial property lease agreement negotiation strategies",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Residential rental property management and tenant screening",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Real estate investment analysis and cap rate calculations",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Property listing optimization for MLS and Zillow",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Mortgage financing options and loan qualification requirements",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Building maintenance schedules and property inspection checklist",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Tenant lease renewal process and rent increase procedures",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Commercial real estate due diligence checklist",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Property management software comparison for landlords",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },
    {
        "content": "Rental property cash flow analysis and NOI calculation",
        "expected": Department.REAL_ESTATE,
        "category": "real-estate"
    },

    # PRIVATE-EQUITY-MA (10 cases)
    {
        "content": "Private equity fund structure and limited partner agreements",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "M&A due diligence process and quality of earnings analysis",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Company valuation methodologies and EBITDA multiple analysis",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Leveraged buyout modeling and debt financing structures",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Portfolio company value creation and operational improvement",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Investment committee memo preparation and deal approval process",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Exit strategy planning and IPO preparation for portfolio companies",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Merger integration planning and synergy identification",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "Deal sourcing and investment thesis development",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },
    {
        "content": "IRR calculation and fund performance reporting",
        "expected": Department.PRIVATE_EQUITY_MA,
        "category": "private-equity-ma"
    },

    # CONSULTING (10 cases)
    {
        "content": "Strategic consulting framework and client engagement methodology",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Business transformation advisory and change management recommendations",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Market analysis and competitive benchmarking assessment",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Management consulting slide deck templates and deliverables",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Client workshop facilitation and stakeholder alignment sessions",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Strategic recommendation development and implementation roadmap",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Industry analysis frameworks and market entry strategy",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Executive summary writing for consulting engagement deliverables",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Cost optimization assessment and operational efficiency recommendations",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },
    {
        "content": "Growth strategy advisory and market expansion analysis",
        "expected": Department.CONSULTING,
        "category": "consulting"
    },

    # PERSONAL-CONTINUING-ED (10 cases)
    {
        "content": "Online course curriculum design and learning module structure",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Professional certification study guide and exam preparation",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Personal skill development roadmap and learning objectives",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Corporate training program design and employee education",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Bootcamp curriculum structure and coding tutorial content",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Continuing education requirements and CPE credit tracking",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Self-improvement course content and personal development materials",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Webinar presentation preparation and educational workshop planning",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Career transition coaching and upskilling pathway development",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },
    {
        "content": "Learning management system content organization and quiz design",
        "expected": Department.PERSONAL_CONTINUING_ED,
        "category": "personal-continuing-ed"
    },

    # RESEARCH-DEVELOPMENT (10 cases - v7.3)
    {
        "content": "R&D prototype development and proof of concept validation methodology",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Innovation lab experiment design and hypothesis testing framework",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Patent filing process and intellectual property documentation",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Research paper publication workflow and peer review submission",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Product development lifecycle from discovery to minimum viable product",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Technology research roadmap and emerging tech feasibility study",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Lab testing protocols and scientific validation procedures",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "User research methodology and design thinking workshop facilitation",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Breakthrough innovation discovery and cutting-edge technology exploration",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
    {
        "content": "Beta testing program management and pilot validation metrics",
        "expected": Department.RESEARCH_DEVELOPMENT,
        "category": "research-development"
    },
]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def classifier():
    """Create department classifier without LLM enhancement for speed"""
    return DepartmentClassifierTool(use_llm_enhancement=False)


@pytest.fixture
def classifier_with_llm():
    """Create department classifier with LLM enhancement"""
    return DepartmentClassifierTool(use_llm_enhancement=True)


@pytest.fixture
def pattern_analyzer():
    """Create pattern analyzer"""
    return PatternAnalyzerTool()


@pytest.fixture
def orchestrator():
    """Create orchestrator service"""
    return OrchestratorAgentService()


# =============================================================================
# CLASSIFICATION ACCURACY TESTS
# =============================================================================

class TestDepartmentClassification:
    """Test department classification accuracy"""

    @pytest.mark.asyncio
    async def test_keyword_classification_accuracy(self, classifier):
        """Test keyword-based classification achieves >90% accuracy"""
        correct = 0
        total = len(TEST_CASES)

        for case in TEST_CASES:
            result = await classifier.classify(case["content"])
            if result.department == case["expected"]:
                correct += 1
            else:
                print(f"MISS: Expected {case['expected'].value}, got {result.department.value}")
                print(f"  Content: {case['content'][:60]}...")
                print(f"  Confidence: {result.confidence:.2%}")

        accuracy = correct / total
        print(f"\nKeyword Classification Accuracy: {accuracy:.2%} ({correct}/{total})")
        assert accuracy >= 0.90, f"Keyword accuracy {accuracy:.2%} below 90% threshold"

    @pytest.mark.asyncio
    async def test_classification_by_department(self, classifier):
        """Test classification accuracy per department"""
        dept_results: Dict[str, Tuple[int, int]] = {}

        for case in TEST_CASES:
            category = case["category"]
            if category not in dept_results:
                dept_results[category] = (0, 0)  # (correct, total)

            result = await classifier.classify(case["content"])
            correct, total = dept_results[category]

            if result.department == case["expected"]:
                dept_results[category] = (correct + 1, total + 1)
            else:
                dept_results[category] = (correct, total + 1)

        print("\n=== Accuracy by Department ===")
        for dept, (correct, total) in sorted(dept_results.items()):
            accuracy = correct / total if total > 0 else 0
            print(f"{dept}: {accuracy:.0%} ({correct}/{total})")
            # Each department should have >80% accuracy
            assert accuracy >= 0.80, f"{dept} accuracy {accuracy:.2%} below 80%"

    @pytest.mark.asyncio
    async def test_confidence_calibration(self, classifier):
        """Test that high confidence correlates with correct classification"""
        high_conf_correct = 0
        high_conf_total = 0
        low_conf_correct = 0
        low_conf_total = 0

        for case in TEST_CASES:
            result = await classifier.classify(case["content"])
            is_correct = result.department == case["expected"]

            if result.confidence >= 0.7:
                high_conf_total += 1
                if is_correct:
                    high_conf_correct += 1
            else:
                low_conf_total += 1
                if is_correct:
                    low_conf_correct += 1

        high_conf_acc = high_conf_correct / high_conf_total if high_conf_total > 0 else 0
        low_conf_acc = low_conf_correct / low_conf_total if low_conf_total > 0 else 0

        print(f"\nHigh confidence (>=70%): {high_conf_acc:.0%} ({high_conf_correct}/{high_conf_total})")
        print(f"Low confidence (<70%): {low_conf_acc:.0%} ({low_conf_correct}/{low_conf_total})")

        # High confidence should have higher accuracy than low confidence
        assert high_conf_acc >= low_conf_acc, "High confidence should be more accurate"


class TestPatternAnalysis:
    """Test pattern analysis functionality"""

    def test_code_detection(self, pattern_analyzer):
        """Test code pattern detection"""
        code_content = """
        def process_data(items):
            return [item * 2 for item in items]
        """
        analysis = pattern_analyzer.analyze(code_content, "script.py")
        assert analysis.has_code is True
        assert analysis.content_type == "code"

    def test_table_detection(self, pattern_analyzer):
        """Test table pattern detection"""
        table_content = """
        | Name | Age | City |
        |------|-----|------|
        | John | 30  | NYC  |
        """
        analysis = pattern_analyzer.analyze(table_content)
        assert analysis.has_tables is True

    def test_privacy_detection(self, pattern_analyzer):
        """Test privacy keyword detection"""
        private_content = "This confidential document contains proprietary information"
        analysis = pattern_analyzer.analyze(private_content)
        assert analysis.privacy_level == "local_only"

    def test_pii_detection(self, pattern_analyzer):
        """Test PII pattern detection (SSN)"""
        pii_content = "Employee SSN: 123-45-6789"
        analysis = pattern_analyzer.analyze(pii_content)
        assert analysis.privacy_level == "local_only"

    def test_complexity_scoring(self, pattern_analyzer):
        """Test complexity score calculation"""
        simple = "Hello world"
        complex_content = """
        Advanced enterprise architecture framework for implementing
        sophisticated microservices infrastructure using distributed
        systems design patterns and algorithms for scalability.
        """ * 10

        simple_analysis = pattern_analyzer.analyze(simple)
        complex_analysis = pattern_analyzer.analyze(complex_content)

        assert complex_analysis.complexity_score > simple_analysis.complexity_score


class TestAssetTypeDecision:
    """Test asset type decision logic"""

    @pytest.fixture
    def decider(self):
        return AssetTypeDeciderTool()

    @pytest.fixture
    def analyzer(self):
        return PatternAnalyzerTool()

    def test_automation_suggests_skill(self, decider, analyzer):
        """Test that automation content suggests skill asset type"""
        content = "Automate the daily report generation process with scheduled batch processing"
        analysis = analyzer.analyze(content)
        decision = decider.decide(content, analysis, Department.IT_ENGINEERING)
        assert AssetType.SKILL in decision.asset_types

    def test_quick_action_suggests_command(self, decider, analyzer):
        """Test that quick action content suggests command asset type"""
        content = "Quick utility shortcut for looking up customer information"
        analysis = analyzer.analyze(content)
        decision = decider.decide(content, analysis, Department.CUSTOMER_SUPPORT)
        assert AssetType.COMMAND in decision.asset_types

    def test_analysis_suggests_agent(self, decider, analyzer):
        """Test that analysis content suggests agent asset type"""
        content = "Analyze and evaluate the competitive landscape with intelligent reasoning"
        analysis = analyzer.analyze(content)
        decision = decider.decide(content, analysis, Department.CONSULTING)
        assert AssetType.AGENT in decision.asset_types

    def test_default_is_prompt(self, decider, analyzer):
        """Test that ambiguous content defaults to prompt"""
        content = "Some general content without clear indicators"
        analysis = analyzer.analyze(content)
        decision = decider.decide(content, analysis, Department.GLOBAL)
        assert AssetType.PROMPT in decision.asset_types

    def test_summary_decision_for_documents(self, decider, analyzer):
        """Test that document content needs summary"""
        content = "This is a comprehensive training document with multiple sections and tables"
        analysis = analyzer.analyze(content, "training_guide.pdf")
        decision = decider.decide(content, analysis, Department.PERSONAL_CONTINUING_ED)
        assert decision.needs_summary is True


class TestOrchestratorIntegration:
    """Integration tests for full orchestrator workflow"""

    @pytest.mark.asyncio
    async def test_full_processing_pipeline(self, orchestrator):
        """Test complete content processing pipeline"""
        content = """
        Advanced Sales Pipeline Management Framework

        This comprehensive training module covers sophisticated techniques for
        managing enterprise B2B sales pipelines, including:

        - Lead scoring algorithms
        - Opportunity stage optimization
        - Predictive forecasting models
        - CRM automation workflows
        """

        result = await orchestrator.process_content(
            content=content,
            filename="sales_training.pdf"
        )

        # Verify classification
        assert result.classification.department == Department.SALES_MARKETING
        assert result.classification.confidence >= 0.5

        # Verify asset decision
        assert len(result.asset_decision.asset_types) > 0
        assert result.asset_decision.primary_type is not None

        # Verify delegation targets
        assert len(result.delegation_targets) > 0

        # Verify output paths generated
        assert len(result.output_paths) > 0

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, orchestrator):
        """Test that statistics are tracked correctly"""
        content = "Simple test content about software development and programming"

        await orchestrator.process_content(content)
        stats = orchestrator.get_stats()

        assert stats["total_processed"] >= 1
        assert "by_department" in stats
        assert "by_asset_type" in stats


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Performance tests for classification speed"""

    @pytest.mark.asyncio
    async def test_classification_speed(self, classifier):
        """Test that classification completes within reasonable time"""
        import time

        content = "Test content for performance measurement about software development"

        start = time.time()
        for _ in range(10):
            await classifier.classify(content)
        elapsed = time.time() - start

        avg_time = elapsed / 10
        print(f"\nAverage classification time: {avg_time*1000:.1f}ms")
        assert avg_time < 0.5, f"Classification too slow: {avg_time:.2f}s"


# =============================================================================
# RUN ACCURACY TEST STANDALONE
# =============================================================================

if __name__ == "__main__":
    """Run accuracy test standalone"""
    import asyncio

    async def run_accuracy_test():
        print("=" * 70)
        print("AGENT-001 Classification Accuracy Test")
        print("=" * 70)

        classifier = DepartmentClassifierTool(use_llm_enhancement=False)

        correct = 0
        total = len(TEST_CASES)
        dept_results: Dict[str, Tuple[int, int]] = {}

        for case in TEST_CASES:
            category = case["category"]
            if category not in dept_results:
                dept_results[category] = (0, 0)

            result = await classifier.classify(case["content"])
            is_correct = result.department == case["expected"]

            if is_correct:
                correct += 1
                dept_correct, dept_total = dept_results[category]
                dept_results[category] = (dept_correct + 1, dept_total + 1)
            else:
                dept_correct, dept_total = dept_results[category]
                dept_results[category] = (dept_correct, dept_total + 1)
                print(f"\n❌ MISS: {case['category']}")
                print(f"   Expected: {case['expected'].value}")
                print(f"   Got: {result.department.value} ({result.confidence:.0%})")
                print(f"   Content: {case['content'][:50]}...")

        # Print results
        print("\n" + "=" * 70)
        print("RESULTS BY DEPARTMENT")
        print("=" * 70)

        for dept, (dept_correct, dept_total) in sorted(dept_results.items()):
            acc = dept_correct / dept_total if dept_total > 0 else 0
            status = "✅" if acc >= 0.9 else "⚠️" if acc >= 0.8 else "❌"
            print(f"{status} {dept}: {acc:.0%} ({dept_correct}/{dept_total})")

        # Overall accuracy
        accuracy = correct / total
        print("\n" + "=" * 70)
        overall_status = "✅ PASS" if accuracy >= 0.96 else "❌ FAIL"
        print(f"OVERALL ACCURACY: {accuracy:.1%} ({correct}/{total}) {overall_status}")
        print("=" * 70)

        return accuracy >= 0.96

    success = asyncio.run(run_accuracy_test())
    exit(0 if success else 1)
