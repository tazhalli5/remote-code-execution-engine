import tempfile
import os
import subprocess
import sys
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel

app=FastAPI(title="Remote Code Execution Engine")

class CodeSubmission(BaseModel):
    code:str
    language:str="python"

@app.get("/")
def health_check():
    return {"status":"ok","message":"Remote Code Execution Engine Running"}

@app.post("/run")
def run_code(submission:CodeSubmission):
    if submission.language.lower()!="python":
        raise HTTPException(status_code=400,detail="only python code supported")
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as temp_file:
        temp_file.write(submission.code)
        file_path = temp_file.name

    try:
        result = subprocess.run(
            ["python", file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout if result.returncode == 0 else result.stderr

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "output": output
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Error: Code execution timed out (5s limit exceeded)."
        }
    except Exception as err:
        return {
            "success": False,
            "output": f"{type(err).__name__}: {str(err)}"
        }
    finally:
        os.remove(file_path)

    

