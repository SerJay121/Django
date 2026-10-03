FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
# dev-залежності включені, щоб запускати тести/лінтери в контейнері
RUN uv pip install --system --no-cache -r pyproject.toml --extra dev

COPY . .
RUN useradd -m app && mkdir -p /app/media /app/staticfiles && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
