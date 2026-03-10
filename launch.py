import subprocess
import sys
import webbrowser
import time

def install_requirements():
    print("Ensuring dependencies are installed...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def launch_server():
    print("Launching Uvicorn server...")
    # Open the browser slightly after starting the server
    webbrowser.open("http://localhost:8000")
    # Start the server (blocking)
    subprocess.check_call([sys.executable, "-m", "uvicorn", "app:app", "--host", "localhost", "--port", "8000", "--reload"])

if __name__ == "__main__":
    try:
        install_requirements()
        launch_server()
    except KeyboardInterrupt:
        print("\nShutting down Instagram Framer...")
    except Exception as e:
        print(f"Error launching: {e}")
