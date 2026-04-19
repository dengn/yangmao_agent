from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models
from app.scrapers import registry
from app.scrapers.base import ScrapedOffer

log = logging.getLogger(__name__)


def _get_or_create_source(db: Session, name: str, label: str) -> models.ScrapeSource:
    src = db.scalar(select(models.ScrapeSource).where(models.ScrapeSource.name == name))
    if src:
        return src
    src = models.ScrapeSource(name=name, kind=name, base_url="", enabled=True)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def run_scraper(db: Session, name: str, limit: int | None = None) -> dict:
    """Run the named scraper end-to-end, upserting offers into the DB.

    Returns a summary dict with run metadata.
    """
    scraper_cls = registry.get_scraper(name)
    scraper = scraper_cls(limit=limit)

    source = _get_or_create_source(db, scraper.name, scraper.label or scraper.name)
    run = models.ScrapeRun(source_id=source.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    found = 0
    created_or_updated = 0
    error_msg: str | None = None
    try:
        for item in scraper.run():
            found += 1
            offer_data = item.to_dict()
            offer_data["source"] = scraper.name
            offer_data["scraped_at"] = datetime.utcnow()
            # Parse date strings back to date objects for the ORM.
            from datetime import date

            for k in ("starts_at", "ends_at"):
                v = offer_data.get(k)
                if isinstance(v, str):
                    offer_data[k] = date.fromisoformat(v)
            crud.create_offer(db, offer_data)
            created_or_updated += 1
            if limit and found >= limit:
                break
        run.status = "ok"
    except Exception as exc:  # keep the partial progress
        log.exception("scraper %s failed", name)
        error_msg = f"{type(exc).__name__}: {exc}"
        run.status = "error"
        run.error = error_msg
    finally:
        run.finished_at = datetime.utcnow()
        run.items_found = found
        run.items_new = created_or_updated
        source.last_run_at = datetime.utcnow()
        db.commit()
        db.refresh(run)

    return {
        "run_id": run.id,
        "scraper": scraper.name,
        "status": run.status,
        "items_found": found,
        "items_upserted": created_or_updated,
        "error": error_msg,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(models.ScrapeRun).order_by(models.ScrapeRun.started_at.desc()).limit(limit)
    ).all()
    out = []
    for r in rows:
        src = db.get(models.ScrapeSource, r.source_id)
        out.append(
            {
                "id": r.id,
                "source": src.name if src else None,
                "status": r.status,
                "items_found": r.items_found,
                "items_new": r.items_new,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error": r.error,
            }
        )
    return out
