# Kızılelma — Railway/Docker deploy
# Python 3.11 slim base, hızlı ve hafif
FROM python:3.11-slim

# Sistem paketleri (lxml için gcc gerekir)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Bağımlılıkları önce kopyala (Docker cache için)
COPY pyproject.toml ./
COPY README.md ./

# Bağımlılıkları kur
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -e .

# Kalan kodu kopyala
COPY kizilelma/ ./kizilelma/
COPY scripts/ ./scripts/

# Kalıcı veri için klasör (Railway volume'u buraya mount edecek)
RUN mkdir -p /data

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV KIZILELMA_DB=/data/kizilelma.db

# Port (Railway otomatik atar, default 8000)
EXPOSE 8000

# Web sunucusunu başlat
CMD ["kizilelma-web"]
