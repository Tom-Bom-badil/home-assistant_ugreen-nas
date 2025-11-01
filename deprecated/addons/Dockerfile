FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates fonts-liberation \
    libnss3 libatk-bridge2.0-0 libxss1 libasound2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm-dev \
    libgtk-3-0 libdrm2 jq dos2unix tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium

COPY . .

RUN dos2unix run.sh \
 && chmod +x run.sh

COPY config.json /app/config.json

EXPOSE 4115

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
