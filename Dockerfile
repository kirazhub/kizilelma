# Kızılelma — Railway/Docker deploy (CACHE OPTIMIZED)
# Python 3.11 slim base. Layer'lar cache için optimize edilmiş.
FROM python:3.11-slim

# === Layer 1: Sistem paketleri (NADIRen değişir, cache'lenir) ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# === Layer 2: pip upgrade (NADIRen değişir) ===
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# === Layer 3: Bağımlılık metadata (sadece pyproject değişince cache invalid olur) ===
COPY pyproject.toml ./
COPY README.md ./

# === Layer 4: Bağımlılıkları kur (pyproject değişmediği sürece SKIP edilir) ===
# Bu trick: önce paketleri kuruyoruz ama kendi kodumuz olmadan
# Bu sayede sadece pyproject değişince yeniden kurulum yapılır
RUN pip install --no-cache-dir \
    httpx \
    beautifulsoup4 \
    lxml \
    feedparser \
    pydantic \
    python-dotenv \
    pytz \
    fastapi \
    "uvicorn[standard]" \
    jinja2 \
    sqlmodel \
    apscheduler \
    anthropic

# === Layer 5: Kendin paketin kodu (HER commit'te değişir, en son kopyalanır) ===
COPY kizilelma/ ./kizilelma/
COPY scripts/ ./scripts/

# === Layer 6: Editable kurulum (sadece kizilelma paketini path'e ekler, hızlı) ===
RUN pip install --no-cache-dir -e . --no-deps

# === Veri klasörü ===
RUN mkdir -p /data

# === DB seed: Lokal'deki 1 yıllık geçmiş veriyi container'a kopyala ===
# Eğer DB dosyası varsa container içine yerleştir
# Volume yoksa bu DB kullanılacak (restart'ta kaybolur ama her deploy'da yenilenir)
COPY kizilelma.db* /data/
RUN if [ -f /data/kizilelma.db ]; then \
        echo "✅ DB seed: $(ls -lh /data/kizilelma.db | awk '{print $5}')"; \
    else \
        echo "⚠️ DB seed yok, runtime'da oluşturulacak"; \
    fi

# === Environment ===
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV KIZILELMA_DB=/data/kizilelma.db
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# === Port ===
EXPOSE 8000

# === Health check (Railway için) ===
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

# === Başlat ===
CMD ["kizilelma-web"]
