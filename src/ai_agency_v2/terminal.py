"""TERMINAL
- Ideally the terminal would be able to be saved and loaded, so the agents can continue where they left off. Almost like tmux.
- The terminal would be able to run commands and display the output.
- The tools would be like new terminal, new command, ls command, and delete.
- so we would have a terminal manager that has a list of terminals running. It can create a new terminal, run a command on a terminal, delete a terminal, and list all terminals. When a new command is run, it would be added to the terminal's history as well as the output. The output is also sent to the agent.
"""

import os
import uuid
import signal
import json
import logging
import datetime
import atexit
import weakref
from typing import Dict, List, Tuple, Optional, Any, Set, Callable

from process import Process, ProcessStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Terminal:
    """
    A class representing a terminal session with command history and output.
    Supports long-running processes.
    """
    def __init__(
        self, 
        terminal_id: str = None,
        base_dir: str = "/tmp",
        timeout: int = 30,
        max_history: int = 100,
        env_vars: Dict[str, str] = None,
    ):
        self.terminal_id = terminal_id if terminal_id else str(uuid.uuid4())
        self.base_dir = base_dir
        self.current_dir = base_dir
        self.timeout = timeout
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.env_vars = env_vars or {}
        self.created_at = datetime.datetime.now().isoformat()
        
        # Track all processes launched by this terminal
        self.processes: Dict[str, Process] = {}
        self.background_processes: Set[str] = set()
        
        # Create the directory if it doesn't exist
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Register cleanup on terminal object destruction
        self._finalizer = weakref.finalize(self, self._cleanup)
        
        logger.info(f"Terminal {self.terminal_id} initialized in {self.base_dir}")
        
    def _cleanup(self):
        """Clean up resources when terminal is destroyed"""
        logger.info(f"Terminal {self.terminal_id} cleaning up processes")
        for process_id, process in list(self.processes.items()):
            if process.is_running():
                logger.info(f"Stopping process {process_id} during terminal cleanup")
                process.stop()
                
    def execute_command(
        self, 
        command: str, 
        timeout: int = None, 
        background: bool = False,
        output_callback: Optional[Callable[[str, str, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute a command in the terminal and store the result in history.
        
        Args:
            command: The command to execute
            timeout: Time in seconds to wait for completion (None = no timeout)
            background: Whether to run as background process
            output_callback: Callback for real-time output from the process
                            Function signature: fn(line, output_type, process_id)
            
        Returns:
            A dictionary containing the command, output, and other info
        """
        logger.info(f"Terminal {self.terminal_id}: Executing command '{command}' (background={background})")
        
        # Handle cd commands specially to change the current directory
        if command.strip().startswith("cd "):
            return self._handle_cd_command(command)
        
        # Handle environment variable setting
        if self._is_env_var_command(command):
            return self._handle_env_var_command(command)
        
        # Handle background command format "command &"
        if command.strip().endswith(" &") and not background:
            command = command[:-2].strip()
            background = True
            
        # Create a new process with output handling
        def on_output(line, output_type, proc_id):
            # Store in the terminal's history (we could optimize to avoid duplicates)
            # Forward to the callback if provided
            if output_callback:
                output_callback(line, output_type, proc_id)
        
        process = Process(
            command=command,
            working_dir=self.current_dir,
            env_vars=self.env_vars,
            background=background,
            on_output=on_output
        )
        
        # Store the process
        self.processes[process.process_id] = process
        if background:
            self.background_processes.add(process.process_id)
        
        # Start the process
        if not process.start():
            output = f"Error: Failed to start process for command '{command}'"
            exit_code = -1
            
            # Create result and add to history
            result = {
                "command": command,
                "output": output,
                "exit_code": exit_code,
                "directory": self.current_dir,
                "timestamp": datetime.datetime.now().isoformat(),
                "process_id": process.process_id,
                "background": background
            }
            
            self.history.append(result)
            return result
            
        # For foreground processes, wait for completion or timeout
        if not background:
            if timeout is None:
                timeout = self.timeout
                
            # Wait for the specified timeout
            wait_time = 0
            interval = 0.1  # Check every 0.1 seconds
            
            while process.is_running() and (timeout is None or wait_time < timeout):
                wait_time += interval
                import time
                time.sleep(interval)
                
            # If still running and we have a timeout, stop the process
            if process.is_running() and timeout is not None:
                logger.info(f"Command timed out after {timeout} seconds, sending stop signal")
                process.stop()
                
            output = process.get_combined_output()
            exit_code = process.exit_code or -1
        else:
            # For background processes, return immediately
            output = f"Process started in background with ID: {process.process_id}"
            exit_code = 0
        
        # Create result and add to history
        result = {
            "command": command,
            "output": output,
            "exit_code": exit_code,
            "directory": self.current_dir,
            "timestamp": datetime.datetime.now().isoformat(),
            "process_id": process.process_id,
            "background": background
        }
        
        self.history.append(result)
        
        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
            
        return result
    
    def add_process_output_listener(self, process_id: str, listener: Callable[[str, str, str], None]) -> bool:
        """
        Add a listener for real-time output from a specific process.
        
        Args:
            process_id: ID of the process to monitor
            listener: Callback function that receives (line, output_type, process_id)
            
        Returns:
            True if listener was added successfully, False otherwise
        """
        process = self.get_process(process_id)
        if not process:
            return False
            
        process.add_output_listener(listener)
        return True
    
    def remove_process_output_listener(self, process_id: str, listener: Callable[[str, str, str], None]) -> bool:
        """
        Remove a listener from a specific process.
        
        Args:
            process_id: ID of the process
            listener: The callback function to remove
            
        Returns:
            True if listener was removed, False otherwise
        """
        process = self.get_process(process_id)
        if not process:
            return False
            
        return process.remove_output_listener(listener)
    
    def _is_env_var_command(self, command: str) -> bool:
        """Check if command is setting an environment variable"""
        cmd = command.strip()
        return (
            cmd.startswith("export ") and "=" in cmd or
            "=" in cmd and not any(c in cmd for c in " \t|&;<>()$`\\\"'*?[]#~=%")
        )

    def _handle_env_var_command(self, command: str) -> Dict[str, Any]:
        """Handle setting environment variables"""
        cmd = command.strip()
        
        try:
            if cmd.startswith("export "):
                # Handle export VAR=value
                var_part = cmd[7:].strip()
                if "=" in var_part:
                    name, value = var_part.split("=", 1)
                    # Remove quotes if present
                    if value and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    self.env_vars[name.strip()] = value
                    output = f"Environment variable {name} set to {value}"
                    exit_code = 0
                else:
                    output = f"Invalid export command: {cmd}"
                    exit_code = 1
            else:
                # Handle VAR=value
                name, value = cmd.split("=", 1)
                # Remove quotes if present
                if value and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                self.env_vars[name.strip()] = value
                output = f"Environment variable {name} set to {value}"
                exit_code = 0
        except Exception as e:
            output = f"Error setting environment variable: {str(e)}"
            exit_code = 1
        
        # Create the result and add to history
        result = {
            "command": command,
            "output": output,
            "exit_code": exit_code,
            "directory": self.current_dir,
            "timestamp": datetime.datetime.now().isoformat(),
            "process_id": None,
            "background": False
        }
        
        self.history.append(result)
        return result
    
    def _handle_cd_command(self, command: str) -> Dict[str, Any]:
        """Handle cd commands to change the current directory."""
        # Extract the target directory
        parts = command.strip().split(" ", 1)
        if len(parts) < 2:
            target_dir = os.path.expanduser("~")  # Default to home dir
        else:
            target_dir = parts[1].strip()
        
        # Handle relative paths
        if not os.path.isabs(target_dir):
            target_dir = os.path.join(self.current_dir, target_dir)
        
        # Normalize the path
        target_dir = os.path.normpath(target_dir)
        
        # Check if the directory exists
        if os.path.isdir(target_dir):
            prev_dir = self.current_dir
            self.current_dir = target_dir
            output = f"Changed directory from {prev_dir} to {target_dir}"
            exit_code = 0
        else:
            output = f"Directory not found: {target_dir}"
            exit_code = 1
        
        # Create the result and add to history
        result = {
            "command": command,
            "output": output,
            "exit_code": exit_code,
            "directory": self.current_dir,
            "timestamp": datetime.datetime.now().isoformat(),
            "process_id": None,
            "background": False
        }
        
        self.history.append(result)
        return result
    
    def list_processes(self, all_processes: bool = False) -> List[Dict[str, Any]]:
        """
        List all running processes or all processes based on parameter.
        
        Args:
            all_processes: If True, include completed processes
            
        Returns:
            List of process dictionaries
        """
        result = []
        for pid, process in self.processes.items():
            if all_processes or process.is_running():
                result.append(process.to_dict())
        return result
    
    def get_process(self, process_id: str) -> Optional[Process]:
        """Get a process by its ID"""
        return self.processes.get(process_id)
    
    def kill_process(self, process_id: str) -> bool:
        """
        Kill a specific process.
        
        Args:
            process_id: ID of the process to kill
            
        Returns:
            True if process was killed, False otherwise
        """
        process = self.get_process(process_id)
        if not process:
            return False
            
        if process.is_running():
            process.stop()
            
        if process_id in self.background_processes:
            self.background_processes.remove(process_id)
            
        return True
    
    def kill_all_processes(self, include_background: bool = True) -> int:
        """
        Kill all running processes launched by this terminal.
        
        Args:
            include_background: If True, also kill background processes
            
        Returns:
            Number of processes killed
        """
        count = 0
        for pid, process in list(self.processes.items()):
            if process.is_running():
                if include_background or pid not in self.background_processes:
                    process.stop()
                    count += 1
                    
        return count
    
    def get_process_output(self, process_id: str) -> Optional[str]:
        """
        Get the latest output from a running process.
        
        Args:
            process_id: ID of the process
            
        Returns:
            The process output or None if process not found
        """
        process = self.get_process(process_id)
        if not process:
            return None
            
        return process.get_combined_output()
    
    def send_input_to_process(self, process_id: str, input_text: str) -> bool:
        """
        Send input to a running process.
        
        Args:
            process_id: ID of the process
            input_text: Text to send to the process
            
        Returns:
            True if input was sent, False otherwise
        """
        process = self.get_process(process_id)
        if not process or not process.is_running():
            return False
            
        return process.send_input(input_text)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the terminal.
        
        Returns:
            A dictionary containing terminal information
        """
        running_processes = sum(1 for p in self.processes.values() if p.is_running())
        background_processes = sum(1 for pid in self.background_processes 
                                  if pid in self.processes and self.processes[pid].is_running())
        
        return {
            "terminal_id": self.terminal_id,
            "current_dir": self.current_dir,
            "base_dir": self.base_dir,
            "history_length": len(self.history),
            "created_at": self.created_at,
            "running_processes": running_processes,
            "background_processes": background_processes
        }
    
    def get_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get the command history.
        
        Args:
            limit: Maximum number of history items to return
            
        Returns:
            List of command history items
        """
        if limit is None or limit > len(self.history):
            return self.history
        return self.history[-limit:]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the terminal to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the terminal
        """
        # We exclude processes from serialization, because they can't be properly serialized/restored
        return {
            "terminal_id": self.terminal_id,
            "base_dir": self.base_dir,
            "current_dir": self.current_dir,
            "timeout": self.timeout,
            "max_history": self.max_history,
            "env_vars": self.env_vars,
            "history": self.history,
            "created_at": self.created_at,
            # We only save the list of running background processes, not the actual process objects
            "background_process_ids": list(self.background_processes)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Terminal':
        """
        Create a terminal instance from a dictionary.
        
        Args:
            data: Dictionary containing terminal data
            
        Returns:
            A new Terminal instance
        """
        terminal = cls(
            terminal_id=data["terminal_id"],
            base_dir=data["base_dir"],
            timeout=data["timeout"],
            max_history=data["max_history"],
            env_vars=data.get("env_vars", {})
        )
        terminal.current_dir = data["current_dir"]
        terminal.history = data["history"]
        terminal.created_at = data["created_at"]
        
        # Restore background process IDs (but not the actual processes)
        terminal.background_processes = set(data.get("background_process_ids", []))
        
        return terminal


class TerminalManager:
    """
    Manages multiple terminal instances with options to save and load sessions.
    """
    def __init__(
        self,
        default_base_dir: str = "/tmp",
        default_timeout: int = 30,
        default_max_history: int = 100,
        default_env_vars: Dict[str, str] = None,
    ):
        self.terminals: Dict[str, Terminal] = {}
        self.default_base_dir = default_base_dir
        self.save_dir = os.path.join(default_base_dir, "terminals")
        
        # Default settings for all terminals
        self.default_timeout = default_timeout
        self.default_max_history = default_max_history
        self.default_env_vars = default_env_vars or {}
        
        # Create the save directory if it doesn't exist
        os.makedirs(self.save_dir, exist_ok=True)
        
        logger.info(f"Terminal manager initialized with save directory: {self.save_dir}")
        
        # Try to load existing terminals
        self.load_all_terminals()
       
    def create_terminal(
        self,
        terminal_id: str = None,
        base_dir: str = None,
        timeout: int = None,
        max_history: int = None,
        env_vars: Dict[str, str] = None,
    ) -> Terminal:
        """
        Create a new terminal instance.
        
        Args:
            terminal_id: Optional ID for the terminal (generated if None)
            base_dir: Base directory for the terminal (uses default if None)
            timeout: Command timeout in seconds (uses default if None)
            max_history: Maximum history entries (uses default if None)
            env_vars: Environment variables (uses default if None)
            
        Returns:
            The created Terminal instance
        """
        # Apply default settings if not provided
        if terminal_id and terminal_id in self.terminals:
            raise ValueError(f"Terminal with ID {terminal_id} already exists")
        
        terminal = Terminal(
            terminal_id=terminal_id,
            base_dir=base_dir or self.default_base_dir,
            timeout=timeout or self.default_timeout,
            max_history=max_history or self.default_max_history,
            env_vars={**self.default_env_vars, **(env_vars or {})}
        )
        
        self.terminals[terminal.terminal_id] = terminal
        logger.info(f"Created new terminal with ID: {terminal.terminal_id}")
        
        # Save the new terminal
        self.save_terminal(terminal.terminal_id)
        
        return terminal
    
    def get_terminal(self, terminal_id: str) -> Optional[Terminal]:
        """
        Get a terminal by its ID.
        
        Args:
            terminal_id: ID of the terminal to retrieve
            
        Returns:
            Terminal instance if found, None otherwise
        """
        return self.terminals.get(terminal_id)
    
    def run_command(self, terminal_id: str, command: str) -> Dict[str, Any]:
        """
        Run a command on a specific terminal.
        
        Args:
            terminal_id: ID of the terminal to run the command on
            command: The command to execute
            
        Returns:
            Result of the command execution
            
        Raises:
            ValueError: If terminal_id doesn't exist
        """
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            raise ValueError(f"Terminal with ID {terminal_id} not found")
        
        result = terminal.execute_command(command)
        
        # Save terminal state after command execution
        self.save_terminal(terminal_id)
        
        return result

    def delete_terminal(self, terminal_id: str) -> bool:
        """
        Delete a terminal instance.
        
        Args:
            terminal_id: ID of the terminal to delete
            
        Returns:
            True if terminal was deleted, False if not found
        """
        if terminal_id in self.terminals:
            del self.terminals[terminal_id]
            
            # Remove saved file if exists
            save_path = os.path.join(self.save_dir, f"{terminal_id}.json")
            if os.path.exists(save_path):
                os.remove(save_path)
                
            logger.info(f"Deleted terminal with ID: {terminal_id}")
            return True
        return False
    
    def list_terminals(self) -> List[Dict[str, Any]]:
        """
        List all terminal instances with their status.
        
        Returns:
            List of terminal status dictionaries
        """
        return [terminal.get_status() for terminal in self.terminals.values()]
    
    def save_terminal(self, terminal_id: str) -> bool:
        """
        Save a terminal's state to disk.
        
        Args:
            terminal_id: ID of the terminal to save
            
        Returns:
            True if successful, False otherwise
        """
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            return False
        
        save_path = os.path.join(self.save_dir, f"{terminal_id}.json")
        try:
            with open(save_path, 'w') as f:
                json.dump(terminal.to_dict(), f, indent=2)
            logger.debug(f"Saved terminal {terminal_id} to {save_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving terminal {terminal_id}: {str(e)}")
            return False
    
    def load_terminal(self, terminal_id: str) -> Optional[Terminal]:
        """
        Load a terminal's state from disk.
        
        Args:
            terminal_id: ID of the terminal to load
            
        Returns:
            Loaded Terminal instance if successful, None otherwise
        """
        save_path = os.path.join(self.save_dir, f"{terminal_id}.json")
        try:
            if os.path.exists(save_path):
                with open(save_path, 'r') as f:
                    data = json.load(f)
                terminal = Terminal.from_dict(data)
                self.terminals[terminal.terminal_id] = terminal
                logger.info(f"Loaded terminal {terminal_id} from {save_path}")
                return terminal
        except Exception as e:
            logger.error(f"Error loading terminal {terminal_id}: {str(e)}")
        
        return None
    
    def load_all_terminals(self) -> int:
        """
        Load all saved terminals from the save directory.
        
        Returns:
            Number of terminals loaded
        """
        count = 0
        if os.path.exists(self.save_dir):
            for filename in os.listdir(self.save_dir):
                if filename.endswith(".json"):
                    terminal_id = filename.replace(".json", "")
                    if self.load_terminal(terminal_id):
                        count += 1
        
        logger.info(f"Loaded {count} terminals from {self.save_dir}")
        return count
    
    def save_all_terminals(self) -> int:
        """
        Save all terminals to disk.
        
        Returns:
            Number of terminals saved
        """
        count = 0
        for terminal_id in self.terminals:
            if self.save_terminal(terminal_id):
                count += 1
        
        logger.info(f"Saved {count} terminals to {self.save_dir}")
        return count

    def show_terminal(self, terminal_id: str) -> Dict[str, Any]:
        """
        Get the current status of a terminal.
        
        Args:
            terminal_id: ID of the terminal to show
            
        Returns:
            A string format with what a human might see the terminal as
        """
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            return {"error": f"Terminal with ID {terminal_id} not found"}
        
        status = terminal.get_status()
        history = terminal.get_history()
        
        terminal_str = ""
        terminal_str += f"Terminal ID: {status['terminal_id']}\n"
        terminal_str += f"Current Directory: {status['current_dir']}\n"
        terminal_str += f"Base Directory: {status['base_dir']}\n"
        terminal_str += f"History Length: {status['history_length']}\n"
        terminal_str += f"Created At: {status['created_at']}\n"
        terminal_str += "\n"
        
        if history:
            terminal_str += "Command History:\n"
            for entry in history:
                terminal_str += f"  Command: {entry['directory']}: {entry['command']}\n"
                terminal_str += f"  Output: {entry['output']}\n"
                terminal_str += "\n"
                
        return terminal_str


# Example usage
if __name__ == "__main__":
    # Create a terminal manager
    manager = TerminalManager(
        default_base_dir="/mnt/pccfs2/backed_up/justinolcott/aiagency/src/agent_workspace/tmp",
        default_env_vars={"CUSTOM_VAR": "test_value"}
    )
    
    # Create a new terminal
    terminal = manager.create_terminal()
    
    # Run some commands
    result = manager.run_command(terminal.terminal_id, "pwd")
    print(f"Command: {result['command']}")
    print(f"Output: {result['output']}")
    
    result = manager.run_command(terminal.terminal_id, "echo $CUSTOM_VAR")
    print(f"Command: {result['command']}")
    print(f"Output: {result['output']}")
    
    # List all terminals
    terminals = manager.list_terminals()
    print(f"Active terminals: {len(terminals)}")
    for term in terminals:
        print(f"  - {term['terminal_id']}: {term['current_dir']}")
        
    # Load a terminal from disk
    loaded_terminal = manager.load_terminal(terminal.terminal_id)
    if loaded_terminal:
        print(f"Loaded terminal: {loaded_terminal.terminal_id}")
        
    # convert to readable format
    print(manager.show_terminal(terminal.terminal_id))