"""Run FastAPI backend and Vite frontend together for local development."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def _npm_executable() -> str | None:
    for name in ("npm", "pnpm", "yarn"):
        path = shutil.which(name)
        if path:
            return path
    return None


def main() -> None:
    npm = _npm_executable()
    if not npm:
        print("Error: npm, pnpm, or yarn not found in PATH.", file=sys.stderr)
        sys.exit(1)

    if not (FRONTEND / "node_modules").is_dir():
        print(
            "Error: frontend dependencies missing. Run: cd frontend && npm install",
            file=sys.stderr,
        )
        sys.exit(1)

    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "backend.main"],
        cwd=ROOT,
    )
    frontend_proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=FRONTEND,
    )
    procs: list[subprocess.Popen[bytes]] = [backend_proc, frontend_proc]

    def terminate_children() -> None:
        for p in procs:
            if p.poll() is None:
                p.terminate()

    exit_code = 0
    try:
        while True:
            if backend_proc.poll() is not None:
                print("Backend process exited.", file=sys.stderr)
                exit_code = backend_proc.returncode or 0
                break
            if frontend_proc.poll() is not None:
                print("Frontend process exited.", file=sys.stderr)
                exit_code = frontend_proc.returncode or 0
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        exit_code = 130
    finally:
        terminate_children()
        for p in procs:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
