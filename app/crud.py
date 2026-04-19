from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app import models


# ---------- Cards ----------

def create_card(db: Session, data: dict) -> models.Card:
    card = models.Card(**data)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def get_card(db: Session, card_id: int) -> models.Card | None:
    return db.get(models.Card, card_id)


def list_cards(db: Session, status: str | None = None) -> list[models.Card]:
    stmt = select(models.Card)
    if status:
        stmt = stmt.where(models.Card.status == status)
    stmt = stmt.order_by(models.Card.issuer, models.Card.name)
    return list(db.scalars(stmt))


def update_card(db: Session, card_id: int, data: dict) -> models.Card | None:
    card = get_card(db, card_id)
    if not card:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(card, k, v)
    db.commit()
    db.refresh(card)
    return card


def delete_card(db: Session, card_id: int) -> bool:
    card = get_card(db, card_id)
    if not card:
        return False
    db.delete(card)
    db.commit()
    return True


# ---------- Benefits ----------

def create_benefit(db: Session, data: dict) -> models.Benefit:
    benefit = models.Benefit(**data)
    db.add(benefit)
    db.commit()
    db.refresh(benefit)
    return benefit


def list_benefits(db: Session, card_id: int | None = None, category: str | None = None) -> list[models.Benefit]:
    stmt = select(models.Benefit)
    if card_id is not None:
        stmt = stmt.where(models.Benefit.card_id == card_id)
    if category:
        stmt = stmt.where(models.Benefit.category == category)
    return list(db.scalars(stmt.order_by(models.Benefit.category, models.Benefit.title)))


def delete_benefit(db: Session, benefit_id: int) -> bool:
    b = db.get(models.Benefit, benefit_id)
    if not b:
        return False
    db.delete(b)
    db.commit()
    return True


# ---------- Offers ----------

def create_offer(db: Session, data: dict) -> models.Offer:
    # Dedup: same source + source_id should upsert.
    src = data.get("source")
    sid = data.get("source_id")
    if src and sid:
        existing = db.scalar(
            select(models.Offer).where(
                and_(models.Offer.source == src, models.Offer.source_id == sid)
            )
        )
        if existing:
            for k, v in data.items():
                if v is not None:
                    setattr(existing, k, v)
            db.commit()
            db.refresh(existing)
            return existing
    offer = models.Offer(**data)
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


def list_offers(
    db: Session,
    card_id: int | None = None,
    issuer: str | None = None,
    active_only: bool = False,
    merchant: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[models.Offer]:
    stmt = select(models.Offer)
    if card_id is not None:
        stmt = stmt.where(models.Offer.card_id == card_id)
    if issuer:
        stmt = stmt.where(models.Offer.issuer == issuer)
    if merchant:
        stmt = stmt.where(models.Offer.merchant.ilike(f"%{merchant}%"))
    if active_only:
        today = date.today()
        stmt = stmt.where(
            or_(models.Offer.ends_at.is_(None), models.Offer.ends_at >= today)
        ).where(
            or_(models.Offer.starts_at.is_(None), models.Offer.starts_at <= today)
        )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                models.Offer.title.ilike(like),
                models.Offer.description.ilike(like),
                models.Offer.merchant.ilike(like),
            )
        )
    stmt = stmt.order_by(models.Offer.ends_at.asc().nullslast()).limit(limit)
    return list(db.scalars(stmt))


def get_offer(db: Session, offer_id: int) -> models.Offer | None:
    return db.get(models.Offer, offer_id)


def delete_offer(db: Session, offer_id: int) -> bool:
    o = get_offer(db, offer_id)
    if not o:
        return False
    db.delete(o)
    db.commit()
    return True


# ---------- Transactions ----------

def create_transaction(db: Session, data: dict) -> models.Transaction:
    tx = models.Transaction(**data)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def list_transactions(
    db: Session, card_id: int | None = None, since: date | None = None
) -> list[models.Transaction]:
    stmt = select(models.Transaction)
    if card_id is not None:
        stmt = stmt.where(models.Transaction.card_id == card_id)
    if since:
        stmt = stmt.where(models.Transaction.occurred_on >= since)
    return list(db.scalars(stmt.order_by(models.Transaction.occurred_on.desc())))
