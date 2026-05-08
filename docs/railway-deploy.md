# Railway Deploy Rehberi

Kızılelma'yı Railway'de 7/24 çalışır hale getirmek için adımlar.

## 1. Railway Hesabı

1. https://railway.app → GitHub ile giriş yap
2. Hesap açıldıktan sonra bir dashboard göreceksin

## 2. Projeyi Deploy Et

1. Dashboard'da **"New Project"** → **"Deploy from GitHub repo"**
2. `kirazhub/kizilelma` reposunu seç
3. Railway otomatik olarak `nixpacks.toml`'ı algılayıp Python projesi kurar
4. İlk build 2-3 dakika sürer

## 3. Environment Variables Ayarla

Deploy olduktan sonra **Variables** sekmesine git ve şunları ekle:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | (senin Telegram bot token'ın) |
| `TELEGRAM_CHAT_ID` | (senin chat id'n) |
| `ANTHROPIC_API_KEY` | (Claude API key'in) |
| `TCMB_API_KEY` | (opsiyonel) |

Kaydettikten sonra Railway otomatik olarak restart eder.

## 4. Domain Bağlama

### Railway'in varsayılan domain'i

- **Settings** → **Networking** → **Generate Domain**
- `kizilelma-production.up.railway.app` gibi bir URL alırsın, anında çalışır

### Kendi domain'ini bağlama (örn. kizilelma.senindomain.com)

1. **Settings** → **Networking** → **Custom Domain**
2. Domain'ini yaz: `kizilelma.senindomain.com`
3. Railway sana CNAME kaydı gösterir, örn:
   ```
   kizilelma  CNAME  xyz.up.railway.app
   ```
4. Domain sağlayıcında (GoDaddy, Namecheap, vb.) DNS panelini aç
5. Bu CNAME kaydını ekle
6. 5-30 dakika içinde aktif olur (DNS propagasyon)
7. Railway otomatik SSL sertifikası verir (HTTPS)

## 5. Kontrol

- Railway dashboard'da **Deployments** sekmesinde "LIVE" yeşil yazıyor mu
- Logları kontrol et: **View Logs**
- Domain'e tarayıcıdan git: Kızılelma arayüzü açılmalı

## 6. Otomatik Güncelleme

Railway GitHub'a push ettiğin her commit'i otomatik deploy eder:
```bash
git push origin main
```
Railway 1-2 dakika içinde yeni sürümü canlıya alır.

## Maliyet

Railway Hobby plan: aylık ~$5 (her ay $5 kredi veriliyor, küçük uygulamalar ücretsiz kalabilir).

## Sorun Giderme

- **Build hatası:** Logları Railway dashboard'da incele
- **Domain çalışmıyor:** DNS propagasyonu için 30 dk bekle
- **AI yorumu gelmiyor:** `ANTHROPIC_API_KEY` env'i doğru mu kontrol et
- **DB kayboluyor:** Railway'in filesystem'i ephemeral (restart'ta sıfırlanır).
  Kalıcı veri için **Volumes** eklenmeli — v2'de yapılabilir. Şimdilik
  GitHub Actions her sabah yeni snapshot üretiyor, fallback olarak yeterli.
