"""卡惠网 (51kahui.com) scraper — best-effort.

反爬注意：卡惠网（以及同类聚合站）对直接请求有反爬策略，沙箱环境里可能拿到 502/403。
在你本地网络跑一般 OK。如果被反爬，可以：

1. 先把首页/列表页 HTML 下载下来（浏览器或 curl），本地离线解析调试 selector。
2. 需要 JS 渲染时，加 Playwright：``pip install playwright && playwright install chromium``，
   然后把 ``_fetch`` 替换成 Playwright 版。
3. 极端情况下走代理或官方接口。

当前实现默认抓取"国内优惠"列表页，使用 BeautifulSoup 解析。SELECTOR 需要根据实际
页面结构调整——注释里写了我的猜测，跑一次看 ``items_found`` 是否为 0 就知道要不要改。
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedOffer
from app.scrapers.registry import register

log = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@register
class KahuiScraper(BaseScraper):
    name = "kahui"
    label = "卡惠网"
    description = "抓取 51kahui.com 国内优惠列表"

    BASE = "https://www.51kahui.com"
    LIST_PATH = "/youhui/"

    # CSS selectors — 可能需要按实际页面调整。
    ITEM_SEL = "ul.merchant-list > li, .activity-item, .youhui-item"
    TITLE_SEL = ".title, h3, a.name"
    MERCHANT_SEL = ".merchant, .shop-name"
    BANK_SEL = ".bank, .bank-name"
    DESC_SEL = ".desc, .content, p"
    DATE_SEL = ".date, .time, .period"
    LINK_SEL = "a"

    def _fetch(self, url: str) -> str:
        with httpx.Client(timeout=15, follow_redirects=True, headers=DEFAULT_HEADERS) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text

    def run(self) -> Iterable[ScrapedOffer]:
        url = urljoin(self.BASE, self.LIST_PATH)
        html = self._fetch(url)
        soup = BeautifulSoup(html, "lxml")

        items = soup.select(self.ITEM_SEL)
        log.info("kahui: %d items found at %s", len(items), url)
        if not items:
            log.warning("kahui: 0 items — selectors likely need tuning. first 500 chars: %r", html[:500])
            return

        count = 0
        for el in items:
            if self.limit and count >= self.limit:
                break
            offer = _parse_item(el, self)
            if offer:
                yield offer
                count += 1


def _text(el, selector: str) -> str | None:
    hit = el.select_one(selector)
    if not hit:
        return None
    return " ".join(hit.stripped_strings) or None


def _parse_item(el, s: KahuiScraper) -> ScrapedOffer | None:
    title = _text(el, s.TITLE_SEL)
    if not title:
        return None
    merchant = _text(el, s.MERCHANT_SEL)
    issuer = _text(el, s.BANK_SEL)
    desc = _text(el, s.DESC_SEL)
    period = _text(el, s.DATE_SEL)
    starts_at, ends_at = _parse_period(period)

    link_el = el.select_one(s.LINK_SEL)
    href = link_el.get("href") if link_el else None
    source_url = urljoin(s.BASE, href) if href else None

    source_id = None
    if source_url:
        m = re.search(r"/(\d+)(?:\.html?)?/?$", source_url)
        if m:
            source_id = f"kahui:{m.group(1)}"
    if not source_id:
        # fall back to a hash-like id from title+merchant
        source_id = f"kahui:{hash((title, merchant)) & 0xffffffff:x}"

    offer_type = _guess_offer_type(title, desc or "")

    return ScrapedOffer(
        source_id=source_id,
        title=title,
        offer_type=offer_type,
        issuer=_normalize_issuer(issuer),
        description=desc,
        merchant=merchant,
        starts_at=starts_at,
        ends_at=ends_at,
        source_url=source_url,
    )


_DATE_RE = re.compile(
    r"(\d{4})[./年-](\d{1,2})[./月-](\d{1,2})\s*[日号]?"
)


def _parse_period(text: str | None) -> tuple[date | None, date | None]:
    if not text:
        return None, None
    hits = _DATE_RE.findall(text)
    if not hits:
        return None, None
    dates = []
    for y, m, d in hits[:2]:
        try:
            dates.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    if len(dates) == 1:
        return None, dates[0]
    if len(dates) >= 2:
        return dates[0], dates[1]
    return None, None


_TYPE_HINTS = [
    ("cashback", ("返现", "笔笔返", "现金")),
    ("discount", ("折", "减", "立减")),
    ("points_multiplier", ("倍积分", "多倍", "积分")),
    ("installment", ("分期", "免息")),
    ("gift", ("礼", "赠", "送")),
]


def _guess_offer_type(*texts: str) -> str:
    blob = " ".join(texts)
    for kind, kws in _TYPE_HINTS:
        if any(k in blob for k in kws):
            return kind
    return "other"


_ISSUER_MAP = {
    "招行": "招商",
    "招商银行": "招商",
    "中信银行": "中信",
    "平安银行": "平安",
    "浦发银行": "浦发",
    "广发银行": "广发",
    "交通银行": "交通",
    "民生银行": "民生",
    "建设银行": "建设",
    "工商银行": "工商",
    "中国银行": "中行",
    "农业银行": "农业",
}


def _normalize_issuer(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    for k, v in _ISSUER_MAP.items():
        if k in s:
            return v
    return s
