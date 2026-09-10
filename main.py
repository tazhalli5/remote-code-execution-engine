import os
import asyncio
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from celery import Celery
from database import engine, Base, get_db
from models import Submission
from sqlalchemy.orm import Session
from task import execute_code_task
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)


app = FastAPI(title="Remote Code Execution Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
celery_app = Celery("task", broker=f"redis://{REDIS_HOST}:6379/0", backend=f"redis://{REDIS_HOST}:6379/0")

class CodeExecutionRequest(BaseModel):
    code: str
    language: str = "python"

class SubmissionCreate(BaseModel):
    language: str
    code: str
    stdin: Optional[str] = ""

@app.get("/", include_in_schema=False)
def serve_index():
    base_dir = os.path.dirname(os.path.realpath(__file__))
    index_path = os.path.join(base_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.post("/run", status_code=status.HTTP_202_ACCEPTED)
def submit_code(payload: CodeExecutionRequest):
    supported_languages = ["python", "javascript", "cpp"]
    if payload.language.lower() not in supported_languages:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported language '{payload.language}'. Supported: {supported_languages}"
        )

    task = celery_app.send_task(
        "execute_code_task", 
        args=[0, payload.code, payload.language.lower()]
    )
    
    return {
        "task_id": task.id,
        "status": "QUEUED",
        "message": "Execution request accepted and queued."
    }
@app.get("/api/v1/submissions")
def get_submissions(db: Session = Depends(get_db)):
    submissions = db.query(Submission).order_by(Submission.id.desc()).all()
    return submissions
@app.post("/api/v1/submissions", status_code=status.HTTP_202_ACCEPTED)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    new_submission = Submission(
        language=payload.language,
        code=payload.code,
        stdin=payload.stdin,
        status="PENDING"
    )
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)

    execute_code_task.apply_async(
        args=[new_submission.id, payload.code, payload.language, payload.stdin],
        task_id=str(new_submission.id)
    )

    return {"submission_id": str(new_submission.id), "status": "PENDING"}

@app.delete("/api/v1/submissions")
def clear_submission_history(db: Session = Depends(get_db)):
    db.query(Submission).delete()
    db.commit()
    return {"message": "History cleared"}

@app.get("/result/{task_id}")
def get_execution_result(task_id: str):
    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "PENDING", "message": "Task is processing or queued."}
    elif task_result.state == "SUCCESS":
        res = task_result.result or {}
        is_ok = res.get("success", False) if isinstance(res, dict) else False
        return {
            "task_id": task_id, 
            "status": "SUCCESS" if is_ok else "FAILED", 
            "result": res
        }
    elif task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "FAILURE", "error": str(task_result.info)}

    return {"task_id": task_id, "status": task_result.state}

@app.websocket("/ws/submissions/{submission_id}")
async def websocket_submission_stream(websocket: WebSocket, submission_id: str, db: Session = Depends(get_db)):
    await websocket.accept()
    await websocket.send_json({"status": "PENDING", "message": "Executing code inside isolated container..."})
    
    while True:
        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        
        task_result = celery_app.AsyncResult(submission_id)
        
        if task_result.state == "SUCCESS":
            res = task_result.result or {}
            is_ok = res.get("success", False) if isinstance(res, dict) else False
            out = res.get("output", "") if isinstance(res, dict) else str(res)
            final_status = "SUCCESS" if is_ok else "FAILED"
            
            if sub:
                sub.status = final_status
                sub.output = out
                db.commit()

            await websocket.send_json({
                "status": final_status, 
                "output": out
            })
            break
            
        elif task_result.state == "FAILURE":
            err_msg = str(task_result.info)
            if sub:
                sub.status = "FAILED"
                sub.output = err_msg
                db.commit()

            await websocket.send_json({"status": "FAILED", "output": err_msg})
            break
            
        await asyncio.sleep(0.5)