FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev iputils-ping && rm -rf /var/lib/apt/lists/*

COPY common ./common
COPY worker/requirements.txt ./worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

COPY worker ./worker
WORKDIR /app/worker

CMD ["python", "-m", "worker.main"]
