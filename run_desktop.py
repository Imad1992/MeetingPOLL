import sys
import os
import time
import socket
import subprocess

# Auto-install pywebview if not present
try:
    import webview
except ImportError:
    print("Installing pywebview for desktop window support...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])
        import webview
    except Exception as e:
        print(f"Could not install pywebview: {e}. Falling back to default browser.")
        webview = None

# Helper to find a free port
def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def main():
    host = "127.0.0.1"
    port = 8000
    
    # Check if port 8000 is in use, if so find a free one
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
    except socket.error:
        # Port 8000 is busy, find another free port
        port = find_free_port()
        print(f"Port 8000 is busy. Using port {port}...")

    # Start FastAPI server in an isolated subprocess to prevent thread starvation
    print("Starting backend server...")
    cmd = [
        sys.executable, 
        "-m", "uvicorn", 
        "app:app", 
        "--host", host, 
        "--port", str(port), 
        "--log-level", "warning"
    ]
    
    # Ensure Cwd is in python path for the subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))
    
    server_process = subprocess.Popen(cmd, env=env)
    
    # Give the server a moment to spin up
    time.sleep(1.5)
    
    url = f"http://{host}:{port}"
    print(f"Server is responding at {url}")
    
    if webview:
        try:
            # Launch native desktop application window
            print("Launching desktop application 'POLL'...")
            webview.create_window(
                title="MeetingPOLL",
                url=url,
                width=1280,
                height=850,
                resizable=True,
                min_size=(800, 600)
            )
            webview.start()
        finally:
            print("Desktop window closed. Stopping backend server...")
            server_process.terminate()
            server_process.wait()
            print("Server stopped. Exiting.")
    else:
        # Fallback to web browser
        import webbrowser
        print("Launching default web browser...")
        webbrowser.open(url)
        print("Press Ctrl+C in this terminal to exit.")
        try:
            server_process.wait()
        except KeyboardInterrupt:
            print("Stopping backend server...")
            server_process.terminate()
            server_process.wait()
            print("Server stopped. Exiting.")

if __name__ == "__main__":
    main()
