FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx pydantic
COPY src/agent_api_stub/ src/agent_api_stub/
CMD ["uvicorn", "src.agent_api_stub.main:app", "--host", "0.0.0.0", "--port", "8000"]
