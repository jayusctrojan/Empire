"""
Course Classification Service for Empire v7.2

Auto-classifies courses into departments and extracts structural metadata
for intelligent filename generation.
"""

import anthropic
import os
import json
import re
from typing import Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


class CourseClassifier:
    """Auto-classify courses and extract structural metadata"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-haiku-4-5"  # Fast and cheap

    async def classify_and_extract(self, filename: str, content_preview: str) -> Dict:
        """
        Classify course into department and extract structural metadata

        Returns:
            {
                "department": "sales-marketing",
                "confidence": 0.92,
                "reasoning": "Content focuses on sales techniques...",
                "suggested_tags": ["sales", "prospecting", "closing"],
                "structure": {
                    "instructor": "Grant Cardone",
                    "company": None,
                    "course_title": "10X Sales System",
                    "has_modules": True,
                    "total_modules": 10,
                    "current_module": 1,
                    "module_name": "Prospecting Fundamentals",
                    "has_lessons": True,
                    "current_lesson": 1,
                    "lesson_name": "Cold Calling Basics",
                    "total_lessons_in_module": 3
                },
                "suggested_filename": "Grant_Cardone-10X_Sales_System-M01-Prospecting_Fundamentals-L01-Cold_Calling_Basics.pdf"
            }
        """

        classification = await self._classify_department(filename, content_preview)
        structure = await self._extract_structure(filename, content_preview)
        suggested_filename = self._generate_filename(structure, filename)

        return {
            **classification,
            "structure": structure,
            "suggested_filename": suggested_filename
        }

    async def _classify_department(self, filename: str, content_preview: str) -> Dict:
        """Classify into one of 12 departments (v7.3)"""

        prompt = f"""Analyze this course material and classify it into the appropriate department.

Filename: {filename}
Content Preview: {content_preview[:3000]}

DEPARTMENTS (use slug format in response):

1. it-engineering - Technology, software, DevOps, data, security, cloud
2. sales-marketing - Sales techniques, marketing, product strategy, customer success
3. customer-support - Technical support, help desk, SLA management, customer service
4. operations-hr-supply - HR, operations, supply chain, procurement, legal compliance
5. finance-accounting - FP&A, accounting, tax, audits, financial risk
6. project-management - Agile, Scrum, PMP, project tools, stakeholder management
7. real-estate - Property management, CRE, real estate investment, leasing, development
8. private-equity-ma - M&A, due diligence, PE fundamentals, valuation, exit strategies
9. consulting - Management consulting, strategy frameworks, client engagement, case interviews
10. personal-continuing-ed - Psychology, NLP, life coaching, mindfulness, personal growth
11. _global - Cross-department content applicable to multiple areas
12. research-development - R&D, innovation, prototyping, experiments, patents, product development

Respond in JSON format:
{{
    "department": "sales-marketing",
    "confidence": 0.92,
    "reasoning": "Content focuses on sales prospecting and closing techniques",
    "suggested_tags": ["sales", "prospecting", "closing", "b2b"]
}}
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        return json.loads(response.content[0].text)

    async def _extract_structure(self, filename: str, content_preview: str) -> Dict:
        """Extract course structure metadata"""

        prompt = f"""Analyze this course material and extract its structural metadata.

Filename: {filename}
Content Preview: {content_preview[:3000]}

Extract the following information:
- Instructor name (person's name, e.g., "Grant Cardone", "Tony Robbins")
- Company name (if corporate course, e.g., "Harvard Business School", "McKinsey")
- Course title
- Module structure (does it have modules?)
- Current module number (if applicable)
- Module name (if applicable)
- Lesson structure (does it have lessons within modules?)
- Current lesson number (if applicable)
- Lesson name (if applicable)
- Total modules in course (estimate if not explicit)
- Total lessons in current module (estimate if not explicit)

IMPORTANT RULES:
1. If it's an individual instructor (Grant Cardone, Tony Robbins), set "instructor" and "company" as null
2. If it's a corporate course (McKinsey, HBS, Udemy), set "company" and "instructor" as null
3. Use null for fields that don't apply or can't be determined
4. Module/lesson numbers should be integers (1, 2, 3, not "01", "02")
5. Keep names concise but descriptive

Respond in JSON format:
{{
    "instructor": "Grant Cardone",
    "company": null,
    "course_title": "10X Sales System",
    "has_modules": true,
    "total_modules": 10,
    "current_module": 1,
    "module_name": "Prospecting Fundamentals",
    "has_lessons": true,
    "current_lesson": 1,
    "lesson_name": "Cold Calling Basics",
    "total_lessons_in_module": 3
}}

OR for a corporate course:
{{
    "instructor": null,
    "company": "McKinsey",
    "course_title": "Strategy Frameworks",
    "has_modules": false,
    "total_modules": null,
    "current_module": null,
    "module_name": null,
    "has_lessons": false,
    "current_lesson": null,
    "lesson_name": null,
    "total_lessons_in_module": null
}}
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return json.loads(response.content[0].text)

    def _generate_filename(self, structure: Dict, original_filename: str) -> str:
        """
        Generate intelligent filename from structure

        Format:
        - With modules and lessons: {Instructor/Company}-{Course}-M{##}-{Module}-L{##}-{Lesson}.ext
        - With modules only: {Instructor/Company}-{Course}-M{##}-{Module}.ext
        - Simple course: {Instructor/Company}-{Course}.ext
        """

        # Get file extension
        ext = original_filename.split(".")[-1] if "." in original_filename else "pdf"

        # Determine source (instructor or company)
        source = structure.get("instructor") or structure.get("company") or "Unknown"
        source = self._sanitize(source)

        # Course title
        course_title = self._sanitize(structure.get("course_title", "Course"))

        # Build filename parts
        parts = [source, course_title]

        # Add module info if exists
        if structure.get("has_modules") and structure.get("current_module"):
            module_num = f"M{structure['current_module']:02d}"  # M01, M02, etc.
            parts.append(module_num)

            if structure.get("module_name"):
                module_name = self._sanitize(structure["module_name"])
                parts.append(module_name)

        # Add lesson info if exists
        if structure.get("has_lessons") and structure.get("current_lesson"):
            lesson_num = f"L{structure['current_lesson']:02d}"  # L01, L02, etc.
            parts.append(lesson_num)

            if structure.get("lesson_name"):
                lesson_name = self._sanitize(structure["lesson_name"])
                parts.append(lesson_name)

        # Join parts and add extension
        filename = "-".join(parts) + f".{ext}"

        # Ensure filename isn't too long (max 200 chars)
        if len(filename) > 200:
            # Truncate lesson/module names if needed
            filename = "-".join(parts[:4]) + f".{ext}"

        return filename

    def _sanitize(self, text: str) -> str:
        """Sanitize text for use in filenames"""
        if not text:
            return "Unknown"

        # Replace spaces with underscores
        text = text.replace(" ", "_")

        # Remove special characters except underscores and hyphens
        text = re.sub(r'[^\w\-]', '', text)

        # Remove multiple underscores
        text = re.sub(r'_+', '_', text)

        # Remove leading/trailing underscores
        text = text.strip("_")

        # Capitalize properly
        text = "_".join(word.capitalize() for word in text.split("_"))

        return text


# Standalone functions for backward compatibility

async def auto_classify_course(filename: str, content_preview: str) -> Dict:
    """
    Auto-classify course and extract structure (standalone function)

    Returns:
        {
            "department": "sales-marketing",
            "confidence": 0.92,
            "reasoning": "...",
            "suggested_tags": [...],
            "structure": {...},
            "suggested_filename": "..."
        }
    """
    classifier = CourseClassifier()
    return await classifier.classify_and_extract(filename, content_preview)


def generate_intelligent_filename(structure: Dict, original_filename: str) -> str:
    """Generate intelligent filename from structure (standalone function)"""
    classifier = CourseClassifier()
    return classifier._generate_filename(structure, original_filename)


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        classifier = CourseClassifier()

        # Test case 1: Course with modules and lessons
        test_content_1 = """
        10X Sales System by Grant Cardone
        Module 1: Prospecting Fundamentals
        Lesson 1: Cold Calling Basics

        In this lesson, we'll cover the fundamentals of cold calling...
        """

        result1 = await classifier.classify_and_extract(
            "grant_cardone_sales.pdf",
            test_content_1
        )

        logger.info("test_1_complete", test_name="Course with modules and lessons", department=result1['department'], suggested_filename=result1['suggested_filename'])

        # Test case 2: Simple corporate course
        test_content_2 = """
        McKinsey Strategy Frameworks
        BCG Matrix Overview

        The Boston Consulting Group (BCG) Matrix is a strategic planning tool...
        """

        result2 = await classifier.classify_and_extract(
            "mckinsey_strategy.pdf",
            test_content_2
        )

        logger.info("test_2_complete", test_name="Simple corporate course", department=result2['department'], suggested_filename=result2['suggested_filename'])

        # Test case 3: NLP course with modules
        test_content_3 = """
        NLP Practitioner Certification - VirtualCoach.com
        Module 5: Advanced Anchoring Techniques

        In this module, we explore advanced anchoring methods...
        """

        result3 = await classifier.classify_and_extract(
            "nlp_course.pdf",
            test_content_3
        )

        logger.info("test_3_complete", test_name="NLP course with modules", department=result3['department'], suggested_filename=result3['suggested_filename'])

    # Run test
    asyncio.run(test())
