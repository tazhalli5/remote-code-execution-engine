from fastapi import FastAPI, HTTPException, Depends, status
from starlette.requests import Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import redis
from fastapi.security.api_key import APIKeyHeader
from task import celery_app, execute_code_task


import models
from database import engine, get_db

from task import celery_app, execute_code_task

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Remote Code Execution Engine")

redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

def rate_limit(request: Request):
    limit: int = 5
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

SUPPORTED_LANGUAGES = ["python", "javascript", "cpp"]

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Remote Code Execution Engine Running"}

@app.post("/run", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(rate_limit)])
def run_code(submission: CodeSubmission):
    if submission.language.lower() not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Choose from: {SUPPORTED_LANGUAGES}"
        )

    
    task = execute_code_task.delay(submission.code, submission.language)

    return {
        "task_id": task.id,
        "status": "Processing",
        "message": "Task queued successfully. Check results at /result/{task_id}"
    }

@app.get("/result/{task_id}")
def get_task_result(task_id: str):
    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "PENDING", "result": None}
    elif task_result.state == "SUCCESS":
        return {"task_id": task_id, "status": "SUCCESS", "result": task_result.result}
    elif task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "FAILURE", "error": str(task_result.info)}
    
    return {"task_id": task_id, "status": task_result.state}

@app.get("/submissions")
def get_submissions(limit: int = 10, db: Session = Depends(get_db)):
    return db.query(models.Submission).order_by(models.Submission.id.desc()).limit(limit).all()