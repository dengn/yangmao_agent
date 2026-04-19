"""Demo scraper with hard-coded offers — useful for smoke testing the pipeline.

Run it with:  python -m app.cli scrape demo
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from app.scrapers.base import BaseScraper, ScrapedOffer
from app.scrapers.registry import register


@register
class DemoScraper(BaseScraper):
    name = "demo"
    label = "Demo（本地假数据）"
    description = "用于验证爬虫流水线是否跑通，不访问网络。"

    def run(self) -> Iterable[ScrapedOffer]:
        today = date.today()
        yield ScrapedOffer(
            source_id="demo-1",
            title="招行周三星巴克 5 折",
            offer_type="discount",
            issuer="招商",
            merchant="星巴克",
            reward_value=0.5,
            reward_cap=25,
            starts_at=today,
            ends_at=today + timedelta(days=60),
            source_url="https://example.com/demo/1",
            tags=["餐饮", "咖啡"],
            description="每周三星巴克 5 折，每月最多 2 次",
        )
        yield ScrapedOffer(
            source_id="demo-2",
            title="中信笔笔返 1%",
            offer_type="cashback",
            issuer="中信",
            min_spend=100,
            reward_value=0.01,
            reward_cap=200,
            starts_at=today,
            ends_at=today + timedelta(days=90),
            source_url="https://example.com/demo/2",
            tags=["返现"],
        )
        yield ScrapedOffer(
            source_id="demo-3",
            title="平安生日月双倍积分",
            offer_type="points_multiplier",
            issuer="平安",
            reward_value=2,
            starts_at=today,
            ends_at=today + timedelta(days=365),
            source_url="https://example.com/demo/3",
            tags=["积分", "生日"],
        )
