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
kizilelma-web             # Web arayüzünü başlat (http://localhost:8000)
```

## Web Terminali

Bloomberg Terminal tarzı bir web arayüzü gelir:

- Koyu tema, monospace font (JetBrains Mono), amber vurgular
- 6 panel: Para piyasası fonları, tahvil/sukuk, TCMB faiz, eurobond, günün zirveleri, canlı log
- Canlı İstanbul saati, durum göstergesi, scan-line / grain efektleri
- Klavye kısayolları: `1-6` panel odak, `/` fon arama, `R` manuel yenileme
- 5 dakikalık otomatik yenileme, in-memory cache
- Tek komut ile başlatılır: `kizilelma-web`

## Mimari

- **Veri Kaynakları:** TEFAS, TCMB EVDS, BIST, Eurobond, RSS Haberleri
- **AI:** Anthropic Claude (Türkçe yorum üretimi)
- **Bildirim:** Telegram Bot API
- **Veritabanı:** SQLite (geçmiş raporlar arşivi)
- **Zamanlama:** GitHub Actions (cron) veya APScheduler (lokal)

## Deploy

Web arayüzünü internete açmak için: [Railway Deploy Rehberi](docs/railway-deploy.md)

Kendi domain'ini bağlamak ve 7/24 çalışmak için Railway'de deploy etmen yeterli.

## Yasal Uyarı

Bu yazılım yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır.
