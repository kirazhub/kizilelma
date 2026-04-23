# Kızılelma — Tasarım Dökümanı

**Tarih:** 23 Nisan 2026
**Versiyon:** v1.0 (İlk Sürüm Tasarımı)
**Durum:** Onay bekliyor

---

## 1. Proje Amacı

Kızılelma, Türkiye'deki sabit getirili ve fon yatırım enstrümanlarını her sabah otomatik tarayan, yapay zekâ destekli yorum üreten ve kullanıcıya Telegram üzerinden günlük rapor gönderen kişisel yatırım danışmanı ajanıdır.

Kullanıcı yatırım kararlarını kendisi verir; Kızılelma sadece bilgi toplar, analiz eder ve öneri sunar. Hiçbir banka veya aracı kuruma bağlanmaz, doğrudan işlem yapmaz.

---

## 2. Hedef Kullanıcı

- Yazılım bilmeyen, fakat finansal yatırım yapan / yapmak isteyen birey
- Her sabah piyasayı taramak için zamanı olmayan ama bilgilendirilmek isteyen kullanıcı
- Karar destek sistemi olarak yapay zekâ kullanmak isteyen yatırımcı

---

## 3. Kapsam (v1)

### 3.1 İzlenecek Kaynaklar

| Kaynak | Tür | Veri Sağlayıcı |
|---|---|---|
| TEFAS Fonları | Hisse, borçlanma, karma, para piyasası, vb. tüm kategoriler | TEFAS resmi API |
| Serbest Fonlar | Nitelikli yatırımcı fonları (sadece izleme amaçlı) | TEFAS resmi API |
| DİBS / Tahviller | Devlet İç Borçlanma Senetleri | BIST verileri / TCMB |
| Kira Sertifikaları (Sukuk) | Kamu ve özel kira sertifikaları | BIST verileri |
| Repo / Ters Repo | Gecelik ve haftalık repo oranları | TCMB EVDS API |
| Eurobond | Türkiye Eurobond getirileri | Investing.com / yfinance |
| Ekonomi Haberleri | TCMB, faiz kararları, piyasa gelişmeleri | RSS Feed (AA, Bloomberg HT, Sözcü Ekonomi) |

### 3.2 Kapsam Dışı (Bu Versiyonda Yok)

- Banka mevduat faizleri
- Döviz / altın takibi (v1.5'te eklenecek)
- Anlık uyarılar (v2)
- Sohbet modu (v2)
- Portföy takibi (v3)
- Hedef takibi (v3)
- AI tahmin modeli (v3+)
- Banka veya aracı kurum entegrasyonu (mevcut değil, planlanmıyor)

---

## 4. Çalışma Modeli

### 4.1 Zamanlama
- **Çalışma günleri:** Pazartesi – Cuma
- **Çalışma saati:** 10:00 (Türkiye saati, UTC+3)
- **Süre:** Tüm rapor süreci yaklaşık 3-5 dakikada tamamlanır
- **Hafta sonu:** Çalışmaz (piyasalar kapalı)

### 4.2 Kullanıcı Bildirimi
- **Kanal:** Telegram (özel bot)
- **Format:** Bölüm bölüm ayrı mesajlar + sonda genel karşılaştırma özeti
- **Mesaj sırası:**
  1. 📊 TEFAS Fonları
  2. 💎 Serbest Fonlar
  3. 🏛️ DİBS / Tahviller
  4. 🕌 Kira Sertifikaları
  5. 🔄 Repo / Ters Repo
  6. 🌍 Eurobond
  7. 📰 Ekonomi Haberleri
  8. 🎯 GÜNÜN ÖZETİ (3 profilli karşılaştırma + öneri)

### 4.3 Karar Tarzı (3 Profilli Yaklaşım)
Her enstrüman ve genel öneri 3 farklı yatırımcı profili için ayrı ayrı değerlendirilir:

- **Muhafazakâr:** Sermaye koruma odaklı (para piyasası fonu, kısa vadeli DİBS, repo)
- **Dengeli:** Risk-getiri dengeli (karma fonlar, orta vadeli tahvil, sukuk)
- **Agresif:** Yüksek getiri odaklı (hisse fonları, serbest fonlar, eurobond)

---

## 5. Mimari

### 5.1 Genel Akış

```
[Zamanlayıcı: Her sabah 10:00 (Pzt-Cum)]
            ↓
[Veri Toplayıcılar — paralel çalışır]
   ├── TEFAS API (fonlar + serbest fonlar)
   ├── TCMB EVDS API (faiz, repo, kur)
   ├── BIST verileri (DİBS, sukuk)
   ├── Eurobond verileri
   └── RSS Feed'ler (haberler)
            ↓
[Analiz Motoru]
   ├── Günlük / haftalık / aylık getiri hesaplama
   ├── Risk skoru (volatilite)
   ├── Sharpe oranı (risk-getiri dengesi)
   └── En iyi N listesi (her kategori için)
            ↓
[AI Yorumcu (Claude / OpenAI)]
   ├── Verileri doğal dilde yorumlar
   ├── 3 profil için ayrı öneri üretir
   └── Haberleri özetler ve piyasa etkisini değerlendirir
            ↓
[Telegram Gönderici]
   └── 8 mesajı sırayla gönderir
            ↓
[Veritabanı (SQLite)]
   └── Geçmiş raporları ve verileri arşivler
```

### 5.2 Modüler Yapı

Her modül bağımsız test edilebilir, tek bir sorumluluğu olur:

```
kizilelma/
├── collectors/          # Veri toplayıcılar
│   ├── tefas.py
│   ├── tcmb.py
│   ├── bist.py
│   ├── eurobond.py
│   └── news.py
├── analyzers/           # Hesaplama ve analiz
│   ├── returns.py       # Getiri hesaplamaları
│   ├── risk.py          # Volatilite, Sharpe
│   └── ranker.py        # En iyi N listesi
├── ai_advisor/          # AI yorum üreticisi
│   ├── prompts.py
│   └── advisor.py
├── telegram_bot/        # Telegram gönderici
│   ├── bot.py
│   └── formatters.py
├── scheduler/           # Zamanlayıcı
│   └── daily_job.py
├── storage/             # Veritabanı
│   ├── models.py
│   └── db.py
├── config.py            # Ayarlar (API key'ler, vb.)
└── main.py              # Ana giriş noktası
```

### 5.3 Bileşen Sorumlulukları

**collectors/** — Her dosya bir veri kaynağından sorumlu. Tek bir fonksiyonu var: `fetch()` → standart formatta veri döner. Diğer modüllerden bağımsızdır.

**analyzers/** — Toplanmış ham veriyi alır, hesaplamaları yapar. Veri kaynağı ne olduğunu bilmez, sadece sayılarla çalışır.

**ai_advisor/** — Hesaplanmış metrikleri okur, doğal dilde yorum üretir. Telegram'ı bilmez, sadece metin döner.

**telegram_bot/** — Hazır metinleri alır, formatlayıp gönderir. Veri toplama veya AI ile ilgilenmez.

**scheduler/** — Sabah 10:00'u tetikler. Bütün modülleri sırayla çağırır.

**storage/** — Geçmiş verileri SQLite'a kaydeder. İlerideki versiyonlarda "geçen ayın şampiyonu" gibi karşılaştırmalar için temel.

---

## 6. Hata Yönetimi

| Senaryo | Davranış |
|---|---|
| Bir veri kaynağı çöktü (örn. TEFAS API down) | İlgili bölüm "veri alınamadı, kaynak şu an erişilemez" notuyla geçilir, diğer bölümler normal çalışır |
| AI servisi (Claude/OpenAI) çöktü | Ham veriler yorumsuz olarak gönderilir, kullanıcıya "AI yorum bu sabah eklenemedi" notu düşer |
| Telegram gönderimi başarısız | Sunucu log'una düşer, bir sonraki çalışmada uyarı mesajı eklenir |
| Tüm sistem çöktü | Sunucu sağlık kontrolü ile uyarı (UptimeRobot gibi ücretsiz servis) |

---

## 7. Teknik Altyapı

### 7.1 Teknoloji Seçimleri

| Bileşen | Seçim | Neden |
|---|---|---|
| Programlama dili | **Python 3.11+** | Veri analizi ve AI için en güçlü ekosistem |
| Veritabanı | **SQLite** | Tek dosya, kurulum yok, v1 için yeterli |
| AI Provider | **Anthropic Claude (Sonnet)** veya **OpenAI GPT-4** | Türkçe yorum kalitesi yüksek |
| Telegram | **python-telegram-bot** kütüphanesi | Resmi, stabil, ücretsiz |
| Zamanlayıcı | **APScheduler** veya **systemd timer** | Bulut sunucuda çalışır |
| HTTP istekleri | **httpx** (async) | Paralel veri toplama için |
| HTML scraping | **BeautifulSoup4** + **lxml** | Banka/borsa sayfaları için |
| RSS okuma | **feedparser** | Haber kaynakları için |

### 7.2 Hosting

- **Tercih:** Küçük bir bulut sunucu (Hetzner CX11 ~€4/ay, DigitalOcean droplet $6/ay, veya Railway free tier)
- **Alternatif:** GitHub Actions (günde 1 kez çalıştırma yeterli olabilir, tamamen ücretsiz)
- **Karar:** İlk olarak GitHub Actions ile başlanabilir, ihtiyaç doğarsa VPS'e geçilir

### 7.3 Maliyet Tahmini (Aylık)

| Kalem | Tutar |
|---|---|
| Sunucu (Hetzner/Railway) | $0 - $6 |
| AI API (Claude Sonnet, ~30 rapor × ~10K token) | ~$3 - $5 |
| Telegram Bot | $0 |
| Veri kaynakları (TEFAS, TCMB) | $0 |
| **Toplam** | **~$5 - $15 / ay** |

---

## 8. Test ve Doğrulama Stratejisi

- **Birim testler:** Her collector, analyzer ve formatter için ayrı testler
- **Mock veri:** API'lerin offline test edilebilmesi için örnek yanıtlar
- **Manuel test modu:** "Şimdi çalıştır" komutu ile sabah 10:00'u beklemeden test
- **Sandbox Telegram:** İlk testler özel test kanalında, sonra ana kanala geçiş

---

## 9. Güvenlik ve Gizlilik

- API anahtarları (.env dosyası, asla git'e commit'lenmez)
- Telegram bot token'ı sadece sunucuda
- Kullanıcının kişisel finansal verisi tutulmaz (sadece halka açık piyasa verileri)
- Yatırım tavsiyesi DEĞİL, bilgilendirme amaçlı uyarı her raporun altında

---

## 10. Yol Haritası (Sonraki Versiyonlar)

| Versiyon | Yeni Özellikler | Tahmini Süre |
|---|---|---|
| **v1.0 (Mevcut)** | Temel rapor sistemi | 1-2 gün |
| **v1.5** | Döviz & altın takibi | +1 gün |
| **v2.0** | Anlık uyarılar + sohbet modu | +3-4 gün |
| **v3.0** | Portföy takibi + hedef takibi | +1 hafta |
| **v3+** | AI tahmin modeli, global piyasa bağlamı | İleride |

---

## 11. Yasal Uyarı

Kızılelma bir yatırım danışmanlık hizmeti DEĞİLDİR. Sermaye Piyasası Kurulu (SPK) lisansı yoktur. Üretilen tüm raporlar bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır. Geçmiş performans gelecekteki getiriyi garanti etmez.

Her raporun sonuna bu uyarı otomatik eklenir.

---

## 12. Onay

- [ ] Kullanıcı tasarımı okudu
- [ ] Kullanıcı onayladı
- [ ] Implementasyon planına geçildi
