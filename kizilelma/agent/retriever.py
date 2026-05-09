"""DB'den AI için context çıkaran modül.

Kullanıcı sorusuna göre DB'den ilgili veriyi basit keyword match ile çeker.
İleride vector search eklenebilir ama şimdilik SQL LIKE + sıralama yeterli.
"""
import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from kizilelma.storage.db import get_engine
from kizilelma.storage.models import (
    FundRecord, RepoRecord, BondRecord,
    SukukRecord, EurobondRecord, SnapshotRecord,
)


def retrieve_context(question: str, engine=None) -> dict:
    """Soruya göre DB'den relevan veriyi çek.

    Dönüş:
        {
            "funds": [...],       # İlgili fonlar
            "repo_rates": [...],  # TCMB oranları
            "bonds": [...],       # Tahviller
            "sukuks": [...],      # Sukuklar
            "eurobonds": [...],   # Eurobondlar
            "latest_snapshot": datetime  # En son veri zamanı
        }
    """
    engine = engine or get_engine()
    q_lower = question.lower()
    context = {
        "funds": [],
        "repo_rates": [],
        "bonds": [],
        "sukuks": [],
        "eurobonds": [],
        "latest_snapshot": None,
    }

    with Session(engine) as session:
        # En son DOLU snapshot'ı bul (fund_count > 0).
        # En son snapshot bazen boş olabilir (toplama patladıysa),
        # bu yüzden gerçekten veri içeren en yeni snapshot'ı arıyoruz.
        latest_snap_stmt = (
            select(SnapshotRecord)
            .where(SnapshotRecord.fund_count > 0)
            .order_by(SnapshotRecord.timestamp.desc())
            .limit(1)
        )
        latest_snap = session.exec(latest_snap_stmt).first()
        if latest_snap is None:
            # Hiçbir snapshot'ta fon yoksa en son kayda düş (eurobond/bond olabilir)
            latest_snap_stmt = (
                select(SnapshotRecord)
                .order_by(SnapshotRecord.timestamp.desc())
                .limit(1)
            )
            latest_snap = session.exec(latest_snap_stmt).first()
        if latest_snap is None:
            return context

        context["latest_snapshot"] = latest_snap.timestamp.isoformat()
        snap_id = latest_snap.id

        # Fon kodu geçiyor mu? (örn. "ANK", "AFA")
        import re
        fund_codes_in_question = re.findall(r'\b[A-Z]{2,4}\b', question)

        # Kategori keyword'leri
        category_keywords = {
            "para piyas": "Para Piyasası",
            "hisse": "Hisse",
            "karma": "Karma",
            "değişken": "Değişken",
            "serbest": "Serbest",
            "katılım": "Katılım",
            "borçlan": "Borçlanma",
            "tahvil": "Borçlanma",
        }

        # Sektör keyword'leri
        sector_keywords = {
            "banka": "banka",
            "teknoloji": "teknoloji",
            "sanayi": "sanayi",
            "enerji": "enerji",
            "gıda": "gıda",
            "sağlık": "sağlık",
            "otomotiv": "otomotiv",
        }

        # ---- Fonlar ----
        # Eğer fon kodu verilmişse direkt onu çek
        if fund_codes_in_question:
            fund_matches = []
            for code in fund_codes_in_question[:5]:
                stmt = (
                    select(FundRecord)
                    .where(FundRecord.code == code)
                    .order_by(FundRecord.snapshot_id.desc())
                    .limit(1)
                )
                match = session.exec(stmt).first()
                if match:
                    fund_matches.append(match)
            if fund_matches:
                context["funds"] = [_fund_to_dict(f) for f in fund_matches]

        # Kategori sorgusu
        elif any(kw in q_lower for kw in category_keywords):
            for kw, cat in category_keywords.items():
                if kw in q_lower:
                    stmt = (
                        select(FundRecord)
                        .where(FundRecord.snapshot_id == snap_id)
                        .where(FundRecord.category.like(f"%{cat}%"))
                        .order_by(FundRecord.return_1y.desc())
                        .limit(10)
                    )
                    funds = list(session.exec(stmt))
                    if funds:
                        context["funds"] = [_fund_to_dict(f) for f in funds]
                    break

        # Sektör sorgusu
        elif any(kw in q_lower for kw in sector_keywords):
            for kw in sector_keywords:
                if kw in q_lower:
                    stmt = (
                        select(FundRecord)
                        .where(FundRecord.snapshot_id == snap_id)
                        .where(FundRecord.name.like(f"%{kw.upper()}%"))
                        .order_by(FundRecord.return_1y.desc())
                        .limit(10)
                    )
                    funds = list(session.exec(stmt))
                    if funds:
                        context["funds"] = [_fund_to_dict(f) for f in funds]
                    break

        # En iyi / en yüksek sorusu
        elif any(kw in q_lower for kw in ["en iyi", "en yüksek", "en kar", "top"]):
            stmt = (
                select(FundRecord)
                .where(FundRecord.snapshot_id == snap_id)
                .where(FundRecord.return_1y > 0)
                .order_by(FundRecord.return_1y.desc())
                .limit(10)
            )
            funds = list(session.exec(stmt))
            context["funds"] = [_fund_to_dict(f) for f in funds]

        # Genel soru — top fonlar
        else:
            stmt = (
                select(FundRecord)
                .where(FundRecord.snapshot_id == snap_id)
                .where(FundRecord.return_1y > 0)
                .order_by(FundRecord.return_1y.desc())
                .limit(5)
            )
            funds = list(session.exec(stmt))
            context["funds"] = [_fund_to_dict(f) for f in funds]

        # ---- TCMB / Repo (her zaman ekle) ----
        repo_stmt = select(RepoRecord).where(RepoRecord.snapshot_id == snap_id)
        repos = list(session.exec(repo_stmt))
        context["repo_rates"] = [
            {
                "type": r.type,
                "maturity": r.maturity,
                "rate": r.rate,
                "date": r.date.isoformat(),
            }
            for r in repos
        ]

        # ---- Tahvil sorgusu ----
        if any(kw in q_lower for kw in ["tahvil", "dibs", "bond"]):
            bond_stmt = (
                select(BondRecord)
                .where(BondRecord.snapshot_id == snap_id)
                .order_by(BondRecord.yield_rate.desc())
                .limit(5)
            )
            bonds = list(session.exec(bond_stmt))
            context["bonds"] = [
                {"isin": b.isin, "yield_rate": b.yield_rate, "maturity": b.maturity_date.isoformat()}
                for b in bonds
            ]

        # ---- Sukuk sorgusu ----
        if any(kw in q_lower for kw in ["sukuk", "kira sertifika", "katılım"]):
            sukuk_stmt = (
                select(SukukRecord)
                .where(SukukRecord.snapshot_id == snap_id)
                .limit(5)
            )
            sukuks = list(session.exec(sukuk_stmt))
            context["sukuks"] = [
                {"isin": s.isin, "issuer": s.issuer, "yield_rate": s.yield_rate}
                for s in sukuks
            ]

        # ---- Eurobond ----
        if any(kw in q_lower for kw in ["eurobond", "dolar", "usd", "euro"]):
            eb_stmt = (
                select(EurobondRecord)
                .where(EurobondRecord.snapshot_id == snap_id)
                .limit(5)
            )
            ebs = list(session.exec(eb_stmt))
            context["eurobonds"] = [
                {"isin": e.isin, "currency": e.currency, "yield_rate": e.yield_rate}
                for e in ebs
            ]

    return context


def _fund_to_dict(f: FundRecord) -> dict:
    """FundRecord'ı AI için temiz dict'e çevir."""
    return {
        "code": f.code,
        "name": f.name,
        "category": f.category,
        "price": round(f.price, 4) if f.price else None,
        "return_1d": round(f.return_1d, 2) if f.return_1d else None,
        "return_1m": round(f.return_1m, 2) if f.return_1m else None,
        "return_3m": round(f.return_3m, 2) if f.return_3m else None,
        "return_6m": round(f.return_6m, 2) if f.return_6m else None,
        "return_1y": round(f.return_1y, 2) if f.return_1y else None,
        "is_qualified": f.is_qualified_investor,
        "date": f.date.isoformat() if f.date else None,
    }


def format_context_for_prompt(context: dict) -> str:
    """Context'i AI prompt'una uygun okunabilir metne çevir."""
    parts = []

    if context.get("latest_snapshot"):
        parts.append(f"En son veri tarihi: {context['latest_snapshot']}\n")

    funds = context.get("funds", [])
    if funds:
        parts.append("### İLGİLİ FONLAR")
        for f in funds:
            parts.append(
                f"- {f['code']} | {f['name'][:40]} | Kategori: {f['category']} | "
                f"Fiyat: {f['price']} TL | "
                f"1G: %{f['return_1d'] or '-'} | 1A: %{f['return_1m'] or '-'} | "
                f"3A: %{f['return_3m'] or '-'} | 1Y: %{f['return_1y'] or '-'}"
            )
        parts.append("")

    repos = context.get("repo_rates", [])
    if repos:
        parts.append("### TCMB FAİZ ORANLARI")
        for r in repos:
            parts.append(f"- {r['type']} ({r['maturity']}): %{r['rate']}")
        parts.append("")

    bonds = context.get("bonds", [])
    if bonds:
        parts.append("### DİBS TAHVİLLER")
        for b in bonds:
            parts.append(f"- {b['isin']}: Getiri %{b['yield_rate']} | Vade: {b['maturity']}")
        parts.append("")

    sukuks = context.get("sukuks", [])
    if sukuks:
        parts.append("### SUKUK (KİRA SERTİFİKALARI)")
        for s in sukuks:
            parts.append(f"- {s['isin']} ({s['issuer']}): Getiri %{s['yield_rate']}")
        parts.append("")

    ebs = context.get("eurobonds", [])
    if ebs:
        parts.append("### EUROBONDLAR")
        for e in ebs:
            parts.append(f"- {e['isin']} ({e['currency']}): Getiri %{e['yield_rate']}")
        parts.append("")

    return "\n".join(parts) if parts else "Veri bulunamadı."
