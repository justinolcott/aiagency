"""
Terminal Manager for managing multiple terminals with proper process handling
"""
import os
import json
import logging
import atexit
import signal
import time
from typing import Dict, List, Optional, Any, Set, Callable, Tuple

from terminal import Terminal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TerminalManager:
    """
    Manages multiple terminal instances with options to save and load sessions.
    Provides proper handling of long-running processes.
    """
    _instance = None  # Singleton instance
    
    @classmethod
    def get_instance(cls, *args, **kwargs):
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        return cls._instance
    
    def __init__(
        self,
        default_base_dir: str = "/tmp",
        default_timeout: int = 30,
        default_max_history: int = 100,
        default_env_vars: Dict[str, str] = None,
        auto_save: bool = True,
        auto_save_interval: int = 60,  # seconds
    ):
        if TerminalManager._instance is not None:
            logger.warning("TerminalManager instance already exists, use get_instance() instead")
        else:
            TerminalManager._instance = self
            
        self.terminals: Dict[str, Terminal] = {}
        self.default_base_dir = default_base_dir
        self.save_dir = os.path.join(default_base_dir, "terminals")
        
        # Default settings for all terminals
        self.default_timeout = default_timeout
        self.default_max_history = default_max_history
        self.default_env_vars = default_env_vars or {}
        
        # Auto-save settings
        self.auto_save = auto_save
        self.auto_save_interval = auto_save_interval
        self._last_save_time = 0
        
        # Create the save directory if it doesn't exist
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Register cleanup function to run on exit
        atexit.register(self._cleanup)
        
        logger.info(f"Terminal manager initialized with save directory: {self.save_dir}")
        
        # Try to load existing terminals
        self.load_all_terminals()
        
        # Start auto-save if enabled
        if self.auto_save:
            self._start_auto_save()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        # Define signal handler
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down gracefully")
            self._cleanup()
            os._exit(0)
        
        # Register signals
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, signal_handler)
    
    def _cleanup(self):
        """Clean up resources on shutdown"""
        logger.info("Terminal manager cleaning up resources")
        
        # Save all terminals
        if self.auto_save:
            self.save_all_terminals()
            
        # Kill all running processes
        for terminal_id, terminal in list(self.terminals.items()):
            logger.info(f"Shutting down terminal {terminal_id}")
            terminal.kill_all_processes(include_background=True)
    
    def _start_auto_save(self):
        """Start a background thread for auto-saving"""
        import threading
        
        def auto_save_worker():
            while True:
                time.sleep(self.auto_save_interval)
                
                # Check if we need to save
                current_time = time.time()
                if current_time - self._last_save_time >= self.auto_save_interval:
                    logger.debug(f"Auto-saving terminals...")
                    self.save_all_terminals()
                    self._last_save_time = current_time
        
        # Start the auto-save thread
        thread = threading.Thread(target=auto_save_worker, daemon=True)
        thread.start()
        logger.info(f"Auto-save started with interval: {self.auto_save_interval} seconds")
    
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
        if self.auto_save:
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
    
    def run_command(
        self, 
        terminal_id: str, 
        command: str, 
        timeout: int = None,
        background: bool = False,
        output_callback: Optional[Callable[[str, str, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Run a command on a specific terminal.
        
        Args:
            terminal_id: ID of the terminal to run the command on
            command: The command to execute
            timeout: Command timeout (None uses terminal's default)
            background: Whether to run as a background process
            output_callback: Optional callback for real-time process output
                            Function signature: fn(line, output_type, process_id)
            
        Returns:
            Result of the command execution
            
        Raises:
            ValueError: If terminal_id doesn't exist
        """
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            raise ValueError(f"Terminal with ID {terminal_id} not found")
        
        result = terminal.execute_command(
            command, 
            timeout=timeout, 
            background=background,
            output_callback=output_callback
        )
        
        # Save terminal state after command execution if needed
        if self.auto_save:
            self.save_terminal(terminal.terminal_id)
        
        return result
    
    def delete_terminal(self, terminal_id: str, kill_processes: bool = True) -> bool:
        """
        Delete a terminal instance.
        
        Args:
            terminal_id: ID of the terminal to delete
            kill_processes: Whether to kill all processes before deleting
            
        Returns:
            True if terminal was deleted, False if not found
        """
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            return False
            
        # Kill all processes if requested
        if kill_processes:
            terminal.kill_all_processes(include_background=True)
            
        # Remove from dict of terminals
        del self.terminals[terminal_id]
            
        # Remove saved file if exists
        save_path = os.path.join(self.save_dir, f"{terminal_id}.json")
        if os.path.exists(save_path):
            os.remove(save_path)
                
        logger.info(f"Deleted terminal with ID: {terminal_id}")
        return True
    
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
            self._last_save_time = time.time()
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
        for terminal_id in list(self.terminals.keys()):
            if self.save_terminal(terminal_id):
                count += 1
        
        logger.info(f"Saved {count} terminals to {self.save_dir}")
        self._last_save_time = time.time()
        return count
    
    def get_process(self, process_id: str) -> Tuple[Optional[Terminal], Optional[Any]]:
        """
        Find a process by ID across all terminals.
        
        Args:
            process_id: ID of the process to find
            
        Returns:
            A tuple of (terminal, process) if found, (None, None) otherwise
        """
        for terminal in self.terminals.values():
            process = terminal.get_process(process_id)
            if process:
                return (terminal, process)
        
        return (None, None)
    
    def kill_process(self, process_id: str) -> bool:
        """
        Kill a process by ID across all terminals.
        
        Args:
            process_id: ID of the process to kill
            
        Returns:
            True if process was killed, False if not found
        """
        terminal, _ = self.get_process(process_id)
        if terminal:
            return terminal.kill_process(process_id)
        return False
    
    def kill_all_processes(self, include_background: bool = True) -> int:
        """
        Kill all running processes across all terminals.
        
        Args:
            include_background: Whether to kill background processes
            
        Returns:
            Number of processes killed
        """
        count = 0
        for terminal in self.terminals.values():
            count += terminal.kill_all_processes(include_background)
        return count
    
    def list_all_processes(self, all_processes: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all processes across all terminals.
        
        Args:
            all_processes: If True, include completed processes
            
        Returns:
            Dictionary mapping terminal IDs to lists of process dictionaries
        """
        result = {}
        for terminal_id, terminal in self.terminals.items():
            processes = terminal.list_processes(all_processes)
            if processes:
                result[terminal_id] = processes
        return result
    
    def send_input_to_process(self, process_id: str, input_text: str) -> bool:
        """
        Send input to a process by ID across all terminals.
        
        Args:
            process_id: ID of the process
            input_text: Text to send to the process
            
        Returns:
            True if input was sent, False if process not found or not running
        """
        terminal, _ = self.get_process(process_id)
        if terminal:
            return terminal.send_input_to_process(process_id, input_text)
        return False
    
    def add_process_output_listener(self, process_id: str, listener: Callable[[str, str, str], None]) -> bool:
        """
        Add a listener for real-time output from a process across all terminals.
        
        Args:
            process_id: ID of the process to monitor
            listener: Callback function for output
            
        Returns:
            True if listener was added, False if process not found
        """
        terminal, _ = self.get_process(process_id)
        if terminal:
            return terminal.add_process_output_listener(process_id, listener)
        return False
    
    def remove_process_output_listener(self, process_id: str, listener: Callable[[str, str, str], None]) -> bool:
        """
        Remove a listener from a process across all terminals.
        
        Args:
            process_id: ID of the process
            listener: The callback function to remove
            
        Returns:
            True if listener was removed, False otherwise
        """
        terminal, _ = self.get_process(process_id)
        if terminal:
            return terminal.remove_process_output_listener(process_id, listener)
        return False
    
    def show_terminal(self, terminal_id: str) -> str:
        """
        Get the current status of a terminal as a formatted string.
        
        Args:
            terminal_id: ID of the terminal to show
            
        Returns:
            A string format with what a human might see the terminal as
        """
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            return f"Error: Terminal with ID {terminal_id} not found"
        
        status = terminal.get_status()
        history = terminal.get_history()
        processes = terminal.list_processes(all_processes=True)
        
        # Build the output string
        output = []
        output.append(f"Terminal ID: {status['terminal_id']}")
        output.append(f"Current Directory: {status['current_dir']}")
        output.append(f"Base Directory: {status['base_dir']}")
        output.append(f"History Length: {status['history_length']}")
        output.append(f"Running Processes: {status['running_processes']}")
        output.append(f"Background Processes: {status['background_processes']}")
        output.append(f"Created At: {status['created_at']}")
        output.append("")
        
        if processes:
            output.append("Active Processes:")
            for proc in processes:
                if proc['status'] == 'running':
                    runtime = proc.get('runtime', 0)
                    runtime_str = f"{runtime:.1f}s" if runtime < 60 else f"{runtime/60:.1f}m"
                    output.append(f"  - {proc['process_id']} ({runtime_str}): {proc['command']}")
            output.append("")
        
        if history:
            output.append("Recent Command History:")
            # Show most recent commands first, limited to 10
            for entry in reversed(history[-10:]):
                cmd = entry['command']
                dir_path = entry['directory']
                timestamp = entry['timestamp'].split('T')[-1].split('.')[0]  # Just time part
                output.append(f"  [{timestamp}] {dir_path}$ {cmd}")
                
                # Truncate output if too long
                out = entry['output']
                if len(out) > 500:
                    out = out[:500] + "... [output truncated]"
                if out:
                    output.append(f"  Output: {out}")
                output.append("")
                
        return "\n".join(output)


# Example usage
if __name__ == "__main__":
    # Create the terminal manager
    manager = TerminalManager(
        default_base_dir="/mnt/pccfs2/backed_up/justinolcott/aiagency/src/agent_workspace/tmp",
        default_env_vars={"CUSTOM_VAR": "test_value"},
        auto_save=True,
        auto_save_interval=30
    )
    
    # Example 1: Basic terminal usage
    print("=== Example 1: Basic Terminal Usage ===")
    
    # Create a new terminal
    terminal = manager.create_terminal()
    
    # Run some commands
    result = manager.run_command(terminal.terminal_id, "pwd")
    print(f"Command: {result['command']}")
    print(f"Output: {result['output']}")
    
    result = manager.run_command(terminal.terminal_id, "echo $CUSTOM_VAR")
    print(f"Command: {result['command']}")
    print(f"Output: {result['output']}")
    
    # Example 2: Long-running background process
    print("\n=== Example 2: Long-running Background Process ===")
    
    # Run a background process (simple HTTP server)
    result = manager.run_command(terminal.terminal_id, "python -m http.server 8888", background=True)
    print(f"Started background process: {result['process_id']}")
    
    # Wait a bit for the server to start
    time.sleep(2)
    
    # Check if it's running
    terminal_obj = manager.get_terminal(terminal.terminal_id)
    process = terminal_obj.get_process(result['process_id'])
    print(f"Process is running: {process.is_running()}")
    
    # Get process output
    output = terminal_obj.get_process_output(result['process_id'])
    print(f"Process output: {output}")
    
    # Example 3: Managing multiple terminals
    print("\n=== Example 3: Managing Multiple Terminals ===")
    
    # Create another terminal
    terminal2 = manager.create_terminal()
    
    # Run a command in the second terminal
    result = manager.run_command(terminal2.terminal_id, "echo 'Hello from terminal 2'")
    print(f"Output from terminal 2: {result['output']}")
    
    # List all terminals
    terminals = manager.list_terminals()
    print(f"Active terminals: {len(terminals)}")
    for term in terminals:
        print(f"  - {term['terminal_id']}: {term['current_dir']} (Processes: {term['running_processes']})")
    
    # Example 4: Terminal cleanup
    print("\n=== Example 4: Terminal Cleanup ===")
    
    # Kill all processes in the first terminal
    count = terminal_obj.kill_all_processes()
    print(f"Killed {count} processes in terminal {terminal.terminal_id}")
    
    # Delete the second terminal
    manager.delete_terminal(terminal2.terminal_id)
    print(f"Deleted terminal {terminal2.terminal_id}")
    
    # Show the remaining terminal status
    print(manager.show_terminal(terminal.terminal_id))

