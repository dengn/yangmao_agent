"""Scraper framework for 薅羊毛 agent.

Each scraper is a subclass of :class:`BaseScraper` registered in
:mod:`app.scrapers.registry`. A scraper's :meth:`run` method yields
:class:`ScrapedOffer` instances; the :mod:`app.scrapers.runner` handles
upserting them into the DB and writing a :class:`~app.models.ScrapeRun`
entry for audit.
"""
from app.scrapers.base import BaseScraper, ScrapedOffer  # noqa: F401
from app.scrapers.registry import available, get_scraper  # noqa: F401
