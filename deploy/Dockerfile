# Image for automate.py: Python, Chromium, ffmpeg and the emoji font the templates use.
# Build from the repo root:  docker build -f deploy/Dockerfile -t social-generator .
FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium ffmpeg fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*
ENV CHROME=/usr/bin/chromium PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
COPY deploy/requirements.txt deploy/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r deploy/requirements.txt
COPY . .
# Runs as an ordinary user. /data is created here so the named volume mounted on it starts out writable.
RUN useradd --create-home --uid 1000 social && mkdir /data && chown social:social /data
USER social
VOLUME /data
CMD ["python", "automate.py", "--out", "/data", "--every", "60"]
