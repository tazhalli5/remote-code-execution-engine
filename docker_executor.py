import docker

def run_in_docker(code: str, timeout: int = 5) -> dict:
    client = docker.from_env()

    container = client.containers.run(
        image="python:3.11-slim",
        command=["python", "-c", code],
        network_mode="none",
        mem_limit="128m",
        nano_cpus=500000000,
        detach=True,
        remove=False
    )

    try:
        result = container.wait(timeout=timeout)
        exit_code = result.get("StatusCode")
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
        success = exit_code == 0
        output = stdout if success else (stderr if stderr else "Execution failed.")
        return {"success": success, "output": output}

    except Exception:
        container.kill()
        return {"success": False, "output": f"Error: Execution timed out ({timeout}s limit exceeded)."}

    finally:
        container.remove()