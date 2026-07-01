#!/usr/bin/env python3

import subprocess, os, psutil, argparse, time

root_path = os.getcwd()
python_path = "/usr/local/lib/python3.12/python3.12"

watched_command = f"{python_path} {root_path}"
bash_dir = os.path.join(root_path, "start_api.sh")
print(bash_dir)

def restart_webhook():
    """
    Restart the server.
    """
    try:
        print("Restarting server...")
        if os.name == 'nt':
            # For Windows, use 'start' to run the script in a new process
            process = subprocess.Popen(
                [bash_dir],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            # For Unix-like systems, use 'bash' to run the script
            process = subprocess.Popen(
                ["bash", bash_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error restarting webhook server: {stderr.decode()}")
            raise subprocess.CalledProcessError(process.returncode, "bash", output=stdout, stderr=stderr)

        print("Webhook server restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error restarting webhook server: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def get_python_processes(command):
    # Iterate over all running processes
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            # Check if the process name or command line contains 'python'
            cmdline = proc.info["cmdline"]
            if command in " ".join(cmdline):
                print(f"Found Python process: {proc.info['pid']} - {' '.join(cmdline)}")
                return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            print(f"Error accessing process info for PID {proc.info['pid']}")
        except Exception as e:
            print(f"Error accessing process info: {e}")
            
    print("No Python processes found matching the command.")
    return True

def get_command_process(command: str) -> list:
    process = []
    
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if command in " ".join(cmdline):
                print(f"Found Python process: {proc.info['pid']} - {' '.join(cmdline)}")
                process.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            print(f"Error accessing process info for PID {proc.info['pid']}")
        except Exception as e:
            print(f"Error accessing process info: {e}")
    return process

def args_parser():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(description="Alice API Restarter")
    parser.add_argument(
        "--restart",
        type=bool,
        default=False,
        help="True / False to restart the webhook server"
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
    if args.restart:
        process = get_command_process(watched_command)
        restart_webhook()
        time.sleep(1)
        for proc in process:
            kill_pid(proc.info['pid'])
            
    print("Starting Alice API Restarter...")
    if get_python_processes(watched_command):
        restart_webhook()
    print("Webhook Restarter finished.")
