FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" sentence-transformers qdrant-client httpx
# Cache buster: 1
COPY src/ src/
CMD ["uvicorn", "src.retrieval_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
