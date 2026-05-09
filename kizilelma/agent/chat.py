"""AI Chat endpoint — Claude Haiku ile RAG."""
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

CLAUDE_MODEL = "claude-haiku-4-5"  # En ucuz model (Haiku)
MAX_TOKENS = 500

SYSTEM_PROMPT = """Sen "Kızılelma" adında, Türkiye finansal piyasaları uzmanı bir AI ajansın.

KURALLAR:
1. SADECE sana verilen context verisine dayanarak cevap ver. Uydurma.
2. Verilerde olmayan rakam veya tarih söyleme.
3. Türkçe, sade, net konuş. Hikaye anlatma.
4. Madde madde, tablo ile veya kısa paragraflarla yanıtla.
5. Yatırım TAVSİYESİ verme — sadece veriye dayalı analiz sun.
6. Cevaplarının sonunda küçük uyarı: "Bu analiz yatırım tavsiyesi değildir."
7. En fazla 4-5 cümle yaz, kısa tut.

Kullanıcı bir şey sorduğunda:
- Önce context'i incele
- Sonra veriye dayalı kısa cevap yaz
- Gerekirse rakam/yüzde kullan
- Yasal uyarıyı ekle
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
    # Geçmiş konuşma (son 6 mesaj)
    for msg in history[-6:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

    # Şimdiki soru + context
    user_content = f"""Veriler:
{context_text}

Soru: {message}"""

    messages.append({"role": "user", "content": user_content})

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
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
