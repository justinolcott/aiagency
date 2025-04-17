from __future__ import annotations

import os
import asyncio
import time
import uuid
import yaml
from uuid import uuid4
from pathlib import Path
from typing import Literal, List, Union, Dict, Optional, Any, Protocol



# import os
# import asyncio
# import time
# import uuid
# import yaml
import shutil
import subprocess
# from uuid import uuid4
# from pathlib import Path
# from typing import Literal, List, Union, Dict, Optional, Any, Protocol


from pydantic import BaseModel, Field
from dataclasses import dataclass

from pydantic_ai import RunContext, Agent as PydanticAgent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ModelRequestPart, ModelResponsePart, ToolReturnPart, TextPart, ToolCallPart, RetryPromptPart
from pydantic_ai.messages import SystemPromptPart, UserPromptPart, TextPart
from pydantic_ai.mcp import MCPServerStdio

from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import Tool, ToolDefinition




# MODELS
@dataclass
class AgentDependencies:
    agency: 'Agency'
    agent_id: str
    
    

# MCP SERVERS
class MCPServerBase(Protocol):
    async def __aenter__(self) -> Any:
        ...
    
    async def __aexit__(self, *args) -> None:
        ...
        
        


class PlaywrightMCPServer:
    def __init__(self, id: int):
        self.id = id
        self.profile_dir = Path(f"./tmp/profile_{id}").resolve()
        self._server = MCPServerStdio(
            "npx",
            args=[
                "@playwright/mcp@latest",
                "--headless",
                "--browser=firefox",
                f"--user-data-dir={self.profile_dir}"
            ]
        )

    async def __aenter__(self):
        return await self._server.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        return await self._server.__aexit__(exc_type, exc, tb)

    def get(self) -> MCPServerStdio:
        return self._server

    async def list_tools(self):
        return await self._server.list_tools()

    async def call_tool(self, tool_name, arguments):
        return await self._server.call_tool(tool_name, arguments)

    @property
    def is_running(self):
        return True

class PythonMCPServer:
    """MCP server for executing Python code in a sandboxed environment using Pyodide."""
    def __init__(self, id: int):
        self.id = id
        self._server = MCPServerStdio(
            "deno",
            args=[
                "run",
                "-N",
                "-R=node_modules",
                "-W=node_modules",
                "--node-modules-dir=auto",
                "jsr:@pydantic/mcp-run-python",
                "stdio"
            ]
        )

    async def __aenter__(self):
        return await self._server.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        return await self._server.__aexit__(exc_type, exc, tb)

    def get(self) -> MCPServerStdio:
        return self._server

    async def list_tools(self):
        return await self._server.list_tools()

    async def call_tool(self, tool_name, arguments):
        return await self._server.call_tool(tool_name, arguments)

    @property
    def is_running(self):
        return True


# SERVER MANAGER
class MCPServerManager:
    def __init__(self):
        self.servers: Dict[str, MCPServerBase] = {}
        self._running_servers: Dict[str, bool] = {}
        self._server_tasks: Dict[str, asyncio.Task] = {}

    def add_server(self, server_id: str, server: MCPServerBase):
        self.servers[server_id] = server
        self._running_servers[server_id] = False

    async def start_server(self, server_id: str) -> bool:
        if server_id not in self.servers:
            print(f"Server {server_id} not found")
            return False
            
        if self._running_servers.get(server_id, False):
            # Already running
            return True
        
        # Create task to run the server
        try:
            self._server_tasks[server_id] = asyncio.create_task(self._run_server(server_id))
            # Wait briefly to ensure the server starts
            await asyncio.sleep(1)
            self._running_servers[server_id] = True
            print(f"Started MCP server: {server_id}")
            return True
        except Exception as e:
            print(f"Failed to start server {server_id}: {e}")
            return False

    async def stop_server(self, server_id: str) -> bool:
        if server_id not in self._server_tasks or not self._running_servers.get(server_id, False):
            return False
        
        # Cancel the task and wait for it to complete
        self._server_tasks[server_id].cancel()
        try:
            await self._server_tasks[server_id]
        except asyncio.CancelledError:
            pass
        
        self._running_servers[server_id] = False
        return True

    async def stop_all_servers(self):
        for server_id in list(self._server_tasks.keys()):
            await self.stop_server(server_id)

    async def _run_server(self, server_id: str):
        server = self.servers[server_id]
        try:
            async with server:
                # Keep the server running until cancelled
                while True:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Handle cancellation
            self._running_servers[server_id] = False
            raise
        except Exception as e:
            print(f"Server {server_id} error: {e}")
            self._running_servers[server_id] = False

    def get_server(self, server_id: str) -> Optional[MCPServerBase]:
        return self.servers.get(server_id)

    def is_running(self, server_id: str) -> bool:
        return self._running_servers.get(server_id, False)

    def get_running_servers(self) -> List[str]:
        return [server_id for server_id, running in self._running_servers.items() if running]

    async def wait_for_server_ready(self, server_id: str, timeout: float = 60.0, interval: float = 2.0) -> bool:
        """Wait for the MCP server to be ready by calling list_tools repeatedly."""
        server = self.get_server(server_id)
        if not server:
            print(f"Server {server_id} not found for readiness check")
            return False
        start = time.time()
        last_error = None
        while time.time() - start < timeout:
            try:
                # Try to call list_tools (should succeed if server is ready)
                if hasattr(server, 'list_tools') and callable(getattr(server, 'list_tools')):
                    result = await server.list_tools()
                    # If no exception, consider it ready
                    return True
                else:
                    # If no list_tools, just return True after a short wait
                    await asyncio.sleep(1)
                    return True
            except Exception as e:
                last_error = e
                await asyncio.sleep(interval)
        print(f"Timeout waiting for server {server_id} to be ready: {last_error}")
        return False


# TOOLS
def create_new_agent_helper(agency: 'Agency', name: str, system_prompt: str, parent_id: str) -> str:
    new_agent_id = agency.next_id()
    new_agent = Agent(
        agency,
        name,
        new_agent_id,
        agency.default_provider,
        system_prompt,
        accessible_tools=[], # No tools by default
        mcp_servers=[] # No servers by default
    )
    
    agency.agents[new_agent_id] = new_agent

    if parent_id in agency.agents:
        new_agent.parent = parent_id
        agency.agents[parent_id].children[new_agent_id] = new_agent

    return f"Created agent: {new_agent.name} with ID: {new_agent_id}"
    

def create_new_agent(ctx: RunContext[AgentDependencies], name: str, system_prompt: str) -> str:
    """Create a new agent with the given name and system prompt."""
    agency = ctx.deps.agency
    parent_id = ctx.deps.agent_id
    return create_new_agent_helper(agency, name, system_prompt, parent_id)

async def prepare_create_new_agent_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    current_depth = agent.curr_depth()
    current_breadth = agent.curr_breadth()
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    if current_depth >= agent.agency.max_depth:
        print("Max depth reached.")
        return None
    if current_breadth >= agent.agency.max_breadth:
        print("Max breadth reached.")
        return None
    
    print("Preparing tool...")
    print(tool_def.parameters_json_schema)
    
    return tool_def

create_new_agent_tool = Tool(create_new_agent, prepare=prepare_create_new_agent_tool)


async def remove_agent_helper(agency: 'Agency', agent_id: str) -> str:
    if agent_id not in agency.agents:
        return f"Agent with ID {agent_id} does not exist."
    
    # remove from parent
    if agency.agents[agent_id].parent_id is not None:
        parent_agent = agency.agents[agency.agents[agent_id].parent_id]
        del parent_agent.children[agent_id]
        
    # change children's parent
    for child_id in agency.agents[agent_id].children.keys():
        child_agent = agency.agents[child_id]
        child_agent.parent_id = None
        agency.agents[child_id] = child_agent      
    
    # remove from agency
    del agency.agents[agent_id]
    
    return f"Removed agent with ID: {agent_id}"

# Message Agent
async def message_agent_helper(agency: 'Agency', agent_id: str, message: str) -> str:
    if agent_id not in agency.agents:
        return f"Agent with ID {agent_id} does not exist."
    
    agent: 'Agent' = agency.agents[agent_id]
    response = await agent.run(message)
    
    return response.data
    
async def message_agent(ctx: RunContext[AgentDependencies], agent_id: str, message: str) -> str:
    """Send a message to the specified agent."""
    agency = ctx.deps.agency
    return await message_agent_helper(agency, agent_id, message)

async def prepare_message_agent_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    sender_agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]

    if not sender_agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    if not sender_agent.children:
        print("No children agents to message.")
        return None
    
    return tool_def

send_message_tool = Tool(message_agent, prepare=prepare_message_agent_tool)

async def call_meeting(ctx: RunContext[AgentDependencies], meeting_objective: str, max_turns: int = 15) -> str:
    print("Calling meeting...")
    agency = ctx.deps.agency
    host_id = ctx.deps.agent_id
    host: Agent = agency.agents[host_id]
    children: List[Agent] = list(host.children.values())
    prompt = ctx.prompt if ctx.prompt else "Meeting called"  # Add fallback for prompt

    if not children:
        return "No agents available to meet."

    # 🔁 Create a temporary clone of the host agent
    temp_host_id = host_id + "_temp"
    temp_host = Agent(
        agency=agency,
        name=f"{host.name} [Active Host]",
        id=temp_host_id,
        provider=host.provider,
        system_prompt=host.system_prompt,
        tools=host.tools, 
        accessible_tools={}
    )
    temp_host.message_history = host.message_history.copy()
    temp_host.message_history.append(
        ModelRequest(
            parts=[
                UserPromptPart(content=prompt)
            ]
        )
    )
    agency.agents[temp_host_id] = temp_host
    
    # Temporarily remove the accessible tools from the children
    original_accessible_tools = {}
    for child in children:
        original_accessible_tools[child.id] = child.accessible_tools.copy()
        child.accessible_tools = {}
    
    participants = [temp_host] + children

    discussion_log = [] # this is for saving and sending back to the host agent as the return of the tool call
    
    # Add a meeting initialized message to the log and each of the agents
    meeting_initialized_message = f"Meeting initialized with objective: {meeting_objective}"
    discussion_log.append({
        "agent_name": temp_host.name,
        "agent_id": temp_host.id,
        "message": meeting_initialized_message,
    })
    temp_host.message_history.append(
        ModelRequest(
            parts=[
                UserPromptPart(content=meeting_initialized_message)
            ]
        )
    )
    for child in children:
        child.message_history.append(
            ModelRequest(
                parts=[
                    UserPromptPart(content=meeting_initialized_message)
                ]
            )
        )
        
    # Add a meeting instructions for each child
    for child in children:
        child.message_history.append(
            ModelRequest(
                parts=[
                    UserPromptPart(content=\
f"""Meeting Instructions:
- Review the discussion so far
- Share your thoughts related to the meeting objective
- Respond to points raised by other participants
- If you have said all you need to contribute, include "READY_TO_MOVE_ON" in your response
""")
                ]
            )
        )
        
    # Add a meeting instructions for the host
    temp_host.message_history.append(
        ModelRequest(
            parts=[
                UserPromptPart(content=\
f"""Meeting Instructions:
- You are the host of this meeting. You will go first. Begin by elaborating on the objective of the meeting.
- Review the discussion so far
- Share your thoughts related to the meeting objective
- Respond to points raised by other participants
- If you have said all you need to contribute and want to end the meeting, include "READY_TO_END_MEETING" in your response
""")
            ]
        )
    )
    
    agents_done = set()
    turn = 0
    max_rounds = max_turns * len(participants)
    max_rounds = min(max_rounds, 15)
    
    # print participants
    print("Participants:")
    for agent in participants:
        print(f"{agent.name} ({agent.id})")

    # Start the back and forth
    # Host should go first
    print("Starting the meeting...")
    
    # For each round, allow each agent to speak who isn't done yet
    for _ in range(max_rounds):
        if len(agents_done) == len(participants):
            print("✅ All agents are ready to move on.")
            break
            
        for agent in participants:
            # if agent.id in agents_done:
            #     continue
                
            turn += 1
            print(f"Turn {turn}: {agent.name} ({agent.id})")
            logging_agent_id = agent.id if agent.id != temp_host_id else host_id
            
            YOUR_TURN_PHRASE = "It is your turn to speak. Please respond."
            try:
                result = await agent.run(YOUR_TURN_PHRASE)
                response = result.data.strip() if result and hasattr(result, 'data') else "No response"
                
                print(f"Response: {response}")
                
                # Add the message to the other agents' message history
                for other_agent in participants:
                    if other_agent.id != agent.id:
                        other_agent.message_history.append(
                            ModelRequest(
                                parts=[
                                    UserPromptPart(content=f"From {agent.name} ({logging_agent_id}): {response}")
                                ]
                            )
                        )
                        
                # Add the message to the discussion log
                discussion_log.append({
                    "agent_name": agent.name,
                    "agent_id": logging_agent_id,
                    "message": response,
                })

                if "READY_TO_END_MEETING" in response.upper() or "READY_TO_MOVE_ON" in response.upper():
                    agents_done.add(agent.id)
                    
                if len(agents_done) == len(participants):
                    print("✅ All agents are ready to move on.")
                    break
                    
            except Exception as e:
                print(f"Error during agent {agent.id} turn: {str(e)}")
                error_msg = f"Error during response: {str(e)}"
                discussion_log.append({
                    "agent_name": agent.name,
                    "agent_id": logging_agent_id,
                    "message": error_msg,
                })
                # Add the agent to agents_done to avoid further errors
                agents_done.add(agent.id)
                
        if turn >= max_rounds:
            print("❗ Max rounds reached.")
            break

    # Final summary
    final_summary = "\n".join([
        f"[{entry['agent_name']} ({entry['agent_id']})]: {entry['message']}"
        for entry in discussion_log
    ])

    # Restore original accessible tools to the children
    for child in children:
        child.accessible_tools = original_accessible_tools.get(child.id, {})
        
    # Add a meeting end message to each of the agents
    meeting_end_message = "Meeting has ended. Thank you for your participation."
    for child in children:
        child.message_history.append(
            ModelRequest(
                parts=[
                    UserPromptPart(content=meeting_end_message)
                ]
            )
        )
        
    # Clean up the temporary host agent
    if temp_host_id in agency.agents:
        del agency.agents[temp_host_id]
        
    return f"Meeting complete. Summary:\n\n{final_summary}"

async def prepare_call_meeting_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    if not agent.children:
        print("No children agents to meet.")
        return None
    
    # override to show which children can be messaged
    # TODO
    
    return tool_def

call_meeting_tool = Tool(call_meeting, prepare=prepare_call_meeting_tool)

# Internal Monologue
async def internal_monologue(ctx: RunContext[AgentDependencies], internal_monologue: str) -> str:
    """Use this tool to think through complex problems, make plans, or reason step by step without outputting to the user."""
    
    # Save the internal monologue to the agent's message history
    return "Internal monologue saved."

async def prepare_internal_monologue_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Optional[ToolDefinition]:
    agent_id = ctx.deps.agent_id
    agency = ctx.deps.agency
    agent = agency.agents[agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None

    tool_def.description = "Use this for thinking through complex problems step by step before taking action. Your thoughts will be saved but not shown to the user."
    
    if 'thought' in tool_def.parameters_json_schema.get('properties', {}):
        tool_def.parameters_json_schema['properties']['thought']['description'] = "Your detailed thought process, planning, or reasoning steps"
        
    return tool_def

internal_monologue_tool = Tool(
    internal_monologue,
    prepare=prepare_internal_monologue_tool,
    description="Use this tool to think through complex problems or make plans without outputting to the user."
)


# FILES
# GET FILE, MAKE FILE, EDIT_FILE, DELETE_FILE, LIST_FILES
# I give the agency access to a folder on the disk. The agency can create, edit, delete, and list files in that folder.
# FILE TOOLS
async def get_file_content(ctx: RunContext[AgentDependencies], file_path: str) -> str:
    """Get the content of a file in the workspace."""
    agency = ctx.deps.agency
    full_path = os.path.join(agency.workspace_path, file_path)
    
    # Ensure the file is within the workspace
    if not os.path.abspath(full_path).startswith(os.path.abspath(agency.workspace_path)):
        return f"Error: Cannot access files outside the workspace: {file_path}"
    
    try:
        if not os.path.exists(full_path):
            return f"Error: File not found: {file_path}"
        
        with open(full_path, 'r') as file:
            content = file.read()
        
        return f"File content of {file_path}:\n\n{content}"
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"

async def prepare_get_file_content_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

get_file_tool = Tool(get_file_content, prepare=prepare_get_file_content_tool)

async def make_file(ctx: RunContext[AgentDependencies], file_path: str, content: str) -> str:
    """Create a new file in the workspace with the specified content."""
    agency = ctx.deps.agency
    full_path = os.path.join(agency.workspace_path, file_path)
    
    # Ensure the file is within the workspace
    if not os.path.abspath(full_path).startswith(os.path.abspath(agency.workspace_path)):
        return f"Error: Cannot create files outside the workspace: {file_path}"
    
    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(full_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        # Check if file already exists
        if os.path.exists(full_path):
            return f"Error: File already exists: {file_path}. Use edit_file to modify it."
        
        with open(full_path, 'w') as file:
            file.write(content)
        
        return f"File created successfully: {file_path}"
    except Exception as e:
        return f"Error creating file {file_path}: {str(e)}"

async def prepare_make_file_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

make_file_tool = Tool(make_file, prepare=prepare_make_file_tool)

async def edit_file(ctx: RunContext[AgentDependencies], file_path: str, content: str) -> str:
    """Edit an existing file in the workspace. Replaces the entire content."""
    agency = ctx.deps.agency
    full_path = os.path.join(agency.workspace_path, file_path)
    
    # Ensure the file is within the workspace
    if not os.path.abspath(full_path).startswith(os.path.abspath(agency.workspace_path)):
        return f"Error: Cannot edit files outside the workspace: {file_path}"
    
    try:
        if not os.path.exists(full_path):
            return f"Error: File not found: {file_path}. Use make_file to create it."
        
        with open(full_path, 'w') as file:
            file.write(content)
        
        return f"File edited successfully: {file_path}"
    except Exception as e:
        return f"Error editing file {file_path}: {str(e)}"

async def prepare_edit_file_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

edit_file_tool = Tool(edit_file, prepare=prepare_edit_file_tool)

async def delete_file(ctx: RunContext[AgentDependencies], file_path: str) -> str:
    """Delete a file from the workspace."""
    agency = ctx.deps.agency
    full_path = os.path.join(agency.workspace_path, file_path)
    
    # Ensure the file is within the workspace
    if not os.path.abspath(full_path).startswith(os.path.abspath(agency.workspace_path)):
        return f"Error: Cannot delete files outside the workspace: {file_path}"
    
    try:
        if not os.path.exists(full_path):
            return f"Error: File not found: {file_path}"
        
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
            return f"Directory deleted successfully: {file_path}"
        else:
            os.remove(full_path)
            return f"File deleted successfully: {file_path}"
    except Exception as e:
        return f"Error deleting file {file_path}: {str(e)}"

async def prepare_delete_file_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

delete_file_tool = Tool(delete_file, prepare=prepare_delete_file_tool)

async def list_files(ctx: RunContext[AgentDependencies], directory: str = "") -> str:
    """List all files in the specified directory within the workspace."""
    agency = ctx.deps.agency
    full_path = os.path.join(agency.workspace_path, directory)
    
    # Ensure the directory is within the workspace
    if not os.path.abspath(full_path).startswith(os.path.abspath(agency.workspace_path)):
        return f"Error: Cannot list files outside the workspace: {directory}"
    
    try:
        if not os.path.exists(full_path):
            return f"Error: Directory not found: {directory}"
        
        if not os.path.isdir(full_path):
            return f"Error: {directory} is not a directory"
        
        file_list = []
        for root, dirs, files in os.walk(full_path):
            rel_root = os.path.relpath(root, agency.workspace_path)
            if rel_root == '.':
                rel_root = ''
            
            # Add directories with trailing slash
            for d in dirs:
                file_list.append(os.path.join(rel_root, d) + '/')
            
            # Add files
            for f in files:
                file_list.append(os.path.join(rel_root, f))
        
        if not file_list:
            return f"No files found in {directory or 'workspace root'}"
        
        file_list.sort()
        return f"Files in {directory or 'workspace root'}:\n" + "\n".join(file_list)
    except Exception as e:
        return f"Error listing files in {directory}: {str(e)}"

async def prepare_list_files_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

list_files_tool = Tool(list_files, prepare=prepare_list_files_tool)


# BASH TOOL (or zsh)
# I give the agency access to a bash shell. The agency can run bash commands and get the output.
# It's location starts in the same folder space as the agency.
# NEW_TERMINAL, RUN_COMMAND, DELETE_TERMINAL, LIST_TERMINALS
# BASH TERMINAL TOOLS
class TerminalProcess:
    def __init__(self, workspace_path: str, terminal_id: str):
        self.workspace_path = workspace_path
        self.terminal_id = terminal_id
        self.process = None
        self.active = False
    
    async def start(self):
        if self.active:
            return False
        
        # Create a bash process that will stay alive
        self.process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.workspace_path,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.active = True
        return True
    
    async def stop(self):
        if not self.active or not self.process:
            return False
        
        try:
            self.process.terminate()
            # Give it a moment to terminate gracefully
            await asyncio.sleep(0.5)
            if self.process.poll() is None:
                # Force kill if it doesn't terminate
                self.process.kill()
            self.active = False
            return True
        except Exception as e:
            print(f"Error stopping terminal {self.terminal_id}: {e}")
            return False
    
    async def run_command(self, command: str) -> str:
        if not self.active or not self.process:
            return "Error: Terminal is not active"
        
        try:
            # Send command with newline to simulate enter key
            self.process.stdin.write(f"{command}\n")
            self.process.stdin.flush()
            
            # Add a marker to know when output is complete
            marker = f"COMMAND_COMPLETE_{uuid.uuid4()}"
            self.process.stdin.write(f"echo {marker}\n")
            self.process.stdin.flush()
            
            # Collect output until the marker is found
            output_lines = []
            while True:
                line = self.process.stdout.readline()
                if marker in line:
                    break
                output_lines.append(line)
            
            # Remove the command from the output
            if output_lines and command in output_lines[0]:
                output_lines.pop(0)
            
            return "".join(output_lines)
        except Exception as e:
            return f"Error executing command: {str(e)}"

class TerminalManager:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.terminals: Dict[str, TerminalProcess] = {}
    
    async def create_terminal(self, terminal_id: Optional[str] = None) -> str:
        if terminal_id is None:
            terminal_id = f"terminal_{uuid.uuid4().hex[:8]}"
        
        if terminal_id in self.terminals:
            return f"Terminal with ID {terminal_id} already exists"
        
        terminal = TerminalProcess(self.workspace_path, terminal_id)
        success = await terminal.start()
        
        if success:
            self.terminals[terminal_id] = terminal
            return f"Created terminal with ID: {terminal_id}"
        else:
            return f"Failed to create terminal with ID: {terminal_id}"
    
    async def delete_terminal(self, terminal_id: str) -> str:
        if terminal_id not in self.terminals:
            return f"Terminal with ID {terminal_id} does not exist"
        
        success = await self.terminals[terminal_id].stop()
        if success:
            del self.terminals[terminal_id]
            return f"Terminal {terminal_id} deleted successfully"
        else:
            return f"Failed to delete terminal {terminal_id}"
    
    async def run_command(self, terminal_id: str, command: str) -> str:
        if terminal_id not in self.terminals:
            return f"Terminal with ID {terminal_id} does not exist"
        
        return await self.terminals[terminal_id].run_command(command)
    
    async def list_terminals(self) -> str:
        if not self.terminals:
            return "No active terminals"
        
        terminal_list = "\n".join([f"- {terminal_id}" for terminal_id in self.terminals.keys()])
        return f"Active terminals:\n{terminal_list}"
    
    async def shutdown_all(self):
        """Shut down all terminal processes."""
        for terminal_id, terminal in list(self.terminals.items()):
            await terminal.stop()
        self.terminals.clear()

# Terminal tool functions
async def new_terminal(ctx: RunContext[AgentDependencies], terminal_id: Optional[str] = None) -> str:
    """Create a new bash terminal in the workspace."""
    agency = ctx.deps.agency
    return await agency.terminal_manager.create_terminal(terminal_id)

async def prepare_new_terminal_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

new_terminal_tool = Tool(new_terminal, prepare=prepare_new_terminal_tool)

async def run_command(ctx: RunContext[AgentDependencies], terminal_id: str, command: str) -> str:
    """Run a bash command in the specified terminal."""
    agency = ctx.deps.agency
    return await agency.terminal_manager.run_command(terminal_id, command)

async def prepare_run_command_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

run_command_tool = Tool(run_command, prepare=prepare_run_command_tool)

async def delete_terminal(ctx: RunContext[AgentDependencies], terminal_id: str) -> str:
    """Delete a terminal from the workspace."""
    agency = ctx.deps.agency
    return await agency.terminal_manager.delete_terminal(terminal_id)

async def prepare_delete_terminal_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

delete_terminal_tool = Tool(delete_terminal, prepare=prepare_delete_terminal_tool)

async def list_terminals(ctx: RunContext[AgentDependencies]) -> str:
    """List all active terminals in the workspace."""
    agency = ctx.deps.agency
    return await agency.terminal_manager.list_terminals()

async def prepare_list_terminals_tool(
    ctx: RunContext[AgentDependencies], tool_def: ToolDefinition
) -> Union[ToolDefinition, None]:
    agent: 'Agent' = ctx.deps.agency.agents[ctx.deps.agent_id]
    
    if not agent.accessible_tools.get(tool_def.name, False):
        print(f"Tool {tool_def.name} is not accessible.")
        return None
    
    return tool_def

list_terminals_tool = Tool(list_terminals, prepare=prepare_list_terminals_tool)


all_tools = [
    create_new_agent_tool,
    send_message_tool,
    call_meeting_tool,
    internal_monologue_tool,
    # get_file_tool,
    # make_file_tool,
    # edit_file_tool,
    # delete_file_tool,
    # list_files_tool,
    # new_terminal_tool,
    # run_command_tool,
    # delete_terminal_tool,
    # list_terminals_tool,
]




# AGENT
class AgentState(BaseModel):
    id: str
    name: str
    system_prompt: str
    provider: str
    tool_names: List[str] = Field(default_factory=list)
    accessible_tools: Dict[str, bool] = Field(default_factory=dict)
    message_history: List[ModelMessage] = Field(default_factory=list)
    parent_id: Optional[str] = None
    child_ids: List[str] = Field(default_factory=list)
    mcp_server_ids: List[str] = Field(default_factory=list)

class Agent:
    def __init__(self,
                 agency: 'Agency',
                 name: str,
                 id: str, 
                 provider: str, 
                 system_prompt: str, 
                 tools: List[Tool] = all_tools, 
                 accessible_tools: Dict[str] = {k.name: True for k in all_tools},
                 mcp_servers: List[str] = []):
        
        self.agency: 'Agency' = agency
        self.name = name
        self.id = id
        self.provider = provider
        self.tools = tools
        self.system_prompt = system_prompt
        self.message_history: List[ModelMessage] = []
        self.accessible_tools = accessible_tools
        self.mcp_server_ids = mcp_servers
        
        # Initialize agent with MCP servers if any
        mcp_servers_list = []
        for server_id in self.mcp_server_ids:
            server = self.agency.server_manager.get_server(server_id)
            if server:
                mcp_servers_list.append(server)
        
        self.agent: PydanticAgent = PydanticAgent(
            provider,
            system_prompt=system_prompt,
            tools=tools,
            mcp_servers=mcp_servers_list  # always a list, even if empty
        )
        
        self.parent_id = None
        self.children = {}
        
        self.curr_depth = lambda: 0 if self.parent_id is None else self.agency.agents[self.parent_id].curr_depth() + 1
        self.curr_breadth = lambda: len(self.children)
        
        # Add System Prompt
        self.message_history.append(
            ModelRequest(
                parts=[
                    SystemPromptPart(
                        content=system_prompt,
                    ),
                ]
            )
        )
        
    async def update_system_prompt(self, new_prompt: str) -> None:
        self.system_prompt = new_prompt
        self.message_history[0].parts[0].content = new_prompt
    
    async def add_mcp_server(self, server_id: str) -> bool:
        """Add an MCP server to this agent and update the PydanticAgent."""
        if server_id in self.mcp_server_ids:
            return False
        
        self.mcp_server_ids.append(server_id)
        
        # Get the actual server
        server = self.agency.server_manager.get_server(server_id)
        if not server:
            return False
        
        # Recreate the PydanticAgent with updated MCP servers
        mcp_servers_list = []
        for sid in self.mcp_server_ids:
            s = self.agency.server_manager.get_server(sid)
            if s:
                mcp_servers_list.append(s)
        
        self.agent = PydanticAgent(
            self.provider,
            system_prompt=self.system_prompt,
            tools=self.tools,
            mcp_servers=mcp_servers_list if mcp_servers_list else None
        )
        
        return True
    
    async def remove_mcp_server(self, server_id: str) -> bool:
        """Remove an MCP server from this agent."""
        if server_id not in self.mcp_server_ids:
            return False
        
        self.mcp_server_ids.remove(server_id)
        
        # Recreate the PydanticAgent with updated MCP servers
        mcp_servers_list = []
        for sid in self.mcp_server_ids:
            s = self.agency.server_manager.get_server(sid)
            if s:
                mcp_servers_list.append(s)
        
        self.agent = PydanticAgent(
            self.provider,
            system_prompt=self.system_prompt,
            tools=self.tools,
            mcp_servers=mcp_servers_list if mcp_servers_list else None
        )
        
        return True
        
    async def run(self, prompt: str) -> AgentRunResult:
        # Ensure all MCP servers associated with this agent are running
        for server_id in self.mcp_server_ids:
            if not self.agency.server_manager.is_running(server_id):
                print(f"Starting MCP server {server_id} for agent {self.id}")
                success = await self.agency.server_manager.start_server(server_id)
                if not success:
                    print(f"Warning: Failed to start MCP server {server_id}")
    
        existing_history = self.message_history.copy()
        deps = AgentDependencies(agency=self.agency, agent_id=self.id)
        result = await self.agent.run(prompt, deps=deps, message_history=existing_history)
        
        self.save_message_history(prompt, result)

        return result
    
    def save_message_history(self, prompt: str, result: AgentRunResult) -> None:
        self.message_history.extend(result.new_messages())
        return
    
    def save_state(self) -> AgentState:
        """Creates a Pydantic model representing the agent's state."""
        return AgentState(
            id=self.id,
            name=self.name,
            system_prompt=self.system_prompt,
            provider=self.provider,
            tool_names=[tool.name for tool in self.tools],
            accessible_tools=self.accessible_tools,
            message_history=self.message_history,
            parent_id=self.parent_id,
            child_ids=list(self.children.keys()),
            mcp_server_ids=self.mcp_server_ids
        )

    @classmethod
    def load_state(cls, state: AgentState, agency: 'Agency', all_tools_map: Dict[str, Tool]) -> 'Agent':
        """Reconstructs an Agent from its saved state."""
        agent_tools = [all_tools_map[name] for name in state.tool_names if name in all_tools_map]

        agent = cls(
            agency=agency,
            name=state.name,
            id=state.id,
            provider=state.provider,
            system_prompt=state.system_prompt,
            tools=agent_tools,
            accessible_tools=state.accessible_tools,
            mcp_servers=state.mcp_server_ids
        )
        agent.message_history = state.message_history
        agent.parent_id = state.parent_id

        return agent

# AGENCY
class AgencyState(BaseModel):
    agency_id: str
    agents: List[AgentState] = Field(default_factory=list)
    current_id: int = 0
    max_depth: int = 3
    max_breadth: int = 3
    max_agents: int = 10
    workspace_id: Optional[str] = None
    
class Agency:
    def __init__(self, state: Optional[AgencyState] = None, tools: List[Tool] = all_tools, workspace_id: Optional[str] = None,
                 main_agent_system_prompt: str = "You are a helpful assistant."
                 ):
        self.agents: Dict[str, Agent] = {}
        self.all_tools_map = {tool.name: tool for tool in tools}
        self.server_manager = MCPServerManager()
        
        # Setup workspace
        self.workspace_base_path = Path("./workspaces").resolve()
        os.makedirs(self.workspace_base_path, exist_ok=True)
        
        # Create or use provided workspace ID
        if state and state.workspace_id:
            self.workspace_id = state.workspace_id
        elif workspace_id:
            self.workspace_id = workspace_id
        else:
            self.workspace_id = f"workspace_{uuid.uuid4().hex[:8]}"
        
        self.workspace_path = os.path.join(self.workspace_base_path, self.workspace_id)
        os.makedirs(self.workspace_path, exist_ok=True)
        print(f"Using workspace: {self.workspace_path}")
        
        # Initialize terminal manager
        self.terminal_manager = TerminalManager(self.workspace_path)

        if state:
            # Load from state
            self.default_provider = ""
            self.current_id = state.current_id
            self.max_depth = state.max_depth
            self.max_breadth = state.max_breadth
            self.max_agents = state.max_agents

            # 1. Create all agents from state
            for agent_state in state.agents:
                agent = Agent.load_state(agent_state, self, self.all_tools_map)
                self.agents[agent.id] = agent
                if agent.id == state.agency_id:
                     self.main_agent = agent
                     self.default_provider = agent.provider

            if not hasattr(self, 'main_agent'):
                 raise ValueError("Main agent ID not found in loaded state")

            # 2. Rebuild parent/child relationships
            for agent_state in state.agents:
                agent = self.agents[agent_state.id]
                agent.parent_id = agent_state.parent_id
                # Link children
                for child_id in agent_state.child_ids:
                    if child_id in self.agents:
                        agent.children[child_id] = self.agents[child_id]
                    else:
                        print(f"Warning: Child agent ID {child_id} not found for parent {agent.id}")

        else:
            # Initialize fresh agency with default configuration
            # self.default_provider = "anthropic:claude-3-5-haiku-latest"
            # self.default_provider = "google-gla:gemini-2.0-flash-lite-preview-02-05"
            # self.default_provider = "anthropic:claude-3-7-sonnet-latest"
            self.default_provider = "openai:gpt-4.1-nano"
            self.default_provider = os.environ.get("DEFAULT_PROVIDER", self.default_provider)
            
            # Initialize MCP servers
            self._setup_mcp_servers()
            
            self.main_agent = Agent(
                self,
                "main_agent",
                "0",
                self.default_provider,
                main_agent_system_prompt,
                tools=list(self.all_tools_map.values()),
                accessible_tools={
                    "create_new_agent": True,
                    "message_agent": True,
                    "call_meeting": True,
                    "internal_monologue": True,
                    # "get_file_content": True,
                    # "make_file": True,
                    # "edit_file": True,
                    # "delete_file": True,
                    # "list_files": True,
                    # "new_terminal": True,
                    # "run_command": True,
                    # "delete_terminal": True,
                    # "list_terminals": True,
                },
                # mcp_servers=["mcp_server_playwright", "mcp_server_python"]
                mcp_servers=[]
            )
            self.agents["0"] = self.main_agent
            self.agents["0"].parent_id = None
            self.current_id = 1
            self.max_depth = 3
            self.max_breadth = 3
            self.max_agents = 10
    
    def _setup_mcp_servers(self):
        """Initialize default MCP servers for the agency."""
        # Create a default Playwright MCP server
        playwright_server_id = "mcp_server_playwright"
        playwright_server = PlaywrightMCPServer(0)
        self.server_manager.add_server(playwright_server_id, playwright_server)
        
        # Create a Python execution MCP server
        python_server_id = "mcp_server_python"
        python_server = PythonMCPServer(0)
        self.server_manager.add_server(python_server_id, python_server)
        
        # Set the default MCP servers for the main agent
        self.default_mcp_servers = [playwright_server_id, python_server_id]
    
    async def create_mcp_server(self, server_id: Optional[str] = None) -> str:
        """Create a new MCP server and return its ID."""
        if server_id is None:
            server_id = f"mcp_server_{len(self.server_manager.servers)}"
        
        if server_id in self.server_manager.servers:
            return f"Server with ID {server_id} already exists"
        
        # Create a new Playwright MCP server
        playwright_server = PlaywrightMCPServer(len(self.server_manager.servers))
        self.server_manager.add_server(server_id, playwright_server)
        
        return f"Created MCP server with ID: {server_id}"
        
    async def run(self, prompt: str) -> AgentRunResult:
        # Start any MCP servers needed by the main agent
        for server_id in self.main_agent.mcp_server_ids:
            if not self.server_manager.is_running(server_id):
                print(f"Starting MCP server {server_id} for main agent")
                success = await self.server_manager.start_server(server_id)
                if not success:
                    print(f"Warning: Failed to start MCP server {server_id}")
                # Wait for the server to be ready (robust readiness check)
                ready = await self.server_manager.wait_for_server_ready(server_id, timeout=120, interval=2)
                if not ready:
                    raise RuntimeError(f"MCP server {server_id} did not become ready in time. Please check logs and try again.")
                
        result = await self.main_agent.run(prompt)
        return result
    
    async def shutdown(self):
        """Properly shut down all MCP servers and terminal processes."""
        await self.server_manager.stop_all_servers()
        await self.terminal_manager.shutdown_all()
    
    def next_id(self) -> str:
        agent_id = str(self.current_id)
        self.current_id += 1
        return agent_id
    
    def __str__(self) -> str:
        return f"Agency with {len(self.agents)} agents and {len(self.server_manager.servers)} MCP servers."
    
    def save_state(self) -> AgencyState:
        """Creates a Pydantic model representing the agency's state."""
        return AgencyState(
            agency_id=self.main_agent.id,
            agents=[agent.save_state() for agent in self.agents.values()],
            current_id=self.current_id,
            max_depth=self.max_depth,
            max_breadth=self.max_breadth,
            max_agents=self.max_agents,
            workspace_id=self.workspace_id,
        )

    def save_to_file(self, directory: str, use_json=True) -> None:
        """Saves the agency state to a file (JSON or YAML)."""
        agency_state = self.save_state()
        file_id = str(uuid.uuid4())
        extension = "json" if use_json else "yaml"
        file_path = os.path.join(directory, f"{file_id}.{extension}")
        print(f"Saving agency state to {file_path}")

        os.makedirs(directory, exist_ok=True)

        with open(file_path, "w") as file:
            if use_json:
                file.write(agency_state.model_dump_json(indent=2))
            else:
                import yaml
                yaml.dump(agency_state.model_dump(mode='python'), file, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str, tools: List[Tool] = all_tools) -> 'Agency':
        """Loads agency state from a file."""
        print(f"Loading agency state from {file_path}")
        _, extension = os.path.splitext(file_path)
        use_json = extension.lower() == ".json"

        with open(file_path, "r") as file:
            if use_json:
                agency_state = AgencyState.model_validate_json(file.read())
            else:
                import yaml
                data = yaml.safe_load(file)
                agency_state = AgencyState.model_validate(data)

        return cls(state=agency_state, tools=tools)

# Usage
async def main():
    SAVE_DIR = "conversations"
    
    # Create a new agency with MCP capabilities and file/bash tools
    agency = Agency(workspace_id="demo_workspace")
    
    try:
        # Example usage that demonstrates the new capabilities
        # Create a file and run some bash commands
        response = await agency.run("""
        Generate a thorough report on tariffs with multiple perspectives. Create a few agents representing different perspectives and experts. Have a meeting/council and generate me a report after. Have the meeting have at least 15 turns, but no more than 35. Everyone should speak at least 3 turns. Please instruct everyone to be concise and a maximum of 100 words.
        """)
        
        print("Response:")
        print(response.data)
        
        # Save the agency state
        agency.save_to_file(SAVE_DIR)
    finally:
        # Ensure proper shutdown of MCP servers and terminals
        await agency.shutdown()
    
if __name__ == "__main__":
    asyncio.run(main())