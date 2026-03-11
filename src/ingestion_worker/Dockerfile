FROM python:3.11-slim

USER root
WORKDIR /app

# Install Java (required by PySpark)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java

COPY pyproject.toml .
# Install dependencies without the editable package (src not yet present)
RUN pip install --no-cache-dir pyspark==3.5.3 temporalio fastapi "uvicorn[standard]" pydantic boto3 pyarrow httpx

COPY src/ src/
COPY data/ data/

# Default: run the Temporal worker
CMD ["python", "-m", "src.ingestion_worker.temporal.worker"]
