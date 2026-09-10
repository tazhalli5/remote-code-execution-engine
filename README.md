# Remote Code Execution (RCE) Engine

A distributed, secure Remote Code Execution Engine designed to compile and execute untrusted user code (Python, JavaScript, C++) safely inside isolated, ephemeral Docker containers. Built with FastAPI, Celery, Redis, and PostgreSQL.

---

## Key Features

* **Multi-Language Support:** Compiles and executes Python 3, JavaScript (Node.js), and C++ workloads.
* **Hardened Docker Sandboxing:**
  * **Memory Limits:** Restricted to `128MB` per run to prevent Out-Of-Memory (OOM) host crashes.
  * **CPU Limits:** Hard limit set to `0.5 CPUs` (`nano_cpus=500000000`) to prevent single-script CPU starvation.
  * **Network Isolation:** Runs with `network_mode="none"` to block external connections and SSRF attempts.
  * **Execution Timeouts:** Hard 5-second execution limit with automated container termination to stop infinite loops.
* **Distributed Architecture:** Asynchronous task queue powered by Celery and Redis to handle workloads without blocking HTTP threads.
* **WebSocket Notifications:** Integrates FastAPI WebSockets to stream final execution results directly to the UI upon completion.
* **Persistent History:** Saves submission states (`PENDING`, `SUCCESS`, `FAILED`) and execution output using PostgreSQL and SQLAlchemy.

---

---

## Tech Stack

* **Backend Framework:** FastAPI (Python 3.11)
* **Task Queue & Broker:** Celery, Redis
* **Database:** PostgreSQL, SQLAlchemy
* **Containerization & Sandboxing:** Docker, Docker Compose
* **Frontend:** HTML5, CSS3, JavaScript (Fetch API, WebSockets)

---

## Getting Started

### Prerequisites

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose) installed.
* Git installed.

---
### Quickstart Setup

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/tazhalli5/remote-code-execution-engine.git](https://github.com/tazhalli5/remote-code-execution-engine.git)
   cd remote-code-execution-engine
   ```
   ```
2.**Start Services via Docker Compose:**
  ```bash
  docker compose -f compose-docker.yml up -d --build
  ```
3.**Verify Service Health:**
  ```bash
  docker compose -f compose-docker.yml ps
  ```
4.**Access the Web Interface:**
 ```bash
    http://localhost:8000
 ```
