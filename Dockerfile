FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps:
# - build-essential: for compiling some Python wheels if needed
# - default-libmysqlclient-dev + pkg-config: for MySQL/MariaDB drivers (mysqlclient)
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

# Prefer a stable WSGI entrypoint: wsgi.py should define `app = create_app()`
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "wsgi:app"]
