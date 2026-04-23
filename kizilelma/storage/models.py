"""SQLModel tabloları — geçmiş raporları ve verileri arşivler."""
import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class SnapshotRecord(SQLModel, table=True):
    """Bir snapshot anının özet bilgisi."""

    __tablename__ = "snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: dt.datetime = Field(index=True)
    fund_count: int = 0
    bond_count: int = 0
    sukuk_count: int = 0
    repo_count: int = 0
    eurobond_count: int = 0
    news_count: int = 0
    errors_json: str = "{}"


class FundRecord(SQLModel, table=True):
    """Tek bir fonun bir gündeki snapshot kaydı."""

    __tablename__ = "funds"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="snapshots.id", index=True)
    code: str = Field(index=True)
    name: str
    category: str
    price: float
    date: dt.date
    return_1d: Optional[float] = None
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None
    is_qualified_investor: bool = False


class RepoRecord(SQLModel, table=True):
    """Repo / TCMB faiz kaydı."""

    __tablename__ = "repo_rates"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="snapshots.id", index=True)
    type: str
    maturity: str
    rate: float
    date: dt.date


class ReportRecord(SQLModel, table=True):
    """Üretilen AI raporunun saklandığı tablo."""

    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="snapshots.id")
    timestamp: dt.datetime = Field(index=True)
    fund_section: Optional[str] = None
    serbest_fund_section: Optional[str] = None
    bond_section: Optional[str] = None
    sukuk_section: Optional[str] = None
    repo_section: Optional[str] = None
    eurobond_section: Optional[str] = None
    news_section: Optional[str] = None
    summary_section: Optional[str] = None
    sent_messages: int = 0
    status: str = "unknown"
