"""Türkçe AI prompt şablonları.

Tüm prompt'lar Claude Sonnet için tasarlandı. 3 profilli (muhafazakâr/dengeli/agresif)
yorum üretimi için yapılandırılmıştır.
"""
from typing import Any

from kizilelma.models import FundData, MarketSnapshot


SYSTEM_PROMPT = """Sen "Kızılelma" adında, Türkiye finansal piyasaları konusunda
uzman bir yatırım danışman ajanısın. Görevin her sabah 10:00'da kullanıcıya
güncel piyasa verilerini değerlendirip, üç farklı yatırımcı profili için
(muhafazakâr, dengeli, agresif) öneri üretmek.

Kuralların:
1. **Türkçe ve sade dil kullan.** Teknik terim kullanırsan parantez içinde açıkla.
2. **3 profilli yaklaşım:** Her bölümün sonunda muhafazakâr/dengeli/agresif için
   ayrı kısa öneri ver.
3. **Veriye sadık kal.** Veride olmayan rakamı uydurma. Belirsizlik varsa "veri yetersiz" de.
4. **Yasal uyarı:** Verdiğin bilgi yatırım tavsiyesi DEĞİLDİR, sadece bilgilendirme
   amaçlıdır. Bunu her bölümün sonunda hatırlatma şart değil ama unutturma.
5. **Madde işaretleri kullan**, düz paragraf yerine. Telegram mesajında okunmalı.
6. **Kısa ve öz yaz.** Her bölüm en fazla 8-10 satır olsun.
"""


def build_fund_section_prompt(top_funds: list[FundData]) -> str:
    """TEFAS fonları için yorum prompt'ı oluştur."""
    fund_lines = []
    for f in top_funds[:10]:
        ret_1m = f.return_1m if f.return_1m is not None else "?"
        ret_1y = f.return_1y if f.return_1y is not None else "?"
        fund_lines.append(
            f"- {f.code} | {f.name} | Kategori: {f.category} | "
            f"1A: %{ret_1m} | 1Y: %{ret_1y}"
        )
    funds_text = "\n".join(fund_lines) if fund_lines else "Veri alınamadı."

    return f"""Aşağıda bugünün en yüksek getirili TEFAS fonları listelenmiştir:

{funds_text}

Bu verilere bakarak şu yapıda bir Türkçe rapor yaz:

📊 *TEFAS FONLARI - GÜNÜN ÖNE ÇIKANLARI*

[2-3 satırda günün TEFAS özeti]

🛡️ *Muhafazakâr için:* [1-2 satır öneri]
⚖️ *Dengeli için:* [1-2 satır öneri]
🚀 *Agresif için:* [1-2 satır öneri]
"""


def build_serbest_fund_prompt(top_funds: list[FundData]) -> str:
    """Serbest fonlar için yorum prompt'ı."""
    fund_lines = []
    for f in top_funds[:5]:
        ret_1y = f.return_1y if f.return_1y is not None else "?"
        fund_lines.append(f"- {f.code} | {f.name} | 1Y: %{ret_1y}")
    funds_text = "\n".join(fund_lines) if fund_lines else "Veri alınamadı."

    return f"""Bugünün en yüksek getirili serbest fonları (sadece nitelikli yatırımcılara açık):

{funds_text}

Bu fonlar yüksek minimum yatırım gerektirir (genelde 1M TL+ portföy).
Kısa bir Türkçe değerlendirme yaz:

💎 *SERBEST FONLAR*

[3-4 satırda özet ve dikkat çekici fonlar]

⚠️ *Not:* Serbest fonlara yatırım için nitelikli yatırımcı statüsü gerekir.
"""


def build_repo_section_prompt(repo_rates: list) -> str:
    """Repo / TCMB faiz prompt'ı."""
    rate_lines = []
    for r in repo_rates[:5]:
        rate_lines.append(f"- {r.type} ({r.maturity}): %{r.rate} ({r.date})")
    rates_text = "\n".join(rate_lines) if rate_lines else "Veri alınamadı."

    return f"""TCMB ve repo oranları:

{rates_text}

Kısa bir Türkçe yorum yaz:

🔄 *REPO / TCMB FAİZİ*

[2-3 satırda mevcut durum ve trend yorumu]
[Risksiz getiri arayanlar için ne anlama geldiği]
"""


def build_news_section_prompt(news_items: list) -> str:
    """Haberler için özet prompt'ı."""
    if not news_items:
        return "Bugün ekonomi haberi alınamadı."

    news_lines = []
    for n in news_items[:8]:
        news_lines.append(f"- {n.published.strftime('%H:%M')} | {n.source}: {n.title}")
    news_text = "\n".join(news_lines)

    return f"""Bugünün ekonomi haberleri:

{news_text}

Bu haberlerden piyasayı etkileyebilecek olanları seç ve Türkçe özetle:

📰 *EKONOMİ HABERLERİ*

[En önemli 3-5 haberi madde madde özetle]
[Piyasa etkisi konusunda kısa bir değerlendirme]
"""


def build_summary_prompt(
    snapshot: MarketSnapshot,
    top_picks: dict[str, Any],
) -> str:
    """Tüm rapor için son özet/karşılaştırma prompt'ı."""
    return f"""Bugünün ({snapshot.timestamp.strftime('%d.%m.%Y')}) tüm piyasa
verileri toplandı:

- TEFAS fon sayısı: {len(snapshot.funds)}
- DİBS sayısı: {len(snapshot.bonds)}
- Sukuk sayısı: {len(snapshot.sukuks)}
- Repo oranı kayıtları: {len(snapshot.repo_rates)}
- Eurobond sayısı: {len(snapshot.eurobonds)}
- Haber sayısı: {len(snapshot.news)}

Tüm bu verileri değerlendirerek 3 profil için NİHAİ KARŞILAŞTIRMA ÖZETİ yaz:

🎯 *GÜNÜN ÖZETİ - 3 PROFİLLİ KARŞILAŞTIRMA*

🛡️ *MUHAFAZAKÂR PROFİL İÇİN*
[3-4 satır: bugün muhafazakâr yatırımcının ne yapması mantıklı]

⚖️ *DENGELİ PROFİL İÇİN*
[3-4 satır: dengeli yatırımcı için günün önerisi]

🚀 *AGRESİF PROFİL İÇİN*
[3-4 satır: agresif yatırımcı için yüksek getiri fırsatları]

⚠️ *Yasal Uyarı:* Bu rapor yatırım tavsiyesi değildir, bilgilendirme amaçlıdır.
Yatırım kararları kendi sorumluluğunuzdadır.
"""
