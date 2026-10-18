FROM python:3.12.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY deliveryguard ./deliveryguard
COPY ui ./ui
COPY migrations ./migrations
COPY alembic.ini ./
COPY .streamlit ./.streamlit
RUN pip install --no-deps . && useradd --create-home --uid 10001 app \
    && mkdir -p /app/data && chown app:app /app/data
USER app
CMD ["uvicorn", "deliveryguard.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
