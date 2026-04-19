from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Iterable


@dataclass
class ScrapedOffer:
    """Normalized shape emitted by scrapers.

    Maps roughly 1:1 onto :class:`app.models.Offer`. Fields not known to the
    scraper can be left as None; the runner fills in ``source``,
    ``scraped_at`` and dedups on ``(source, source_id)``.
    """

    title: str
    offer_type: str  # cashback/discount/points_multiplier/installment/gift/other
    source_id: str | None = None  # external stable id — required for dedup
    issuer: str | None = None
    description: str | None = None
    merchant: str | None = None
    min_spend: float | None = None
    reward_value: float | None = None
    reward_cap: float | None = None
    starts_at: date | None = None
    ends_at: date | None = None
    source_url: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["starts_at"] = self.starts_at.isoformat() if self.starts_at else None
        d["ends_at"] = self.ends_at.isoformat() if self.ends_at else None
        return d


class BaseScraper(ABC):
    """Abstract scraper. Subclasses set :attr:`name` and implement :meth:`run`."""

    name: str = ""  # short id, e.g. "kahui"
    label: str = ""  # display label, e.g. "卡惠网"
    description: str = ""

    def __init__(self, limit: int | None = None):
        self.limit = limit

    @abstractmethod
    def run(self) -> Iterable[ScrapedOffer]:
        """Yield scraped offers. Exceptions are caught by the runner."""
        raise NotImplementedError
