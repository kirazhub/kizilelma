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
        context_text = format_context_for_prompt(context)
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
    user_content = f"""Güncel piyasa verilerim (cevabında kullan ama liste halinde listeleme, doğal anlat):

{context_text}

---

Kullanıcının sorusu: {message}

Hatırlatma: Arkadaş sohbeti gibi, akıcı paragraflar halinde cevap ver. Liste yapma!"""

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
