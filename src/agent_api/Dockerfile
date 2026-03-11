FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.6" \
    "temporalio>=1.7.1" \
    "langgraph>=0.2.0" \
    "httpx>=0.27.0" \
    "redis>=5.0.0" \
    "sse-starlette>=2.0.0" \
    "prometheus-client>=0.20.0"
# Cache buster 1
COPY src/ src/
CMD ["uvicorn", "src.agent_api.main:app", "--host", "0.0.0.0", "--port", "8003"]
