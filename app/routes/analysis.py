from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import analysis
from app.db import get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/cards/{card_id}")
def evaluate_card(card_id: int, db: Session = Depends(get_db)):
    result = analysis.evaluate_owned_card(db, card_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


class ProspectBenefit(BaseModel):
    title: str
    estimated_annual_value: float | None = None


class ProspectCard(BaseModel):
    issuer: str | None = None
    name: str | None = None
    annual_fee: float = 0.0
    annual_fee_waiver: str | None = None
    opening_bonus_value: float = 0.0
    benefits: list[ProspectBenefit] = []


@router.post("/prospect")
def prospect(payload: ProspectCard):
    return analysis.evaluate_prospect_card(payload.model_dump())


@router.get("/monthly")
def monthly(year: int | None = None, month: int | None = None, db: Session = Depends(get_db)):
    today = date.today()
    return analysis.monthly_report(db, year or today.year, month or today.month)


@router.get("/yearly")
def yearly(year: int | None = None, db: Session = Depends(get_db)):
    return analysis.yearly_report(db, year or date.today().year)
