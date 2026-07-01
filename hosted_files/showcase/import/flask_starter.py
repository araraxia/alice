#!/usr/bin/env python3

import subprocess, os, psutil, argparse, time, platform, ctypes
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Normalize paths for comparison - use forward slashes consistently
venv_python = str((ROOT_DIR / ".venv" / "Scripts" / "python.exe").as_posix())
flask_entry = str((ROOT_DIR / "src" / "application.py").as_posix())

print(f"Looking for process: {venv_python} running {flask_entry}")

# Determine which start script to use based on platform
if platform.system() == "Windows":
    # Use bash script on Windows - it has proper nohup for background processes
    # PowerShell scripts have issues with subprocess.Popen and detached processes
    start_script = ROOT_DIR / "start_api.sh"
    if not start_script.exists():
        start_script = ROOT_DIR / "start_api.ps1"  # Fallback to PowerShell
else:
    start_script = ROOT_DIR / "start_api.sh"

print(f"Using start script: {start_script}")


def is_admin():
    """Check if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def restart_flask():
    """
    Restart the Meno Helper Webhook server.
    """
    try:
        print("Restarting webhook server...")

        # Check if running as admin
        if platform.system() == "Windows":
            admin_status = (
                "with Administrator privileges"
                if is_admin()
                else "WITHOUT Administrator privileges"
            )
            print(f"Current process is running {admin_status}")

        # For PowerShell scripts on Windows
        if str(start_script).endswith(".ps1"):
            # Run PowerShell script with NoElevate flag (since we're already elevated if needed)
            command = [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(start_script),
                "-NoElevate",  # Don't try to elevate again, use current privileges
            ]
            print(f"Executing command: {' '.join(command)}")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS,
            )
        else:
            # For bash scripts
            process = subprocess.Popen(
                [str(start_script)],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS,
            )

        # Don't wait for detached process - let it run in background
        print(f"Started background process, not waiting for completion")
        print("Webhook server restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error restarting webhook server: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def is_flask_running():
    """
    Check if the Flask webhook server is already running.
    Returns: (bool, list) - (is_running, list_of_processes)
    """
    flask_processes = []

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if not cmdline:
                continue

            # Convert cmdline to forward slashes for comparison
            cmdline_str = " ".join(cmdline).replace("\\", "/").lower()

            # Check if this is our Flask process
            # Look for both python.exe and Meno_Helper_Webhook.py in the command
            if (venv_python.lower() in cmdline_str or "python.exe" in cmdline_str) and (
                flask_entry.lower() in cmdline_str
                or "meno_helper_webhook.py" in cmdline_str
            ):
                print(
                    f"Found Flask process: PID {proc.info['pid']} - {' '.join(cmdline)}"
                )
                flask_processes.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Skip processes we can't access
            pass
        except Exception as e:
            # Skip processes with errors
            pass

    if flask_processes:
        print(f"Flask is already running with {len(flask_processes)} instance(s)")
        return True, flask_processes
    else:
        print("No Flask processes found")
        return False, []


def get_python_processes(command):
    """Deprecated - use is_flask_running() instead"""
    is_running, processes = is_flask_running()
    return not is_running  # Return True if NOT running (for legacy compatibility)


def get_command_process(command: str) -> list:
    """Get Flask processes - returns list of processes"""
    is_running, processes = is_flask_running()
    return processes


def args_parser():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(description="Meno Helper Webhook Restarter")
    parser.add_argument(
        "--restart",
        type=bool,
        default=False,
        help="True / False to restart the webhook server",
    )
    return parser.parse_args()


def kill_pid(pid):
    """
    Kill a process by its PID.
    """
    try:
        p = psutil.Process(pid)
        p.terminate()
        p.wait(timeout=5)
        print(f"Process {pid} terminated successfully.")
    except psutil.NoSuchProcess:
        print(f"Process {pid} does not exist.")
    except psutil.AccessDenied:
        print(f"Access denied to terminate process {pid}.")
    except Exception as e:
        print(f"Error terminating process {pid}: {e}")


if __name__ == "__main__":
    args = args_parser()

    print("Starting Meno Helper Webhook Restarter...")
    print("=" * 60)

    # Check if Flask is currently running
    is_running, existing_processes = is_flask_running()

    if args.restart:
        print("\nRestart mode: Will kill existing processes and start new instance")

        # Start new instance first
        restart_flask()
        time.sleep(2)  # Give it time to start

        # Then kill old instances
        for proc in existing_processes:
            print(f"Killing old process: PID {proc.info['pid']}")
            kill_pid(proc.info["pid"])

    else:
        # Normal start mode
        if is_running:
            print("\nFlask is already running!")
            print("Found existing processes:")
            for proc in existing_processes:
                print(f"  - PID: {proc.info['pid']}")
            print("\nTo restart, use: python src/webhook_starter.py --restart True")
            print("Exiting without starting a new instance.")
        else:
            print("\nNo existing Flask process found. Starting new instance...")
            restart_flask()

    print("=" * 60)
    print("Webhook Restarter finished.")
