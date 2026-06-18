FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code only (config.json is git/docker-ignored — config comes from env vars)
COPY news_agent.py .

# Runs once and exits — Render Cron Job triggers it on a schedule.
CMD ["python", "news_agent.py"]
