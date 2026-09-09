import os
import base64
import docker
from celery import Celery
from requests.exceptions import ReadTimeout
from docker.errors import APIError

from database import SessionLocal
from models import Submission

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

celery_app = Celery(
    "task",
    broker=f"redis://{REDIS_HOST}:6379/0",
    backend=f"redis://{REDIS_HOST}:6379/0"
)

def get_python_command(code: str, stdin: str = "") -> list[str]:
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    stdin_b64 = base64.b64encode((stdin or "").encode("utf-8")).decode("utf-8")
    
    cmd = (
        f"printf '%s' '{code_b64}' | base64 -d > /tmp/solution.py && "
        f"printf '%s' '{stdin_b64}' | base64 -d > /tmp/input.txt && "
        f"python3 /tmp/solution.py < /tmp/input.txt"
    ) if stdin else (
        f"printf '%s' '{code_b64}' | base64 -d > /tmp/solution.py && "
        f"python3 /tmp/solution.py < /dev/null"
    )
    return ["sh", "-c", cmd]

def get_cpp_command(code: str, stdin: str = "") -> list[str]:
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    stdin_b64 = base64.b64encode((stdin or "").encode("utf-8")).decode("utf-8")
    
    cmd = (
        f"printf '%s' '{code_b64}' | base64 -d > /tmp/solution.cpp && "
        f"printf '%s' '{stdin_b64}' | base64 -d > /tmp/input.txt && "
        f"g++ /tmp/solution.cpp -o /tmp/solution && "
        f"chmod +x /tmp/solution && "
        f"/tmp/solution < /tmp/input.txt"
    ) if stdin else (
        f"printf '%s' '{code_b64}' | base64 -d > /tmp/solution.cpp && "
        f"g++ /tmp/solution.cpp -o /tmp/solution && "
        f"chmod +x /tmp/solution && "
        f"/tmp/solution < /dev/null"
    )
    return ["sh", "-c", cmd]

def get_js_command(code: str, stdin: str = "") -> list[str]:
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    stdin_b64 = base64.b64encode((stdin or "").encode("utf-8")).decode("utf-8")
    
    cmd = (
        f"printf '%s' '{code_b64}' | base64 -d > /tmp/solution.js && "
        f"printf '%s' '{stdin_b64}' | base64 -d > /tmp/input.txt && "
        f"node /tmp/solution.js < /tmp/input.txt"
    ) if stdin else (
        f"printf '%s' '{code_b64}' | base64 -d > /tmp/solution.js && "
        f"node /tmp/solution.js < /dev/null"
    )
    return ["sh", "-c", cmd]

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "command": get_python_command
    },
    "javascript": {
        "image": "node:20-slim",
        "command": get_js_command
    },
    "cpp": {
        "image": "gcc:latest",
        "command": get_cpp_command
    }
}

@celery_app.task(name="execute_code_task")
def execute_code_task(submission_id: int, code: str, language: str = "python", stdin: str = "", timeout: int = 5) -> dict:
    lang = language.lower()
    if lang not in LANGUAGE_CONFIG:
        db = SessionLocal()
        try:
            sub = db.query(Submission).filter(Submission.id == submission_id).first()
            if sub:
                sub.status = "FAILED"
                sub.output = f"Unsupported language: '{language}'"
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        return {"submission_id": submission_id, "success": False, "output": f"Unsupported language: '{language}'"}

    config = LANGUAGE_CONFIG[lang]
    client = docker.from_env()

    try:
        container = client.containers.run(
            image=config["image"],
            command=config["command"](code, stdin),
            network_mode="none",
            mem_limit="128m",
            nano_cpus=500000000,
            pids_limit=64,
            read_only=True,
            tmpfs={
                '/tmp': 'rw,exec,nosuid,size=64m'
            },
            detach=True,
            remove=False
        )

        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", 1)
            output_text = container.logs(stdout=True, stderr=True).decode("utf-8")
            
            success = (exit_code == 0)
            output = output_text if output_text.strip() else ("Execution succeeded." if success else "Execution failed.")
        except (ReadTimeout, APIError, Exception):
            try:
                container.kill()
            except Exception:
                pass
            success = False
            output = f"Error: Code execution timed out ({timeout}s limit reached)."
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass

    except Exception as e:
        success = False
        output = f"Container Runtime Error: {str(e)}"

    db = SessionLocal()
    try:
        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if sub:
            sub.status = "SUCCESS" if success else "FAILED"
            sub.output = output
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return {
        "submission_id": submission_id,
        "success": success,
        "output": output
    }