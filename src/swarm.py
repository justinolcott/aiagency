from typing import Annotated, Dict, List, Any, TypedDict
from langchain_core.tools import tool
from langchain_core.messages import AnyMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph_swarm import create_handoff_tool, create_swarm

# Define some development tools for our engineers

@tool
def create_backend_api(endpoint: str, method: str, request_schema: str, response_schema: str) -> str:
    """Create a backend API endpoint with the specified method, request schema, and response schema."""
    return f"Created API endpoint: {endpoint} ({method})\nRequest schema: {request_schema}\nResponse schema: {response_schema}"

@tool
def implement_frontend_component(name: str, props: str, description: str) -> str:
    """Implement a frontend component with the given name, props, and description."""
    return f"Created component: {name}\nProps: {props}\nDescription: {description}"

@tool
def check_api_compatibility(endpoint: str, frontend_component: str) -> str:
    """Check if a frontend component is compatible with a backend API endpoint."""
    return f"Compatibility check between {endpoint} and {frontend_component}: Compatible"

# Create our specialized engineers
def create_dev_swarm(model_name="gpt-4o", temperature=0):
    model = ChatOpenAI(model=model_name, temperature=temperature)
    
    # Backend engineer
    backend_engineer = create_react_agent(
        model,
        [
            create_backend_api,
            check_api_compatibility,
            create_handoff_tool(
                agent_name="FrontendEngineer",
                description="Hand off to the frontend engineer for UI implementation"
            )
        ],
        prompt="""You are an expert backend software engineer. 
        You specialize in designing and implementing APIs, database models, and server-side logic.
        When asked about frontend concerns, consider handing off to the frontend engineer.
        Always think step-by-step about the backend architecture before implementing.""",
        name="BackendEngineer",
    )
    
    # Frontend engineer
    frontend_engineer = create_react_agent(
        model,
        [
            implement_frontend_component,
            check_api_compatibility,
            create_handoff_tool(
                agent_name="BackendEngineer",
                description="Hand off to the backend engineer for API implementation"
            )
        ],
        prompt="""You are an expert frontend software engineer.
        You specialize in creating UI components, managing state, and connecting to backend APIs.
        When asked about backend concerns, consider handing off to the backend engineer.
        Always think about usability and user experience before implementing components.""",
        name="FrontendEngineer",
    )
    
    # Create swarm
    checkpointer = InMemorySaver()
    workflow = create_swarm(
        [backend_engineer, frontend_engineer],
        default_active_agent="BackendEngineer"
    )
    app = workflow.compile(checkpointer=checkpointer)
    
    return app, checkpointer

# Usage example
def run_dev_swarm(question: str, thread_id: str = "1"):
    app, checkpointer = create_dev_swarm()
    config = {"configurable": {"thread_id": thread_id}}
    
    response = app.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config,
    )
    return response

def main():
    # Example usage
    print("Development Swarm Initialized")
    print("-" * 50)
    
    # Test with a backend-focused question
    response1 = run_dev_swarm("We need an API endpoint for user authentication. Can you implement it?")
    print("Response to backend question:")
    print(response1)
    print("-" * 50)
    
    # Test with a frontend-focused question (continuing the conversation)
    response2 = run_dev_swarm("Now create a login form that uses this API.", thread_id="1")
    print("Response to frontend question:")
    print(response2)
    print("-" * 50)
    
    # Test with a full-stack question
    response3 = run_dev_swarm("We need a complete user profile page with edit functionality. How would we implement this?", thread_id="2")
    print("Response to full-stack question:")
    print(response3)

if __name__ == "__main__":
    main()