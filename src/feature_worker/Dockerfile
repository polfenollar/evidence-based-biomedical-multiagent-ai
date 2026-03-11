FROM python:3.11-slim

USER root
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java

COPY pyproject.toml .
RUN pip install --no-cache-dir pyspark==3.5.3 temporalio "feast[redis]" pandas pyarrow psycopg2-binary

COPY src/ src/

CMD ["python", "-m", "src.feature_worker.temporal.worker"]
