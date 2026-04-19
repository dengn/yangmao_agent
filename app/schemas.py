from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CardIn(BaseModel):
    issuer: str
    name: str
    level: str | None = None
    network: str | None = None
    annual_fee: float = 0.0
    annual_fee_waiver: str | None = None
    points_rule: str | None = None
    opened_at: date | None = None
    status: str = "active"
    notes: str | None = None


class CardOut(CardIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class BenefitIn(BaseModel):
    card_id: int | None = None
    category: str
    title: str
    description: str | None = None
    times_per_cycle: int | None = None
    reset_cycle: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None


class BenefitOut(BenefitIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class OfferIn(BaseModel):
    card_id: int | None = None
    issuer: str | None = None
    title: str
    description: str | None = None
    offer_type: str
    merchant: str | None = None
    min_spend: float | None = None
    reward_value: float | None = None
    reward_cap: float | None = None
    starts_at: date | None = None
    ends_at: date | None = None
    source: str = "manual"
    source_url: str | None = None
    source_id: str | None = None
    tags: list[str] | None = None


class OfferOut(OfferIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scraped_at: datetime | None
    created_at: datetime


class TransactionIn(BaseModel):
    card_id: int
    offer_id: int | None = None
    occurred_on: date
    amount: float
    merchant: str | None = None
    reward_value: float = 0.0
    notes: str | None = None


class TransactionOut(TransactionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ChatIn(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatOut(BaseModel):
    reply: str
    history: list[dict]
    tool_calls: list[dict] = []
