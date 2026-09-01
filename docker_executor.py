import docker
from requests.exceptions import ReadTimeout
from docker.errors import APIError

# Map supported languages to their Docker image and execution command
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
            "sh", "-c",
            f'echo \'{code.replace("\'", "\'\\\'\'")}\' > /tmp/solution.cpp && g++ /tmp/solution.cpp -o /tmp/solution && /tmp/solution'
        ]
    }
}


def run_in_docker(code: str, language: str = "python", timeout: int = 5) -> dict:
    lang = language.lower()
    
    # Check if language is supported
    if lang not in LANGUAGE_CONFIG:
        return {
            "success": False,
            "output": f"Language '{language}' is not supported."
        }

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
            "output": output_text if output_text else ("Execution completed." if success else "Execution failed.")
        }

    except (ReadTimeout, APIError, Exception):
        
        try:
            container.kill()
        except Exception:
            pass
        return {
            "success": False,
            "output": f"Error: Execution timed out ({timeout}s limit reached)."
        }

    finally:
        
        try:
            container.remove(force=True)
        except Exception:
            pass