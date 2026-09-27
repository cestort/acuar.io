FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SQLITE_PATH=/data/db.sqlite3

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Los estáticos se generan en la imagen; la clave solo sirve para este paso.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
 && useradd --uid 1000 --no-create-home app \
 && mkdir -p /data \
 && chown app:app /data \
 && chmod +x docker/entrypoint.sh

USER app

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["docker/entrypoint.sh"]
