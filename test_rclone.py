
import subprocess
import sys
import time
import re
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RCLONE_EXE = BASE_DIR / "tools" / "rclone" / "rclone.exe"

def test_interactive_rclone():
    if not RCLONE_EXE.exists():
        print("Rclone executable not found")
        return

    cmd = [
        str(RCLONE_EXE), "config", "create",
        "test_gdrive", "drive",
        "--config", "rclone.conf" # Use a local config for testing purposes
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    print("Process started. Waiting for output...")
    
    start_time = time.time()
    max_wait = 120 # 2 minutes
    url_found = False

    try:
        while True:
            if time.time() - start_time > max_wait:
                print("Timeout waiting for rclone")
                process.terminate()
                break
                
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if line:
                stripped = line.strip()
                print(f"[RCLONE_OUT] {stripped}")
                
                if "http://127.0.0.1" in line and "/auth" in line and not url_found:
                    print("--> Found Auth URL!")
                    match = re.search(r'(http://127\.0\.0\.1:\d+/auth\?state=[\w-]+)', line)
                    if match:
                        url = match.group(1)
                        print(f"--> Extracted URL: {url}")
                        webbrowser.open(url)
                        url_found = True
                    else:
                        print("--> Could not extract URL with regex")

    except KeyboardInterrupt:
        print("Interrupted by user")
        process.terminate()
    finally:
        if process.poll() is None:
            process.terminate()
            
    print(f"Process finished with code: {process.returncode}")

if __name__ == "__main__":
    test_interactive_rclone()
