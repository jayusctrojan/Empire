"""
CrewAI service integration for Empire v7.3

Provides interface to CrewAI multi-agent orchestration service for:
- Multi-document processing workflows
- Sequential agent collaboration
- Complex multi-step analysis
- Agent pool management and dynamic agent creation
- Crew orchestration and resource allocation
"""
import os
import requests
import httpx
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime
from supabase import Client

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

    def __init__(self, supabase: Optional[Client] = None):
        self.base_url = os.getenv("CREWAI_SERVICE_URL", "https://jb-crewai.onrender.com")
        self.api_key = os.getenv("CREWAI_API_KEY")
        self.enabled = os.getenv("CREWAI_ENABLED", "true").lower() == "true"
        self.supabase = supabase

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

    async def health_check(self) -> bool:
        """
        Check if CrewAI service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
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

    # ==================== Agent Pool Management Methods ====================

    def create_agent(
        self,
        agent_name: str,
        role: str,
        goal: str,
        backstory: str,
        tools: Optional[List[str]] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new agent in the agent pool.

        Args:
            agent_name: Unique name for the agent
            role: Role/job title of the agent
            goal: Primary objective of the agent
            backstory: Background/context for the agent
            tools: List of tool names the agent can use
            llm_config: LLM configuration for the agent

        Returns:
            Created agent data with ID

        Example:
            ```python
            agent = crewai_service.create_agent(
                agent_name="document_analyzer",
                role="Document Analysis Specialist",
                goal="Extract and analyze key information from documents",
                backstory="Expert in document processing with 10 years experience",
                tools=["llamaindex", "pdf_parser"],
                llm_config={"model": "claude-3-sonnet", "temperature": 0.7}
            )
            ```
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for agent management")

        try:
            agent_data = {
                "agent_name": agent_name,
                "role": role,
                "goal": goal,
                "backstory": backstory,
                "tools": tools or [],
                "llm_config": llm_config or {},
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("crewai_agents").insert(agent_data).execute()

            logger.info("Agent created", agent_name=agent_name, agent_id=result.data[0]["id"])
            return result.data[0]

        except Exception as e:
            logger.error("Failed to create agent", agent_name=agent_name, error=str(e))
            raise

    def get_agent(self, agent_id: Optional[str] = None, agent_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve an agent by ID or name.

        Args:
            agent_id: UUID of the agent
            agent_name: Name of the agent

        Returns:
            Agent data or None if not found
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for agent management")

        try:
            if agent_id:
                result = self.supabase.table("crewai_agents").select("*").eq("id", agent_id).execute()
            elif agent_name:
                result = self.supabase.table("crewai_agents").select("*").eq("agent_name", agent_name).execute()
            else:
                raise ValueError("Either agent_id or agent_name must be provided")

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error("Failed to get agent", agent_id=agent_id, agent_name=agent_name, error=str(e))
            raise

    def get_agents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all agents in the pool.

        Args:
            active_only: If True, only return active agents

        Returns:
            List of agent data dictionaries
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for agent management")

        try:
            query = self.supabase.table("crewai_agents").select("*")

            if active_only:
                query = query.eq("is_active", True)

            result = query.execute()
            return result.data

        except Exception as e:
            logger.error("Failed to list agents", error=str(e))
            raise

    def update_agent(
        self,
        agent_id: str,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        backstory: Optional[str] = None,
        tools: Optional[List[str]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update an existing agent's configuration.

        Args:
            agent_id: UUID of the agent to update
            role: New role (optional)
            goal: New goal (optional)
            backstory: New backstory (optional)
            tools: New tools list (optional)
            llm_config: New LLM config (optional)
            is_active: New active status (optional)

        Returns:
            Updated agent data
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for agent management")

        try:
            update_data = {"updated_at": datetime.utcnow().isoformat()}

            if role is not None:
                update_data["role"] = role
            if goal is not None:
                update_data["goal"] = goal
            if backstory is not None:
                update_data["backstory"] = backstory
            if tools is not None:
                update_data["tools"] = tools
            if llm_config is not None:
                update_data["llm_config"] = llm_config
            if is_active is not None:
                update_data["is_active"] = is_active

            result = self.supabase.table("crewai_agents").update(update_data).eq("id", agent_id).execute()

            logger.info("Agent updated", agent_id=agent_id)
            return result.data[0]

        except Exception as e:
            logger.error("Failed to update agent", agent_id=agent_id, error=str(e))
            raise

    def delete_agent(self, agent_id: str, soft_delete: bool = True) -> bool:
        """
        Delete an agent from the pool.

        Args:
            agent_id: UUID of the agent to delete
            soft_delete: If True, mark as inactive; if False, permanently delete

        Returns:
            True if successful
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for agent management")

        try:
            if soft_delete:
                # Soft delete: mark as inactive
                self.supabase.table("crewai_agents").update({
                    "is_active": False,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", agent_id).execute()
            else:
                # Hard delete
                self.supabase.table("crewai_agents").delete().eq("id", agent_id).execute()

            logger.info("Agent deleted", agent_id=agent_id, soft_delete=soft_delete)
            return True

        except Exception as e:
            logger.error("Failed to delete agent", agent_id=agent_id, error=str(e))
            raise

    # ==================== Crew Management Methods ====================

    def create_crew(
        self,
        crew_name: str,
        description: str,
        agent_ids: List[str],
        process_type: str = "sequential",
        memory_enabled: bool = True,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new crew (team of agents).

        Args:
            crew_name: Unique name for the crew
            description: Description of the crew's purpose
            agent_ids: List of agent UUIDs in the crew
            process_type: Process type (sequential, hierarchical)
            memory_enabled: Enable crew memory
            verbose: Enable verbose logging

        Returns:
            Created crew data with ID

        Example:
            ```python
            crew = crewai_service.create_crew(
                crew_name="document_processing_crew",
                description="Multi-agent crew for document analysis",
                agent_ids=["agent-uuid-1", "agent-uuid-2"],
                process_type="sequential"
            )
            ```
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for crew management")

        try:
            crew_data = {
                "crew_name": crew_name,
                "description": description,
                "agent_ids": agent_ids,
                "process_type": process_type,
                "memory_enabled": memory_enabled,
                "verbose_mode": verbose,  # Map to database column name
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("crewai_crews").insert(crew_data).execute()

            logger.info("Crew created", crew_name=crew_name, crew_id=result.data[0]["id"])
            return result.data[0]

        except Exception as e:
            logger.error("Failed to create crew", crew_name=crew_name, error=str(e))
            raise

    def get_crew(self, crew_id: Optional[str] = None, crew_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve a crew by ID or name.

        Args:
            crew_id: UUID of the crew
            crew_name: Name of the crew

        Returns:
            Crew data or None if not found
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for crew management")

        try:
            if crew_id:
                result = self.supabase.table("crewai_crews").select("*").eq("id", crew_id).execute()
            elif crew_name:
                result = self.supabase.table("crewai_crews").select("*").eq("crew_name", crew_name).execute()
            else:
                raise ValueError("Either crew_id or crew_name must be provided")

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error("Failed to get crew", crew_id=crew_id, crew_name=crew_name, error=str(e))
            raise

    def get_crews(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all crews.

        Args:
            active_only: If True, only return active crews

        Returns:
            List of crew data dictionaries
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for crew management")

        try:
            query = self.supabase.table("crewai_crews").select("*")

            if active_only:
                query = query.eq("is_active", True)

            result = query.execute()
            return result.data

        except Exception as e:
            logger.error("Failed to list crews", error=str(e))
            raise

    def update_crew(
        self,
        crew_id: str,
        description: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
        process_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update an existing crew's configuration.

        Args:
            crew_id: UUID of the crew to update
            description: New description (optional)
            agent_ids: New agent IDs list (optional)
            process_type: New process type (optional)
            is_active: New active status (optional)

        Returns:
            Updated crew data
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for crew management")

        try:
            update_data = {"updated_at": datetime.utcnow().isoformat()}

            if description is not None:
                update_data["description"] = description
            if agent_ids is not None:
                update_data["agent_ids"] = agent_ids
            if process_type is not None:
                update_data["process_type"] = process_type
            if is_active is not None:
                update_data["is_active"] = is_active

            result = self.supabase.table("crewai_crews").update(update_data).eq("id", crew_id).execute()

            logger.info("Crew updated", crew_id=crew_id)
            return result.data[0]

        except Exception as e:
            logger.error("Failed to update crew", crew_id=crew_id, error=str(e))
            raise

    def delete_crew(self, crew_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a crew.

        Args:
            crew_id: UUID of the crew to delete
            soft_delete: If True, mark as inactive; if False, permanently delete

        Returns:
            True if successful
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for crew management")

        try:
            if soft_delete:
                # Soft delete: mark as inactive
                self.supabase.table("crewai_crews").update({
                    "is_active": False,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", crew_id).execute()
            else:
                # Hard delete
                self.supabase.table("crewai_crews").delete().eq("id", crew_id).execute()

            logger.info("Crew deleted", crew_id=crew_id, soft_delete=soft_delete)
            return True

        except Exception as e:
            logger.error("Failed to delete crew", crew_id=crew_id, error=str(e))
            raise

    # ==================== Workflow Execution & Orchestration ====================

    def execute_crew(
        self,
        crew_id: str,
        input_data: Dict[str, Any],
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        execution_type: str = "manual"
    ) -> Dict[str, Any]:
        """
        Execute a crew workflow and track execution in database.

        Args:
            crew_id: UUID of the crew to execute
            input_data: Input data for the workflow
            document_id: Optional document ID to associate
            user_id: Optional user ID for tracking
            execution_type: Type of execution (manual, scheduled, triggered)

        Returns:
            Execution record with initial status

        Example:
            ```python
            execution = crewai_service.execute_crew(
                crew_id="crew-uuid",
                input_data={"query": "Analyze document", "doc_ids": ["doc1", "doc2"]},
                document_id="doc1",
                user_id="user123",
                execution_type="manual"
            )
            ```
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for crew execution")

        if not self.enabled:
            raise RuntimeError("CrewAI service is disabled")

        try:
            # Get crew details
            crew = self.get_crew(crew_id=crew_id)
            if not crew:
                raise ValueError(f"Crew {crew_id} not found")

            if not crew.get("is_active", False):
                raise ValueError(f"Crew {crew_id} is not active")

            # Get agents in the crew
            agent_ids = crew.get("agent_ids", [])
            if not agent_ids:
                raise ValueError(f"Crew {crew_id} has no agents")

            # Create execution record
            execution_data = {
                "crew_id": crew_id,
                "document_id": document_id,
                "user_id": user_id,
                "execution_type": execution_type,
                "input_data": input_data,
                "status": "pending",
                "total_tasks": len(agent_ids),
                "completed_tasks": 0,
                "failed_tasks": 0,
                "started_at": datetime.utcnow().isoformat(),
                "created_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("crewai_executions").insert(execution_data).execute()
            execution_id = result.data[0]["id"]

            logger.info(
                "Crew execution started",
                execution_id=execution_id,
                crew_id=crew_id,
                agent_count=len(agent_ids)
            )

            # Call CrewAI REST API to execute workflow
            try:
                response = requests.post(
                    f"{self.base_url}/api/crew/execute",
                    json={
                        "crew_id": crew_id,
                        "agents": agent_ids,
                        "input_data": input_data,
                        "execution_id": execution_id,
                        "process_type": crew.get("process_type", "sequential"),
                        "memory_enabled": crew.get("memory_enabled", True),
                        "verbose": crew.get("verbose_mode", False)  # Read from database column
                    },
                    headers=self._headers(),
                    timeout=300  # 5 minute timeout for workflow execution
                )

                if response.status_code == 200:
                    # Update execution with results
                    workflow_result = response.json()

                    self.supabase.table("crewai_executions").update({
                        "status": "completed",
                        "completed_tasks": workflow_result.get("completed_tasks", len(agent_ids)),
                        "results": workflow_result.get("results"),
                        "execution_time_ms": workflow_result.get("execution_time_ms"),
                        "completed_at": datetime.utcnow().isoformat()
                    }).eq("id", execution_id).execute()

                    logger.info("Crew execution completed", execution_id=execution_id)

                    return {
                        **result.data[0],
                        "status": "completed",
                        "results": workflow_result.get("results")
                    }
                else:
                    # Update execution with error
                    error_msg = f"CrewAI service error: {response.text}"
                    self.supabase.table("crewai_executions").update({
                        "status": "failed",
                        "error_message": error_msg,
                        "completed_at": datetime.utcnow().isoformat()
                    }).eq("id", execution_id).execute()

                    logger.error("Crew execution failed", execution_id=execution_id, error=error_msg)
                    raise RuntimeError(error_msg)

            except requests.exceptions.Timeout:
                # Update execution with timeout error
                self.supabase.table("crewai_executions").update({
                    "status": "failed",
                    "error_message": "Execution timeout",
                    "completed_at": datetime.utcnow().isoformat()
                }).eq("id", execution_id).execute()

                logger.error("Crew execution timeout", execution_id=execution_id)
                raise RuntimeError("Crew execution timeout")

        except Exception as e:
            logger.error("Failed to execute crew", crew_id=crew_id, error=str(e))
            raise

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution details by ID.

        Args:
            execution_id: UUID of the execution

        Returns:
            Execution data or None if not found
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for execution tracking")

        try:
            result = self.supabase.table("crewai_executions").select("*").eq("id", execution_id).execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error("Failed to get execution", execution_id=execution_id, error=str(e))
            raise

    def get_executions(
        self,
        crew_id: Optional[str] = None,
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List executions with optional filtering.

        Args:
            crew_id: Filter by crew ID
            document_id: Filter by document ID
            user_id: Filter by user ID
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of execution records
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for execution tracking")

        try:
            query = self.supabase.table("crewai_executions").select("*")

            if crew_id:
                query = query.eq("crew_id", crew_id)
            if document_id:
                query = query.eq("document_id", document_id)
            if user_id:
                query = query.eq("user_id", user_id)
            if status:
                query = query.eq("status", status)

            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()

            return result.data

        except Exception as e:
            logger.error("Failed to list executions", error=str(e))
            raise

    def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: UUID of the execution to cancel

        Returns:
            True if successful
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for execution tracking")

        try:
            # Update execution status to cancelled
            self.supabase.table("crewai_executions").update({
                "status": "cancelled",
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", execution_id).eq("status", "pending").execute()

            # Note: We may also want to call the CrewAI service to actually stop the execution
            # This depends on whether the CrewAI service supports cancellation

            logger.info("Execution cancelled", execution_id=execution_id)
            return True

        except Exception as e:
            logger.error("Failed to cancel execution", execution_id=execution_id, error=str(e))
            raise

    # ==================== Agent Pool Statistics ====================

    def get_agent_pool_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the agent pool.

        Returns:
            Dictionary with agent pool statistics

        Example:
            ```python
            stats = crewai_service.get_agent_pool_stats()
            # {
            #     "total_agents": 10,
            #     "active_agents": 8,
            #     "inactive_agents": 2,
            #     "total_crews": 3,
            #     "active_crews": 3,
            #     "agents_by_role": {"Document Analyst": 3, "Researcher": 2, ...},
            #     "recent_executions": 15
            # }
            ```
        """
        if not self.supabase:
            raise RuntimeError("Supabase client required for agent pool stats")

        try:
            # Get agent statistics
            all_agents = self.supabase.table("crewai_agents").select("*").execute()
            active_agents = [a for a in all_agents.data if a.get("is_active", False)]

            # Count agents by role
            agents_by_role = {}
            for agent in all_agents.data:
                role = agent.get("role", "Unknown")
                agents_by_role[role] = agents_by_role.get(role, 0) + 1

            # Get crew statistics
            all_crews = self.supabase.table("crewai_crews").select("*").execute()
            active_crews = [c for c in all_crews.data if c.get("is_active", False)]

            # Get recent executions (last 24 hours)
            from datetime import timedelta
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            recent_execs = self.supabase.table("crewai_executions").select(
                "id", count="exact"
            ).gte("created_at", cutoff).execute()

            stats = {
                "total_agents": len(all_agents.data),
                "active_agents": len(active_agents),
                "inactive_agents": len(all_agents.data) - len(active_agents),
                "total_crews": len(all_crews.data),
                "active_crews": len(active_crews),
                "agents_by_role": agents_by_role,
                "recent_executions_24h": recent_execs.count if recent_execs.count else 0,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info("Agent pool stats retrieved", **stats)
            return stats

        except Exception as e:
            logger.error("Failed to get agent pool stats", error=str(e))
            raise


# Global singleton instance
crewai_service = CrewAIService()
