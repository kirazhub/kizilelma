# Kızılelma Kullanım Kılavuzu

## Her Sabah Ne Olur?

Hafta içi her gün saat **10:00**'da Telegram'a sırayla 8 mesaj düşer:

1. 📊 **TEFAS Fonları** — En yüksek getirili 10 fon + 3 profilli yorum
2. 💎 **Serbest Fonlar** — Nitelikli yatırımcı fonları
3. 🏛️ **DİBS / Tahviller** — Devlet iç borçlanma senetleri
4. 🕌 **Kira Sertifikaları** — Sukuk verileri
5. 🔄 **Repo / TCMB Faizi** — Politika faizi ve repo oranları
6. 🌍 **Eurobond** — Türkiye eurobond getirileri
7. 📰 **Ekonomi Haberleri** — Günün önemli ekonomi haberleri (özet)
8. 🎯 **GÜNÜN ÖZETİ** — 3 profilli karşılaştırma ve nihai öneri

## Mesajları Anlamak

Her bölümün sonunda 3 farklı yatırımcı profili için ayrı öneri vardır:

- 🛡️ **Muhafazakâr** — Sermayeyi korumayı önceleyen, düşük risk
- ⚖️ **Dengeli** — Risk ve getiriyi dengeleyen
- 🚀 **Agresif** — Yüksek getiri için yüksek risk alabilen

**Sen kendi profiline göre okumalısın.** Aynı gün için 3 farklı tavsiye olabilir, çünkü farklı insanlar için farklı önerilen şeyler vardır.

## Manuel Çalıştırma

İstediğin zaman rapor almak istersen:

### GitHub'dan

1. Repo'da **Actions** sekmesine git
2. "Kızılelma Günlük Rapor" → "Run workflow"
3. ~3 dakika içinde Telegram'a düşer

### Bilgisayarda

```bash
source venv/bin/activate
kizilelma run-now
```

## Hata Olursa

Bir veri kaynağı çökerse (örn. TEFAS site bakıma girer), o bölümde "veri alınamadı" yazar ama diğer bölümler normal çalışır. Tüm sistem çökerse Telegram'a hiç mesaj düşmez — Actions log'una bakarak nedenini görebilirsin.

## Yasal Uyarı

> Bu rapor yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır. Geçmiş performans gelecekteki getiriyi garanti etmez.
