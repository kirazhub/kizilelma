# Kızılelma

Türkiye'deki yatırım fonları, tahviller, sukuk, repo ve eurobond getirilerini her sabah otomatik analiz eden ve Telegram üzerinden 3 profilli (muhafazakâr / dengeli / agresif) yatırım raporu gönderen kişisel yatırım danışmanı ajanı.

## Kurulum

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Test

```bash
pytest
```

## Yasal Uyarı

Bu yazılım yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır.
