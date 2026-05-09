# Kızılelma

Türkiye'deki yatırım fonları, tahviller, sukuk, repo ve eurobond getirilerini her sabah otomatik toplayıp analiz eden, Bloomberg Terminal tarzı bir web arayüzü ve AI sohbet asistanıyla sunan kişisel yatırım danışmanı ajanı.

## Hızlı Başlangıç

- 📖 [Kurulum Rehberi](docs/kurulum.md) — API anahtarları, GitHub Actions
- 📖 [Kullanım Kılavuzu](docs/kullanim-klavuzu.md) — Web arayüzü ve AI asistanı kullanımı
- 📖 [Railway Deploy](docs/railway-deploy.md) — 7/24 yayın için

## Komutlar

```bash
kizilelma run-now    # Şimdi veri topla, AI raporu üret ve DB'ye kaydet
kizilelma start      # Lokal zamanlayıcıyı başlat (Pzt-Cum 10:00)
kizilelma-web        # Web arayüzünü başlat (http://localhost:8000)
```

## Web Terminali

Bloomberg Terminal tarzı bir web arayüzü:

- Koyu tema, monospace font (JetBrains Mono), amber vurgular
- 6 panel: Para piyasası fonları, tahvil/sukuk, TCMB faiz, eurobond, günün zirveleri, canlı log
- AI sohbet asistanı (Claude tabanlı) — verilerin üzerinden soru sor
- Canlı İstanbul saati, durum göstergesi, scan-line / grain efektleri
- Klavye kısayolları: `1-6` panel odak, `/` fon arama, `R` manuel yenileme
- 5 dakikalık otomatik yenileme, in-memory cache
- Tek komut ile başlatılır: `kizilelma-web`

## Mimari

- **Veri Kaynakları:** TEFAS, TCMB EVDS, BIST, Eurobond, RSS Haberleri
- **AI:** Anthropic Claude (Türkçe yorum + sohbet asistanı)
- **Web:** FastAPI + Jinja2
- **Veritabanı:** SQLite (geçmiş raporlar arşivi)
- **Zamanlama:** GitHub Actions (cron) veya APScheduler (lokal)

## Deploy

Web arayüzünü internete açmak için: [Railway Deploy Rehberi](docs/railway-deploy.md)

Kendi domain'ini bağlamak ve 7/24 çalışmak için Railway'de deploy etmen yeterli.

## Yasal Uyarı

Bu yazılım yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır.
