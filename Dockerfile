# The toolkit is a sibling folder, so this image must be built from the parent
# directory: `docker build -f fdip/Dockerfile .`. docker-compose.yml does that.
FROM python:3.12-slim

# tesseract for scans, and the pdfium runtime deps pypdfium2 needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Toolkits_Management /app/Toolkits_Management
COPY fdip /app/fdip
# pdfplumber and pillow by name rather than through the toolkit's `docs` and
# `ocr` extras: `docs` also drags in docling, hundreds of megabytes this image
# never uses. Without pdfplumber the API starts, accepts uploads, and fails
# every document at the parse stage with "a parser is not installed" — the
# toolkit's base install is standard-library only by design.
# deploy/Dockerfile.app carries the same two lines for the same reason.
RUN pip install --no-cache-dir -e /app/Toolkits_Management \
    && pip install --no-cache-dir -e /app/fdip \
    && pip install --no-cache-dir "pdfplumber>=0.11" "pillow>=10.0"

WORKDIR /app/fdip
ENV FDIP_DATA_DIR=/data \
    FDIP_DB_URL=sqlite:////data/fdip.db \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "fdip.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
