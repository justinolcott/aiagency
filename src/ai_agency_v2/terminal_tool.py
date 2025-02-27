"""
Terminal tool for LLM agents to use terminal functionality.
Provides a Langchain-compatible interface for terminal operations.
"""
import json
import time
from typing import Dict, List, Any, Optional, Type, Union
import logging

# Langchain imports
from langchain.tools import BaseTool, Tool, ToolException
from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain_core.pydantic_v1 import BaseModel, Field

# Import our terminal management classes
from .terminal_manager import TerminalManager
from .process import OutputType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Singleton instance of terminal manager to be used across all tools
_terminal_manager = None

def get_terminal_manager(
    base_dir: str = "/tmp",
    auto_save: bool = True
) -> TerminalManager:
    """Get the singleton instance of terminal manager"""
    global _terminal_manager
    if _terminal_manager is None:
        _terminal_manager = TerminalManager(
            default_base_dir=base_dir,
            auto_save=auto_save
        )
    return _terminal_manager


class CreateTerminalInput(BaseModel):
    """Input for create_terminal tool"""
    base_dir: Optional[str] = Field(
        default=None, 
        description="Base directory for the terminal. Default is /tmp."
    )
    env_vars: Optional[Dict[str, str]] = Field(
        default=None, 
        description="Environment variables to set for the terminal session."
    )


class CreateTerminalTool(BaseTool):
    """Tool for creating a new terminal session."""
    name: str = "create_terminal"
    description: str = (
        "Creates a new terminal session for running commands. "
        "Returns the terminal ID which is needed for other terminal operations."
    )
    args_schema: Type[BaseModel] = CreateTerminalInput
    return_direct: bool = False

    def _run(
        self, 
        base_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Create a new terminal session."""
        manager = get_terminal_manager()
        try:
            terminal = manager.create_terminal(
                base_dir=base_dir,
                env_vars=env_vars
            )
            return (
                f"Created new terminal with ID: {terminal.terminal_id}\n"
                f"Base directory: {terminal.base_dir}\n"
                f"Use this terminal_id in other terminal operations."
            )
        except Exception as e:
            raise ToolException(f"Failed to create terminal: {str(e)}")


class RunCommandInput(BaseModel):
    """Input for run_command tool"""
    terminal_id: str = Field(
        ...,
        description="ID of the terminal to run the command in."
    )
    command: str = Field(
        ...,
        description="Command to execute in the terminal."
    )
    background: bool = Field(
        default=False,
        description="Whether to run the command in the background (non-blocking)."
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Timeout in seconds. If None, uses the terminal's default."
    )


class RunCommandTool(BaseTool):
    """Tool for running a command in a terminal."""
    name: str = "run_command"
    description: str = (
        "Runs a command in a specified terminal session. "
        "Can run commands in the foreground (blocking) or background. "
        "Returns the command output and exit code."
    )
    args_schema: Type[BaseModel] = RunCommandInput
    return_direct: bool = False

    def _run(
        self,
        terminal_id: str,
        command: str,
        background: bool = False,
        timeout: Optional[int] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Run a command in a terminal."""
        manager = get_terminal_manager()

        try:
            def output_callback(line, output_type, process_id):
                if run_manager:
                    if output_type == OutputType.SYSTEM:
                        prefix = "SYSTEM: "
                    elif output_type == OutputType.STDERR:
                        prefix = "ERROR: "
                    else:
                        prefix = ""
                    
                    # Stream output via callback handler if available
                    run_manager.on_text(f"{prefix}{line}", verbose=True)
            
            result = manager.run_command(
                terminal_id=terminal_id,
                command=command,
                background=background,
                timeout=timeout,
                output_callback=output_callback
            )

            if background:
                return (
                    f"Command started in background with process ID: {result['process_id']}\n"
                    f"You can check on it later using list_processes or get_process_output."
                )
            else:
                output_str = result["output"]
                # If output is very long, truncate it
                if len(output_str) > 4000:
                    output_str = output_str[:4000] + "\n[Output truncated due to length...]"
                
                return (
                    f"Command: {command}\n"
                    f"Exit code: {result['exit_code']}\n"
                    f"Output:\n{output_str}"
                )
                
        except ValueError as e:
            raise ToolException(f"Terminal not found: {str(e)}")
        except Exception as e:
            raise ToolException(f"Error running command: {str(e)}")


class ListTerminalsInput(BaseModel):
    """Input for list_terminals tool"""
    detailed: bool = Field(
        default=False,
        description="Whether to show detailed information about each terminal."
    )


class ListTerminalsTool(BaseTool):
    """Tool for listing all available terminal sessions."""
    name: str = "list_terminals"
    description: str = (
        "Lists all available terminal sessions with their IDs and status. "
        "Use 'detailed=True' to get more information about each terminal."
    )
    args_schema: Type[BaseModel] = ListTerminalsInput
    return_direct: bool = False

    def _run(
        self,
        detailed: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """List all terminals."""
        manager = get_terminal_manager()
        terminals = manager.list_terminals()
        
        if not terminals:
            return "No terminals available. Create a new terminal using create_terminal."
            
        if detailed:
            result = []
            for term in terminals:
                term_obj = manager.get_terminal(term['terminal_id'])
                if term_obj:
                    result.append(manager.show_terminal(term['terminal_id']))
                else:
                    result.append(f"Terminal {term['terminal_id']}: [Details not available]")
            return "\n\n".join(result)
        else:
            result = ["Available terminals:"]
            for term in terminals:
                result.append(
                    f"Terminal {term['terminal_id']}:\n"
                    f"  - Current directory: {term['current_dir']}\n"
                    f"  - Running processes: {term['running_processes']}\n"
                    f"  - Background processes: {term['background_processes']}"
                )
            return "\n\n".join(result)


class GetTerminalHistoryInput(BaseModel):
    """Input for get_terminal_history tool"""
    terminal_id: str = Field(
        ...,
        description="ID of the terminal to get history from."
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of history items to return. Default is 10."
    )


class GetTerminalHistoryTool(BaseTool):
    """Tool for retrieving command history from a terminal."""
    name: str = "get_terminal_history"
    description: str = (
        "Retrieves the command history from a specified terminal session. "
        "Shows commands that were run and their output."
    )
    args_schema: Type[BaseModel] = GetTerminalHistoryInput
    return_direct: bool = False

    def _run(
        self,
        terminal_id: str,
        limit: int = 10,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Get terminal command history."""
        manager = get_terminal_manager()
        
        try:
            terminal = manager.get_terminal(terminal_id)
            if not terminal:
                return f"No terminal found with ID: {terminal_id}"
                
            history = terminal.get_history(limit)
            if not history:
                return f"No command history for terminal {terminal_id}"
                
            result = [f"Command history for terminal {terminal_id}:"]
            for idx, entry in enumerate(history):
                cmd_output = entry["output"]
                # Truncate long outputs
                if len(cmd_output) > 500:
                    cmd_output = cmd_output[:500] + "\n[Output truncated...]"
                
                result.append(
                    f"{idx+1}. Command: {entry['command']}\n"
                    f"   Directory: {entry['directory']}\n"
                    f"   Exit code: {entry.get('exit_code', 'N/A')}\n"
                    f"   Output:\n{cmd_output}\n"
                )
                
            return "\n".join(result)
            
        except Exception as e:
            raise ToolException(f"Error getting terminal history: {str(e)}")


class ListProcessesInput(BaseModel):
    """Input for list_processes tool"""
    terminal_id: Optional[str] = Field(
        default=None,
        description="ID of the terminal to list processes for. If None, lists processes for all terminals."
    )
    all_processes: bool = Field(
        default=False,
        description="Whether to include completed processes in the listing."
    )


class ListProcessesTool(BaseTool):
    """Tool for listing running processes in terminals."""
    name: str = "list_processes"
    description: str = (
        "Lists running processes in terminals. "
        "Can list processes for a specific terminal or all terminals. "
        "Use 'all_processes=True' to include completed processes."
    )
    args_schema: Type[BaseModel] = ListProcessesInput
    return_direct: bool = False

    def _run(
        self,
        terminal_id: Optional[str] = None,
        all_processes: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """List processes in terminals."""
        manager = get_terminal_manager()
        
        try:
            if terminal_id:
                # List processes for a specific terminal
                terminal = manager.get_terminal(terminal_id)
                if not terminal:
                    return f"No terminal found with ID: {terminal_id}"
                    
                processes = terminal.list_processes(all_processes=all_processes)
                
                if not processes:
                    return f"No {'active or completed' if all_processes else 'active'} processes found in terminal {terminal_id}"
                    
                result = [f"Processes in terminal {terminal_id}:"]
                for proc in processes:
                    runtime = proc.get("runtime", 0)
                    runtime_str = f"{runtime:.1f}s" if runtime < 60 else f"{runtime/60:.1f}m"
                    status_str = f"{proc['status'].upper()}"
                    if proc['status'] != "running":
                        status_str += f" (exit: {proc['exit_code']})" if proc['exit_code'] is not None else ""
                    
                    result.append(
                        f"- Process {proc['process_id']} [{status_str}] ({runtime_str}):\n"
                        f"  Command: {proc['command']}\n"
                        f"  Working directory: {proc['working_dir']}"
                    )
                return "\n\n".join(result)
            else:
                # List processes for all terminals
                all_proc_dict = manager.list_all_processes(all_processes=all_processes)
                
                if not all_proc_dict:
                    return f"No {'active or completed' if all_processes else 'active'} processes found in any terminal"
                    
                result = []
                for term_id, processes in all_proc_dict.items():
                    result.append(f"Processes in terminal {term_id}:")
                    for proc in processes:
                        runtime = proc.get("runtime", 0)
                        runtime_str = f"{runtime:.1f}s" if runtime < 60 else f"{runtime/60:.1f}m"
                        status_str = f"{proc['status'].upper()}"
                        if proc['status'] != "running":
                            status_str += f" (exit: {proc['exit_code']})" if proc['exit_code'] is not None else ""
                        
                        result.append(
                            f"- Process {proc['process_id']} [{status_str}] ({runtime_str}):\n"
                            f"  Command: {proc['command']}\n"
                            f"  Working directory: {proc['working_dir']}"
                        )
                return "\n\n".join(result)
                
        except Exception as e:
            raise ToolException(f"Error listing processes: {str(e)}")


class KillProcessInput(BaseModel):
    """Input for kill_process tool"""
    process_id: str = Field(
        ...,
        description="ID of the process to kill."
    )


class KillProcessTool(BaseTool):
    """Tool for killing a specific process."""
    name: str = "kill_process"
    description: str = (
        "Kills a specific process by its ID. "
        "Use this to terminate long-running or background processes."
    )
    args_schema: Type[BaseModel] = KillProcessInput
    return_direct: bool = False

    def _run(
        self,
        process_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Kill a process."""
        manager = get_terminal_manager()
        
        try:
            success = manager.kill_process(process_id)
            if success:
                return f"Process {process_id} has been terminated successfully."
            else:
                return f"No active process found with ID: {process_id}"
                
        except Exception as e:
            raise ToolException(f"Error killing process: {str(e)}")


class GetProcessOutputInput(BaseModel):
    """Input for get_process_output tool"""
    process_id: str = Field(
        ...,
        description="ID of the process to get output from."
    )


class GetProcessOutputTool(BaseTool):
    """Tool for getting output from a process."""
    name: str = "get_process_output"
    description: str = (
        "Gets the current output from a specific process. "
        "Useful for checking the status of a running background process."
    )
    args_schema: Type[BaseModel] = GetProcessOutputInput
    return_direct: bool = False

    def _run(
        self,
        process_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Get process output."""
        manager = get_terminal_manager()
        
        try:
            terminal, process = manager.get_process(process_id)
            if not terminal or not process:
                return f"No process found with ID: {process_id}"
                
            output = process.get_combined_output()
            
            # If output is very long, truncate it
            if len(output) > 4000:
                output = output[:4000] + "\n[Output truncated due to length...]"
                
            status = "RUNNING" if process.is_running() else process.status.upper()
            runtime = process.get_runtime()
            runtime_str = f"{runtime:.1f}s" if runtime < 60 else f"{runtime/60:.1f}m"
            
            return (
                f"Process {process_id} [{status}] ({runtime_str}):\n"
                f"Command: {process.command}\n"
                f"Output:\n{output}"
            )
                
        except Exception as e:
            raise ToolException(f"Error getting process output: {str(e)}")


class SendInputToProcessInput(BaseModel):
    """Input for send_input_to_process tool"""
    process_id: str = Field(
        ...,
        description="ID of the process to send input to."
    )
    input_text: str = Field(
        ...,
        description="Text to send to the process as input."
    )


class SendInputToProcessTool(BaseTool):
    """Tool for sending input to a running process."""
    name: str = "send_input_to_process"
    description: str = (
        "Sends input to a running process. "
        "Useful for interactive processes that expect user input."
    )
    args_schema: Type[BaseModel] = SendInputToProcessInput
    return_direct: bool = False

    def _run(
        self,
        process_id: str,
        input_text: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Send input to a process."""
        manager = get_terminal_manager()
        
        try:
            success = manager.send_input_to_process(process_id, input_text)
            if success:
                return f"Input sent successfully to process {process_id}: '{input_text}'"
            else:
                return f"Failed to send input. Process {process_id} may not be running or doesn't accept input."
                
        except Exception as e:
            raise ToolException(f"Error sending input to process: {str(e)}")


class DeleteTerminalInput(BaseModel):
    """Input for delete_terminal tool"""
    terminal_id: str = Field(
        ...,
        description="ID of the terminal to delete."
    )
    kill_processes: bool = Field(
        default=True,
        description="Whether to kill all processes in the terminal before deleting."
    )


class DeleteTerminalTool(BaseTool):
    """Tool for deleting a terminal session."""
    name: str = "delete_terminal"
    description: str = (
        "Deletes a terminal session and optionally kills all processes running in it. "
        "Use this to clean up when a terminal is no longer needed."
    )
    args_schema: Type[BaseModel] = DeleteTerminalInput
    return_direct: bool = False

    def _run(
        self,
        terminal_id: str,
        kill_processes: bool = True,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Delete a terminal."""
        manager = get_terminal_manager()
        
        try:
            success = manager.delete_terminal(terminal_id, kill_processes=kill_processes)
            if success:
                return f"Terminal {terminal_id} has been deleted successfully."
            else:
                return f"No terminal found with ID: {terminal_id}"
                
        except Exception as e:
            raise ToolException(f"Error deleting terminal: {str(e)}")


def get_terminal_tools() -> List[BaseTool]:
    """
    Get a list of all terminal tools that can be used with Langchain agents.
    
    Returns:
        List of BaseTool instances for terminal operations
    """
    return [
        CreateTerminalTool(),
        RunCommandTool(),
        ListTerminalsTool(),
        GetTerminalHistoryTool(),
        ListProcessesTool(),
        KillProcessTool(),
        GetProcessOutputTool(),
        SendInputToProcessTool(),
        DeleteTerminalTool(),
    ]


def get_terminal_toolkit(base_dir: str = None) -> Dict[str, Tool]:
    """
    Get a dictionary of terminal tools for use with Langchain.
    
    Args:
        base_dir: Base directory for terminal operations
        
    Returns:
        Dictionary mapping tool names to Tool instances
    """
    # Initialize the terminal manager with custom base directory if provided
    if base_dir:
        get_terminal_manager(base_dir=base_dir)
    
    # Create a dict of tools
    tools = {}
    for tool in get_terminal_tools():
        tools[tool.name] = tool
    
    return tools


if __name__ == "__main__":
    # Example usage
    import sys
    from langchain.agents import AgentType, initialize_agent
    from langchain.chains import LLMChain
    from langchain_openai import ChatOpenAI
    
    # Example prompt
    prompt_template = """You are a terminal assistant that helps users execute commands.
    
    Available tools:
    - create_terminal: Create a new terminal session
    - run_command: Run a command in a terminal
    - list_terminals: List available terminals
    - list_processes: List running processes
    - get_process_output: Get output from a process
    - kill_process: Kill a process
    - delete_terminal: Delete a terminal
    
    User question: {input}
    """
    
    # Create LLM and tools
    try:
        llm = ChatOpenAI(temperature=0)
        tools = get_terminal_tools()
        
        # Create an agent with the tools
        agent = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
        
        # Interact with the agent
        if len(sys.argv) > 1:
            query = " ".join(sys.argv[1:])
        else:
            query = "Create a new terminal and run the command 'ls -la'"
            
        print(f"Query: {query}")
        result = agent.run(query)
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error initializing agent (this is just a demonstration): {str(e)}")
        
        # Fallback to direct tool usage
        print("\nDemonstrating direct tool usage:")
        term_tool = CreateTerminalTool()
        terminal_id = term_tool._run()
        print(terminal_id)
        
        term_id = terminal_id.split(":")[1].split("\n")[0].strip()
        run_tool = RunCommandTool()
        result = run_tool._run(terminal_id=term_id, command="ls -la")
        print(result)
