# Backend FastAPI — image de production (deps runtime uniquement).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Le code est nécessaire pour que setuptools découvre le package « app » à l'install.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Migrations Alembic (service `migrate`).
COPY alembic.ini ./
COPY migrations ./migrations

EXPOSE 8000

# Surchargé par docker-compose (uvicorn / alembic upgrade head).
CMD ["uvicorn", "app.interface.main:app", "--host", "0.0.0.0", "--port", "8000"]
