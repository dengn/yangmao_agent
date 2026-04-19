from datetime import datetime, date

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    network: Mapped[str | None] = mapped_column(String(32), nullable=True)  # VISA/MC/UP/JCB/AE
    annual_fee: Mapped[float] = mapped_column(Float, default=0.0)
    annual_fee_waiver: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening_bonus_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    opening_bonus_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/closed/pending
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    benefits: Mapped[list["Benefit"]] = relationship(back_populates="card", cascade="all, delete-orphan")
    offers: Mapped[list["Offer"]] = relationship(back_populates="card")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="card")


class Benefit(Base):
    __tablename__ = "benefits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(32))  # lounge/hotel/dining/points/insurance/other
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    times_per_cycle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reset_cycle: Mapped[str | None] = mapped_column(String(16), nullable=True)  # annual/monthly/quarterly
    estimated_annual_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    card: Mapped["Card | None"] = relationship(back_populates="benefits")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True, index=True)
    issuer: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_type: Mapped[str] = mapped_column(String(32))  # cashback/discount/points_multiplier/installment/gift/other
    merchant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    min_spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    starts_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    ends_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")  # manual/kahui/51credit/...
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)  # external id for dedup
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    card: Mapped["Card | None"] = relationship(back_populates="offers")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"), nullable=True, index=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)
    merchant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reward_value: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    card: Mapped["Card"] = relationship(back_populates="transactions")


class ScrapeSource(Base):
    __tablename__ = "scrape_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(32))  # kahui/51credit/custom
    base_url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("scrape_sources.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/ok/error
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
