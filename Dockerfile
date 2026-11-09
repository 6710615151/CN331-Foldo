# FOLDO production image (Render "docker" runtime, also runs anywhere with Docker).
# A custom image is needed because WeasyPrint (PDF export) depends on the Pango
# and HarfBuzz C libraries, which a plain Python runtime does not provide.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# WeasyPrint runtime libraries + Thai and Latin fonts so PDFs render Thai text.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libjpeg62-turbo \
        fonts-noto-core fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static files are collected at build time; a throw-away key is enough for that.
RUN DJANGO_DEBUG=false DJANGO_SECRET_KEY=build-only-collectstatic \
    python manage.py collectstatic --noinput

# Run as an unprivileged user.
RUN useradd --create-home foldo && mkdir -p /app/media && chown -R foldo /app
USER foldo

EXPOSE 8000
CMD ["sh", "scripts/start.sh"]
