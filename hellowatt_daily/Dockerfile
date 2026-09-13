# Download portable Python wheels with Debian's resolver.
FROM python:3.12-slim-bookworm AS dependencies
WORKDIR /deps
COPY requirements.txt ./
RUN python -m pip download --disable-pip-version-check \
    --only-binary=:all: --platform any \
    --dest /wheels -r requirements.txt

# Keep the existing Alpine runtime and its cron implementation.
FROM python:3.12-alpine
RUN apk add --no-cache tzdata
ENV TZ=Europe/Paris PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
COPY --from=dependencies /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index \
    --find-links=/wheels -r requirements.txt \
    && python -m pip check \
    && python -c 'import requests, paho.mqtt.client' \
    && rm -rf /wheels
COPY collecteur.py run.py start.sh /app/
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
