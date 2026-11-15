"""Start both local services and stop them together with Ctrl+C."""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")
    children = []
    try:
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "monitor.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=ROOT,
                env=env,
            )
        )
        children.append(
            subprocess.Popen(["npm", "--prefix", "frontend", "run", "dev"], cwd=ROOT, env=env)
        )
        print("SARScope: http://127.0.0.1:5173 — Ctrl+C stops both services.", flush=True)
        while all(p.poll() is None for p in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in children:
            if p.poll() is None:
                p.terminate()
        for p in children:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    main()
