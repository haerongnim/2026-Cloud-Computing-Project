# syntax=docker/dockerfile:1

# -----------------------------------------------------
# Build Stage
FROM python:3.11-slim AS build-stage

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app

RUN python -m venv /app/venv

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------
# Runtime Stage
FROM python:3.11-slim AS runtime-stage

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app

COPY --from=build-stage /app/venv /app/venv

COPY . .

RUN useradd -m appuser -u 1000
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
