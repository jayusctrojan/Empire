# Task ID: 195

**Title:** Implement LangGraph Tool Calling

**Status:** cancelled

**Dependencies:** None

**Priority:** medium

**Description:** Implement proper tool calling with LLM.bind_tools() in the LangGraph workflows to enable effective tool usage within the workflow.

**Details:**

This task involves completing 1 TODO in app/workflows/langgraph_workflows.py:

```python
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import Dict, List, Any, Optional, TypedDict, Annotated

# Define tool schemas
class SearchTool(TypedDict):
    """Tool for searching documents"""
    query: str
    filters: Optional[Dict[str, Any]]

class CalculateTool(TypedDict):
    """Tool for performing calculations"""
    expression: str

class RetrieveTool(TypedDict):
    """Tool for retrieving specific information"""
    entity_id: str
    fields: Optional[List[str]]

# Implement tools
@tool
def search_documents(args: SearchTool) -> Dict[str, Any]:
    """Search for documents matching the query and filters"""
    query = args["query"]
    filters = args.get("filters", {})
    
    # Implement actual search logic
    # This is a placeholder
    results = [{"id": "doc1", "title": "Example Document", "score": 0.95}]
    
    return {"results": results, "count": len(results)}

@tool
def calculate(args: CalculateTool) -> Dict[str, Any]:
    """Evaluate a mathematical expression"""
    expression = args["expression"]
    
    try:
        # Use safer eval with restricted globals
        result = eval(expression, {"__builtins__": {}}, {"math": __import__("math")})
        return {"result": result, "expression": expression}
    except Exception as e:
        return {"error": str(e), "expression": expression}

@tool
def retrieve_entity(args: RetrieveTool) -> Dict[str, Any]:
    """Retrieve information about a specific entity"""
    entity_id = args["entity_id"]
    fields = args.get("fields", ["name", "description"])
    
    # Implement actual retrieval logic
    # This is a placeholder
    entity = {"id": entity_id, "name": "Example Entity", "description": "This is an example entity"}
    
    # Filter to requested fields
    result = {field: entity.get(field) for field in fields if field in entity}
    
    return {"entity": result}

# Define available tools
AVAILABLE_TOOLS = [search_documents, calculate, retrieve_entity]

# Define state schema
class WorkflowState(TypedDict):
    """State for the workflow"""
    question: str
    context: Optional[Dict[str, Any]]
    tools_output: Optional[List[Dict[str, Any]]]
    answer: Optional[str]

# Define workflow nodes
def analyze_question(state: WorkflowState, llm: BaseChatModel) -> Dict[str, Any]:
    """Analyze the question and determine next steps"""
    question = state["question"]
    context = state.get("context", {})
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)
    
    # Create prompt for analysis
    prompt = f"""Analyze this question and determine if you need to use tools to answer it.
    Question: {question}
    
    If you need to use tools, use them directly. If you can answer without tools, provide the answer.
    """
    
    # Get response from LLM
    response = llm_with_tools.invoke(prompt)
    
    # Check if tools were used
    tool_calls = getattr(response, "tool_calls", [])
    
    if tool_calls:
        return {"next": "execute_tools", "tool_calls": tool_calls}
    else:
        return {"next": "generate_answer", "direct_answer": response.content}

def execute_tools(state: WorkflowState) -> Dict[str, Any]:
    """Execute the tools requested by the LLM"""
    tool_calls = state.get("tool_calls", [])
    tools_output = []
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # Find the matching tool
        matching_tool = next((t for t in AVAILABLE_TOOLS if t.name == tool_name), None)
        
        if matching_tool:
            try:
                # Execute the tool
                result = matching_tool(tool_args)
                tools_output.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                    "success": True
                })
            except Exception as e:
                tools_output.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "error": str(e),
                    "success": False
                })
    
    return {"next": "generate_answer", "tools_output": tools_output}

def generate_answer(state: WorkflowState, llm: BaseChatModel) -> Dict[str, Any]:
    """Generate the final answer based on tool outputs and context"""
    question = state["question"]
    tools_output = state.get("tools_output", [])
    direct_answer = state.get("direct_answer")
    
    if direct_answer:
        # If we already have a direct answer, use it
        return {"next": END, "answer": direct_answer}
    
    # Create prompt with tool outputs
    tools_output_str = "\n".join([f"Tool: {o['tool']}\nResult: {o['result']}" for o in tools_output if o.get("success")])
    
    prompt = f"""Based on the following tool outputs, answer the original question.
    
    Question: {question}
    
    Tool Outputs:
    {tools_output_str}
    
    Provide a comprehensive answer based on this information.
    """
    
    # Get response from LLM
    response = llm.invoke(prompt)
    
    return {"next": END, "answer": response.content}

# Create the workflow
def create_research_workflow(llm: Optional[BaseChatModel] = None) -> StateGraph:
    """Create a research workflow with tool calling"""
    # Use provided LLM or default to OpenAI
    workflow_llm = llm or ChatOpenAI(model="gpt-4-turbo")
    
    # Create workflow graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("analyze_question", lambda state: analyze_question(state, workflow_llm))
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("generate_answer", lambda state: generate_answer(state, workflow_llm))
    
    # Add edges
    workflow.add_edge("analyze_question", "execute_tools")
    workflow.add_edge("analyze_question", "generate_answer")
    workflow.add_edge("execute_tools", "generate_answer")
    
    # Set entry point
    workflow.set_entry_point("analyze_question")
    
    return workflow.compile()

# Example usage
def run_research_workflow(question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the research workflow with a question"""
    workflow = create_research_workflow()
    
    # Initialize state
    initial_state = {"question": question, "context": context or {}}
    
    # Run workflow
    result = workflow.invoke(initial_state)
    
    return result
```

**Test Strategy:**

1. Unit tests for each tool function with various inputs
2. Unit tests for workflow nodes (analyze_question, execute_tools, generate_answer)
3. Integration tests for the complete workflow
4. Test cases:
   - Questions that can be answered directly
   - Questions requiring tool usage
   - Questions requiring multiple tools
   - Error handling in tool execution
5. Test with different LLM models to ensure compatibility
6. Verify tool binding works correctly with different LangChain versions
7. Performance testing with complex queries requiring multiple tool calls
