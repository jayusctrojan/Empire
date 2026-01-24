# Task ID: 184

**Title:** Implement LangGraph Tool Calling

**Status:** done

**Dependencies:** None

**Priority:** medium

**Description:** Implement proper tool calling with LLM.bind_tools() in the LangGraph workflows to enable structured tool usage.

**Details:**

In `app/workflows/langgraph_workflows.py`, implement the following TODO:

```python
def create_research_workflow(tools=None):
    """Create a research workflow with tool calling capabilities."""
    # Initialize the LLM
    llm = ChatAnthropic(model="claude-3-opus-20240229", temperature=0.2)
    
    # Define the tools if provided
    if tools:
        # Implement proper tool calling with LLM.bind_tools()
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm
    
    # Define workflow states
    @workflow.state
    class State:
        question: str
        context: Optional[List[str]] = None
        tools_results: Optional[List[Dict]] = None
        reasoning: Optional[str] = None
        answer: Optional[str] = None
        follow_up_questions: Optional[List[str]] = None
    
    # Define workflow nodes
    @workflow.node
    async def analyze_question(state: State):
        """Analyze the question and determine what tools are needed."""
        prompt = PromptTemplate("""
        You are a research assistant analyzing a question.
        
        Question: {question}
        
        First, think about what information you need to answer this question.
        Then, determine which tools would be most helpful to gather this information.
        
        Available tools: {tool_descriptions}
        
        Provide your reasoning about what information is needed and which tools to use.
        """)
        
        # Get tool descriptions
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]) if tools else "No tools available"
        
        # Call LLM
        response = await llm.ainvoke(
            prompt.format(question=state.question, tool_descriptions=tool_descriptions)
        )
        
        return {"reasoning": response.content}
    
    @workflow.node
    async def execute_tools(state: State):
        """Execute the appropriate tools based on the question."""
        if not tools:
            return {"tools_results": []}
        
        prompt = PromptTemplate("""
        You are a research assistant with access to several tools.
        
        Question: {question}
        Your reasoning: {reasoning}
        
        Based on your reasoning, use the appropriate tools to gather information needed to answer the question.
        Be specific in your tool calls and only call tools that are necessary.
        """)
        
        # Call LLM with tools
        response = await llm_with_tools.ainvoke(
            prompt.format(question=state.question, reasoning=state.reasoning)
        )
        
        # Extract tool calls and results
        tool_results = []
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # Find the matching tool
            matching_tool = next((t for t in tools if t.name == tool_name), None)
            if matching_tool:
                try:
                    # Execute the tool
                    result = await matching_tool.ainvoke(**tool_args)
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                except Exception as e:
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "error": str(e)
                    })
        
        return {"tools_results": tool_results}
    
    @workflow.node
    async def generate_answer(state: State):
        """Generate a comprehensive answer based on tool results."""
        prompt = PromptTemplate("""
        You are a research assistant providing an answer to a question.
        
        Question: {question}
        Your reasoning: {reasoning}
        
        Tool results:
        {tool_results}
        
        Based on the information gathered, provide a comprehensive answer to the question.
        Include citations to specific tool results where appropriate.
        If you don't have enough information, acknowledge the limitations in your answer.
        """)
        
        # Format tool results
        tool_results_text = ""
        for i, result in enumerate(state.tools_results):
            tool_results_text += f"Result {i+1} - {result['tool']}:\n"
            if "error" in result:
                tool_results_text += f"Error: {result['error']}\n"
            else:
                tool_results_text += f"Args: {json.dumps(result['args'])}\n"
                tool_results_text += f"Result: {json.dumps(result['result'])}\n"
            tool_results_text += "\n"
        
        # Call LLM
        response = await llm.ainvoke(
            prompt.format(
                question=state.question,
                reasoning=state.reasoning,
                tool_results=tool_results_text
            )
        )
        
        return {"answer": response.content}
    
    @workflow.node
    async def suggest_follow_ups(state: State):
        """Suggest follow-up questions based on the answer."""
        prompt = PromptTemplate("""
        You are a research assistant suggesting follow-up questions.
        
        Original question: {question}
        Your answer: {answer}
        
        Based on the answer provided, suggest 3 follow-up questions that would be logical next steps in this research.
        Format each question on a new line, starting with a number and a period.
        """)
        
        # Call LLM
        response = await llm.ainvoke(
            prompt.format(question=state.question, answer=state.answer)
        )
        
        # Parse follow-up questions
        follow_ups = []
        for line in response.content.split("\n"):
            match = re.match(r'^\d+\.\s+(.+)$', line)
            if match:
                follow_ups.append(match.group(1))
        
        return {"follow_up_questions": follow_ups}
    
    # Define the workflow
    builder = workflow.builder()
    builder.add_node("analyze_question", analyze_question)
    builder.add_node("execute_tools", execute_tools)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("suggest_follow_ups", suggest_follow_ups)
    
    # Define the edges
    builder.add_edge("analyze_question", "execute_tools")
    builder.add_edge("execute_tools", "generate_answer")
    builder.add_edge("generate_answer", "suggest_follow_ups")
    
    # Set the entry point
    builder.set_entry_point("analyze_question")
    
    # Build and return the workflow
    return builder.build()
```

**Test Strategy:**

1. Unit tests:
   - Test tool binding with mock tools
   - Test each workflow node individually
   - Test state transitions between nodes

2. Integration tests:
   - Test the complete workflow with sample questions
   - Test with various tool combinations
   - Test error handling when tools fail

3. Functional tests:
   - Test with actual LLM calls (in staging environment)
   - Verify tool calling format is correct
   - Verify follow-up question generation
