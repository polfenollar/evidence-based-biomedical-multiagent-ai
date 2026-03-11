FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.6" \
    "redis>=5.0.0"
COPY src/ src/
CMD ["uvicorn", "src.audit_api.main:app", "--host", "0.0.0.0", "--port", "8004"]
