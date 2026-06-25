FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

# Usuario no-root: el proceso (gunicorn/scheduler) corre sin privilegios.
# `app` posee /app para poder escribir staticfiles en collectstatic (runtime).
RUN adduser --disabled-password --gecos "" --no-create-home app \
    && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "notisnotis.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
