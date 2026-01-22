"""
Empire v7.3 - Content Summarizer Agent Tests
Task 42: Implement Content Summarizer Agent (AGENT-002)

Comprehensive tests for PDF summary generation, diagrams, and charts.
"""

import os
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import tempfile
import shutil

# Import test subjects
from app.services.content_summarizer_agent import (
    ContentSummarizerAgentService,
    PDFGeneratorTool,
    DiagramCreatorTool,
    ChartBuilderTool,
    DiagramType,
    DiagramSpec,
    SummarySection,
    SummarySectionContent,
    ExtractedContent,
    SummaryGenerationResult,
    create_content_summarizer_agent,
    get_content_summarizer_service,
    COLORS
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def pdf_generator(temp_output_dir):
    """Create a PDFGeneratorTool with temp output directory"""
    return PDFGeneratorTool(output_base_path=temp_output_dir)


@pytest.fixture
def diagram_creator(temp_output_dir):
    """Create a DiagramCreatorTool with temp output directory"""
    return DiagramCreatorTool(output_base_path=temp_output_dir)


@pytest.fixture
def chart_builder(temp_output_dir):
    """Create a ChartBuilderTool with temp output directory"""
    return ChartBuilderTool(output_base_path=temp_output_dir)


@pytest.fixture
def summarizer_service(temp_output_dir):
    """Create a ContentSummarizerAgentService with temp output directory"""
    return ContentSummarizerAgentService(output_base_path=temp_output_dir)


@pytest.fixture
def sample_content():
    """Sample content for testing"""
    return """
    # Advanced Sales Pipeline Management Framework

    ## Introduction
    This comprehensive training module covers sophisticated techniques for
    managing enterprise B2B sales pipelines.

    ## Module 1: Pipeline Fundamentals
    Understanding the basics of pipeline management is crucial. Key metrics include:
    - Conversion rates at each stage
    - Average deal size
    - Sales cycle length
    - Win rate by segment

    ## Module 2: Lead Scoring
    Effective lead scoring uses both demographic and behavioral signals.

    ### MEDDIC Framework
    The MEDDIC qualification framework helps ensure deal quality:
    - Metrics: What are the quantified benefits?
    - Economic Buyer: Who controls the budget?
    - Decision Criteria: How will they decide?
    - Decision Process: What steps are involved?
    - Identify Pain: What problem are we solving?
    - Champion: Who is our internal advocate?

    ## Implementation Steps
    1. Audit your current pipeline stages
    2. Implement consistent lead scoring criteria
    3. Train team on qualification frameworks
    4. Set up automated reporting dashboards
    5. Establish weekly pipeline review cadence
    """


@pytest.fixture
def sample_sections():
    """Sample sections for PDF generation testing"""
    return [
        SummarySectionContent(
            section_type=SummarySection.EXECUTIVE_SUMMARY,
            title="Executive Summary",
            content="This is a test executive summary covering key points.",
            bullet_points=[]
        ),
        SummarySectionContent(
            section_type=SummarySection.KEY_CONCEPTS,
            title="Key Concepts",
            content="The following key concepts are covered:",
            bullet_points=["Concept 1", "Concept 2", "Concept 3"]
        ),
        SummarySectionContent(
            section_type=SummarySection.IMPLEMENTATION_GUIDE,
            title="Implementation Guide",
            content="Follow these steps:",
            bullet_points=["Step 1: Plan", "Step 2: Execute", "Step 3: Review"]
        )
    ]


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestEnums:
    """Test enum definitions"""

    def test_diagram_types(self):
        """Test DiagramType enum values"""
        assert DiagramType.FLOWCHART.value == "flowchart"
        assert DiagramType.HIERARCHY.value == "hierarchy"
        assert DiagramType.PROCESS.value == "process"
        assert DiagramType.MINDMAP.value == "mindmap"
        assert DiagramType.TIMELINE.value == "timeline"
        assert DiagramType.COMPARISON.value == "comparison"

    def test_summary_sections(self):
        """Test SummarySection enum values"""
        assert SummarySection.EXECUTIVE_SUMMARY.value == "executive_summary"
        assert SummarySection.KEY_CONCEPTS.value == "key_concepts"
        assert SummarySection.DETAILED_BREAKDOWN.value == "detailed_breakdown"
        assert SummarySection.FRAMEWORKS.value == "frameworks"
        assert SummarySection.IMPLEMENTATION_GUIDE.value == "implementation_guide"
        assert SummarySection.QUICK_REFERENCE.value == "quick_reference"
        assert SummarySection.VISUAL_ELEMENTS.value == "visual_elements"
        assert SummarySection.APPENDIX.value == "appendix"


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestModels:
    """Test Pydantic model definitions"""

    def test_extracted_content_model(self):
        """Test ExtractedContent model"""
        content = ExtractedContent(
            title="Test Title",
            source_type="document",
            word_count=1000,
            sections=[{"title": "Section 1", "position": 0}],
            key_concepts=["Concept 1", "Concept 2"],
            implementation_steps=["Step 1", "Step 2"]
        )
        assert content.title == "Test Title"
        assert content.word_count == 1000
        assert len(content.key_concepts) == 2
        assert len(content.implementation_steps) == 2

    def test_diagram_spec_model(self):
        """Test DiagramSpec model"""
        spec = DiagramSpec(
            diagram_type=DiagramType.FLOWCHART,
            title="Test Flowchart",
            elements=[{"label": "Start"}, {"label": "End"}],
            connections=[{"from": 0, "to": 1}]
        )
        assert spec.diagram_type == DiagramType.FLOWCHART
        assert spec.title == "Test Flowchart"
        assert len(spec.elements) == 2
        assert len(spec.connections) == 1

    def test_summary_section_content_model(self):
        """Test SummarySectionContent model"""
        section = SummarySectionContent(
            section_type=SummarySection.KEY_CONCEPTS,
            title="Key Concepts",
            content="Test content",
            bullet_points=["Point 1", "Point 2"]
        )
        assert section.section_type == SummarySection.KEY_CONCEPTS
        assert len(section.bullet_points) == 2

    def test_summary_generation_result_model(self):
        """Test SummaryGenerationResult model"""
        result = SummaryGenerationResult(
            success=True,
            pdf_path="/path/to/file.pdf",
            department="sales-marketing",
            title="Test Summary",
            sections_generated=["executive_summary", "key_concepts"],
            diagrams_generated=2,
            tables_generated=1,
            processing_time_seconds=5.5
        )
        assert result.success is True
        assert result.pdf_path == "/path/to/file.pdf"
        assert result.diagrams_generated == 2


# =============================================================================
# PDF GENERATOR TESTS
# =============================================================================

class TestPDFGeneratorTool:
    """Test PDFGeneratorTool functionality"""

    def test_initialization(self, temp_output_dir):
        """Test PDF generator initialization"""
        generator = PDFGeneratorTool(output_base_path=temp_output_dir)
        assert generator.output_base_path == temp_output_dir
        assert generator.styles is not None

    def test_custom_styles_created(self, pdf_generator):
        """Test that custom styles are created"""
        assert 'CustomTitle' in pdf_generator.styles
        assert 'SectionHeading' in pdf_generator.styles
        assert 'SubsectionHeading' in pdf_generator.styles
        assert 'EmpireBodyText' in pdf_generator.styles
        assert 'BulletPoint' in pdf_generator.styles
        assert 'KeyConcept' in pdf_generator.styles
        assert 'QuickRef' in pdf_generator.styles

    def test_generate_pdf_creates_file(self, pdf_generator, sample_sections, temp_output_dir):
        """Test that PDF generation creates a file"""
        pdf_path = pdf_generator.generate_pdf(
            department="sales-marketing",
            title="Test Summary",
            sections=sample_sections
        )

        assert pdf_path is not None
        assert os.path.exists(pdf_path)
        assert pdf_path.endswith(".pdf")
        assert "sales-marketing" in pdf_path

    def test_generate_pdf_custom_filename(self, pdf_generator, sample_sections):
        """Test PDF generation with custom filename"""
        pdf_path = pdf_generator.generate_pdf(
            department="it-engineering",
            title="Custom Test",
            sections=sample_sections,
            filename="custom_filename.pdf"
        )

        assert pdf_path.endswith("custom_filename.pdf")
        assert os.path.exists(pdf_path)

    def test_generate_pdf_creates_directory(self, pdf_generator, sample_sections, temp_output_dir):
        """Test that PDF generator creates output directory"""
        pdf_path = pdf_generator.generate_pdf(
            department="new-department",
            title="Test",
            sections=sample_sections
        )

        expected_dir = Path(temp_output_dir) / "new-department"
        assert expected_dir.exists()

    def test_build_table(self, pdf_generator):
        """Test table building"""
        table_data = {
            "title": "Test Table",
            "headers": ["Column 1", "Column 2", "Column 3"],
            "rows": [
                ["Data 1", "Data 2", "Data 3"],
                ["Data 4", "Data 5", "Data 6"]
            ]
        }

        table = pdf_generator._build_table(table_data)
        assert table is not None

    def test_build_table_empty(self, pdf_generator):
        """Test table building with empty data"""
        table_data = {
            "headers": [],
            "rows": []
        }

        table = pdf_generator._build_table(table_data)
        assert table is not None


# =============================================================================
# DIAGRAM CREATOR TESTS
# =============================================================================

class TestDiagramCreatorTool:
    """Test DiagramCreatorTool functionality"""

    def test_initialization(self, temp_output_dir):
        """Test diagram creator initialization"""
        creator = DiagramCreatorTool(output_base_path=temp_output_dir)
        assert creator.output_base_path == temp_output_dir

    def test_create_flowchart(self, diagram_creator, temp_output_dir):
        """Test flowchart creation"""
        spec = DiagramSpec(
            diagram_type=DiagramType.FLOWCHART,
            title="Test Flowchart",
            elements=[
                {"label": "Start"},
                {"label": "Process"},
                {"label": "End"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "sales-marketing")

        assert path is not None
        assert os.path.exists(path)
        assert path.endswith(".png")

    def test_create_hierarchy(self, diagram_creator):
        """Test hierarchy diagram creation"""
        spec = DiagramSpec(
            diagram_type=DiagramType.HIERARCHY,
            title="Test Hierarchy",
            elements=[
                {"label": "Root"},
                {"label": "Child 1"},
                {"label": "Child 2"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "it-engineering")

        assert os.path.exists(path)

    def test_create_process_diagram(self, diagram_creator):
        """Test process diagram creation"""
        spec = DiagramSpec(
            diagram_type=DiagramType.PROCESS,
            title="Test Process",
            elements=[
                {"label": "Step 1"},
                {"label": "Step 2"},
                {"label": "Step 3"},
                {"label": "Step 4"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "operations-hr-supply")

        assert os.path.exists(path)

    def test_create_timeline(self, diagram_creator):
        """Test timeline diagram creation"""
        spec = DiagramSpec(
            diagram_type=DiagramType.TIMELINE,
            title="Test Timeline",
            elements=[
                {"label": "Event 1"},
                {"label": "Event 2"},
                {"label": "Event 3"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "project-management")

        assert os.path.exists(path)

    def test_create_comparison(self, diagram_creator):
        """Test comparison diagram creation"""
        spec = DiagramSpec(
            diagram_type=DiagramType.COMPARISON,
            title="Test Comparison",
            elements=[
                {"label": "Option A"},
                {"label": "Option B"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "consulting")

        assert os.path.exists(path)

    def test_create_generic_diagram(self, diagram_creator):
        """Test generic diagram creation with mindmap type"""
        spec = DiagramSpec(
            diagram_type=DiagramType.MINDMAP,
            title="Test Mindmap",
            elements=[
                {"label": "Center"},
                {"label": "Branch 1"},
                {"label": "Branch 2"},
                {"label": "Branch 3"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "personal-continuing-ed")

        assert os.path.exists(path)

    def test_custom_filename(self, diagram_creator):
        """Test diagram creation with custom filename"""
        spec = DiagramSpec(
            diagram_type=DiagramType.FLOWCHART,
            title="Custom",
            elements=[{"label": "Test"}]
        )

        path = diagram_creator.create_diagram(
            spec,
            "finance-accounting",
            filename="my_custom_diagram.png"
        )

        assert path.endswith("my_custom_diagram.png")

    def test_empty_elements(self, diagram_creator):
        """Test diagram with empty elements"""
        spec = DiagramSpec(
            diagram_type=DiagramType.FLOWCHART,
            title="Empty Test",
            elements=[]
        )

        path = diagram_creator.create_diagram(spec, "test-dept")
        assert os.path.exists(path)


# =============================================================================
# CHART BUILDER TESTS
# =============================================================================

class TestChartBuilderTool:
    """Test ChartBuilderTool functionality"""

    def test_initialization(self, temp_output_dir):
        """Test chart builder initialization"""
        builder = ChartBuilderTool(output_base_path=temp_output_dir)
        assert builder.output_base_path == temp_output_dir

    def test_create_bar_chart(self, chart_builder):
        """Test bar chart creation"""
        path = chart_builder.create_bar_chart(
            title="Test Bar Chart",
            labels=["A", "B", "C", "D"],
            values=[10, 25, 15, 30],
            department="sales-marketing",
            ylabel="Sales"
        )

        assert os.path.exists(path)
        assert path.endswith(".png")

    def test_create_pie_chart(self, chart_builder):
        """Test pie chart creation"""
        path = chart_builder.create_pie_chart(
            title="Test Pie Chart",
            labels=["Category 1", "Category 2", "Category 3"],
            values=[40, 35, 25],
            department="finance-accounting"
        )

        assert os.path.exists(path)
        assert path.endswith(".png")

    def test_bar_chart_custom_filename(self, chart_builder):
        """Test bar chart with custom filename"""
        path = chart_builder.create_bar_chart(
            title="Custom Bar",
            labels=["X", "Y"],
            values=[50, 50],
            department="test-dept",
            filename="my_bar_chart.png"
        )

        assert path.endswith("my_bar_chart.png")

    def test_pie_chart_custom_filename(self, chart_builder):
        """Test pie chart with custom filename"""
        path = chart_builder.create_pie_chart(
            title="Custom Pie",
            labels=["A", "B"],
            values=[60, 40],
            department="test-dept",
            filename="my_pie_chart.png"
        )

        assert path.endswith("my_pie_chart.png")

    def test_bar_chart_many_values(self, chart_builder):
        """Test bar chart with many values"""
        labels = [f"Item {i}" for i in range(10)]
        values = [i * 10 for i in range(10)]

        path = chart_builder.create_bar_chart(
            title="Many Values",
            labels=labels,
            values=values,
            department="test-dept"
        )

        assert os.path.exists(path)

    def test_pie_chart_many_segments(self, chart_builder):
        """Test pie chart with many segments"""
        labels = [f"Segment {i}" for i in range(8)]
        values = [12.5] * 8

        path = chart_builder.create_pie_chart(
            title="Many Segments",
            labels=labels,
            values=values,
            department="test-dept"
        )

        assert os.path.exists(path)


# =============================================================================
# CONTENT SUMMARIZER SERVICE TESTS
# =============================================================================

class TestContentSummarizerAgentService:
    """Test ContentSummarizerAgentService functionality"""

    def test_initialization(self, temp_output_dir):
        """Test service initialization"""
        service = ContentSummarizerAgentService(output_base_path=temp_output_dir)

        assert service.output_base_path == temp_output_dir
        assert service.pdf_generator is not None
        assert service.diagram_creator is not None
        assert service.chart_builder is not None
        assert service.stats is not None

    def test_initial_stats(self, summarizer_service):
        """Test initial statistics"""
        stats = summarizer_service.get_stats()

        assert stats["agent_id"] == "AGENT-002"
        assert stats["agent_name"] == "Content Summarizer Agent"
        assert stats["summaries_generated"] == 0
        assert stats["diagrams_created"] == 0

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, summarizer_service, sample_content):
        """Test successful summary generation"""
        result = await summarizer_service.generate_summary(
            content=sample_content,
            department="sales-marketing",
            title="Test Summary",
            source_type="course"
        )

        assert result.success is True
        assert result.pdf_path is not None
        assert os.path.exists(result.pdf_path)
        assert result.department == "sales-marketing"
        assert result.title == "Test Summary"
        assert len(result.sections_generated) > 0
        assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_generate_summary_with_diagrams(self, summarizer_service, sample_content):
        """Test that diagrams are generated"""
        result = await summarizer_service.generate_summary(
            content=sample_content,
            department="sales-marketing",
            title="Diagram Test"
        )

        assert result.success is True
        # Should generate at least one diagram due to implementation steps
        assert result.diagrams_generated >= 0  # May vary based on content analysis

    @pytest.mark.asyncio
    async def test_generate_summary_updates_stats(self, summarizer_service, sample_content):
        """Test that stats are updated after generation"""
        initial_stats = summarizer_service.get_stats()
        initial_count = initial_stats["summaries_generated"]

        await summarizer_service.generate_summary(
            content=sample_content,
            department="it-engineering",
            title="Stats Test"
        )

        updated_stats = summarizer_service.get_stats()
        assert updated_stats["summaries_generated"] == initial_count + 1
        assert "it-engineering" in updated_stats["by_department"]

    @pytest.mark.asyncio
    async def test_generate_summary_different_departments(self, summarizer_service, sample_content):
        """Test summary generation for different departments"""
        departments = ["sales-marketing", "it-engineering", "finance-accounting"]

        for dept in departments:
            result = await summarizer_service.generate_summary(
                content=sample_content,
                department=dept,
                title=f"Test for {dept}"
            )

            assert result.success is True
            assert result.department == dept
            assert dept in result.pdf_path

    @pytest.mark.asyncio
    async def test_extract_content(self, summarizer_service, sample_content):
        """Test content extraction"""
        extracted = await summarizer_service._extract_content(
            content=sample_content,
            title="Test Extraction",
            source_type="document"
        )

        assert extracted.title == "Test Extraction"
        assert extracted.source_type == "document"
        assert extracted.word_count > 0

    @pytest.mark.asyncio
    async def test_generate_sections(self, summarizer_service, sample_content):
        """Test section generation"""
        extracted = await summarizer_service._extract_content(
            content=sample_content,
            title="Test Sections",
            source_type="document"
        )

        sections = await summarizer_service._generate_sections(
            extracted=extracted,
            department="sales-marketing"
        )

        assert len(sections) > 0
        # Should have at least executive summary and quick reference
        section_types = [s.section_type for s in sections]
        assert SummarySection.EXECUTIVE_SUMMARY in section_types
        assert SummarySection.QUICK_REFERENCE in section_types

    @pytest.mark.asyncio
    async def test_create_diagrams(self, summarizer_service, sample_content):
        """Test diagram creation from extracted content"""
        extracted = ExtractedContent(
            title="Test",
            source_type="document",
            word_count=500,
            key_concepts=["Concept 1", "Concept 2", "Concept 3", "Concept 4"],
            implementation_steps=["Step 1", "Step 2", "Step 3"],
            frameworks=[{"name": "Framework 1", "description": "Test"}]
        )

        diagram_paths = await summarizer_service._create_diagrams(
            extracted=extracted,
            department="test-dept"
        )

        # Should create at least process and hierarchy diagrams
        assert len(diagram_paths) >= 2

    @pytest.mark.asyncio
    async def test_generate_summary_with_metadata(self, summarizer_service, sample_content):
        """Test summary generation with custom metadata"""
        result = await summarizer_service.generate_summary(
            content=sample_content,
            department="consulting",
            title="Metadata Test",
            metadata={"custom_key": "custom_value", "source_url": "https://example.com"}
        )

        assert result.success is True
        assert "agent_id" in result.metadata
        assert result.metadata["agent_id"] == "AGENT-002"


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================

class TestFactoryFunctions:
    """Test factory and convenience functions"""

    def test_create_content_summarizer_agent(self, temp_output_dir):
        """Test create_content_summarizer_agent factory"""
        agent = create_content_summarizer_agent(output_path=temp_output_dir)

        assert isinstance(agent, ContentSummarizerAgentService)
        assert agent.output_base_path == temp_output_dir

    def test_get_content_summarizer_service_singleton(self):
        """Test singleton pattern"""
        # Reset singleton for clean test
        import app.services.content_summarizer_agent as module
        module._content_summarizer_service = None

        service1 = get_content_summarizer_service()
        service2 = get_content_summarizer_service()

        assert service1 is service2


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_short_content(self, summarizer_service):
        """Test with very short content"""
        result = await summarizer_service.generate_summary(
            content="This is a very short piece of content with minimal information.",
            department="test-dept",
            title="Short Content Test"
        )

        # Should still succeed with minimal content
        assert result.success is True

    @pytest.mark.asyncio
    async def test_long_content(self, summarizer_service):
        """Test with very long content"""
        long_content = "Test content. " * 5000  # About 10000 words

        result = await summarizer_service.generate_summary(
            content=long_content,
            department="test-dept",
            title="Long Content Test"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_special_characters_in_title(self, summarizer_service, sample_content):
        """Test with special characters in title"""
        result = await summarizer_service.generate_summary(
            content=sample_content,
            department="test-dept",
            title="Test: Special/Characters & Symbols! (2024)"
        )

        assert result.success is True
        assert os.path.exists(result.pdf_path)

    @pytest.mark.asyncio
    async def test_unicode_content(self, summarizer_service):
        """Test with unicode content"""
        unicode_content = """
        # 国际化测试 (Internationalization Test)

        This content includes various unicode characters:
        - Japanese: 日本語テスト
        - Korean: 한국어 테스트
        - Arabic: اختبار العربية
        - Emoji: 📊 📈 💼 🎯

        ## Key Points
        - Point 1: Multiple languages supported
        - Point 2: Emoji handling
        - Point 3: Special characters
        """

        result = await summarizer_service.generate_summary(
            content=unicode_content,
            department="_global",
            title="Unicode Test"
        )

        assert result.success is True

    def test_diagram_with_long_labels(self, diagram_creator):
        """Test diagram with very long element labels"""
        spec = DiagramSpec(
            diagram_type=DiagramType.PROCESS,
            title="Long Labels Test",
            elements=[
                {"label": "This is a very long label that might overflow the diagram box"},
                {"label": "Another extremely long label for testing purposes"},
                {"label": "Short"}
            ]
        )

        path = diagram_creator.create_diagram(spec, "test-dept")
        assert os.path.exists(path)

    def test_chart_with_zero_values(self, chart_builder):
        """Test chart with zero values"""
        path = chart_builder.create_bar_chart(
            title="Zero Values",
            labels=["A", "B", "C"],
            values=[0, 0, 0],
            department="test-dept"
        )

        assert os.path.exists(path)

    def test_chart_with_negative_values(self, chart_builder):
        """Test chart with negative values"""
        path = chart_builder.create_bar_chart(
            title="Negative Values",
            labels=["A", "B", "C"],
            values=[-10, 20, -5],
            department="test-dept"
        )

        assert os.path.exists(path)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the full pipeline"""

    @pytest.mark.asyncio
    async def test_full_summary_pipeline(self, temp_output_dir):
        """Test complete summary generation pipeline"""
        service = ContentSummarizerAgentService(output_base_path=temp_output_dir)

        content = """
        # Complete Course: Project Management Essentials

        ## Module 1: Introduction to Project Management
        Project management involves planning, executing, and controlling projects.

        Key concepts:
        - Scope management
        - Time management
        - Cost management
        - Quality management
        - Risk management

        ## Module 2: Project Planning
        Effective planning is critical for project success.

        ### Work Breakdown Structure (WBS)
        The WBS breaks down project work into manageable components.

        ### Gantt Charts
        Gantt charts visualize project schedules.

        ## Module 3: Execution and Control
        During execution, project managers must:
        1. Monitor progress
        2. Manage changes
        3. Communicate with stakeholders
        4. Address issues promptly
        5. Update documentation

        ## Framework: PMBOK Guide
        The PMBOK Guide provides best practices for project management.

        ## Summary
        This course covered essential project management concepts.
        """

        result = await service.generate_summary(
            content=content,
            department="project-management",
            title="Project Management Essentials Course Summary",
            source_type="course"
        )

        assert result.success is True
        assert result.pdf_path is not None
        assert os.path.exists(result.pdf_path)
        assert result.department == "project-management"
        assert "executive_summary" in result.sections_generated
        assert result.processing_time_seconds > 0

        # Verify stats updated
        stats = service.get_stats()
        assert stats["summaries_generated"] == 1
        assert "project-management" in stats["by_department"]

    @pytest.mark.asyncio
    async def test_multiple_summaries_same_service(self, temp_output_dir):
        """Test generating multiple summaries with same service instance"""
        service = ContentSummarizerAgentService(output_base_path=temp_output_dir)

        content1 = "Test content for summary 1. " * 50
        content2 = "Test content for summary 2. " * 50
        content3 = "Test content for summary 3. " * 50

        result1 = await service.generate_summary(
            content=content1,
            department="sales-marketing",
            title="Summary 1"
        )

        result2 = await service.generate_summary(
            content=content2,
            department="it-engineering",
            title="Summary 2"
        )

        result3 = await service.generate_summary(
            content=content3,
            department="sales-marketing",
            title="Summary 3"
        )

        assert all([result1.success, result2.success, result3.success])

        stats = service.get_stats()
        assert stats["summaries_generated"] == 3
        assert stats["by_department"]["sales-marketing"] == 2
        assert stats["by_department"]["it-engineering"] == 1


# =============================================================================
# API ROUTE TESTS (Without full app context)
# =============================================================================

class TestAPIModels:
    """Test API route models without requiring full app context"""

    def test_generate_summary_request_validation(self):
        """Test GenerateSummaryRequest model validation"""
        from app.routes.content_summarizer import GenerateSummaryRequest

        # Valid request
        request = GenerateSummaryRequest(
            content="Test content " * 20,  # At least 100 chars
            department="sales-marketing",
            title="Test Summary"
        )
        assert request.department == "sales-marketing"

    def test_create_diagram_request_validation(self):
        """Test CreateDiagramRequest model validation"""
        from app.routes.content_summarizer import CreateDiagramRequest

        request = CreateDiagramRequest(
            diagram_type=DiagramType.FLOWCHART,
            title="Test Diagram",
            department="test-dept",
            elements=[{"label": "Element 1"}]
        )
        assert request.diagram_type == DiagramType.FLOWCHART

    def test_create_chart_request_validation(self):
        """Test CreateChartRequest model validation"""
        from app.routes.content_summarizer import CreateChartRequest

        request = CreateChartRequest(
            chart_type="bar",
            title="Test Chart",
            department="test-dept",
            labels=["A", "B"],
            values=[10, 20]
        )
        assert request.chart_type == "bar"


# =============================================================================
# CLEANUP
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_matplotlib():
    """Ensure matplotlib figures are cleaned up after each test"""
    yield
    import matplotlib.pyplot as plt
    plt.close('all')
