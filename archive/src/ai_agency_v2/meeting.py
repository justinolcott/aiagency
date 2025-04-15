from typing import List, Dict, Any, TypedDict
from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.messages import BaseMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel

class Agent(BaseModel):
    """Agent participating in the meeting."""
    name: str
    model: Any  # This would typically be a LangChain model or similar
    system_message: str

class MeetingState(TypedDict):
    """State for the meeting."""
    agents: List[Agent]
    description: str
    messages: List[Dict[str, Any]]  # Full conversation history
    current_agent_idx: int
    meeting_complete: bool
    
def create_meeting_node():
    """Create a meeting node for a LangGraph."""
    
    def initialize_meeting(_, description: str, agents: List[Agent]) -> MeetingState:
        """Initialize a new meeting with the given description and agents."""
        messages = []
        # Add initial meeting description as a human message
        meeting_intro = (
            f"Meeting Goal: {description}\n\n"
            "This is a conversation between multiple agents. "
            "When it's your turn, you can respond or type 'PASS' to skip your turn, "
            "or 'MEETING END' when the discussion is complete."
        )
        messages.append({"role": "human", "content": meeting_intro, "from": "Facilitator"})
        
        return {
            "agents": agents,
            "description": description,
            "messages": messages,
            "current_agent_idx": 0,
            "meeting_complete": False
        }
    
    def format_messages_for_agent(state: MeetingState, agent_idx: int) -> List[BaseMessage]:
        """Format messages for the current agent."""
        agent = state["agents"][agent_idx]
        
        # Start with the agent's system message
        formatted_messages = [SystemMessage(content=agent.system_message)]
        
        # Add the meeting description and conversation history
        for msg in state["messages"]:
            if msg["role"] == "human":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                # Format AI messages with the agent name as prefix
                sender = msg.get("from", "Unknown Agent")
                content = f"{sender}: {msg['content']}"
                formatted_messages.append(HumanMessage(content=content))
        
        # Add a message to indicate it's this agent's turn
        formatted_messages.append(HumanMessage(content=f"It's your turn, {agent.name}. Please provide your next contribution to the conversation."))
        
        return formatted_messages
    
    def agent_turn(state: MeetingState) -> MeetingState:
        """Process the current agent's turn."""
        current_idx = state["current_agent_idx"]
        agent = state["agents"][current_idx]
        
        # Format messages for this agent
        messages = format_messages_for_agent(state, current_idx)
        
        # Get response from the agent
        response = agent.model.invoke(messages)
        response_content = response.content
        
        # Add the agent's response to the conversation history
        new_message = {
            "role": "ai", 
            "content": response_content, 
            "from": agent.name
        }
        
        updated_messages = state["messages"] + [new_message]
        
        # Check if meeting should end
        meeting_complete = "MEETING END" in response_content or all(
            "PASS" in msg["content"] for msg in updated_messages[-len(state["agents"]):] 
            if msg["role"] == "ai"
        )
        
        # Move to the next agent
        next_idx = (current_idx + 1) % len(state["agents"])
        
        return {
            **state,
            "messages": updated_messages,
            "current_agent_idx": next_idx,
            "meeting_complete": meeting_complete
        }
    
    def should_continue(state: MeetingState) -> str:
        """Determine if the meeting should continue or end."""
        if state["meeting_complete"]:
            return END
        else:
            return "agent_turn"
    # Create the graph
    workflow = StateGraph(MeetingState)
    workflow.add_node("agent_turn", agent_turn)
    workflow.set_entry_point("agent_turn")
    workflow.add_conditional_edges("agent_turn", should_continue)
    graph = workflow.compile()
    
    # Return a function that creates and runs a meeting
    def run_meeting(description: str, agents: List[Agent]) -> List[Dict[str, Any]]:
        """Run a meeting with the given description and agents."""
        initial_state = initialize_meeting({
            "agents": [],
            "description": "",
            "messages": [],
            "current_agent_idx": 0,
            "meeting_complete": False
        }, description, agents)
        
        result = graph.invoke(initial_state)
        return result["messages"]
    
    return run_meeting


# Example of how to use this
if __name__ == "__main__":
    from model import LoggingChatDeepSeek
    
    # Create the meeting tool
    meeting = create_meeting_node()
    
    # Create agents
    agent1 = Agent(
        name="Frontend Engineer",
        model=LoggingChatDeepSeek(model="deepseek-chat"),
        system_message=(
            "You are a frontend engineer specializing in React/TypeScript development. "
            "You're discussing the API requirements for a new todo app with a backend engineer. "
            "Focus on the data you need from the API to implement features like creating, "
            "updating, listing, and deleting todos, user authentication, and any other "
            "frontend requirements. Be specific about the shape of the data you expect."
        )
    )
    
    agent2 = Agent(
        name="Backend Engineer",
        model=LoggingChatDeepSeek(model="deepseek-chat"),
        system_message=(
            "You are a backend engineer specializing in API development with Node.js and Express. "
            "You're discussing the API design for a new todo app with a frontend engineer. "
            "Focus on defining clear API endpoints, request/response formats, authentication methods, "
            "and database schema considerations. Ensure the API is RESTful and follows best practices."
        )
    )
    
    # Run the meeting for just one turn to demonstrate the process
    initial_state = {
        "agents": [agent1, agent2],
        "description": "Design the API for a new todo app",
        "messages": [{"role": "human", "content": "Meeting Goal: Design the API for a new todo app\n\nThis is a conversation between multiple agents. When it's your turn, you can respond or type 'PASS' to skip your turn, or 'MEETING END' when the discussion is complete.", "from": "Facilitator"}],
        "current_agent_idx": 0,
        "meeting_complete": False
    }
    
    # Get the workflow
    workflow = StateGraph(MeetingState)
    # Define agent_turn function directly
    def agent_turn(state: MeetingState) -> MeetingState:
        """Process the current agent's turn."""
        current_idx = state["current_agent_idx"]
        agent = state["agents"][current_idx]
        
        # Format messages for this agent
        formatted_messages = [SystemMessage(content=agent.system_message)]
        
        # Add the meeting description and conversation history
        for msg in state["messages"]:
            if msg["role"] == "human":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                # Format AI messages with the agent name as prefix
                sender = msg.get("from", "Unknown Agent")
                content = f"{sender}: {msg['content']}"
                formatted_messages.append(HumanMessage(content=content))
        
        # Add a message to indicate it's this agent's turn
        formatted_messages.append(HumanMessage(content=f"It's your turn, {agent.name}. Please provide your next contribution to the conversation."))
        
        # Get response from the agent
        response = agent.model.invoke(formatted_messages)
        response_content = response.content
        
        # Add the agent's response to the conversation history
        new_message = {
            "role": "ai", 
            "content": response_content, 
            "from": agent.name
        }
        
        updated_messages = state["messages"] + [new_message]
        
        # Check if meeting should end
        meeting_complete = "MEETING END" in response_content or all(
            "PASS" in msg["content"] for msg in updated_messages[-len(state["agents"]):] 
            if msg["role"] == "ai"
        )
        
        # Move to the next agent
        next_idx = (current_idx + 1) % len(state["agents"])
        
        return {
            **state,
            "messages": updated_messages,
            "current_agent_idx": next_idx,
            "meeting_complete": meeting_complete
        }
        
    workflow.add_node("agent_turn", agent_turn)
    workflow.set_entry_point("agent_turn")
    workflow.add_conditional_edges(
        "agent_turn", 
        lambda state: END if state["meeting_complete"] else "agent_turn"
    )
    graph = workflow.compile()
    
    # Process one turn
    result = graph.invoke(initial_state)
    
    # Print just the latest message
    latest_msg = result["messages"][-1]
    print(f"{latest_msg['from']}: {latest_msg['content']}")
