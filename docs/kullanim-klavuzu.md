# Kızılelma Kullanım Kılavuzu

## Her Sabah Ne Olur?

Hafta içi her gün saat **10:00**'da (GitHub Actions ile) sistem şunları yapar:

1. TEFAS, TCMB, BIST, Eurobond ve haber kaynaklarından güncel veriyi paralel olarak toplar
2. Anthropic Claude ile her bölüm için Türkçe yorum üretir (3 yatırımcı profili: muhafazakâr / dengeli / agresif)
3. Tüm veriyi ve raporu SQLite veritabanına kaydeder

Sonra sen istediğin zaman web arayüzünden bu veriyi görebilirsin.

## Web Arayüzü

Tarayıcıdan `http://localhost:8000` (veya kendi domain'in) adresine gir. 6 panelde son verileri görürsün:

1. 📊 **TEFAS Fonları** — En yüksek getirili fonlar + 3 profilli yorum
2. 🏛️ **DİBS / Tahviller / Sukuk** — Devlet iç borçlanma ve kira sertifikaları
3. 🔄 **Repo / TCMB Faizi** — Politika faizi ve repo oranları
4. 🌍 **Eurobond** — Türkiye eurobond getirileri
5. 📰 **Ekonomi Haberleri** — Günün önemli haberleri
6. 🎯 **Günün Özeti** — 3 profilli karşılaştırma ve nihai öneri

### Klavye Kısayolları

- `1-6` → ilgili panele odaklan
- `/` → fon arama
- `R` → manuel yenileme

### AI Sohbet Asistanı

Sayfada Claude tabanlı bir sohbet kutusu var. Verilerin üzerinden soru sorabilirsin:

- "Bugün hangi fon en çok kazandırdı?"
- "Eurobond getirisi son 1 ayda nasıl?"
- "Muhafazakâr profil için bugünün önerisi ne?"

## 3 Yatırımcı Profili

Her bölümün sonunda 3 farklı profil için ayrı yorum vardır:

- 🛡️ **Muhafazakâr** — Sermayeyi korumayı önceleyen, düşük risk
- ⚖️ **Dengeli** — Risk ve getiriyi dengeleyen
- 🚀 **Agresif** — Yüksek getiri için yüksek risk alabilen

**Sen kendi profiline göre okumalısın.** Aynı gün için 3 farklı tavsiye olabilir, çünkü farklı insanlar için farklı öneriler vardır.

## Manuel Çalıştırma

İstediğin zaman veriyi yenilemek istersen:

### GitHub'dan

1. Repo'da **Actions** sekmesine git
2. "Kızılelma Veri Toplama" → "Run workflow"
3. ~3 dakika içinde DB güncellenir, web arayüzü yeni veriyi gösterir

### Bilgisayarda

```bash
source venv/bin/activate
kizilelma run-now
```

## Hata Olursa

Bir veri kaynağı çökerse (örn. TEFAS site bakıma girer), o bölümde "veri alınamadı" yazar ama diğer bölümler normal çalışır. Tüm sistem çökerse Actions log'una bakarak nedenini görebilirsin.

## Yasal Uyarı

> Bu rapor yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır. Geçmiş performans gelecekteki getiriyi garanti etmez.
