# Wise Help Assistant — app only (TLS + basic auth: use docker-compose with Caddy).
FROM python:3.12-slim-bookworm

WORKDIR /app

# No pip deps; retriever + server use the stdlib only.
COPY server.py retriever.py database.py ./
COPY src ./src
COPY data ./data

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "server.py"]
