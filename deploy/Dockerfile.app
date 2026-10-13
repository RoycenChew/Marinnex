# One image for both the API and the worker. They run the same code and differ
# only in their command, so two images would be two things to keep in step.
#
# Build context is the PARENT of this repository, because the toolkit is a
# sibling checkout and Docker cannot copy from above its context:
#
#     docker build -f Marinnex/deploy/Dockerfile.app .
#
# docker-compose.prod.yml does that for you.
# The folder this repository is checked out into. `Marinnex` on the server;
# override it when your local clone is named something else, which is what
# makes the local verification a real build rather than a symlink trick.
ARG APP_DIR=Marinnex

FROM python:3.12-slim AS base
ARG APP_DIR

# tesseract: scans. The language packs matter — `msa` is Malay, and a Malaysian
# invoice is routinely bilingual, so reading it with English data alone loses
# half the labels. libgl1/libglib2.0-0 are what pypdfium2 links against.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-msa \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# A non-root user owns the code and the data. The uid is fixed so the bind
# mount on the host can be chowned to match before the container ever starts.
RUN useradd --create-home --uid 10001 marinnex

WORKDIR /app
COPY --chown=marinnex:marinnex Toolkits_Management /app/Toolkits_Management
COPY --chown=marinnex:marinnex ${APP_DIR} /app/Marinnex

# The toolkit is installed from the sibling folder, which the deploy script
# checks out at tag v0.9.0. Installed first and separately so a change to the
# application does not rebuild the toolkit layer.
# pdfplumber and pillow by name rather than through the toolkit's `docs` and
# `ocr` extras: `docs` also drags in docling, hundreds of megabytes this image
# never uses. Without pdfplumber every document fails at the parse stage with
# "a parser is not installed", which is how this line came to exist.
RUN pip install --no-cache-dir /app/Toolkits_Management \
    && pip install --no-cache-dir /app/Marinnex \
    && pip install --no-cache-dir \
        "pdfplumber>=0.11" \
        "pillow>=10.0" \
        "uvicorn[standard]>=0.30"

WORKDIR /app/Marinnex
USER marinnex

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FDIP_DATA_DIR=/data \
    FDIP_DB_URL=sqlite:////data/fdip.db \
    FDIP_ENV=production

EXPOSE 8000

# Two workers on a t3.small: enough to keep the API responsive while one
# request is blocked on a model call, few enough to leave the worker process
# and Caddy their share of 2 GB.
CMD ["uvicorn", "fdip.api.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
