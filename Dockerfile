FROM python:3.13-slim
WORKDIR /app
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY datasets ./datasets
COPY database ./database
RUN pip install --no-cache-dir "fastapi>=0.110,<1" "uvicorn>=0.27,<1" "pydantic>=2,<3" "psycopg[binary]>=3.1,<4"
ENV PYTHONUNBUFFERED=1 DEMO_WRITE_ENABLED=0 PUBLIC_READ_ONLY=1
EXPOSE 10000
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
