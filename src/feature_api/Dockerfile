FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" "feast[redis]" pandas pyarrow psycopg2-binary
COPY src/ src/
CMD ["uvicorn", "src.feature_api.main:app", "--host", "0.0.0.0", "--port", "8002"]
