FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies in a single layer to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates fonts-liberation \
    libnss3 libatk-bridge2.0-0 libxss1 libasound2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm-dev \
    libgtk-3-0 libdrm2 jq dos2unix tzdata \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy and install Python requirements
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir -r requirements.txt

# Set Playwright cache to shared location and install browsers as root
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium \
 && rm -rf /ms-playwright/firefox* \
 && rm -rf /ms-playwright/webkit*

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser \
 && chown -R appuser:appuser /app \
 && chmod -R 755 /ms-playwright

# Copy application files
COPY . .
RUN dos2unix run.sh \
 && chmod +x run.sh \
 && chown -R appuser:appuser /app

# Switch to appuser for runtime
USER appuser

EXPOSE 4115

# Use exec form for better signal handling
ENTRYPOINT ["/bin/bash", "/app/run.sh"]
