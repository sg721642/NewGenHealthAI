"""
NewGenHealthAI — Local Development Launcher
Authoritative local launcher for starting backend (FastAPI) and frontend (Vite) services.
Eliminates shell-based process execution, runtime version overrides, and orphaned processes.
"""

import os
import sys
import time
import signal
import shutil
import urllib.request
import urllib.error
import subprocess
from typing import Optional, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
IS_WINDOWS = sys.platform == "win32"


def get_python_executable() -> str:
    """Resolve Python executable: prioritize current active virtualenv, then .venv, then sys.executable."""
    # If already running inside a virtualenv
    if sys.prefix != sys.base_prefix:
        return sys.executable

    # Check for local .venv
    local_venv = os.path.join(BASE_DIR, ".venv")
    if os.path.exists(local_venv):
        candidate = (
            os.path.join(local_venv, "Scripts", "python.exe")
            if IS_WINDOWS
            else os.path.join(local_venv, "bin", "python")
        )
        if os.path.exists(candidate):
            return candidate

    return sys.executable


def get_npm_executable() -> str:
    """Resolve npm executable without shell=True."""
    npm_cmd = shutil.which("npm.cmd" if IS_WINDOWS else "npm")
    if not npm_cmd:
        npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
    return npm_cmd


def setup_environment(install_deps: bool = False) -> bool:
    """Prepare local environment directories and optionally install dependencies."""
    # Safe model cache path in project root
    cache_dir = os.path.join(BASE_DIR, "model_cache")
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["HF_HOME"] = cache_dir

    python_exe = get_python_executable()
    npm_bin = get_npm_executable()

    if install_deps:
        req_file = os.path.join(BACKEND_DIR, "requirements.txt")
        if os.path.exists(req_file):
            print(f"[NewGenHealthAI] Installing backend dependencies using {python_exe}...")
            res = subprocess.run([python_exe, "-m", "pip", "install", "-r", req_file])
            if res.returncode != 0:
                print(f"[ERROR] Failed to install backend dependencies (exit code {res.returncode})", file=sys.stderr)
                return False

    # Check frontend dependencies
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.exists(node_modules) or install_deps:
        print("[NewGenHealthAI] Installing frontend dependencies...")
        res = subprocess.run([npm_bin, "install"], cwd=FRONTEND_DIR)
        if res.returncode != 0:
            print(f"[ERROR] Failed to install frontend dependencies (exit code {res.returncode})", file=sys.stderr)
            return False

    return True


def wait_for_backend(url: str = "http://localhost:8000/api/v1/health", max_retries: int = 30, delay: float = 1.0) -> bool:
    """Poll backend health check until ready or timeout."""
    print("[NewGenHealthAI] Waiting for backend to become ready...")
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NewGenHealthAI-Launcher"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    print(f"[NewGenHealthAI] Backend healthy after {attempt}s!")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(delay)
    print(f"[ERROR] Backend failed to respond at {url} within {max_retries * delay:.0f}s", file=sys.stderr)
    return False


def terminate_process(proc: Optional[subprocess.Popen]):
    """Terminate child process cleanly without leaving orphaned workers."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def main():
    install_deps = "--install-deps" in sys.argv or "--setup" in sys.argv
    if not setup_environment(install_deps=install_deps):
        sys.exit(1)

    python_exe = get_python_executable()
    npm_bin = get_npm_executable()

    env = {
        **os.environ,
        "PYTHONPATH": BACKEND_DIR,
        "ALLOW_MODEL_DOWNLOADS": "false",
    }

    backend_cmd: List[str] = [
        python_exe,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]

    backend_proc: Optional[subprocess.Popen] = None
    frontend_proc: Optional[subprocess.Popen] = None

    def shutdown_handler(signum, frame):
        print("\n[NewGenHealthAI] Shutting down services...")
        terminate_process(frontend_proc)
        terminate_process(backend_proc)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        print("[NewGenHealthAI] Starting backend on http://127.0.0.1:8000...")
        backend_proc = subprocess.Popen(backend_cmd, cwd=BACKEND_DIR, env=env)

        if not wait_for_backend():
            print("[ERROR] Aborting launch because backend failed health check.", file=sys.stderr)
            terminate_process(backend_proc)
            sys.exit(1)

        print("[NewGenHealthAI] Starting frontend development server...")
        frontend_cmd: List[str] = [npm_bin, "run", "dev"]
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=FRONTEND_DIR)

        # Wait for frontend process to finish (or Ctrl+C)
        frontend_proc.wait()

    except KeyboardInterrupt:
        print("\n[NewGenHealthAI] Interrupted by user.")
    finally:
        terminate_process(frontend_proc)
        terminate_process(backend_proc)


if __name__ == "__main__":
    main()
