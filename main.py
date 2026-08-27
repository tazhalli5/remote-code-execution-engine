from fastapi import FastAPI
from pydantic import BaseModel

app=FastAPI(title="Remote Code Execution Engine")

class CodeSubmission(BaseModel):
    code:str
    language:str="python"

@app.get("/")
def health_check():
    return {"status":"ok","message":"Remote Code Execution Engine Running"}

@app.post("/submit")  
def submit_code(submission:CodeSubmission):
    return{
        "status":"success",
        "message":"code submmited successfully",
        "submmitted_code":submission.code,

    }