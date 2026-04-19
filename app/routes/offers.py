from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db

router = APIRouter(prefix="/api/offers", tags=["offers"])


@router.get("", response_model=list[schemas.OfferOut])
def list_offers(
    card_id: int | None = None,
    issuer: str | None = None,
    merchant: str | None = None,
    active_only: bool = False,
    q: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return crud.list_offers(
        db,
        card_id=card_id,
        issuer=issuer,
        merchant=merchant,
        active_only=active_only,
        q=q,
        limit=limit,
    )


@router.post("", response_model=schemas.OfferOut)
def create_offer(payload: schemas.OfferIn, db: Session = Depends(get_db)):
    return crud.create_offer(db, payload.model_dump())


@router.get("/{offer_id}", response_model=schemas.OfferOut)
def get_offer(offer_id: int, db: Session = Depends(get_db)):
    o = crud.get_offer(db, offer_id)
    if not o:
        raise HTTPException(404, "offer not found")
    return o


@router.delete("/{offer_id}")
def delete_offer(offer_id: int, db: Session = Depends(get_db)):
    if not crud.delete_offer(db, offer_id):
        raise HTTPException(404, "offer not found")
    return {"ok": True}
