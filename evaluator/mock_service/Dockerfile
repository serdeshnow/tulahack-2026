FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir fastapi httpx pydantic pyyaml uvicorn python-multipart

COPY mock_service /app/mock_service

CMD ["uvicorn", "mock_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
