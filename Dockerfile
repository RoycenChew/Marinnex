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
RUN pip install --no-cache-dir -e /app/Toolkits_Management \
    && pip install --no-cache-dir -e /app/fdip

WORKDIR /app/fdip
ENV FDIP_DATA_DIR=/data \
    FDIP_DB_URL=sqlite:////data/fdip.db \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "fdip.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
