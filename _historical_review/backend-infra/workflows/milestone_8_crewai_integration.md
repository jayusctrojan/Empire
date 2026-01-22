# Milestone 8: CrewAI Multi-Agent Integration

**Purpose**: Implement CrewAI multi-agent workflows for advanced document analysis, content generation, and automated asset creation.

**Key Technologies**:
- CrewAI for multi-agent orchestration
- Claude API for agent LLM capabilities
- Supabase for crew execution tracking
- Celery for async crew task execution
- FastAPI endpoints for crew management

**Architecture**:
- Specialized agents for different tasks (Research, Analysis, Writing, Fact-Checking)
- Sequential and parallel task execution
- Agent memory and context sharing
- Results storage in Supabase
- Integration with document processing pipeline

---

## 8.1 Supabase Schema - CrewAI Tables

```sql
-- ============================================================================
-- Milestone 8: CrewAI Integration Schema
-- ============================================================================

-- Agent definitions table
CREATE TABLE IF NOT EXISTS public.crewai_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(100) UNIQUE NOT NULL,
    role VARCHAR(255) NOT NULL,
    goal TEXT NOT NULL,
    backstory TEXT NOT NULL,
    tools JSONB DEFAULT '[]', -- Array of tool names
    llm_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_agents
CREATE INDEX IF NOT EXISTS idx_crewai_agents_name ON public.crewai_agents(agent_name);
CREATE INDEX IF NOT EXISTS idx_crewai_agents_active ON public.crewai_agents(is_active) WHERE is_active = true;

-- Crew definitions table
CREATE TABLE IF NOT EXISTS public.crewai_crews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crew_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    process_type VARCHAR(50) DEFAULT 'sequential', -- 'sequential', 'hierarchical', 'parallel'
    agent_ids UUID[] NOT NULL, -- Array of agent UUIDs
    memory_enabled BOOLEAN DEFAULT true,
    verbose BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_crews
CREATE INDEX IF NOT EXISTS idx_crewai_crews_name ON public.crewai_crews(crew_name);
CREATE INDEX IF NOT EXISTS idx_crewai_crews_active ON public.crewai_crews(is_active) WHERE is_active = true;

-- Task templates table
CREATE TABLE IF NOT EXISTS public.crewai_task_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    agent_id UUID REFERENCES crewai_agents(id) ON DELETE CASCADE,
    context_requirements JSONB DEFAULT '[]',
    parameters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_task_templates
CREATE INDEX IF NOT EXISTS idx_task_templates_name ON public.crewai_task_templates(template_name);
CREATE INDEX IF NOT EXISTS idx_task_templates_agent ON public.crewai_task_templates(agent_id);

-- Crew executions table
CREATE TABLE IF NOT EXISTS public.crewai_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crew_id UUID NOT NULL REFERENCES crewai_crews(id) ON DELETE CASCADE,
    document_id VARCHAR(64) REFERENCES documents(document_id) ON DELETE CASCADE,
    user_id VARCHAR(100),
    execution_type VARCHAR(50) NOT NULL, -- 'analysis', 'generation', 'validation', 'extraction'
    input_data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    total_tasks INTEGER NOT NULL,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    results JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_executions
CREATE INDEX IF NOT EXISTS idx_crew_exec_crew ON public.crewai_executions(crew_id);
CREATE INDEX IF NOT EXISTS idx_crew_exec_document ON public.crewai_executions(document_id);
CREATE INDEX IF NOT EXISTS idx_crew_exec_status ON public.crewai_executions(status);
CREATE INDEX IF NOT EXISTS idx_crew_exec_type ON public.crewai_executions(execution_type);
CREATE INDEX IF NOT EXISTS idx_crew_exec_created ON public.crewai_executions(created_at DESC);

-- Task executions table (individual agent tasks)
CREATE TABLE IF NOT EXISTS public.crewai_task_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES crewai_executions(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES crewai_agents(id) ON DELETE CASCADE,
    task_description TEXT NOT NULL,
    task_order INTEGER NOT NULL,
    expected_output TEXT,
    actual_output TEXT,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    tokens_used INTEGER,
    execution_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_task_executions
CREATE INDEX IF NOT EXISTS idx_task_exec_execution ON public.crewai_task_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_task_exec_agent ON public.crewai_task_executions(agent_id);
CREATE INDEX IF NOT EXISTS idx_task_exec_status ON public.crewai_task_executions(status);
CREATE INDEX IF NOT EXISTS idx_task_exec_order ON public.crewai_task_executions(execution_id, task_order);

-- Agent interactions table (for tracking agent-to-agent communication)
CREATE TABLE IF NOT EXISTS public.crewai_agent_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES crewai_executions(id) ON DELETE CASCADE,
    from_agent_id UUID NOT NULL REFERENCES crewai_agents(id) ON DELETE CASCADE,
    to_agent_id UUID REFERENCES crewai_agents(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL, -- 'delegation', 'question', 'result_sharing'
    message TEXT NOT NULL,
    response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_agent_interactions
CREATE INDEX IF NOT EXISTS idx_agent_interact_execution ON public.crewai_agent_interactions(execution_id);
CREATE INDEX IF NOT EXISTS idx_agent_interact_from ON public.crewai_agent_interactions(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_interact_to ON public.crewai_agent_interactions(to_agent_id);

-- Generated assets table (outputs from crew executions)
CREATE TABLE IF NOT EXISTS public.crewai_generated_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES crewai_executions(id) ON DELETE CASCADE,
    document_id VARCHAR(64) REFERENCES documents(document_id) ON DELETE CASCADE,
    asset_type VARCHAR(50) NOT NULL, -- 'summary', 'report', 'analysis', 'visualization', 'metadata'
    asset_name VARCHAR(255) NOT NULL,
    content TEXT,
    content_format VARCHAR(20) DEFAULT 'text', -- 'text', 'json', 'html', 'markdown'
    metadata JSONB DEFAULT '{}',
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crewai_generated_assets
CREATE INDEX IF NOT EXISTS idx_gen_assets_execution ON public.crewai_generated_assets(execution_id);
CREATE INDEX IF NOT EXISTS idx_gen_assets_document ON public.crewai_generated_assets(document_id);
CREATE INDEX IF NOT EXISTS idx_gen_assets_type ON public.crewai_generated_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_gen_assets_created ON public.crewai_generated_assets(created_at DESC);

-- ============================================================================
-- Functions for CrewAI
-- ============================================================================

-- Function: Get crew execution summary
CREATE OR REPLACE FUNCTION get_crew_execution_summary(
    p_execution_id UUID
)
RETURNS TABLE (
    execution_info JSONB,
    task_summary JSONB,
    agent_performance JSONB,
    generated_assets JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH exec_info AS (
        SELECT jsonb_build_object(
            'execution_id', ce.id,
            'crew_name', cc.crew_name,
            'status', ce.status,
            'execution_type', ce.execution_type,
            'total_tasks', ce.total_tasks,
            'completed_tasks', ce.completed_tasks,
            'failed_tasks', ce.failed_tasks,
            'execution_time_ms', ce.execution_time_ms,
            'started_at', ce.started_at,
            'completed_at', ce.completed_at
        ) AS info
        FROM crewai_executions ce
        JOIN crewai_crews cc ON ce.crew_id = cc.id
        WHERE ce.id = p_execution_id
    ),
    task_info AS (
        SELECT jsonb_agg(
            jsonb_build_object(
                'task_id', cte.id,
                'agent_name', ca.agent_name,
                'description', cte.task_description,
                'status', cte.status,
                'execution_time_ms', cte.execution_time_ms,
                'tokens_used', cte.tokens_used
            ) ORDER BY cte.task_order
        ) AS tasks
        FROM crewai_task_executions cte
        JOIN crewai_agents ca ON cte.agent_id = ca.id
        WHERE cte.execution_id = p_execution_id
    ),
    agent_perf AS (
        SELECT jsonb_agg(
            jsonb_build_object(
                'agent_name', ca.agent_name,
                'tasks_completed', COUNT(*) FILTER (WHERE cte.status = 'completed'),
                'tasks_failed', COUNT(*) FILTER (WHERE cte.status = 'failed'),
                'avg_execution_time_ms', AVG(cte.execution_time_ms)::INTEGER,
                'total_tokens', SUM(cte.tokens_used)
            )
        ) AS performance
        FROM crewai_task_executions cte
        JOIN crewai_agents ca ON cte.agent_id = ca.id
        WHERE cte.execution_id = p_execution_id
        GROUP BY ca.agent_name
    ),
    assets_info AS (
        SELECT jsonb_agg(
            jsonb_build_object(
                'asset_id', cga.id,
                'asset_type', cga.asset_type,
                'asset_name', cga.asset_name,
                'confidence_score', cga.confidence_score,
                'created_at', cga.created_at
            )
        ) AS assets
        FROM crewai_generated_assets cga
        WHERE cga.execution_id = p_execution_id
    )
    SELECT
        (SELECT info FROM exec_info),
        (SELECT tasks FROM task_info),
        (SELECT performance FROM agent_perf),
        (SELECT assets FROM assets_info);
END;
$$ LANGUAGE plpgsql;

-- Function: Get crew performance statistics
CREATE OR REPLACE FUNCTION get_crew_performance_stats(
    p_crew_id UUID DEFAULT NULL,
    p_time_window INTERVAL DEFAULT '7 days'
)
RETURNS TABLE (
    crew_name VARCHAR(100),
    total_executions BIGINT,
    successful_executions BIGINT,
    failed_executions BIGINT,
    success_rate DECIMAL(5, 2),
    avg_execution_time_ms DECIMAL(10, 2),
    total_tokens_used BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cc.crew_name,
        COUNT(ce.id)::BIGINT AS total_executions,
        COUNT(*) FILTER (WHERE ce.status = 'completed')::BIGINT AS successful_executions,
        COUNT(*) FILTER (WHERE ce.status = 'failed')::BIGINT AS failed_executions,
        (COUNT(*) FILTER (WHERE ce.status = 'completed')::DECIMAL / NULLIF(COUNT(*)::DECIMAL, 0) * 100)::DECIMAL(5, 2) AS success_rate,
        AVG(ce.execution_time_ms)::DECIMAL(10, 2) AS avg_execution_time_ms,
        (
            SELECT COALESCE(SUM(cte.tokens_used), 0)
            FROM crewai_task_executions cte
            WHERE cte.execution_id = ANY(ARRAY_AGG(ce.id))
        )::BIGINT AS total_tokens_used
    FROM crewai_crews cc
    LEFT JOIN crewai_executions ce ON cc.id = ce.crew_id
    WHERE
        ce.created_at > NOW() - p_time_window
        AND (p_crew_id IS NULL OR cc.id = p_crew_id)
    GROUP BY cc.crew_name
    ORDER BY total_executions DESC;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Update timestamps
CREATE OR REPLACE FUNCTION update_crewai_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_crewai_agents_timestamp
    BEFORE UPDATE ON crewai_agents
    FOR EACH ROW
    EXECUTE FUNCTION update_crewai_timestamp();

CREATE TRIGGER update_crewai_crews_timestamp
    BEFORE UPDATE ON crewai_crews
    FOR EACH ROW
    EXECUTE FUNCTION update_crewai_timestamp();

CREATE TRIGGER update_task_templates_timestamp
    BEFORE UPDATE ON crewai_task_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_crewai_timestamp();
```

---

## 8.2 Python Services - CrewAI Integration

### 8.2.1 CrewAI Service

```python
# app/services/crewai_service.py

from typing import Dict, List, Optional
from datetime import datetime
from crewai import Agent, Task, Crew, Process
import httpx
from supabase import create_client, Client
from app.config import Settings

settings = Settings()

class CrewAIService:
    """Service for managing CrewAI multi-agent workflows"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.anthropic_api_key = settings.anthropic_api_key

    async def create_agent_definition(
        self,
        agent_name: str,
        role: str,
        goal: str,
        backstory: str,
        tools: List[str] = None,
        llm_config: Dict = None
    ) -> Dict:
        """Create an agent definition in database"""
        agent_data = {
            'agent_name': agent_name,
            'role': role,
            'goal': goal,
            'backstory': backstory,
            'tools': tools or [],
            'llm_config': llm_config or {
                'model': 'claude-sonnet-4-5-20250929',
                'temperature': 0.7,
                'max_tokens': 4096
            }
        }

        result = self.supabase.table('crewai_agents').insert(agent_data).execute()
        return result.data[0] if result.data else None

    async def create_crew_definition(
        self,
        crew_name: str,
        description: str,
        agent_ids: List[str],
        process_type: str = 'sequential',
        memory_enabled: bool = True
    ) -> Dict:
        """Create a crew definition"""
        crew_data = {
            'crew_name': crew_name,
            'description': description,
            'agent_ids': agent_ids,
            'process_type': process_type,
            'memory_enabled': memory_enabled
        }

        result = self.supabase.table('crewai_crews').insert(crew_data).execute()
        return result.data[0] if result.data else None

    async def build_agent_from_definition(self, agent_def: Dict) -> Agent:
        """Build a CrewAI Agent from database definition"""
        # Configure LLM
        llm_config = agent_def.get('llm_config', {})

        agent = Agent(
            role=agent_def['role'],
            goal=agent_def['goal'],
            backstory=agent_def['backstory'],
            verbose=True,
            allow_delegation=True,
            # Tools would be configured here based on agent_def['tools']
            llm_config={
                'model': llm_config.get('model', 'claude-sonnet-4-5-20250929'),
                'temperature': llm_config.get('temperature', 0.7),
                'api_key': self.anthropic_api_key
            }
        )

        return agent

    async def execute_crew(
        self,
        crew_id: str,
        document_id: str,
        user_id: Optional[str] = None,
        execution_type: str = 'analysis',
        input_data: Dict = None
    ) -> Dict:
        """Execute a crew workflow"""
        # Get crew definition
        crew_def = self.supabase.table('crewai_crews') \
            .select('*, crewai_agents(*)') \
            .eq('id', crew_id) \
            .single() \
            .execute()

        if not crew_def.data:
            raise ValueError(f"Crew not found: {crew_id}")

        crew_data = crew_def.data

        # Create execution record
        execution_data = {
            'crew_id': crew_id,
            'document_id': document_id,
            'user_id': user_id,
            'execution_type': execution_type,
            'input_data': input_data or {},
            'total_tasks': len(crew_data['crewai_agents']),
            'status': 'running',
            'started_at': datetime.now().isoformat()
        }

        exec_result = self.supabase.table('crewai_executions') \
            .insert(execution_data) \
            .execute()

        execution_id = exec_result.data[0]['id']

        try:
            # Build agents
            agents = []
            for agent_def in crew_data['crewai_agents']:
                agent = await self.build_agent_from_definition(agent_def)
                agents.append(agent)

            # Build tasks
            tasks = await self._build_tasks_for_document(
                agents=agents,
                document_id=document_id,
                execution_id=execution_id,
                input_data=input_data
            )

            # Create and execute crew
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential if crew_data['process_type'] == 'sequential' else Process.hierarchical,
                verbose=crew_data['verbose'],
                memory=crew_data['memory_enabled']
            )

            start_time = datetime.now()
            results = crew.kickoff()
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update execution record
            self.supabase.table('crewai_executions') \
                .update({
                    'status': 'completed',
                    'results': {'output': str(results)},
                    'execution_time_ms': execution_time,
                    'completed_at': datetime.now().isoformat(),
                    'completed_tasks': len(tasks)
                }) \
                .eq('id', execution_id) \
                .execute()

            return {
                'execution_id': execution_id,
                'status': 'completed',
                'results': results,
                'execution_time_ms': execution_time
            }

        except Exception as e:
            # Update execution with failure
            self.supabase.table('crewai_executions') \
                .update({
                    'status': 'failed',
                    'error_message': str(e),
                    'completed_at': datetime.now().isoformat()
                }) \
                .eq('id', execution_id) \
                .execute()

            raise

    async def _build_tasks_for_document(
        self,
        agents: List[Agent],
        document_id: str,
        execution_id: str,
        input_data: Dict
    ) -> List[Task]:
        """Build tasks for document analysis"""
        # Get document content
        doc_result = self.supabase.table('documents') \
            .select('*, document_chunks(content)') \
            .eq('document_id', document_id) \
            .single() \
            .execute()

        if not doc_result.data:
            raise ValueError(f"Document not found: {document_id}")

        document = doc_result.data
        content = "\n\n".join([chunk['content'] for chunk in document['document_chunks'][:10]])

        tasks = []

        # Task 1: Initial Analysis (Research Agent)
        if len(agents) > 0:
            task1 = Task(
                description=f"""Analyze the following document and extract key information:

                Document: {document['filename']}
                Content: {content[:2000]}...

                Extract:
                1. Main topics and themes
                2. Key entities (people, organizations, locations)
                3. Important facts and claims
                4. Document structure and organization
                5. Content quality assessment
                """,
                expected_output="Structured analysis with topics, entities, facts, and quality assessment",
                agent=agents[0]
            )
            tasks.append(task1)

            # Log task execution
            await self._log_task_execution(
                execution_id=execution_id,
                agent_id=agents[0].id if hasattr(agents[0], 'id') else None,
                task_description=task1.description,
                task_order=1
            )

        # Task 2: Content Synthesis (Content Strategist)
        if len(agents) > 1:
            task2 = Task(
                description="""Based on the analysis from the previous task, synthesize the information into:

                1. Executive summary (3-5 sentences)
                2. Key findings and insights
                3. Content categorization and taxonomy
                4. Recommendations for further analysis
                """,
                expected_output="Comprehensive synthesis with summary, findings, and recommendations",
                agent=agents[1],
                context=[tasks[0]] if tasks else []
            )
            tasks.append(task2)

            await self._log_task_execution(
                execution_id=execution_id,
                agent_id=agents[1].id if hasattr(agents[1], 'id') else None,
                task_description=task2.description,
                task_order=2
            )

        # Task 3: Fact Verification (Fact Checker)
        if len(agents) > 2:
            task3 = Task(
                description="""Verify all factual claims identified in the previous analysis:

                1. Identify all factual claims
                2. Assess confidence level for each claim (0.0-1.0)
                3. Flag any potentially inaccurate or unsupported claims
                4. Provide citations or sources where possible
                """,
                expected_output="Fact verification report with confidence scores and citations",
                agent=agents[2],
                context=[tasks[0], tasks[1]] if len(tasks) >= 2 else []
            )
            tasks.append(task3)

            await self._log_task_execution(
                execution_id=execution_id,
                agent_id=agents[2].id if hasattr(agents[2], 'id') else None,
                task_description=task3.description,
                task_order=3
            )

        return tasks

    async def _log_task_execution(
        self,
        execution_id: str,
        agent_id: Optional[str],
        task_description: str,
        task_order: int
    ):
        """Log task execution to database"""
        task_data = {
            'execution_id': execution_id,
            'agent_id': agent_id,
            'task_description': task_description,
            'task_order': task_order,
            'status': 'pending',
            'started_at': datetime.now().isoformat()
        }

        self.supabase.table('crewai_task_executions').insert(task_data).execute()

    async def get_execution_summary(self, execution_id: str) -> Dict:
        """Get detailed execution summary"""
        result = self.supabase.rpc(
            'get_crew_execution_summary',
            {'p_execution_id': execution_id}
        ).execute()

        if not result.data:
            return None

        return result.data[0]

    async def get_crew_performance(
        self,
        crew_id: Optional[str] = None,
        time_window: str = '7 days'
    ) -> List[Dict]:
        """Get crew performance statistics"""
        result = self.supabase.rpc(
            'get_crew_performance_stats',
            {
                'p_crew_id': crew_id,
                'p_time_window': time_window
            }
        ).execute()

        return result.data if result.data else []

crewai_service = CrewAIService()
```

### 8.2.2 Pre-configured Crews

```python
# app/services/crewai_presets.py

from app.services.crewai_service import crewai_service

async def setup_default_crews():
    """Setup default crew configurations"""

    # Create Research Analyst Agent
    research_agent = await crewai_service.create_agent_definition(
        agent_name='research_analyst',
        role='Senior Research Analyst',
        goal='Analyze documents and extract key insights, entities, and themes',
        backstory='Expert analyst with 15 years of experience in document analysis, research methodology, and information extraction',
        tools=['document_search', 'web_search', 'summarizer'],
        llm_config={
            'model': 'claude-sonnet-4-5-20250929',
            'temperature': 0.5,
            'max_tokens': 4096
        }
    )

    # Create Content Strategist Agent
    strategist_agent = await crewai_service.create_agent_definition(
        agent_name='content_strategist',
        role='Content Strategy Expert',
        goal='Synthesize information and create actionable insights',
        backstory='Seasoned strategist specializing in content organization, taxonomy design, and strategic planning',
        tools=['pattern_analyzer', 'theme_extractor', 'categorizer'],
        llm_config={
            'model': 'claude-sonnet-4-5-20250929',
            'temperature': 0.7,
            'max_tokens': 4096
        }
    )

    # Create Fact Checker Agent
    fact_checker_agent = await crewai_service.create_agent_definition(
        agent_name='fact_checker',
        role='Senior Fact Verification Specialist',
        goal='Verify claims and validate information accuracy',
        backstory='Meticulous fact-checker with expertise in verification methodologies and source validation',
        tools=['web_search', 'database_query', 'citation_validator'],
        llm_config={
            'model': 'claude-sonnet-4-5-20250929',
            'temperature': 0.3,
            'max_tokens': 4096
        }
    )

    # Create Document Analysis Crew
    analysis_crew = await crewai_service.create_crew_definition(
        crew_name='document_analysis_crew',
        description='Comprehensive document analysis with research, synthesis, and fact-checking',
        agent_ids=[research_agent['id'], strategist_agent['id'], fact_checker_agent['id']],
        process_type='sequential',
        memory_enabled=True
    )

    return {
        'agents': [research_agent, strategist_agent, fact_checker_agent],
        'crews': [analysis_crew]
    }
```

---

## 8.3 FastAPI Endpoints

```python
# app/routers/crewai.py

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
from app.services.crewai_service import crewai_service
from app.services.admin_service import verify_admin_token

router = APIRouter(prefix="/crewai", tags=["crewai"])

@router.post("/crews/execute")
async def execute_crew(
    crew_id: str,
    document_id: str,
    user_id: Optional[str] = None,
    execution_type: str = 'analysis',
    input_data: Optional[Dict] = None
) -> Dict:
    """Execute a crew workflow on a document"""
    try:
        result = await crewai_service.execute_crew(
            crew_id=crew_id,
            document_id=document_id,
            user_id=user_id,
            execution_type=execution_type,
            input_data=input_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}")
async def get_execution_summary(execution_id: str) -> Dict:
    """Get detailed execution summary"""
    summary = await crewai_service.get_execution_summary(execution_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Execution not found")

    return summary

@router.get("/crews/performance")
async def get_crew_performance(
    crew_id: Optional[str] = None,
    time_window: str = '7 days'
) -> Dict:
    """Get crew performance statistics"""
    stats = await crewai_service.get_crew_performance(crew_id, time_window)
    return {'statistics': stats}

@router.post("/agents", dependencies=[Depends(verify_admin_token)])
async def create_agent(
    agent_name: str,
    role: str,
    goal: str,
    backstory: str,
    tools: List[str] = None,
    llm_config: Dict = None
) -> Dict:
    """Create a new agent definition (admin only)"""
    agent = await crewai_service.create_agent_definition(
        agent_name=agent_name,
        role=role,
        goal=goal,
        backstory=backstory,
        tools=tools,
        llm_config=llm_config
    )
    return agent

@router.post("/crews", dependencies=[Depends(verify_admin_token)])
async def create_crew(
    crew_name: str,
    description: str,
    agent_ids: List[str],
    process_type: str = 'sequential',
    memory_enabled: bool = True
) -> Dict:
    """Create a new crew definition (admin only)"""
    crew = await crewai_service.create_crew_definition(
        crew_name=crew_name,
        description=description,
        agent_ids=agent_ids,
        process_type=process_type,
        memory_enabled=memory_enabled
    )
    return crew
```

---

## 8.4 Celery Task for Async Execution

```python
# app/tasks/crewai_tasks.py

from celery import shared_task
from app.services.crewai_service import crewai_service

@shared_task(name='execute_crew_async')
def execute_crew_async(
    crew_id: str,
    document_id: str,
    user_id: str = None,
    execution_type: str = 'analysis',
    input_data: dict = None
):
    """Execute CrewAI workflow asynchronously"""
    import asyncio

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        crewai_service.execute_crew(
            crew_id=crew_id,
            document_id=document_id,
            user_id=user_id,
            execution_type=execution_type,
            input_data=input_data
        )
    )

    return result
```

---

## 8.5 Environment Variables

```bash
# Add to .env

# CrewAI Settings
CREWAI_ENABLED=true
CREWAI_MAX_ITERATIONS=5
CREWAI_TIMEOUT_SECONDS=300
CREWAI_DEFAULT_TEMPERATURE=0.7

# Agent LLM Settings
AGENT_LLM_MODEL=claude-sonnet-4-5-20250929
AGENT_LLM_MAX_TOKENS=4096
```

---

## 8.6 Docker Compose Update

```yaml
# Add to docker-compose.yml environment variables

services:
  web:
    environment:
      # ... existing vars ...
      - CREWAI_ENABLED=${CREWAI_ENABLED}
      - AGENT_LLM_MODEL=${AGENT_LLM_MODEL}

  celery_worker:
    environment:
      # ... existing vars ...
      - CREWAI_ENABLED=${CREWAI_ENABLED}
      - AGENT_LLM_MODEL=${AGENT_LLM_MODEL}
```

---

**Performance Targets**:
- Single agent task: 2-10 seconds
- 3-agent sequential workflow: 10-30 seconds
- Execution tracking overhead: <100ms
- Database logging: <50ms per event

**Integration Points**:
- Automatically analyze new documents after processing
- Triggered by admin or API request
- Results stored as generated assets
- Integrated with document metadata

**Next**: Create reference files (database_setup, service_patterns, etc.)
