# Kurulum Rehberi

Bu rehber, Kızılelma'yı sıfırdan kurmak için tüm adımları içerir. Komut satırı bilmen gerekmiyor — adımları sırayla takip et.

## 1. Telegram Bot Oluştur

1. Telegram'da `@BotFather` hesabını bul
2. `/newbot` yaz
3. Bot için bir isim seç (örn. "Kızılelma Bot")
4. Username seç (sonu `_bot` ile bitmeli, örn. `kizilelma_kiraz_bot`)
5. BotFather sana bir TOKEN verecek — bunu sakla, başkasıyla paylaşma

### Chat ID'ni öğren

1. Yeni oluşturduğun bot'a Telegram'da bir mesaj at (örn. "merhaba")
2. Tarayıcında şu adresi aç (TOKEN'ı kendininkiyle değiştir):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. JSON yanıtında `"chat":{"id":XXXXXX}` kısmını bul
4. Bu sayı senin chat ID'n. Sakla.

## 2. TCMB EVDS API Anahtarı

1. https://evds2.tcmb.gov.tr adresine git
2. Sağ üstten "Üye Ol" → e-posta + şifre ile kayıt
3. Giriş yaptıktan sonra "Profil" → "API Anahtarı" sekmesinden anahtarını al
4. Sakla.

## 3. Anthropic Claude API Anahtarı

1. https://console.anthropic.com adresine git
2. Hesap oluştur (kredi kartı gerekebilir, ücretsiz krediyle başla)
3. "API Keys" → "Create Key" → anahtarı kopyala, sakla.

## 4. GitHub'da Çalıştırmak İçin (Önerilen — Bedava + Otomatik)

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
2. **New repository secret** ile şu 4 sırrı ekle:
   - `TCMB_API_KEY`: TCMB anahtarın
   - `ANTHROPIC_API_KEY`: Claude anahtarın
   - `TELEGRAM_BOT_TOKEN`: BotFather'dan aldığın token
   - `TELEGRAM_CHAT_ID`: Yukarıda aldığın chat ID

### Test Et

1. **Actions** sekmesine git
2. "Kızılelma Günlük Rapor" workflow'unu seç
3. Sağ üstten "Run workflow" → "Run workflow" tıkla
4. ~3 dakika içinde Telegram'a rapor düşmeli ✅

### Otomatik Çalışma

Artık her hafta içi (Pzt-Cum) saat 10:00'da otomatik olarak çalışır. Hiçbir şey yapmana gerek yok.

## 5. Yerel Bilgisayarda Test (İsteğe Bağlı)

Eğer önce kendi Mac'inde test etmek istersen:

```bash
cd ~/Desktop/Kızıl\ Elma
python3 -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env
# .env dosyasını aç ve değerleri doldur
kizilelma test-telegram   # Telegram bağlantısını test et
kizilelma run-now         # Tam rapor üret ve gönder
```
