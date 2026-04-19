from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db

router = APIRouter(prefix="/api/benefits", tags=["benefits"])


@router.get("", response_model=list[schemas.BenefitOut])
def list_benefits(
    card_id: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    return crud.list_benefits(db, card_id=card_id, category=category)


@router.post("", response_model=schemas.BenefitOut)
def create_benefit(payload: schemas.BenefitIn, db: Session = Depends(get_db)):
    return crud.create_benefit(db, payload.model_dump())


@router.delete("/{benefit_id}")
def delete_benefit(benefit_id: int, db: Session = Depends(get_db)):
    if not crud.delete_benefit(db, benefit_id):
        raise HTTPException(404, "benefit not found")
    return {"ok": True}
