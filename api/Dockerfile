FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# uv run re-syncs the environment by default, which would pull the dev
# group (pytest et al.) from PyPI on every container start and every
# railway.json preDeployCommand run. The venv built above already has
# exactly what --no-dev asked for; UV_NO_SYNC=1 makes `uv run` skip that
# resync and just execute against it.
ENV UV_NO_SYNC=1

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
