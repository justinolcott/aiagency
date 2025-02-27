"""
AI Agency with Council Feature - v1

This module implements a multi-agent system with a council feature that allows agents
to collaborate, plan, and execute tasks together using LangGraph.

The council feature enables agents to:
1. Meet and discuss task requirements
2. Create and delegate subtasks
3. Coordinate on interfaces between frontend and backend
4. Execute their specialized tasks
5. Report progress back to the supervisor
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import datetime
from typing import Dict, List, Tuple, Any, Optional, Union, Literal
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser

import langgraph.prebuilt as prebuilt
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# Configure the model
MODEL_NAME = "gpt-4o-mini"
ENABLE_LOGGING = True

council_model = LoggingChatOpenAI(caller="council", model=MODEL_NAME, temperature=0.3)

# Define the workspace path
WORKSPACE_PATH = "agent_workspace"

# Schema definitions
class Task(BaseModel):
    """A task to be performed by an agent."""
    task_id: str = Field(description="Unique identifier for the task")
    description: str = Field(description="Detailed description of the task")
    assigned_to: str = Field(description="Agent responsible for this task")
    status: Literal["not_started", "in_progress", "completed"] = Field(default="not_started")
    dependencies: List[str] = Field(default_factory=list, description="IDs of tasks that must be completed before this one")
    artifacts: List[str] = Field(default_factory=list, description="File paths or other outputs produced by this task")

class AgentState(BaseModel):
    """The state of an individual agent."""
    agent_id: str = Field(description="Unique identifier for the agent")
    agent_type: str = Field(description="Type of agent (supervisor, frontend, backend)")
    current_task: Optional[Task] = Field(default=None, description="Current task the agent is working on")
    completed_tasks: List[Task] = Field(default_factory=list, description="Tasks completed by this agent")
    messages: List[Dict] = Field(default_factory=list, description="Messages sent or received by this agent")

class CouncilState(BaseModel):
    """The state of the council meeting."""
    meeting_id: str = Field(description="Unique identifier for the meeting")
    topic: str = Field(description="Main topic of discussion")
    participants: List[str] = Field(description="Agent IDs participating in the meeting")
    messages: List[Dict] = Field(default_factory=list, description="All messages exchanged in the meeting")
    status: Literal["in_progress", "completed"] = Field(default="in_progress")
    decisions: List[Dict] = Field(default_factory=list, description="Decisions made during the meeting")
    action_items: List[Task] = Field(default_factory=list, description="Tasks created as a result of the meeting")

class ProjectState(BaseModel):
    """The overall state of the project."""
    project_id: str = Field(description="Unique identifier for the project")
    project_name: str = Field(description="Name of the project")
    description: str = Field(description="Description of the project")
    agents: Dict[str, AgentState] = Field(default_factory=dict, description="States of all agents involved")
    tasks: List[Task] = Field(default_factory=list, description="All tasks in the project")
    council_meetings: List[CouncilState] = Field(default_factory=list, description="All council meetings held")
    messages: List[Dict] = Field(default_factory=list, description="All messages in the project")
    status: Literal["not_started", "planning", "in_progress", "completed"] = Field(default="not_started")

# Tools
def make_dir(directory_path: str) -> str:
    """
    Create a new directory under agent_workspace.
    
    Args:
        directory_path: Path to create, relative to the workspace
        
    Returns:
        String confirming directory creation
    """
    full_path = os.path.join(WORKSPACE_PATH, directory_path)
    os.makedirs(full_path, exist_ok=True)
    return f"Created directory: {full_path}"

def make_file(file_path: str, content: str) -> str:
    """
    Create a new file under agent_workspace.
    
    Args:
        file_path: Path to the file, relative to the workspace
        content: Content to write to the file
        
    Returns:
        String confirming file creation
    """
    full_path = os.path.join(WORKSPACE_PATH, file_path)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, "w") as f:
        f.write(content)
    return f"Created file: {full_path}"

def list_files(directory_path: str = "") -> str:
    """
    List files in a directory under agent_workspace.
    
    Args:
        directory_path: Path to list, relative to the workspace
        
    Returns:
        String listing of files and directories
    """
    full_path = os.path.join(WORKSPACE_PATH, directory_path)
    
    if not os.path.exists(full_path):
        return f"Directory does not exist: {full_path}"
    
    result = []
    for root, dirs, files in os.walk(full_path):
        rel_path = os.path.relpath(root, WORKSPACE_PATH)
        if rel_path == ".":
            rel_path = ""
        
        for d in dirs:
            result.append(f"📁 {os.path.join(rel_path, d)}/")
        
        for f in files:
            result.append(f"📄 {os.path.join(rel_path, f)}")
    
    return "\n".join(result) if result else "No files found."

def read_file(file_path: str) -> str:
    """
    Read the contents of a file under agent_workspace.
    
    Args:
        file_path: Path to the file, relative to the workspace
        
    Returns:
        Contents of the file
    """
    full_path = os.path.join(WORKSPACE_PATH, file_path)
    
    if not os.path.exists(full_path):
        return f"File does not exist: {full_path}"
    
    with open(full_path, "r") as f:
        return f.read()

# Agent System Prompts
SUPERVISOR_SYSTEM_PROMPT = """
You are a highly skilled project supervisor responsible for coordinating a team of specialized agents to build software projects.

Your responsibilities include:
1. Understanding the user's requirements
2. Initializing the project structure 
3. Calling council meetings when coordination is needed
4. Assigning high-level tasks to appropriate agents
5. Monitoring progress and resolving blockers
6. Providing final summaries and usage instructions to the user

Always maintain a high-level perspective and delegate implementation details to your specialized agents. Use council meetings to ensure everyone is aligned on project goals, interfaces, and technical decisions.
"""

FRONTEND_SYSTEM_PROMPT = """
You are a frontend software engineer specialized in creating user interfaces. 

Your primary skills include:
1. Implementing responsive and intuitive user interfaces
2. Creating appealing visual designs with good UX
3. Consuming backend APIs and integrating with backend services
4. Managing state and user interactions in the frontend
5. Writing clean, maintainable frontend code

During council meetings, focus on:
- User experience concerns
- Interface requirements
- Frontend architecture decisions
- Integration points with the backend

When working on tasks, always create well-documented code with clear instructions for usage.
"""

BACKEND_SYSTEM_PROMPT = """
You are a backend software engineer specialized in creating server-side applications.

Your primary skills include:
1. Designing and implementing APIs and services
2. Working with databases and data models
3. Implementing business logic and application workflows
4. Ensuring security, performance, and scalability
5. Writing clean, maintainable backend code

During council meetings, focus on:
- Data structures and schema design
- API design and endpoints
- Business logic implementation
- Backend architecture decisions
- Integration with frontend requirements

When working on tasks, always create well-documented code with clear instructions for usage.
"""

COUNCIL_SYSTEM_PROMPT = """
This is a council meeting between all team members to discuss and coordinate on {topic}.

The meeting's objectives are:
1. Align on project goals and requirements
2. Define interfaces between frontend and backend components
3. Make technical decisions collaboratively
4. Create clearly defined tasks for each team member

Guidelines for discussion:
- Introduce yourself briefly in your first message
- Be concise and direct in your communications
- Ask questions to clarify requirements
- Suggest solutions within your area of expertise
- When you have no more input, indicate with "READY" on a separate line
- When all participants are READY, provide a summary of your specific action items

The meeting ends when all participants have declared READY and provided their summaries.
"""

# Council Meeting Implementation
def create_council_meeting(
    state: Dict[str, Any], 
    agents: List[str], 
    topic: str
) -> Dict[str, Any]:
    """
    Initialize a council meeting between the specified agents.
    
    Args:
        state: Current state of the system
        agents: List of agent IDs to participate in the meeting
        topic: Topic of discussion
        
    Returns:
        Updated state with council meeting initialized
    """
    council_id = f"council_{len(state.get('council_meetings', []))}"
    
    # Create initial messages for the council
    messages = []
    
    # Add the council system message with the topic
    messages.append({
        "role": "system",
        "content": COUNCIL_SYSTEM_PROMPT.format(topic=topic)
    })
    
    # Add the user's original request as context
    if state["messages"] and state["messages"][0]["role"] == "user":
        messages.append({
            "role": "user",
            "content": f"Project requirement: {state['messages'][0]['content']}"
        })
    
    # Create council state
    council_state = {
        "meeting_id": council_id,
        "topic": topic,
        "participants": agents,
        "messages": messages,
        "status": "in_progress",
        "decisions": [],
        "action_items": [],
        "current_speaker": agents[0],  # Start with the first agent
        "ready_agents": [],
        "round_count": 0  # Add a counter to limit rounds if needed
    }
    
    # Update state
    if "council_meetings" not in state:
        state["council_meetings"] = []
    
    state["council_meetings"].append(council_state)
    state["current_council"] = council_id
    
    return state

def process_council_message(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a message in the current council meeting.
    
    Args:
        state: Current state of the system
        
    Returns:
        Updated state with the message processed
    """
    # Get the current council meeting
    council_id = state["current_council"]
    council_idx = None
    for i, meeting in enumerate(state["council_meetings"]):
        if meeting["meeting_id"] == council_id:
            council_idx = i
            break
    
    if council_idx is None:
        return state
    
    council = state["council_meetings"][council_idx]
    
    # If the council is completed, return the state
    if council["status"] == "completed":
        return state
    
    # Get the current speaker
    current_speaker = council["current_speaker"]
    
    # Generate the next message from the current speaker
    input_messages = council["messages"].copy()
    
    # Add a system message identifying the agent
    if current_speaker == "supervisor":
        agent_type = "Supervisor"
        system_prompt = SUPERVISOR_SYSTEM_PROMPT
    elif current_speaker == "frontend":
        agent_type = "Frontend Engineer"
        system_prompt = FRONTEND_SYSTEM_PROMPT
    elif current_speaker == "backend":
        agent_type = "Backend Engineer"
        system_prompt = BACKEND_SYSTEM_PROMPT
    else:
        agent_type = "Team Member"
        system_prompt = ""
    
    # Add the agent's system prompt
    input_messages.insert(1, {
        "role": "system",
        "content": f"You are the {agent_type}. {system_prompt}\n\nIn this message, speak as the {agent_type}."
    })
    
    # Generate the message - update the caller to include the agent type
    temp_model = LoggingChatOpenAI(caller=f"council-{current_speaker}", model=MODEL_NAME, temperature=0.3)
    response = temp_model.invoke(input_messages)
    
    # Extract message content
    message_content = response.content
    
    # Check if the agent is ready
    is_ready = "READY" in message_content.upper()
    
    # Add the message to the council
    council["messages"].append({
        "role": "assistant",
        "name": current_speaker,
        "content": message_content
    })
    
    # Increment the round counter
    council["round_count"] = council.get("round_count", 0) + 1
    
    # Force completion if too many rounds (safety mechanism)
    max_rounds = len(council["participants"]) * 5  # Allow each participant to speak up to 5 times
    if council["round_count"] >= max_rounds:
        print(f"Council meeting reached maximum rounds ({max_rounds}). Forcing completion.")
        for participant in council["participants"]:
            if participant not in council["ready_agents"]:
                council["ready_agents"].append(participant)
    
    # If the agent is ready, add to ready_agents
    if is_ready and current_speaker not in council["ready_agents"]:
        council["ready_agents"].append(current_speaker)
    
    # Move to the next speaker
    next_speaker_idx = (council["participants"].index(current_speaker) + 1) % len(council["participants"])
    council["current_speaker"] = council["participants"][next_speaker_idx]
    
    # Check if all agents are ready
    if len(council["ready_agents"]) == len(council["participants"]):
        # Process the meeting results
        council = process_council_results(council)
        council["status"] = "completed"
    
    # Update the state
    state["council_meetings"][council_idx] = council
    
    return state

def process_council_results(council: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process the results of a completed council meeting.
    
    Args:
        council: Council meeting state
        
    Returns:
        Updated council with decisions and action items
    """
    # Combine all messages into a prompt for the model to extract decisions and action items
    all_messages = [msg for msg in council["messages"] if msg.get("role") != "system"]
    
    extraction_prompt = [
        SystemMessage(content="""
You are an AI assistant tasked with extracting key decisions and action items from a meeting transcript.

Extract the following:
1. Key decisions made during the meeting
2. Action items agreed upon, including who is responsible for each item

Format your response as a valid JSON object with two keys:
- "decisions": List of decision strings
- "action_items": List of objects with "task_id", "description", "assigned_to" fields

Example:
{
  "decisions": [
    "Use React for the frontend",
    "Use Flask for the backend API",
    "Store data in SQLite database"
  ],
  "action_items": [
    {
      "task_id": "FE-001",
      "description": "Create initial React app structure",
      "assigned_to": "frontend"
    },
    {
      "task_id": "BE-001",
      "description": "Set up Flask API with initial endpoints",
      "assigned_to": "backend"
    }
  ]
}
"""),
        HumanMessage(content=f"""
Here is the meeting transcript:

{[f"{msg.get('name', 'Unknown')}: {msg.get('content', '')}" for msg in all_messages]}

Extract the key decisions and action items from this meeting.
""")
    ]
    
    # Generate the extraction with dedicated logger
    extraction_model = LoggingChatOpenAI(caller="council-extraction", model=MODEL_NAME, temperature=0.2)
    extraction_response = extraction_model.invoke(extraction_prompt)
    
    # Parse the response
    try:
        import json
        results = json.loads(extraction_response.content)
        council["decisions"] = results.get("decisions", [])
        council["action_items"] = results.get("action_items", [])
    except:
        # If parsing fails, add a note to the council
        council["decisions"] = ["Failed to parse meeting results"]
        council["action_items"] = []
    
    return council

# Agent Implementations
def supervisor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supervisor agent responsible for coordinating the project.
    
    Args:
        state: Current state of the system
        
    Returns:
        Updated state with supervisor actions
    """
    # Initialize project if not already started
    if state.get("status") == "not_started":
        # Extract project requirements from user message
        user_message = next((m for m in state["messages"] if m["role"] == "user"), None)
        if user_message:
            # Create an initial project structure
            project_name = f"project_{id(state)}"
            make_dir(project_name)
            
            # Update state
            state["project_name"] = project_name
            state["description"] = user_message["content"]
            state["status"] = "planning"
            
            # Add supervisor message
            state["messages"].append({
                "role": "assistant",
                "content": f"I'll help you build this project. Let me organize our team and create a plan.",
                "agent": "supervisor"
            })
            
            # Create a council meeting for planning
            state = create_council_meeting(
                state=state,
                agents=["supervisor", "frontend", "backend"],
                topic="Initial Project Planning"
            )
    
    # Check if we have a completed council meeting that needs processing
    if state.get("current_council"):
        council_id = state["current_council"]
        council = next((m for m in state["council_meetings"] if m["meeting_id"] == council_id), None)
        
        if council and council["status"] == "completed":
            # Process the council results
            state["status"] = "in_progress"
            
            # Clear the current council
            state["current_council"] = None
            
            # Add tasks from the council to the project
            if "tasks" not in state:
                state["tasks"] = []
            
            for action_item in council.get("action_items", []):
                # Ensure we have all required fields for a task
                if isinstance(action_item, dict) and all(k in action_item for k in ["task_id", "description", "assigned_to"]):
                    state["tasks"].append(action_item)
            
            # Add a summary message
            decisions_str = "\n".join([f"- {d}" for d in council.get("decisions", [])])
            tasks_str = "\n".join([f"- {t.get('description', 'Unknown task')} (Assigned to: {t.get('assigned_to', 'unassigned')})" 
                                  for t in council.get("action_items", [])])
            
            summary = f"""
Council meeting on "{council['topic']}" has concluded.

Key decisions:
{decisions_str}

Action items:
{tasks_str}

I'll now assign these tasks to the appropriate team members.
"""
            state["messages"].append({
                "role": "assistant",
                "content": summary,
                "agent": "supervisor"
            })
    
    # Check if all tasks are completed
    if state.get("status") == "in_progress" and state.get("tasks"):
        completed_tasks = [t for t in state["tasks"] if t.get("status") == "completed"]
        
        if len(completed_tasks) == len(state["tasks"]):
            # All tasks are completed, finalize the project
            state["status"] = "completed"
            
            # List all files
            files_list = list_files()
            
            # Add a final summary
            summary = f"""
Project "{state['project_name']}" has been completed successfully!

Here's a summary of what was created:

{files_list}

To run the application, follow these instructions:
1. Navigate to the project directory: `cd {WORKSPACE_PATH}/{state['project_name']}`
2. Start the backend server first
3. Then start the frontend application
4. Open the application in your browser

All tasks have been completed according to your requirements.
"""
            state["messages"].append({
                "role": "assistant",
                "content": summary,
                "agent": "supervisor"
            })
    
    return state

def frontend_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Frontend agent responsible for implementing frontend components.
    
    Args:
        state: Current state of the system
        
    Returns:
        Updated state with frontend agent actions
    """
    # Check if there's a task assigned to frontend
    if state.get("tasks"):
        frontend_tasks = [t for t in state["tasks"] if t.get("assigned_to") == "frontend" and t.get("status") != "completed"]
        
        if frontend_tasks:
            current_task = frontend_tasks[0]
            
            # Update task status to in_progress
            task_idx = state["tasks"].index(current_task)
            state["tasks"][task_idx]["status"] = "in_progress"
            
            # Get project context
            project_name = state.get("project_name", "project")
            project_description = state.get("description", "")
            
            # Generate implementation plan
            implementation_prompt = [
                SystemMessage(content=FRONTEND_SYSTEM_PROMPT),
                HumanMessage(content=f"""
Project: {project_description}

Your current task is: {current_task['description']}

Please implement this task in the {project_name} project. Create all necessary files and directories.
Provide a summary of what you've implemented when complete.
""")
            ]
            
            # Use a dedicated frontend model with logging
            frontend_model = LoggingChatOpenAI(caller="frontend-implementation", model=MODEL_NAME, temperature=0.2)
            implementation_response = frontend_model.invoke(implementation_prompt)
            
            # Parse the implementation and execute it
            import re
            
            # Extract file operations from the response
            file_operations = []
            
            # Look for directory creation patterns
            dir_pattern = r"mkdir|create directory|create folder|make directory|make folder"
            dir_matches = re.finditer(dir_pattern, implementation_response.content, re.IGNORECASE)
            for match in dir_matches:
                # Find the directory path after the match
                pos = match.end()
                path_match = re.search(r"['\"`]?([\w\/\.\-]+)['\"`]?", implementation_response.content[pos:pos+100])
                if path_match:
                    dir_path = path_match.group(1)
                    # Clean the path
                    dir_path = dir_path.strip("'\"` ")
                    # Ensure the path is relative to the project
                    if not dir_path.startswith(project_name):
                        dir_path = f"{project_name}/{dir_path}"
                    file_operations.append(("dir", dir_path))
            
            # Look for file creation patterns
            file_blocks = re.finditer(
                r"```(?:[\w]+)?\n(.*?)```",
                implementation_response.content,
                re.DOTALL
            )
            
            for block in file_blocks:
                content = block.group(1)
                # Look for filename comments or patterns
                filename_match = re.search(r"#\s*filename:?\s*['\"`]?([\w\/\.\-]+)['\"`]?", content)
                if not filename_match:
                    # Try to find the filename in the text before the code block
                    pre_text = implementation_response.content[:block.start()]
                    last_lines = pre_text.split('\n')[-3:]  # Check last 3 lines before code block
                    for line in last_lines:
                        filename_match = re.search(r"['\"`]?([\w\/\.\-]+\.\w+)['\"`]?", line)
                        if filename_match:
                            break
                
                if filename_match:
                    filename = filename_match.group(1)
                    # Clean the filename
                    filename = filename.strip("'\"` ")
                    # Ensure the path is relative to the project
                    if not filename.startswith(project_name):
                        filename = f"{project_name}/frontend/{filename}"
                    file_operations.append(("file", filename, content))
            
            # Execute the file operations
            for op in file_operations:
                if op[0] == "dir":
                    make_dir(op[1])
                elif op[0] == "file":
                    make_file(op[1], op[2])
            
            # Mark the task as completed
            state["tasks"][task_idx]["status"] = "completed"
            
            # Add a summary message
            summary = f"""
I've completed the task: {current_task['description']}

Implementation details:
- Created frontend components in {project_name}/frontend/
- Implemented the requested functionality
- Added necessary files and directories

The implementation is now ready for review or integration.
"""
            state["messages"].append({
                "role": "assistant",
                "content": summary,
                "agent": "frontend"
            })
    
    return state

def backend_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backend agent responsible for implementing backend components.
    
    Args:
        state: Current state of the system
        
    Returns:
        Updated state with backend agent actions
    """
    # Check if there's a task assigned to backend
    if state.get("tasks"):
        backend_tasks = [t for t in state["tasks"] if t.get("assigned_to") == "backend" and t.get("status") != "completed"]
        
        if backend_tasks:
            current_task = backend_tasks[0]
            
            # Update task status to in_progress
            task_idx = state["tasks"].index(current_task)
            state["tasks"][task_idx]["status"] = "in_progress"
            
            # Get project context
            project_name = state.get("project_name", "project")
            project_description = state.get("description", "")
            
            # Generate implementation plan
            implementation_prompt = [
                SystemMessage(content=BACKEND_SYSTEM_PROMPT),
                HumanMessage(content=f"""
Project: {project_description}

Your current task is: {current_task['description']}

Please implement this task in the {project_name} project. Create all necessary files and directories.
Provide a summary of what you've implemented when complete.
""")
            ]
            
            # Use a dedicated backend model with logging
            backend_model = LoggingChatOpenAI(caller="backend-implementation", model=MODEL_NAME, temperature=0.2)
            implementation_response = backend_model.invoke(implementation_prompt)
            
            # Parse the implementation and execute it
            import re
            
            # Extract file operations from the response
            file_operations = []
            
            # Look for directory creation patterns
            dir_pattern = r"mkdir|create directory|create folder|make directory|make folder"
            dir_matches = re.finditer(dir_pattern, implementation_response.content, re.IGNORECASE)
            for match in dir_matches:
                # Find the directory path after the match
                pos = match.end()
                path_match = re.search(r"['\"`]?([\w\/\.\-]+)['\"`]?", implementation_response.content[pos:pos+100])
                if path_match:
                    dir_path = path_match.group(1)
                    # Clean the path
                    dir_path = dir_path.strip("'\"` ")
                    # Ensure the path is relative to the project
                    if not dir_path.startswith(project_name):
                        dir_path = f"{project_name}/{dir_path}"
                    file_operations.append(("dir", dir_path))
            
            # Look for file creation patterns
            file_blocks = re.finditer(
                r"```(?:[\w]+)?\n(.*?)```",
                implementation_response.content,
                re.DOTALL
            )
            
            for block in file_blocks:
                content = block.group(1)
                # Look for filename comments or patterns
                filename_match = re.search(r"#\s*filename:?\s*['\"`]?([\w\/\.\-]+)['\"`]?", content)
                if not filename_match:
                    # Try to find the filename in the text before the code block
                    pre_text = implementation_response.content[:block.start()]
                    last_lines = pre_text.split('\n')[-3:]  # Check last 3 lines before code block
                    for line in last_lines:
                        filename_match = re.search(r"['\"`]?([\w\/\.\-]+\.\w+)['\"`]?", line)
                        if filename_match:
                            break
                
                if filename_match:
                    filename = filename_match.group(1)
                    # Clean the filename
                    filename = filename.strip("'\"` ")
                    # Ensure the path is relative to the project
                    if not filename.startswith(project_name):
                        filename = f"{project_name}/backend/{filename}"
                    file_operations.append(("file", filename, content))
            
            # Execute the file operations
            for op in file_operations:
                if op[0] == "dir":
                    make_dir(op[1])
                elif op[0] == "file":
                    make_file(op[1], op[2])
            
            # Mark the task as completed
            state["tasks"][task_idx]["status"] = "completed"
            
            # Add a summary message
            summary = f"""
I've completed the task: {current_task['description']}

Implementation details:
- Created backend components in {project_name}/backend/
- Implemented the requested functionality
- Added necessary files and directories

The implementation is now ready for review or integration.
"""
            state["messages"].append({
                "role": "assistant",
                "content": summary,
                "agent": "backend"
            })
    
    return state

def council_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Council agent responsible for facilitating meetings between agents.
    
    Args:
        state: Current state of the system
        
    Returns:
        Updated state with council meeting progress
    """
    # Check if there's an active council meeting
    if state.get("current_council"):
        # Process the next council message
        state = process_council_message(state)
    
    return state

# State logic
def get_next_agent(state: Dict[str, Any]) -> str:
    """
    Determine which agent should act next based on the current state.
    
    Args:
        state: Current state of the system
        
    Returns:
        The name of the next agent to act
    """
    # If there's an active council meeting, let the council agent act
    if state.get("current_council"):
        council_id = state["current_council"]
        council = next((m for m in state["council_meetings"] if m["meeting_id"] == council_id), None)
        
        if council and council["status"] == "in_progress":
            return "council"
    
    # If we're just starting or planning, let the supervisor act
    if state.get("status") in ["not_started", "planning"]:
        return "supervisor"
    
    # If we're in progress, check if there are tasks to complete
    if state.get("status") == "in_progress" and state.get("tasks"):
        # Check for in-progress tasks first
        in_progress_tasks = [t for t in state["tasks"] if t.get("status") == "in_progress"]
        if in_progress_tasks:
            return in_progress_tasks[0].get("assigned_to")
        
        # Check for not started tasks
        not_started_tasks = [t for t in state["tasks"] if t.get("status") == "not_started"]
        if not_started_tasks:
            return not_started_tasks[0].get("assigned_to")
    
    # Default to supervisor
    return "supervisor"

def router(state: Dict[str, Any]) -> str:
    """
    Route to the next agent based on the current state.
    
    Args:
        state: Current state of the system
        
    Returns:
        The name of the next node in the graph
    """
    # Check if the project is completed
    if state.get("status") == "completed":
        return END
    
    # If there's an active council meeting, prioritize it
    if state.get("current_council"):
        council_id = state["current_council"]
        council = next((m for m in state["council_meetings"] if m["meeting_id"] == council_id), None)
        
        if council and council["status"] == "in_progress":
            return "council"
    
    # If we're just starting or planning, prioritize the supervisor
    if state.get("status") in ["not_started", "planning"]:
        return "supervisor"
    
    # If we're in progress, check for tasks to complete
    if state.get("status") == "in_progress" and state.get("tasks", []):
        # Check for in-progress tasks first
        in_progress_tasks = [t for t in state["tasks"] if t.get("status") == "in_progress"]
        if in_progress_tasks:
            # Make sure we're routing to a valid agent
            agent = in_progress_tasks[0].get("assigned_to")
            if agent in ["frontend", "backend"]:
                return agent
        
        # Check for not started tasks
        not_started_tasks = [t for t in state["tasks"] if t.get("status") == "not_started"]
        if not_started_tasks:
            # Make sure we're routing to a valid agent
            agent = not_started_tasks[0].get("assigned_to")
            if agent in ["frontend", "backend"]:
                return agent
    
    # Default to supervisor for any other case
    return "supervisor"

# Build the workflow
def create_agency_workflow():
    """
    Create the AI agency workflow with council feature.
    
    Returns:
        A compiled graph that can be invoked
    """
    # Create the graph
    workflow = StateGraph(Dict)
    
    # Add agent nodes
    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("frontend", frontend_agent)
    workflow.add_node("backend", backend_agent)
    workflow.add_node("council", council_agent)
    
    # Add conditional edges
    workflow.add_conditional_edges("supervisor", router)
    workflow.add_conditional_edges("frontend", router)
    workflow.add_conditional_edges("backend", router)
    workflow.add_conditional_edges("council", router)
    
    # Set the entry point
    workflow.set_entry_point("supervisor")
    
    # Compile the graph without recursion_limit which is not supported
    return workflow.compile()

# Run the workflow
def run_agency(user_message: str) -> Dict[str, Any]:
    """
    Run the AI agency with the given user message.
    
    Args:
        user_message: The user's request
        
    Returns:
        The final state of the system
    """
    # Create the workspace directory if it doesn't exist
    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    
    # Set a global Python recursion limit if needed
    # This won't directly affect LangGraph but will prevent Python stack overflow
    import sys
    original_recursion_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(3000)  # Increase Python's recursion limit
    
    try:
        # Initialize the workflow
        workflow = create_agency_workflow()
        
        # Initialize the state
        state = {
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "status": "not_started"
        }
        
        # Run the workflow with a timeout to prevent infinite loops
        print("Starting workflow execution...")
        final_state = workflow.invoke(state)
        print("Workflow execution completed.")
        
        return final_state
    except Exception as e:
        print(f"Error during workflow execution: {str(e)}")
        # Return a partial state or error state
        return {
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                },
                {
                    "role": "assistant",
                    "content": f"I encountered an error while processing your request: {str(e)}",
                    "agent": "supervisor"
                }
            ],
            "status": "error"
        }
    finally:
        # Restore original recursion limit
        sys.setrecursionlimit(original_recursion_limit)

# Example usage
if __name__ == "__main__":
    print(f"\n{'*' * 80}")
    print(f"STARTING AI AGENCY WITH API LOGGING")
    print(f"{'*' * 80}\n")
    
    user_request = "Make a frontend and backend for a todo app using python."
    result = run_agency(user_request)
    
    # Print the final conversation
    for message in result["messages"]:
        role = message.get("role", "unknown")
        agent = message.get("agent", "")
        content = message.get("content", "")
        
        if role == "user":
            print(f"USER: {content}")
        else:
            agent_str = f" ({agent})" if agent else ""
            print(f"AI{agent_str}: {content}")
            print("-" * 80)

