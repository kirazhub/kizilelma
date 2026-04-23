# Kızılelma

Türkiye'deki yatırım fonları, tahviller, sukuk, repo ve eurobond getirilerini her sabah otomatik analiz eden ve Telegram üzerinden 3 profilli (muhafazakâr / dengeli / agresif) yatırım raporu gönderen kişisel yatırım danışmanı ajanı.

## Hızlı Başlangıç

- 📖 [Kurulum Rehberi](docs/kurulum.md) — Telegram bot, API anahtarları, GitHub Actions
- 📖 [Kullanım Kılavuzu](docs/kullanim-klavuzu.md) — Günlük raporları nasıl okuyacağın

## Komutlar

```bash
kizilelma test-telegram   # Telegram bağlantısını test et
kizilelma run-now         # Şimdi tek bir rapor gönder
kizilelma start           # Zamanlayıcıyı başlat (lokal kullanım)
```

## Mimari

- **Veri Kaynakları:** TEFAS, TCMB EVDS, BIST, Eurobond, RSS Haberleri
- **AI:** Anthropic Claude (Türkçe yorum üretimi)
- **Bildirim:** Telegram Bot API
- **Veritabanı:** SQLite (geçmiş raporlar arşivi)
- **Zamanlama:** GitHub Actions (cron) veya APScheduler (lokal)

## Yasal Uyarı

Bu yazılım yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır.
