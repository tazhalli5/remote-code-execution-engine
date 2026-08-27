import io
import os
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
    buffer=io.StringIO()
    sys.stdout=buffer

    try:
        scope = {}
        exec(submission.code, scope)
        output = buffer.getvalue()
        
        return {
            "success": True,
            "output": output
        }
    except Exception as err:
        return {
            "success": False,
            "output": f"{type(err).__name__}: {str(err)}"
        }

    finally:
        sys.stdout=sys.__stdout__


    

