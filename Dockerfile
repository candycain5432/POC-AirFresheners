# Small official Python image.
FROM python:3.13-slim

# Don't write .pyc files; print logs straight away.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INSTANCE_DIR=/data

WORKDIR /srv

# Install dependencies first so Docker can cache this layer between code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user, and give it the data folder (database + uploads).
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser

EXPOSE 8000

# --preload creates the app (and database tables) once before forking workers.
CMD ["gunicorn", "--preload", "--workers", "2", "--bind", "0.0.0.0:8000", "app:create_app()"]
