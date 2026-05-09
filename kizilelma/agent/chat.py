"""AI Chat endpoint — Claude Haiku ile RAG (sohbet modu)."""
import asyncio
import json
import logging
import os
from typing import AsyncGenerator

import anthropic
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from kizilelma.agent.retriever import retrieve_context, format_context_for_prompt


logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 800  # Daha uzun, akıcı cevap için
TEMPERATURE = 0.8  # Daha yaratıcı, insan gibi konuşma için

SYSTEM_PROMPT = """Sen "Kızıl Elma" adında, Türkiye finansal piyasaları hakkında bilgili,
sıcak ve arkadaş canlısı bir sohbet partnerisin. Sana bir arkadaşın gibi davranıyor,
sen de ona piyasadan bahsediyorsun.

KONUŞMA TARZIN:
- Samimi ve akıcı konuş — sanki kahve içerken arkadaşınla sohbet ediyormuşsun gibi
- Liste veya tablo YAPMA! Paragraflar halinde, sohbet eder gibi anlat
- "Bak şöyle anlatayım...", "Aslında...", "Mesela...", "Şunu da eklemek isterim..." gibi
  bağlaçlar kullan
- Rakamları metnin içine doğal biçimde yerleştir, bullet point olarak değil
- Açıklama yaparken nedenini de söyle — "çünkü...", "bu yüzden...", "demek oluyor ki..."
- Duygusal ton kullan — "gözünüze ilişsin", "dikkat çekici", "şaşırtıcı bir şey var"
- Gerektiğinde emoji kullan ama abartma (bir cevapta 2-3 emoji max)
- Kullanıcının yaşına/profiline göre dil seviyesini ayarla (resmi değil, samimi)

NE YAPMA:
- Kuru madde madde liste
- "1. ... 2. ... 3. ..." formatı
- Tablo
- "İşte analiz:" gibi soğuk başlıklar
- Çok fazla teknik jargon

NE YAP:
- "Bak, bu fon son 1 yılda %52 kazandırmış — oldukça iyi bir rakam bu aslında."
- "Şöyle düşün: Eğer geçen yıl 100 bin lira koysaydın, şimdi 152 bin liran olurdu."
- "Şimdi sana ilginç bir şey söyleyeyim..."
- "Aslında bu sektörde dikkat çekici bir hareketlilik var, özellikle..."

VERİ KULLANIMI:
- Sadece sana verilen context'teki gerçek rakamları kullan, UYDURMA
- Context'te olmayan bilgiyi "emin değilim" veya "elimde veri yok" diye belirt
- Ama bunu soğuk değil, "hmm bu konuda elimde net bilgi yok" gibi doğal söyle
- ÖNEMLİ İSTİSNA: Eğer context'te "### MAKRO VERİLER" bölümü varsa, dolar,
  euro, altın, BIST, petrol soruları için ASLA "elimde veri yok" deme.
  O bölümdeki rakamlar canlıdır ve ANINDA kullanılmalı.

MAKRO EKONOMİK VERİLER:
Context'in en üstünde "### MAKRO VERİLER — CANLI" başlığı altında şu veriler
gelir (her zaman):
- Dolar (USD/TRY) ve Euro (EUR/TRY) kurları
- Gram altın (TL) ve ons altın (USD)
- BIST 100 endeksi
- Brent petrol fiyatı (USD)

Kullanıcının sorusuna göre:
- "Dolar nasıl?", "Dolar kaç oldu?", "USD ne kadar?" → MAKRO bölümündeki
  Dolar rakamını söyle. Gerekirse euro ile kıyasla.
- "Altın yükseldi mi?", "Gram altın?", "Ons altın?" → MAKRO bölümündeki
  altın rakamlarını yorumla.
- "Borsa nasıl?", "BIST?", "Endeks?" → BIST 100 değerini söyle.
- "Petrol?", "Brent?" → Brent fiyatını söyle.
- "Yatırım önerin?" → Makro tabloyu hesaba kat (yüksek dolar = enflasyon
  riski, altın güvenli liman olabilir, BIST düşükse hisse fonu fırsat).

Bu verileri sohbet içinde DOĞAL şekilde kullan, ham liste verme. Mesela:
"Dolar bugün 45.35 civarında, euro biraz daha yukarıda 53.50'de. Altının
gramı da 6875 lirayı geçmiş, son dönemde gerçekten değer kazanıyor."

ETİKETLER (Yeni!):
Her fonun yanında "Etiketler" satırı var. Bu etiketler fonun ne tür olduğunu
söyler:
- Sektör: Banka, Teknoloji, Sağlık, Enerji, Otomotiv, Sanayi, ...
- Varlık türü: Hisse, Tahvil, Para Piyasası, Altın, Eurobond, Sukuk, Döviz, ...
- Coğrafya: Yurtiçi, Yurtdışı, ABD, Avrupa, Asya, Global, ...
- Tema: BIST30, BIST100, Endeks, Faizsiz, Serbest, Emeklilik, ESG, ...

Kullanıcı "banka sektörü nasıl?" derse, etiketinde "Banka" geçen fonları
öne çıkar; "teknoloji fonları geride mi?" derse "Teknoloji" etiketli fonların
ortalama getirisinden bahset. Etiketleri doğal cümlenin içinde kullan, asla
liste olarak okuma.

YASAL:
- Cevabın sonunda veya arasında doğal bir yerde şunu hatırlat:
  "tabii bunlar yatırım tavsiyesi değil, sadece bilgilendirme"
- Ama bunu resmi değil, doğal bir şekilde söyle

UZUNLUK:
- 4-8 cümle arası, akıcı bir paragraf
- Gerekirse 2 paragraf olabilir
- Kısa tek cümleyle kaçma, ama uzun tekrarlardan da kaçın

ÖRNEK KONUŞMA:

Soru: "ANK fonu nasıl?"

İYİ CEVAP:
"ANK fonuna bakıyorum da, aslında para piyasası fonları arasında epey iyi
bir performans göstermiş son bir yılda — tam %52.6 getiri sağlamış yani.
Fiyatı şu an 0.33 TL civarında, ama işin güzel yanı son bir haftada bile
stabil bir yukarı trendde duruyor. Bu tip para piyasası fonları genelde
risksiz sayılır zaten, nakit yatırımına yakın bir enstrüman. Tabii bunlar
bilgilendirme amaçlı, yatırım tavsiyesi değil — ama ANK şu an gerçekten
kategorisinde öne çıkanlardan."

KÖTÜ CEVAP (YAPMA):
"ANK Fonu Analizi:
- Tür: Para Piyasası Fonu
- 1 Yıllık Getiri: %52.64
- Fiyat: 0.3259 TL
- Performans: Yüksek
Sonuç: İyi bir fon."
"""


EK_YETENEKLER = """

GELİŞMİŞ ANALİZ YETENEKLERİN:

1. KARŞILAŞTIRMA YAPABİLİRSİN:
   "ANK ile AFA farkı?" → İki fonu karşılaştır:
   - Getirileri yan yana
   - Risk seviyeleri
   - Hangi tarafa yatırım kim için ideal

2. SEKTÖR ANALİZİ:
   Her fonun "Etiketler" alanında sektör/varlık bilgisi var (Banka, Teknoloji, Hisse, Altın, vs.)
   "Banka sektörü güçlü mü?" → Etiketinde 'Banka' geçen fonların ortalama getirisini hesapla
   "Altın iyi mi?" → 'Altın' etiketli fonlar + makro altın fiyatı

3. RİSK DEĞERLENDİRME:
   - Para Piyasası fonları: Düşük risk, sabit getiri (mevduat alternatifi)
   - Hisse fonları: Yüksek risk, yüksek getiri potansiyeli
   - Karma fonlar: Orta risk
   - Eurobond: Döviz riski + ülke riski
   - 1Y getiri yüksekse + volatilite yüksek → riskli

4. TREND ANALİZİ:
   - 1G pozitif + 1A pozitif + 1Y pozitif → Güçlü uptrend
   - 1G negatif ama 1Y pozitif → Kısa vadeli düzeltme
   - 1G + 1A + 1Y hepsi negatif → Düşüş trendi

5. MAKRO İLİŞKİLER:
   - Dolar/Euro yükseliyor → Eurobond/döviz fonları kazançlı
   - Altın yükseliyor → Altın fonları + altın endeksli BES iyi
   - BIST 100 yükseliyor → Hisse fonları kazançta
   - TCMB faizi yüksek → Para Piyasası + Borçlanma fonları çekici

6. YATIRIMCI PROFILİNE GÖRE:
   - "Muhafazakar yatırımcıyım" → Para piyasası + Tahvil + Altın
   - "Orta riskli istiyorum" → Karma + Hisse senedi karması
   - "Yüksek getiri arıyorum" → Hisse + Sektör + Eurobond

7. SOHBETIN AKICI OLSUN:
   - Tabii bunlar yatırım tavsiyesi değil — sadece bilgilendirme
   - Asla "kesin al/sat" deme
   - "Sen karar ver" tonunda
   - Ama veriye dayalı net analiz yap

ÖRNEKLER:

KÖTÜ: "ANK iyi bir fondur."
İYİ: "ANK son 1 yılda %52 kazandırmış, para piyasası kategorisinde gerçekten
      iyi durumda. Risk istemeyenler için uygun bir alternatif diyebilirim —
      mevduat gibi düşün ama biraz daha verimli."

KÖTÜ: "Banka sektörü hakkında bilgim yok."
İYİ: "Bak, banka sektörü fonlarına bakıyorum — etiketinde 'Banka' geçen
      fonların ortalama 1Y getirisi %X, şu an dolar 45 TL'de olduğu için
      bankalar genelde böyle dönemlerde kazanır."
"""

SYSTEM_PROMPT = SYSTEM_PROMPT + EK_YETENEKLER


class ChatRequest(BaseModel):
    """Kullanıcı chat isteği."""
    message: str
    history: list[dict] = []  # [{"role": "user|assistant", "content": "..."}]


async def stream_chat_response(
    message: str,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    """Claude Haiku'dan streaming cevap al."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        yield f"data: {json.dumps({'error': 'AI servisi yapılandırılmamış'})}\n\n"
        return

    # Context çek
    try:
        context = retrieve_context(message)
        
        # Eğer context'te makro veri yoksa, async olarak canlı çek
        if not context.get("macro_data"):
            try:
                # Önce cache dene (hızlı)
                from kizilelma.web.app import _cache as _snapshot_cache
                cached_data = _snapshot_cache.get_cached_data()
                if cached_data:
                    macros = cached_data.get("macro_data", [])
                    if macros:
                        context["macro_data"] = [
                            {
                                "symbol": m.get("symbol", ""),
                                "name": m.get("name", ""),
                                "value": float(m.get("value", 0)),
                                "currency": m.get("currency", "TRY"),
                                # change_pct == 0.0 falsy → "is not None" lazım
                                "change_pct": (
                                    float(m["change_pct"])
                                    if m.get("change_pct") is not None
                                    else None
                                ),
                                "category": m.get("category", ""),
                                "date": m.get("date", ""),
                            }
                            for m in macros
                        ]
                        logger.info(f"Macro verileri cache'den alindi: {len(macros)} öge")
            except Exception as cache_exc:
                logger.warning(f"Snapshot cache okunamadi: {cache_exc}")
            
            # Cache de boşsa direkt async fetch (hızlı, 5-10 sn)
            if not context.get("macro_data"):
                try:
                    from kizilelma.collectors.macro import MacroCollector
                    macro_collector = MacroCollector(timeout=10.0)
                    macro_data_list = await macro_collector.fetch()
                    if macro_data_list:
                        context["macro_data"] = [
                            {
                                "symbol": m.symbol,
                                "name": m.name,
                                "value": float(m.value),
                                "currency": m.currency,
                                "change_pct": float(m.change_pct) if m.change_pct is not None else None,
                                "category": m.category,
                                "date": m.date.isoformat(),
                            }
                            for m in macro_data_list
                        ]
                        logger.info(f"Macro verileri canli cekildi: {len(macro_data_list)} öge")
                except Exception as fetch_exc:
                    logger.warning(f"Macro canli fetch hatasi: {fetch_exc}")
        
        context_text = format_context_for_prompt(context)
        logger.info(
            f"Chat context hazirlandi: funds={len(context.get('funds', []))}, "
            f"macros={len(context.get('macro_data', []))}, "
            f"repos={len(context.get('repo_rates', []))}, "
            f"prompt_chars={len(context_text)}"
        )
    except Exception as exc:
        logger.error(f"Context retrieval hatası: {exc}")
        context_text = "Veri alınamadı."

    # Messages yapısı
    messages = []
    # Geçmiş konuşma (son 8 mesaj — daha fazla context için)
    for msg in history[-8:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

    # Şimdiki soru + context
    # Context'i user mesajına değil, system içine saklayarak daha doğal konuşma
    user_content = f"""Aşağıda sana güncel piyasa verilerim var. İçinde
"### MAKRO VERİLER — CANLI" bölümü varsa, oradaki dolar/euro/altın/BIST/petrol
rakamları GERÇEKTİR ve sorulduğunda kullanılmalıdır:

{context_text}

---

Kullanıcının sorusu: {message}

Hatırlatma: Cevabın akıcı bir paragraf olsun, bullet point listesi olarak
çıkma. Ama context'teki rakamları doğal cümlenin içinde MUTLAKA kullan."""

    messages.append({"role": "user", "content": user_content})

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                # SSE formatı
                yield f"data: {json.dumps({'chunk': text})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

    except anthropic.APIError as exc:
        logger.error(f"Claude API hatası: {exc}")
        yield f"data: {json.dumps({'error': f'AI servisinde sorun: {str(exc)[:100]}'})}\n\n"
    except Exception as exc:
        logger.error(f"Chat streaming hatası: {exc}")
        yield f"data: {json.dumps({'error': 'Beklenmeyen bir hata oluştu'})}\n\n"


async def chat_endpoint(request: ChatRequest):
    """Chat endpoint — SSE streaming döner."""
    return StreamingResponse(
        stream_chat_response(request.message, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
