FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    "temporalio>=1.7.1" \
    "langgraph>=0.2.0" \
    "httpx>=0.27.0"
# Cache buster 1
COPY src/ src/
CMD ["python", "-m", "src.agent_worker.temporal.worker"]
