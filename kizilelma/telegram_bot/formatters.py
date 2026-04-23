"""Telegram mesaj formatlama yardımcıları.

AdvisorReport'u Telegram'a uygun mesajlara çevirir.
- Telegram MarkdownV2 limitleri: 4096 karakter
- Uzun mesajlar otomatik bölünür
- Her mesaja başlık (tarih + index) ve altlık (yasal uyarı) eklenir
"""
import datetime as dt

from kizilelma.ai_advisor.advisor import AdvisorReport


MAX_MESSAGE_LENGTH = 4096
LEGAL_NOTICE = (
    "_Bu rapor yatırım tavsiyesi değildir; bilgilendirme amaçlıdır._"
)


# Bölümlerin sırası (sabit)
SECTION_ORDER = [
    "fund_section",
    "serbest_fund_section",
    "bond_section",
    "sukuk_section",
    "repo_section",
    "eurobond_section",
    "news_section",
    "summary_section",
]


def split_into_messages(report: AdvisorReport) -> list[str]:
    """AdvisorReport'u Telegram mesaj listesine çevir.

    - Boş/None bölümler atlanır
    - Telegram limitini aşan bölümler parçalanır
    - Her mesaja başlık ve altlık eklenir
    """
    timestamp = dt.datetime.now()
    sections = []
    for field_name in SECTION_ORDER:
        content = getattr(report, field_name, None)
        if content and content.strip():
            sections.append(content)

    raw_messages: list[str] = []
    for section in sections:
        chunks = _split_long_text(section, max_len=MAX_MESSAGE_LENGTH - 200)
        raw_messages.extend(chunks)

    total = len(raw_messages)
    final_messages = [
        add_header_and_footer(msg, timestamp, index=i + 1, total=total)
        for i, msg in enumerate(raw_messages)
    ]
    return final_messages


def _split_long_text(text: str, max_len: int) -> list[str]:
    """Uzun metni satır sınırlarında parçala.

    Tek bir satır bile ``max_len``'i aşıyorsa, o satırı karakter bazında
    (hard-cut) böler — hiçbir parça limiti aşmaz.
    """
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        # Tek satırın kendisi bile limiti aşıyorsa — önce birikimi boşalt,
        # sonra satırı hard-cut ile parçala.
        if len(line) > max_len:
            if current:
                chunks.append(current.rstrip())
                current = ""
            for i in range(0, len(line), max_len):
                chunks.append(line[i : i + max_len])
            continue

        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current.rstrip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current.rstrip())
    return chunks


def add_header_and_footer(
    body: str,
    timestamp: dt.datetime,
    index: int,
    total: int,
) -> str:
    """Mesaja başlık ve altlık ekle."""
    date_str = timestamp.strftime("%d.%m.%Y")
    header = f"🌅 *KIZILELMA RAPORU* — {date_str} \\({index}/{total}\\)\n\n"
    footer = f"\n\n{LEGAL_NOTICE}"
    return header + body + footer


def sanitize_markdown(text: str) -> str:
    """Telegram MarkdownV2 için özel karakterleri escape et.

    Şimdilik no-op (Markdown legacy modda kullanılacak). İleride MarkdownV2
    geçilirse burada özel karakter escape mantığı eklenecek.
    """
    return text
