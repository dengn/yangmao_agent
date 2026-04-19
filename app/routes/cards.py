from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("", response_model=list[schemas.CardOut])
def list_cards(status: str | None = None, db: Session = Depends(get_db)):
    return crud.list_cards(db, status=status)


@router.post("", response_model=schemas.CardOut)
def create_card(payload: schemas.CardIn, db: Session = Depends(get_db)):
    return crud.create_card(db, payload.model_dump())


@router.get("/{card_id}", response_model=schemas.CardOut)
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = crud.get_card(db, card_id)
    if not card:
        raise HTTPException(404, "card not found")
    return card


@router.patch("/{card_id}", response_model=schemas.CardOut)
def update_card(card_id: int, payload: schemas.CardIn, db: Session = Depends(get_db)):
    card = crud.update_card(db, card_id, payload.model_dump(exclude_unset=True))
    if not card:
        raise HTTPException(404, "card not found")
    return card


@router.delete("/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db)):
    if not crud.delete_card(db, card_id):
        raise HTTPException(404, "card not found")
    return {"ok": True}
