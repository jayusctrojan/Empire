"""
CrewAI service integration for Empire v7.3

Provides interface to CrewAI multi-agent orchestration service for:
- Multi-document processing workflows
- Sequential agent collaboration
- Complex multi-step analysis
"""
import os
import requests
import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)


class CrewAIService:
    """
    Interface to CrewAI multi-agent orchestration service.

    CrewAI handles:
    - Sequential multi-agent workflows
    - Document processing pipelines
    - Multi-step analysis with specialized agents
    - Framework extraction and synthesis
    """

    def __init__(self):
        self.base_url = os.getenv("CREWAI_SERVICE_URL", "https://jb-crewai.onrender.com")
        self.api_key = os.getenv("CREWAI_API_KEY")
        self.enabled = os.getenv("CREWAI_ENABLED", "true").lower() == "true"

        if not self.enabled:
            logger.warning("CrewAI service disabled")
        elif not self.api_key:
            logger.warning("CREWAI_API_KEY not set, authentication may fail")
        else:
            logger.info("CrewAI service initialized", base_url=self.base_url)

    def _headers(self) -> Dict[str, str]:
        """Get request headers with optional authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def health_check(self) -> bool:
        """
        Check if CrewAI service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        if not self.enabled:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            is_healthy = response.status_code == 200
            logger.info("CrewAI health check", healthy=is_healthy)
            return is_healthy
        except Exception as e:
            logger.error("CrewAI health check failed", error=str(e))
            return False

    def process_query(
        self,
        query: str,
        workflow_type: str = "document_analysis",
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Process query using CrewAI multi-agent workflow.

        Args:
            query: User query to process
            workflow_type: Type of CrewAI workflow to use
            max_iterations: Maximum agent iterations

        Returns:
            Dict with answer, agents_used, steps, and metadata

        Example:
            ```python
            result = crewai_service.process_query(
                query="Analyze these contracts and extract common terms",
                workflow_type="document_analysis",
                max_iterations=3
            )
            ```
        """
        if not self.enabled:
            raise RuntimeError("CrewAI service is disabled")

        try:
            logger.info(
                "CrewAI query processing started",
                query=query[:100],
                workflow=workflow_type
            )

            payload = {
                "query": query,
                "workflow_type": workflow_type,
                "max_iterations": max_iterations
            }

            response = requests.post(
                f"{self.base_url}/api/crew/process",
                json=payload,
                headers=self._headers(),
                timeout=120  # 2 minute timeout for multi-agent processing
            )

            if response.status_code != 200:
                logger.error(
                    "CrewAI query processing failed",
                    status_code=response.status_code,
                    response=response.text
                )
                raise RuntimeError(f"CrewAI service error: {response.text}")

            result = response.json()

            logger.info(
                "CrewAI query processing completed",
                agents_used=len(result.get("agents_used", [])),
                steps=len(result.get("steps", []))
            )

            return result

        except requests.exceptions.Timeout:
            logger.error("CrewAI request timeout")
            raise RuntimeError("CrewAI service timeout")
        except Exception as e:
            logger.error("CrewAI query processing error", error=str(e))
            raise

    def analyze_documents(
        self,
        document_ids: List[str],
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Analyze multiple documents using CrewAI agents.

        Args:
            document_ids: List of document IDs to analyze
            analysis_type: Type of analysis to perform

        Returns:
            Analysis results from multi-agent workflow

        Example:
            ```python
            result = crewai_service.analyze_documents(
                document_ids=["doc1", "doc2", "doc3"],
                analysis_type="framework_extraction"
            )
            ```
        """
        if not self.enabled:
            raise RuntimeError("CrewAI service is disabled")

        try:
            logger.info(
                "CrewAI document analysis started",
                doc_count=len(document_ids),
                analysis_type=analysis_type
            )

            payload = {
                "document_ids": document_ids,
                "analysis_type": analysis_type
            }

            response = requests.post(
                f"{self.base_url}/api/crew/analyze-documents",
                json=payload,
                headers=self._headers(),
                timeout=180  # 3 minute timeout for multi-document analysis
            )

            if response.status_code != 200:
                logger.error(
                    "CrewAI document analysis failed",
                    status_code=response.status_code
                )
                raise RuntimeError(f"CrewAI service error: {response.text}")

            result = response.json()

            logger.info("CrewAI document analysis completed")
            return result

        except Exception as e:
            logger.error("CrewAI document analysis error", error=str(e))
            raise

    def get_available_workflows(self) -> List[str]:
        """
        Get list of available CrewAI workflow types.

        Returns:
            List of workflow type names
        """
        if not self.enabled:
            return []

        try:
            response = requests.get(
                f"{self.base_url}/api/crew/workflows",
                headers=self._headers(),
                timeout=10
            )

            if response.status_code == 200:
                workflows = response.json().get("workflows", [])
                logger.info("CrewAI workflows retrieved", count=len(workflows))
                return workflows
            else:
                logger.warning("Failed to get CrewAI workflows")
                return []

        except Exception as e:
            logger.error("Error getting CrewAI workflows", error=str(e))
            return []


# Global singleton instance
crewai_service = CrewAIService()
