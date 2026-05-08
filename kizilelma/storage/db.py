"""SQLite DB erişim katmanı.

Snapshot'ları ve raporları saklar; tarihsel sorgular için yardımcılar sağlar.
"""
import datetime as dt
import json
import logging
import os
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.models import MarketSnapshot
from kizilelma.storage.models import (
    BondRecord,
    EurobondRecord,
    FundRecord,
    NewsRecord,
    RepoRecord,
    ReportRecord,
    SnapshotRecord,
    SukukRecord,
)


logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "kizilelma.db"


def get_engine(db_path: Optional[str] = None):
    """SQLite engine döndür."""
    path = db_path or os.getenv("KIZILELMA_DB", DEFAULT_DB_PATH)
    url = f"sqlite:///{path}"
    return create_engine(url, echo=False)


def init_db(engine=None) -> None:
    """Tabloları oluştur (varsa atla)."""
    engine = engine or get_engine()
    SQLModel.metadata.create_all(engine)


def save_snapshot(snapshot: MarketSnapshot, engine=None) -> int:
    """Bir MarketSnapshot'ı DB'ye yaz, snapshot_id döndür."""
    engine = engine or get_engine()
    with Session(engine) as session:
        record = SnapshotRecord(
            timestamp=snapshot.timestamp,
            fund_count=len(snapshot.funds),
            bond_count=len(snapshot.bonds),
            sukuk_count=len(snapshot.sukuks),
            repo_count=len(snapshot.repo_rates),
            eurobond_count=len(snapshot.eurobonds),
            news_count=len(snapshot.news),
            errors_json=json.dumps(snapshot.errors, ensure_ascii=False),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        snap_id = record.id

        # Fonları kaydet
        for f in snapshot.funds:
            session.add(
                FundRecord(
                    snapshot_id=snap_id,
                    code=f.code,
                    name=f.name,
                    category=f.category,
                    price=float(f.price),
                    date=f.date,
                    return_1d=_to_float(f.return_1d),
                    return_1w=_to_float(f.return_1w),
                    return_1m=_to_float(f.return_1m),
                    return_3m=_to_float(f.return_3m),
                    return_6m=_to_float(f.return_6m),
                    return_1y=_to_float(f.return_1y),
                    is_qualified_investor=f.is_qualified_investor,
                )
            )

        # Repo kayıtları
        for r in snapshot.repo_rates:
            session.add(
                RepoRecord(
                    snapshot_id=snap_id,
                    type=r.type,
                    maturity=r.maturity,
                    rate=float(r.rate),
                    date=r.date,
                )
            )

        # DİBS tahvilleri
        for b in snapshot.bonds:
            session.add(
                BondRecord(
                    snapshot_id=snap_id,
                    isin=b.isin,
                    maturity_date=b.maturity_date,
                    coupon_rate=_to_float(b.coupon_rate),
                    yield_rate=float(b.yield_rate),
                    price=float(b.price),
                    date=b.date,
                )
            )

        # Sukuk (kira sertifikaları)
        for s in snapshot.sukuks:
            session.add(
                SukukRecord(
                    snapshot_id=snap_id,
                    isin=s.isin,
                    issuer=s.issuer,
                    maturity_date=s.maturity_date,
                    yield_rate=float(s.yield_rate),
                    price=float(s.price),
                    date=s.date,
                )
            )

        # Eurobondlar
        for e in snapshot.eurobonds:
            session.add(
                EurobondRecord(
                    snapshot_id=snap_id,
                    isin=e.isin,
                    maturity_date=e.maturity_date,
                    currency=e.currency,
                    yield_rate=float(e.yield_rate),
                    price=float(e.price),
                    date=e.date,
                )
            )

        # Haberler
        for n in snapshot.news:
            session.add(
                NewsRecord(
                    snapshot_id=snap_id,
                    title=n.title,
                    url=n.url,
                    source=n.source,
                    published=n.published,
                    summary=n.summary,
                )
            )

        session.commit()
        return snap_id


def save_report(
    report: AdvisorReport,
    snapshot_id: int,
    sent_messages: int,
    status: str,
    engine=None,
) -> int:
    """Bir AdvisorReport'u DB'ye yaz, report_id döndür."""
    engine = engine or get_engine()
    with Session(engine) as session:
        record = ReportRecord(
            snapshot_id=snapshot_id,
            timestamp=dt.datetime.now(),
            fund_section=report.fund_section,
            serbest_fund_section=report.serbest_fund_section,
            bond_section=report.bond_section,
            sukuk_section=report.sukuk_section,
            repo_section=report.repo_section,
            eurobond_section=report.eurobond_section,
            news_section=report.news_section,
            summary_section=report.summary_section,
            sent_messages=sent_messages,
            status=status,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def get_recent_snapshots(limit: int = 10, engine=None) -> list[SnapshotRecord]:
    """En yeni snapshot kayıtlarını döner."""
    engine = engine or get_engine()
    with Session(engine) as session:
        statement = (
            select(SnapshotRecord)
            .order_by(SnapshotRecord.timestamp.desc())
            .limit(limit)
        )
        return list(session.exec(statement))


def get_fund_history(
    fund_code: str,
    limit: int = 30,
    engine=None,
) -> list[FundRecord]:
    """Belirli bir fonun geçmiş kayıtlarını döner."""
    engine = engine or get_engine()
    with Session(engine) as session:
        statement = (
            select(FundRecord)
            .where(FundRecord.code == fund_code)
            .order_by(FundRecord.date.desc())
            .limit(limit)
        )
        return list(session.exec(statement))


def _to_float(value) -> Optional[float]:
    """Decimal/None → float/None."""
    if value is None:
        return None
    return float(value)


def get_latest_full_snapshot(engine=None) -> Optional[dict]:
    """En son başarılı snapshot'ı tüm verileriyle döndür.

    DB'deki SnapshotRecord + ilgili FundRecord / RepoRecord'ları birleştirip
    canlı `MarketSnapshot.model_dump()` ile aynı şemada bir dict üretir.

    Web arayüzünün fallback (yedek) mekanizması bu fonksiyonu kullanır:
    canlı veri çekilemediğinde en son kaydedilen veriyi gösterip kullanıcıyı
    boş ekranla karşılaşmaktan korur.

    Args:
        engine: Test için özel engine (opsiyonel)

    Returns:
        En son snapshot'ın dict hali; DB boşsa None.
        Dict içinde `is_historical=True` bayrağı bulunur.
    """
    engine = engine or get_engine()
    with Session(engine) as session:
        # En son DOLU snapshot — boş kayıtlar (fund_count=0 & repo_count=0)
        # atlanır. Böylece bugün canlı çekim başarısız olsa bile kullanıcı,
        # en son başarılı günün verisini görür.
        stmt = (
            select(SnapshotRecord)
            .where(
                (SnapshotRecord.fund_count > 0)
                | (SnapshotRecord.repo_count > 0)
            )
            .order_by(SnapshotRecord.timestamp.desc())
            .limit(1)
        )
        snap = session.exec(stmt).first()

        # Eğer dolu kayıt yoksa en sonuncuya düş (yine de boş olabilir ama
        # en azından timestamp bilgisi verilir)
        if snap is None:
            stmt = (
                select(SnapshotRecord)
                .order_by(SnapshotRecord.timestamp.desc())
                .limit(1)
            )
            snap = session.exec(stmt).first()

        if snap is None:
            return None

        # Bu snapshot'ın fonları
        fund_stmt = select(FundRecord).where(FundRecord.snapshot_id == snap.id)
        fund_records = list(session.exec(fund_stmt))

        # Repo oranları
        repo_stmt = select(RepoRecord).where(RepoRecord.snapshot_id == snap.id)
        repo_records = list(session.exec(repo_stmt))

        # Bonds (DİBS)
        bond_stmt = select(BondRecord).where(BondRecord.snapshot_id == snap.id)
        bond_records = list(session.exec(bond_stmt))

        # Sukuks (kira sertifikaları)
        sukuk_stmt = select(SukukRecord).where(SukukRecord.snapshot_id == snap.id)
        sukuk_records = list(session.exec(sukuk_stmt))

        # Eurobondlar
        eb_stmt = select(EurobondRecord).where(EurobondRecord.snapshot_id == snap.id)
        eb_records = list(session.exec(eb_stmt))

        # Haberler
        news_stmt = select(NewsRecord).where(NewsRecord.snapshot_id == snap.id)
        news_records = list(session.exec(news_stmt))

        # errors JSON parse et — bozuksa boş dict
        try:
            errors = json.loads(snap.errors_json) if snap.errors_json else {}
        except (ValueError, TypeError):
            errors = {}

        # MarketSnapshot.model_dump() ile aynı şema
        return {
            "timestamp": snap.timestamp.isoformat(),
            "snapshot_id": snap.id,
            "is_historical": True,  # UI bu bayrağa göre "ARŞİV" etiketi gösterir
            "funds": [
                {
                    "code": f.code,
                    "name": f.name,
                    "category": f.category,
                    "price": str(f.price),
                    "date": f.date.isoformat(),
                    "return_1d": str(f.return_1d) if f.return_1d is not None else None,
                    "return_1w": str(f.return_1w) if f.return_1w is not None else None,
                    "return_1m": str(f.return_1m) if f.return_1m is not None else None,
                    "return_3m": str(f.return_3m) if f.return_3m is not None else None,
                    "return_6m": str(f.return_6m) if f.return_6m is not None else None,
                    "return_1y": str(f.return_1y) if f.return_1y is not None else None,
                    "is_qualified_investor": f.is_qualified_investor,
                    "asset_tags": [],  # Eski DB kayıtlarında bu alan yok, boş dön
                }
                for f in fund_records
            ],
            "repo_rates": [
                {
                    "type": r.type,
                    "maturity": r.maturity,
                    "rate": str(r.rate),
                    "date": r.date.isoformat(),
                }
                for r in repo_records
            ],
            "bonds": [
                {
                    "isin": b.isin,
                    "maturity_date": b.maturity_date.isoformat(),
                    "coupon_rate": str(b.coupon_rate) if b.coupon_rate is not None else None,
                    "yield_rate": str(b.yield_rate),
                    "price": str(b.price),
                    "date": b.date.isoformat(),
                }
                for b in bond_records
            ],
            "sukuks": [
                {
                    "isin": s.isin,
                    "issuer": s.issuer,
                    "maturity_date": s.maturity_date.isoformat(),
                    "yield_rate": str(s.yield_rate),
                    "price": str(s.price),
                    "date": s.date.isoformat(),
                }
                for s in sukuk_records
            ],
            "eurobonds": [
                {
                    "isin": e.isin,
                    "maturity_date": e.maturity_date.isoformat(),
                    "currency": e.currency,
                    "yield_rate": str(e.yield_rate),
                    "price": str(e.price),
                    "date": e.date.isoformat(),
                }
                for e in eb_records
            ],
            "news": [
                {
                    "title": n.title,
                    "url": n.url,
                    "source": n.source,
                    "published": n.published.isoformat(),
                    "summary": n.summary,
                }
                for n in news_records
            ],
            "errors": errors,
        }
