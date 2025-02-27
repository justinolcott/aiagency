from meeting import create_meeting_node, Agent
from model import LoggingChatDeepSeek

def run_example_meeting():
    """Run an example meeting between multiple AI agents."""
    
    # Create the meeting node
    meeting = create_meeting_node()
    
    # Create agents with different roles
    agents = [
        Agent(
            name="Product Manager",
            model=LoggingChatDeepSeek(model="deepseek-chat"),
            system_message="You are a product manager focused on user needs and business value. Be concise."
        ),
        Agent(
            name="Engineer",
            model=LoggingChatDeepSeek(model="deepseek-chat"),
            system_message="You are a software engineer focused on technical feasibility and implementation details. Be concise."
        ),
        Agent(
            name="UX Designer",
            model=LoggingChatDeepSeek(model="deepseek-chat"),
            system_message="You are a UX designer focused on user experience and interface design. Be concise."
        )
    ]
    
    # Define the meeting description
    description = "Brainstorm ideas for a new mobile app that helps users track their carbon footprint"
    
    # Run the meeting
    result = meeting(description=description, agents=agents)
    
    # Print the meeting transcript
    print("\n=== MEETING TRANSCRIPT ===\n")
    for msg in result:
        if msg["role"] == "human":
            print(f"Facilitator: {msg['content']}")
            print("-" * 50)
        else:
            print(f"{msg['from']}: {msg['content']}")
            print("-" * 50)

if __name__ == "__main__":
    run_example_meeting()
