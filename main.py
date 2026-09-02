import docker
from fastapi import FastAPI, HTTPException, Depends, Security
from starlette.requests import Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from requests.exceptions import ReadTimeout
from docker.errors import APIError
import redis
from requests.exceptions import RequestException
from fastapi.security.api_key import APIKeyHeader


import models
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Remote Code Execution Engine")


redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


API_KEY = "my-secret-key-123"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(header_key: str = Security(api_key_header)):
    if header_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid or missing API key."
        )


def rate_limit(request: Request):
    limit: int = 5,
    window_seconds: int = 60
    client_ip = request.client.host
    redis_key = f"rate_limit:{client_ip}"

    try:
        current_requests = redis_client.incr(redis_key)
        if current_requests == 1:
            redis_client.expire(redis_key, window_seconds)

        if current_requests > limit:
            ttl = redis_client.ttl(redis_key)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {ttl} seconds."
            )
    except redis.RedisError:

        pass

class CodeSubmission(BaseModel):
    code: str
    language: str = "python"


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

def run_in_docker(code: str, language: str = "python", timeout: int = 5) -> dict:
    lang = language.lower()
    if lang not in LANGUAGE_CONFIG:
        return {"success": False, "output": f"Unsupported language: '{language}'"}

    config = LANGUAGE_CONFIG[lang]
    client = docker.from_env()

    container = client.containers.run(
        image=config["image"],
        command=config["command"](code),
        network_mode="none",
        mem_limit="128m",
        nano_cpus=500000000,
        detach=True,
        remove=False
    )

    try:
        result = container.wait(timeout=timeout)
        exit_code = result.get("StatusCode", 1)
        output_text = container.logs().decode("utf-8")
        success = (exit_code == 0)

        return {
            "success": success,
            "output": output_text if output_text else ("Execution succeeded." if success else "Execution failed.")
        }
    except (ReadTimeout, APIError, Exception):
        try:
            container.kill()
        except Exception:
            pass
        return {"success": False, "output": f"Error: Code execution timed out ({timeout}s limit reached)."}
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Remote Code Execution Engine Running"}

SUPPORTED_LANGUAGES = ["python", "javascript", "cpp"]

@app.post("/run", dependencies=[Depends(rate_limit)])
def run_code(
    submission: CodeSubmission,
    db: Session = Depends(get_db)
):
    if submission.language.lower() not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Choose from: {SUPPORTED_LANGUAGES}"
        )

    result = run_in_docker(submission.code, language=submission.language)

    db_record = models.Submission(
        code=submission.code,
        language=submission.language,
        output=result["output"],
        success=result["success"]
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)

    return {
        "id": db_record.id,
        "success": db_record.success,
        "output": db_record.output,
        "created_at": db_record.created_at
    }

@app.get("/submissions")
def get_submissions(limit: int = 10, db: Session = Depends(get_db)):
    return db.query(models.Submission).order_by(models.Submission.id.desc()).limit(limit).all()