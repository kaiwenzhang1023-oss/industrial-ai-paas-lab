FROM python:3.14-slim
LABEL org.opencontainers.image.title="Industrial AI PaaS Lab" org.opencontainers.image.version="1.8-c4.3"
WORKDIR /app
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY datasets ./datasets
COPY database ./database
RUN pip install --no-cache-dir "fastapi>=0.110,<1" "uvicorn>=0.27,<1" "pydantic>=2,<3" "psycopg[binary]>=3.1,<4"
ENV PYTHONUNBUFFERED=1 DEMO_WRITE_ENABLED=0 PUBLIC_READ_ONLY=1
# Runtime is non-root by default; orchestration must still apply read-only FS,
# dropped capabilities, no-new-privileges, resource limits and network policy.
USER 10001:10001
EXPOSE 10000
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
