FROM python:3.11-slim

WORKDIR /app

# System libraries for OpenCV, EasyOCR, and OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ML models during build so containers start fast.
# EasyOCR English (~100 MB), sentence-transformers (~90 MB), spaCy (~50 MB).
# BART zero-shot (~1.6 GB) is skipped — it downloads lazily on first categorization.
RUN python -c "from easyocr import Reader; Reader(['en'], gpu=False)" \
 && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
 && python -m spacy download en_core_web_sm

COPY . .

RUN chmod +x start.sh

EXPOSE 8000

# start.sh runs `alembic upgrade head` then starts uvicorn
CMD ["sh", "start.sh"]
