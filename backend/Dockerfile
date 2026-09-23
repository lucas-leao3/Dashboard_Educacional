# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN useradd --create-home --uid 1000 app
COPY --from=build /install /usr/local
COPY --chown=app:app backend/app /app/app
# O entrypoint roda `alembic upgrade head` antes do uvicorn (ver
# docker-compose.yml), então a receita das migrações vai na imagem.
COPY --chown=app:app backend/alembic.ini /app/alembic.ini
COPY --chown=app:app backend/migrations /app/migrations
USER app
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
