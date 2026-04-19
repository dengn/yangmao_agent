from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[schemas.TransactionOut])
def list_transactions(
    card_id: int | None = None, since: date | None = None, db: Session = Depends(get_db)
):
    return crud.list_transactions(db, card_id=card_id, since=since)


@router.post("", response_model=schemas.TransactionOut)
def create_transaction(payload: schemas.TransactionIn, db: Session = Depends(get_db)):
    return crud.create_transaction(db, payload.model_dump())
