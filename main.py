import tempfile
import os
import subprocess
import sys
from fastapi import FastAPI,HTTPException,Depends
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session

import models
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app=FastAPI(title="Remote Code Execution Engine")

class CodeSubmission(BaseModel):
    code:str
    language:str="python"

@app.get("/")
def health_check():
    return {"status":"ok","message":"Remote Code Execution Engine Running"}

@app.post("/run")
def run_code(submission:CodeSubmission , db: Session = Depends(get_db)):
    if submission.language.lower()!="python":
        raise HTTPException(status_code=400,detail="only python code supported")
    file_path = None
    output = None
    success = False
    exit_code = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as temp_file:
            temp_file.write(submission.code)
            file_path = temp_file.name
        result = subprocess.run(
            ["python", file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        success = result.returncode == 0
        exit_code = result.returncode

    except subprocess.TimeoutExpired:
        output = "Error: Code execution timed out (5s limit exceeded)."
        success = False

    except Exception as err:
        output = f"{type(err).__name__}: {str(err)}"
        success = False

    finally:
        if file_path:
            os.remove(file_path)


    db_record = models.Submission(
        code=submission.code,
        language=submission.language,
        output=output,
        success=success
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