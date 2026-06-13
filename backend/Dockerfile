FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; psycopg[binary] and google libs ship wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV STORAGE_DIR=/data \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data/audio

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
