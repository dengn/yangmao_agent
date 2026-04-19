from __future__ import annotations

from typing import Type

from app.scrapers.base import BaseScraper

_registry: dict[str, Type[BaseScraper]] = {}


def register(cls: Type[BaseScraper]) -> Type[BaseScraper]:
    if not cls.name:
        raise ValueError(f"scraper {cls.__name__} missing `name` attribute")
    _registry[cls.name] = cls
    return cls


def available() -> list[dict]:
    return [
        {"name": c.name, "label": c.label, "description": c.description}
        for c in _registry.values()
    ]


def get_scraper(name: str) -> Type[BaseScraper]:
    if name not in _registry:
        raise KeyError(f"unknown scraper: {name!r}. available: {list(_registry)}")
    return _registry[name]


def _load_builtins():
    # Import for side effects so @register decorators run.
    from app.scrapers import demo, kahui  # noqa: F401


_load_builtins()
