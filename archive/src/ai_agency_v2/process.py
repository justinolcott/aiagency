"""
Process management module for handling long-running processes
"""
import os
import signal
import subprocess
import threading
import time
import logging
import datetime
from typing import Dict, Any, Optional, Callable, Tuple, List, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProcessStatus:
    """Process status constants"""
    RUNNING = "running"
    STOPPED = "stopped"
    FINISHED = "finished"
    FAILED = "failed"
    UNKNOWN = "unknown"

# Output stream types
class OutputType:
    """Output stream type constants"""
    STDOUT = "stdout"
    STDERR = "stderr"
    SYSTEM = "system"  # For system messages (not from process)

class Process:
    """
    Represents a single running process that can be managed, including long-running processes.
    """
    def __init__(
        self,
        command: str,
        working_dir: str,
        env_vars: Dict[str, str] = None,
        process_id: str = None,
        background: bool = False,
        on_output: Optional[Callable[[str, str, str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ):
        """
        Initialize a new Process.
        
        Args:
            command: The command to run
            working_dir: Working directory for the process
            env_vars: Environment variables
            process_id: Optional unique ID (generated if not provided)
            background: Whether this is a background process
            on_output: Callback function for process output. 
                       Signature: fn(line: str, output_type: str, process_id: str)
            on_exit: Callback function for process exit
        """
        from uuid import uuid4
        
        self.process_id = process_id or str(uuid4())
        self.command = command
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.background = background
        self.on_output = on_output
        self.on_exit = on_exit
        
        self.process: Optional[subprocess.Popen] = None
        self.status = ProcessStatus.STOPPED
        self.exit_code: Optional[int] = None
        self.output_buffer = []
        self.error_buffer = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # List of additional output listeners added after initialization
        self._output_listeners: List[Callable[[str, str, str], None]] = []
        
        self._output_thread = None
        self._error_thread = None
        self._monitor_thread = None
        self._stopping = False
        
        logger.info(f"Process {self.process_id} created for command: {command}")
    
    def add_output_listener(self, listener: Callable[[str, str, str], None]) -> None:
        """
        Add a listener for real-time output from the process.
        
        Args:
            listener: Callback function that takes (line, output_type, process_id)
                     where output_type is 'stdout' or 'stderr'
        """
        if listener not in self._output_listeners:
            self._output_listeners.append(listener)
    
    def remove_output_listener(self, listener: Callable[[str, str, str], None]) -> bool:
        """
        Remove an output listener.
        
        Args:
            listener: The callback function to remove
            
        Returns:
            True if listener was found and removed, False otherwise
        """
        if listener in self._output_listeners:
            self._output_listeners.remove(listener)
            return True
        return False
    
    def _notify_output(self, line: str, output_type: str) -> None:
        """
        Notify all listeners of new output.
        
        Args:
            line: The output line
            output_type: Type of output ('stdout' or 'stderr')
        """
        # Call the main output callback if defined
        if self.on_output:
            self.on_output(line, output_type, self.process_id)
            
        # Call all registered listeners
        for listener in self._output_listeners:
            try:
                listener(line, output_type, self.process_id)
            except Exception as e:
                logger.error(f"Error in output listener: {str(e)}")
    
    def start(self) -> bool:
        """
        Start the process.
        
        Returns:
            True if process started successfully, False otherwise
        """
        if self.process and self.status == ProcessStatus.RUNNING:
            logger.warning(f"Process {self.process_id} is already running")
            return False
            
        try:
            # Create a new process group so we can manage it as a group
            env = {**os.environ, **self.env_vars}
            
            # Add PYTHONUNBUFFERED=1 to force unbuffered output for Python processes
            if "python" in self.command.lower():
                env["PYTHONUNBUFFERED"] = "1"
            
            # Start the process - use universal_newlines instead of text for better compatibility
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if not self.background else subprocess.DEVNULL,
                cwd=self.working_dir,
                env=env,
                universal_newlines=True,  # Use universal_newlines for better cross-platform handling
                bufsize=1,  # Line buffering - smaller buffer size for more real-time output
                preexec_fn=os.setsid  # Create a new process group
            )
            
            self.start_time = time.time()
            self.status = ProcessStatus.RUNNING
            self._stopping = False
            
            # Notify of process start via system message
            start_msg = f"Process started with PID {self.process.pid}"
            self._notify_output(start_msg, OutputType.SYSTEM)
            
            # Start threads to collect output
            self._output_thread = threading.Thread(
                target=self._read_output,
                args=(self.process.stdout, self.output_buffer, OutputType.STDOUT),
                daemon=True
            )
            self._error_thread = threading.Thread(
                target=self._read_output,
                args=(self.process.stderr, self.error_buffer, OutputType.STDERR),
                daemon=True
            )
            self._monitor_thread = threading.Thread(
                target=self._monitor_process,
                daemon=True
            )
            
            self._output_thread.start()
            self._error_thread.start()
            self._monitor_thread.start()
            
            logger.info(f"Process {self.process_id} started with PID {self.process.pid}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to start process: {str(e)}"
            logger.error(f"Failed to start process {self.process_id}: {str(e)}")
            self._notify_output(error_msg, OutputType.SYSTEM)
            self.status = ProcessStatus.FAILED
            return False

    def _read_output(self, pipe, buffer, output_type):
        """Read output from the process and store in buffer"""
        while self.process and self.status == ProcessStatus.RUNNING:
            try:
                # Use read(1) to read character by character for real-time output
                # This is slower but more responsive than readline()
                line = ""
                char = pipe.read(1)
                
                # If pipe is closed, break
                if not char:
                    break
                    
                # Collect characters until we find a newline
                while char and char != '\n':
                    line += char
                    char = pipe.read(1)
                    if not char:  # End of file
                        break
                
                # Add newline if we found one
                if char == '\n':
                    line += '\n'
                
                if line:  # Only process if we have some text
                    buffer.append(line)
                    self._notify_output(line, output_type)
            except (BrokenPipeError, IOError, ValueError) as e:
                # Pipe was closed or process ended
                logger.debug(f"Pipe error in process {self.process_id}: {str(e)}")
                break
                
        logger.debug(f"Read output thread ending for process {self.process_id} (type: {output_type})")
    
    def _monitor_process(self):
        """Monitor the process and update status when it exits"""
        if not self.process:
            return
            
        exit_code = self.process.wait()
        self.exit_code = exit_code
        self.end_time = time.time()
        
        if self._stopping:
            self.status = ProcessStatus.STOPPED
            exit_msg = f"Process stopped with exit code {exit_code}"
        else:
            self.status = ProcessStatus.FINISHED if exit_code == 0 else ProcessStatus.FAILED
            exit_msg = f"Process {'completed successfully' if exit_code == 0 else 'failed'} with exit code {exit_code}"
        
        # Notify of process exit via system message
        self._notify_output(exit_msg, OutputType.SYSTEM)
        
        logger.info(f"Process {self.process_id} exited with code {exit_code}")
        
        if self.on_exit:
            self.on_exit(exit_code)
    
    def send_input(self, input_text: str) -> bool:
        """
        Send input to the process stdin.
        
        Args:
            input_text: Text to send to the process
            
        Returns:
            True if input was sent, False if process is not running
        """
        if not self.process or self.status != ProcessStatus.RUNNING:
            return False
            
        try:
            self.process.stdin.write(input_text + "\n")
            self.process.stdin.flush()
            return True
        except:
            return False
    
    def stop(self, timeout: int = 5) -> bool:
        """
        Stop the process gracefully (SIGTERM), then forcefully (SIGKILL) if it doesn't exit.
        
        Args:
            timeout: Seconds to wait before sending SIGKILL
            
        Returns:
            True if process was stopped, False if it wasn't running
        """
        if not self.process or self.status != ProcessStatus.RUNNING:
            return False
            
        self._stopping = True
        self._notify_output("Sending stop signal to process...", OutputType.SYSTEM)
        
        try:
            # Send SIGTERM to the process group
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            
            # Wait for the process to exit
            for _ in range(timeout):
                if self.process.poll() is not None:
                    break
                time.sleep(1)
            
            # If still running, send SIGKILL
            if self.process.poll() is None:
                self._notify_output("Process didn't respond to SIGTERM, sending SIGKILL...", OutputType.SYSTEM)
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=2)
            
            self._notify_output("Process stopped successfully", OutputType.SYSTEM)
            logger.info(f"Process {self.process_id} stopped")
            return True
        except Exception as e:
            error_msg = f"Error stopping process: {str(e)}"
            self._notify_output(error_msg, OutputType.SYSTEM)
            logger.error(f"Error stopping process {self.process_id}: {str(e)}")
            return False
    
    def is_running(self) -> bool:
        """Check if the process is currently running"""
        if not self.process:
            return False
            
        # Check if process has exited
        if self.process.poll() is not None and self.status == ProcessStatus.RUNNING:
            # Process exited but status wasn't updated by monitor thread
            self.status = ProcessStatus.FINISHED if self.process.returncode == 0 else ProcessStatus.FAILED
            self.exit_code = self.process.returncode
            return False
            
        return self.status == ProcessStatus.RUNNING
    
    def get_output(self) -> str:
        """Get the current output of the process"""
        return "".join(self.output_buffer)
    
    def get_error(self) -> str:
        """Get the current error output of the process"""
        return "".join(self.error_buffer)
    
    def get_combined_output(self) -> str:
        """Get combined stdout and stderr output"""
        return self.get_output() + self.get_error()
    
    def get_runtime(self) -> float:
        """Get the runtime in seconds"""
        if not self.start_time:
            return 0
            
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert process to dictionary for serialization"""
        return {
            "process_id": self.process_id,
            "command": self.command,
            "working_dir": self.working_dir,
            "env_vars": self.env_vars,
            "background": self.background,
            "status": self.status,
            "exit_code": self.exit_code,
            "output": self.get_output(),
            "error": self.get_error(),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "runtime": self.get_runtime(),
            "pid": self.process.pid if self.process else None,
        }

    def __str__(self) -> str:
        """String representation of the process"""
        status_str = f"[{self.status.upper()}]"
        if self.status != ProcessStatus.RUNNING:
            status_str += f" (exit: {self.exit_code})" if self.exit_code is not None else ""
        
        runtime = self.get_runtime()
        runtime_str = f"{runtime:.1f}s" if runtime < 60 else f"{runtime/60:.1f}m"
        
        return f"Process {self.process_id} {status_str} {runtime_str}: {self.command}"

if __name__ == "__main__":
    # Example usage with output monitoring
    def on_output_handler(line: str, output_type: str, process_id: str):
        prefix = {
            OutputType.STDOUT: "[OUT]",
            OutputType.STDERR: "[ERR]",
            OutputType.SYSTEM: "[SYS]"
        }.get(output_type, "[???]")
        print(f"{prefix} {line.rstrip()}")

    def on_exit_handler(exit_code: int):
        print(f"Process finished with exit code {exit_code}")

    # Create a process that runs a Python loop printing "hello" every 1 second for 5 seconds
    process = Process(
        command='python -c "import time\nfor i in range(5):\n  print(\'hello\')\n  time.sleep(1)"',
        working_dir="/mnt/pccfs2/backed_up/justinolcott/aiagency/src/agent_workspace/tmp/terminals",
        on_output=on_output_handler,
        on_exit=on_exit_handler
    )
    
    process.start()
    
    try:
        # Wait for user interrupt
        while process.is_running():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping process...")
        process.stop()