import os
from celery import Celery
import docker
from sqlalchemy.orm import Session
from requests.exceptions import ReadTimeout
from docker.errors import APIError

import models
from database import SessionLocal

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

celery_app = Celery(
    "task",
    broker=f"redis://{REDIS_HOST}:6379/0",
    backend=f"redis://{REDIS_HOST}:6379/0"
)

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "command": lambda code: ["python", "-c", code]
    },
    "javascript": {
        "image": "node:20-slim",
        "command": lambda code: ["node", "-e", code]
    },
    "cpp": {
        "image": "gcc:latest",
        "command": lambda code: [
            "sh",
            "-c",
            f"echo '{code.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}' > /tmp/solution.cpp && g++ /tmp/solution.cpp -o /tmp/solution && /tmp/solution"
        ]
    }
}

@celery_app.task(name="execute_code_task")
def execute_code_task(code: str, language: str = "python", timeout: int = 5) -> dict:
    lang = language.lower()
    if lang not in LANGUAGE_CONFIG:
        return {"success": False, "output": f"Unsupported language: '{language}'"}

    config = LANGUAGE_CONFIG[lang]
    client = docker.from_env()

    try:
        container = client.containers.run(
            image=config["image"],
            command=config["command"](code),
            network_mode="none",             
            mem_limit="128m",                
            nano_cpus=500000000,             
            pids_limit=64,                  
            read_only=True,                  
            cap_drop=["ALL"],                
            tmpfs={'/tmp': 'rw,noexec,nosuid,size=64m'},
            detach=True,
            remove=False
        )

        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", 1)
            output_text = container.logs().decode("utf-8")
            success = (exit_code == 0)
            output = output_text if output_text else ("Execution succeeded." if success else "Execution failed.")
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

    db: Session = SessionLocal()
    try:
        db_record = models.Submission(
            code=code,
            language=language,
            output=output,
            success=success
        )
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        submission_id = db_record.id
    finally:
        db.close()

    return {
        "submission_id": submission_id,
        "success": success,
        "output": output
    }