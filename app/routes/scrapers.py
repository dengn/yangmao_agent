from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.scrapers import registry, runner

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])


@router.get("")
def list_scrapers():
    return registry.available()


@router.post("/{name}/run")
def run_scraper(name: str, limit: int | None = None, db: Session = Depends(get_db)):
    try:
        return runner.run_scraper(db, name, limit=limit)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/runs")
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    return runner.list_runs(db, limit=limit)
