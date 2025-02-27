"""
Example demonstrating real-time output monitoring for long-running processes.
"""
import sys
import os
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_agency_v2.terminal_manager import TerminalManager
from src.ai_agency_v2.process import OutputType

def main():
    # Create the terminal manager
    manager = TerminalManager(
        default_base_dir="/mnt/pccfs2/backed_up/justinolcott/aiagency/src/agent_workspace/tmp",
        default_env_vars={"CUSTOM_VAR": "test_value"},
        auto_save=True
    )
    
    # Example: Using real-time output monitoring with JavaScript development server
    
    # Create a real-time output handler
    def real_time_output_handler(line, output_type, process_id):
        prefix = {
            OutputType.STDOUT: "📝",
            OutputType.STDERR: "❌",
            OutputType.SYSTEM: "🔧"
        }.get(output_type, "?")
        
        # You could filter or process output here
        if output_type == OutputType.STDERR and "error" in line.lower():
            print(f"\033[91m{prefix} ERROR: {line.strip()}\033[0m")  # Red for errors
        elif output_type == OutputType.STDOUT:
            if "warning" in line.lower():
                print(f"\033[93m{prefix} {line.strip()}\033[0m")  # Yellow for warnings
            else:
                print(f"\033[92m{prefix} {line.strip()}\033[0m")  # Green for regular output
        else:
            print(f"{prefix} {line.strip()}")
    
    # Create a terminal
    terminal = manager.create_terminal()
    print(f"Created terminal with ID: {terminal.terminal_id}")
    
    # Start a long-running development server
    print("Starting development server with real-time output monitoring...")
    result = manager.run_command(
        terminal.terminal_id,
        # Example command - replace with real command as needed
        'python -c "import time; import sys; '
        'print(\'Server starting...\', flush=True); '
        'for i in range(10): '
        '    if i % 3 == 0: '
        '        sys.stderr.write(f\'Warning: Test error {i}\\n\'); '
        '        sys.stderr.flush(); '
        '    else: '
        '        print(f\'Server log: Processing request {i}\', flush=True); '
        '    time.sleep(1); '
        'print(\'Server stopped.\', flush=True)"',
        background=True,
        output_callback=real_time_output_handler
    )
    
    process_id = result["process_id"]
    print(f"Started background process with ID: {process_id}")
    
    # Wait for the process to finish or user interrupt
    try:
        terminal_obj = manager.get_terminal(terminal.terminal_id)
        process = terminal_obj.get_process(process_id)
        
        print("Press Ctrl+C to stop the server...")
        while process.is_running():
            time.sleep(0.1)
            
        print(f"Process completed with exit code: {process.exit_code}")
        
    except KeyboardInterrupt:
        print("\nStopping server...")
        terminal_obj.kill_process(process_id)
        print("Server stopped.")
    
    # Clean up
    print("Cleaning up...")
    manager.delete_terminal(terminal.terminal_id)
    print("Done.")

if __name__ == "__main__":
    main()
