FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps:
# - build-essential: for compiling some Python wheels if needed
# - pkg-config + default-libmysqlclient-dev: for MySQL/MariaDB drivers (mysqlclient) if you use it
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

COPY . .

# Container listens on 8000. Host port mapping is handled by docker-compose.
EXPOSE 8000

# Flask app factory entrypoint (no wsgi.py required)
# Ensure your project exposes: app/create_app()  (i.e., app:create_app())
CMD sh -c 'gunicorn -w ${GUNICORN_WORKERS:-2} -b 0.0.0.0:8000 "app:create_app()"'
