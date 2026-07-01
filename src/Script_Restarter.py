#!/usr/bin/env python3
# Aria Corona - February 17th, 2025
# This script is used to check for currently running python scripts and what arguments they were run with,
# compare them against a list of scripts, and starting any that are not currently running.

import psutil, json, logging, os, subprocess

# Init logging
log_path = os.path.join("logs", "script_restarter.log")
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# Set up console handler for debug logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))

# Add the console handler to the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Set the root logger's level to DEBUG
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

# Load the configuration file
conf_path = os.path.join("conf", "restart_scripts.json")
with open(conf_path, "r") as f:
    restart_scripts = json.load(f)

# Output the loaded configuration to console
logger.debug("Arguments loaded from configuration file:")
for i, script in enumerate(restart_scripts, start=1):
    msg = f"Arguments: {script}" if i < len(restart_scripts) else f"Arguments: {script}\n"
    logger.debug(msg)

def start_script(script_cmd):
    logger.info(f"Starting {script_cmd}")
    try:
        # Start the script with the specified arguments
        subprocess.Popen(
        script_cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    except Exception as e:
        logger.error(f"Failed to start script {script_cmd}: {e}", exc_info=True)

def get_python_processes():
    python_processes = []
    commands = []
    
    # Iterate over all running processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if the process name or command line contains 'python'
            cmdline = proc.info['cmdline']
            if 'python' in proc.info['name'].lower() or (cmdline and 'python' in ' '.join(cmdline).lower()):
                python_processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception as e:
            logger.error(f"Error accessing process info: {e}", exc_info=True)   

    # Get the list of arguments for Python processes
    if (python_processes):
        logger.debug("Currently running Python processes:")
        for proc in python_processes:
            logger.debug(f"PID: {proc['pid']}, Name: {proc['name']}, Command Line: {' '.join(proc['cmdline'])}")
            commands.append(' '.join(proc['cmdline']))
    else:
        logger.debug("No Python processes are currently running.")
        
    return commands

def main():
    commands = get_python_processes()
        
    for script in restart_scripts:
        if script not in commands:
            logger.debug(f"Script not running: {script}")
            start_script(script)

if __name__ == "__main__":
    main()