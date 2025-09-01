
import time
import subprocess

while True:
    print("Test_Server_Loop.py - Starting test server, press Ctrl+C to restart the server.")
    try:
        subprocess.run(["python", "root-app.py"])
    except KeyboardInterrupt:
        print("\n\n\nTest_Server_Loop.py - Stopping test server, press Ctrl+C to stop the server.")
        time.sleep(1.5)
        continue