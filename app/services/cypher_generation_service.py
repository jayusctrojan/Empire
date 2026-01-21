"""
Empire v7.3 - Cypher Generation Service (Task 31)

Translates natural language questions into Cypher queries using Claude Sonnet.
Provides safe, parameterized query generation for knowledge graph queries.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CypherGenerationConfig:
    """Configuration for Cypher generation"""
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 1024
    temperature: float = 0.0  # Deterministic for query generation


# Graph schema for context
GRAPH_SCHEMA = """
Neo4j Knowledge Graph Schema:

Node Labels:
- Document: {doc_id: string, title: string, content: string, doc_type: string, department: string, metadata: map}
- Entity: {entity_id: string, name: string, entity_type: string, metadata: map}
- Department: {slug: string, display_name: string, description: string, is_active: boolean}

Relationship Types:
- MENTIONS: Document -> Entity (document mentions an entity)
- REFERENCES: Document -> Document (document references another)
- RELATED_TO: Entity -> Entity (entities are related)
- CONTAINS: Document -> Entity (document contains entity)
- BELONGS_TO: Document -> Department (document belongs to department)
- PART_OF: Entity -> Entity (entity is part of another)
- HAS_ENTITY: Document -> Entity (document has entity)

Common Entity Types:
- person, organization, location, regulation, policy, product, concept, date, amount
"""


class CypherGenerationService:
    """
    Service for generating Cypher queries from natural language.

    Uses Claude Sonnet to translate user questions into safe, executable
    Cypher queries for the Neo4j knowledge graph.
    """

    def __init__(self, config: Optional[CypherGenerationConfig] = None):
        """
        Initialize Cypher generation service.

        Args:
            config: Optional configuration for the service.
        """
        self.config = config or CypherGenerationConfig()
        self._client = None
        logger.info("Initialized CypherGenerationService")

    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            except ImportError:
                logger.error("anthropic package not installed")
                raise
            except Exception as e:
                logger.error(f"Failed to create Anthropic client: {e}")
                raise
        return self._client

    async def generate_cypher(
        self,
        question: str,
        max_results: int = 20,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a Cypher query from a natural language question.

        Args:
            question: Natural language question about the knowledge graph.
            max_results: Maximum number of results to return.
            context: Optional additional context about the query.

        Returns:
            Dictionary with 'cypher', 'explanation', and 'parameters'.
        """
        try:
            client = self._get_client()

            system_prompt = f"""You are a Cypher query expert for Neo4j. Generate safe, read-only Cypher queries based on user questions.

{GRAPH_SCHEMA}

Rules:
1. ONLY generate READ queries (MATCH, RETURN, WITH, WHERE, ORDER BY, LIMIT)
2. NEVER generate write operations (CREATE, MERGE, SET, DELETE, REMOVE)
3. Always use LIMIT to prevent large result sets (default: {max_results})
4. Use parameterized patterns where possible
5. Return meaningful properties, not just node IDs
6. Handle case-insensitive matching with toLower() when appropriate
7. For text searches, use CONTAINS or =~ for regex

Respond in this exact JSON format:
{{
    "cypher": "MATCH (n:Label) WHERE ... RETURN ... LIMIT {max_results}",
    "explanation": "Brief explanation of what the query does",
    "confidence": 0.0-1.0
}}

If the question cannot be translated to a valid Cypher query, respond with:
{{
    "cypher": "",
    "explanation": "Reason why query cannot be generated",
    "confidence": 0.0
}}"""

            user_message = f"Question: {question}"
            if context:
                user_message += f"\n\nAdditional context: {context}"

            response = client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )

            # Parse the response
            response_text = response.content[0].text.strip()

            # Extract JSON from response
            import json
            try:
                # Try to parse as JSON directly
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                    result = json.loads(json_str)
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0].strip()
                    result = json.loads(json_str)
                else:
                    result = {
                        "cypher": "",
                        "explanation": "Failed to parse response",
                        "confidence": 0.0
                    }

            # Validate the query is read-only
            cypher = result.get("cypher", "")
            if cypher and not self._is_safe_query(cypher):
                logger.warning(f"Unsafe query rejected: {cypher}")
                return {
                    "cypher": "",
                    "explanation": "Generated query was rejected for safety reasons",
                    "confidence": 0.0
                }

            logger.info(f"Generated Cypher query for: {question[:50]}...")
            return result

        except Exception as e:
            logger.error(f"Cypher generation failed: {e}", exc_info=True)
            return {
                "cypher": "",
                "explanation": f"Query generation failed: {str(e)}",
                "confidence": 0.0
            }

    def _is_safe_query(self, cypher: str) -> bool:
        """
        Validate that a Cypher query is safe (read-only).

        Args:
            cypher: Cypher query string.

        Returns:
            True if the query is safe to execute.
        """
        # Normalize for checking
        upper_cypher = cypher.upper()

        # Forbidden keywords for write operations
        forbidden = [
            "CREATE", "MERGE", "SET", "DELETE", "REMOVE",
            "DETACH", "DROP", "CALL", "FOREACH"
        ]

        for keyword in forbidden:
            # Check for keyword as a word (not part of another word)
            if f" {keyword} " in f" {upper_cypher} " or upper_cypher.startswith(f"{keyword} "):
                return False

        return True

    async def explain_query(self, cypher: str) -> str:
        """
        Generate a natural language explanation of a Cypher query.

        Args:
            cypher: Cypher query to explain.

        Returns:
            Human-readable explanation of the query.
        """
        try:
            client = self._get_client()

            response = client.messages.create(
                model=self.config.model,
                max_tokens=500,
                temperature=0.0,
                system="You are a Cypher query expert. Explain what this query does in simple terms.",
                messages=[{"role": "user", "content": f"Explain this Cypher query:\n\n{cypher}"}]
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Query explanation failed: {e}")
            return f"Unable to explain query: {str(e)}"

    async def suggest_queries(self, topic: str, count: int = 5) -> list:
        """
        Suggest relevant Cypher queries for a topic.

        Args:
            topic: Topic to generate queries for.
            count: Number of queries to suggest.

        Returns:
            List of suggested queries with explanations.
        """
        try:
            client = self._get_client()

            response = client.messages.create(
                model=self.config.model,
                max_tokens=1500,
                temperature=0.3,
                system=f"""You are a Cypher query expert. Generate {count} useful Cypher queries for exploring a knowledge graph about the given topic.

{GRAPH_SCHEMA}

Respond with a JSON array of objects, each with 'cypher' and 'description' fields.""",
                messages=[{"role": "user", "content": f"Generate queries for topic: {topic}"}]
            )

            import json
            response_text = response.content[0].text.strip()

            try:
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                    return json.loads(json_str)
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0].strip()
                    return json.loads(json_str)
                else:
                    return json.loads(response_text)
            except json.JSONDecodeError:
                return []

        except Exception as e:
            logger.error(f"Query suggestion failed: {e}")
            return []


# Singleton instance
_cypher_generation_service: Optional[CypherGenerationService] = None


def get_cypher_generation_service(
    config: Optional[CypherGenerationConfig] = None
) -> CypherGenerationService:
    """
    Get or create singleton Cypher generation service instance.

    Args:
        config: Optional configuration.

    Returns:
        CypherGenerationService instance.
    """
    global _cypher_generation_service

    if _cypher_generation_service is None:
        _cypher_generation_service = CypherGenerationService(config=config)

    return _cypher_generation_service


def reset_cypher_generation_service():
    """Reset the singleton instance (useful for testing)."""
    global _cypher_generation_service
    _cypher_generation_service = None
