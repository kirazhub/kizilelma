# Kurulum Rehberi

Bu rehber, Kızılelma'yı sıfırdan kurmak için tüm adımları içerir. Komut satırı bilmen gerekmiyor — adımları sırayla takip et.

## 1. TCMB EVDS API Anahtarı

1. https://evds2.tcmb.gov.tr adresine git
2. Sağ üstten "Üye Ol" → e-posta + şifre ile kayıt
3. Giriş yaptıktan sonra "Profil" → "API Anahtarı" sekmesinden anahtarını al
4. Sakla.

## 2. Anthropic Claude API Anahtarı

1. https://console.anthropic.com adresine git
2. Hesap oluştur (kredi kartı gerekebilir, ücretsiz krediyle başla)
3. "API Keys" → "Create Key" → anahtarı kopyala, sakla.

## 3. GitHub'da Çalıştırmak İçin (Önerilen — Bedava + Otomatik)

### Repo'yu Oluştur

1. https://github.com/new adresinden yeni boş repo oluştur (private veya public)
2. Adı: `kizilelma`

### Kodu Yükle

Terminal aç ve şunları yaz (her satırı tek tek):

```bash
cd ~/Desktop/Kızıl\ Elma
git remote add origin https://github.com/<kullanıcı_adın>/kizilelma.git
git push -u origin main
```

### Sırları Ekle

GitHub'da repo sayfanda:
1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** ile şu 2 sırrı ekle:
   - `TCMB_API_KEY`: TCMB anahtarın
   - `ANTHROPIC_API_KEY`: Claude anahtarın

### Test Et

1. **Actions** sekmesine git
2. "Kızılelma Veri Toplama" workflow'unu seç
3. Sağ üstten "Run workflow" → "Run workflow" tıkla
4. ~3 dakika içinde DB güncellenmiş olur ✅

### Otomatik Çalışma

Artık her hafta içi (Pzt-Cum) saat 10:00'da otomatik veri toplar ve DB'ye kaydeder. Hiçbir şey yapmana gerek yok.

## 4. Web Arayüzünü Yayınla

Web arayüzünü 7/24 yayınlamak için: [Railway Deploy Rehberi](railway-deploy.md)

## 5. Yerel Bilgisayarda Test (İsteğe Bağlı)

Eğer önce kendi Mac'inde test etmek istersen:

```bash
cd ~/Desktop/Kızıl\ Elma
python3 -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env
# .env dosyasını aç ve değerleri doldur
kizilelma run-now    # Veri topla, AI raporu üret, DB'ye kaydet
kizilelma-web        # http://localhost:8000 üzerinden web arayüzünü aç
```
