"""Analysis / reporting functions.

Three user-visible pieces:

1. :func:`evaluate_owned_card` — summarize net annual value of a card we hold.
2. :func:`evaluate_prospect_card` — compute net value for a hypothetical new
   card given structured input.
3. :func:`monthly_report` / :func:`yearly_report` — aggregate the
   ``transactions`` table.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app import models


# ---------- Owned-card evaluation ----------

@dataclass
class CardEvaluation:
    card_id: int
    card_label: str
    annual_fee: float
    annual_fee_waiver: str | None
    opening_bonus_value: float
    total_benefits_estimated: float
    benefits_breakdown: list[dict]
    actual_rewards_12m: float
    actual_tx_count_12m: int
    net_ongoing_annual: float  # benefits - annual_fee
    net_first_year: float  # + opening bonus
    net_observed_12m: float  # actual rewards - annual fee
    signal: str
    notes: list[str]


def evaluate_owned_card(db: Session, card_id: int) -> dict:
    card = db.get(models.Card, card_id)
    if not card:
        return {"error": "card not found"}

    benefits = list(
        db.scalars(select(models.Benefit).where(models.Benefit.card_id == card_id))
    )
    bonuses_total = sum(b.estimated_annual_value or 0 for b in benefits)
    benefits_breakdown = [
        {
            "id": b.id,
            "title": b.title,
            "category": b.category,
            "times_per_cycle": b.times_per_cycle,
            "reset_cycle": b.reset_cycle,
            "estimated_annual_value": b.estimated_annual_value,
        }
        for b in benefits
    ]

    opening_bonus = card.opening_bonus_value or 0
    annual_fee = card.annual_fee or 0

    # 12-month actuals from transactions
    cutoff = date.today().replace(year=date.today().year - 1)
    tx_rows = list(
        db.scalars(
            select(models.Transaction).where(
                and_(
                    models.Transaction.card_id == card_id,
                    models.Transaction.occurred_on >= cutoff,
                )
            )
        )
    )
    actual_rewards = sum(t.reward_value or 0 for t in tx_rows)
    tx_count = len(tx_rows)

    net_ongoing = bonuses_total - annual_fee
    net_first_year = bonuses_total + opening_bonus - annual_fee
    net_observed = actual_rewards - annual_fee

    notes: list[str] = []
    signal = "neutral"
    if annual_fee == 0:
        signal = "free"
        notes.append("无年费，持有几乎无成本。")
    else:
        if net_ongoing > annual_fee * 1.5:
            signal = "strong_keep"
            notes.append("预估权益价值远高于年费，强烈推荐保留。")
        elif net_ongoing > 0:
            signal = "keep"
            notes.append("权益价值覆盖年费，可以保留。")
        elif net_ongoing > -annual_fee * 0.3:
            signal = "marginal"
            notes.append("权益价值接近年费，需要结合实际使用情况判断。")
        else:
            signal = "consider_close"
            notes.append("预估权益价值明显低于年费，可以考虑销卡或协商年费减免。")

    missing_value = [b.title for b in benefits if b.estimated_annual_value is None]
    if missing_value:
        notes.append(
            f"有 {len(missing_value)} 条权益还没填 `estimated_annual_value`，"
            f"估算可能偏低：{', '.join(missing_value[:3])}"
            + ("..." if len(missing_value) > 3 else "")
        )
    if tx_count == 0:
        notes.append("过去 12 个月没有消费记录，actual 部分基于 0 计算。")

    return {
        "card_id": card.id,
        "card_label": f"{card.issuer} {card.name}",
        "annual_fee": annual_fee,
        "annual_fee_waiver": card.annual_fee_waiver,
        "opening_bonus_value": opening_bonus,
        "total_benefits_estimated": round(bonuses_total, 2),
        "benefits_breakdown": benefits_breakdown,
        "actual_rewards_12m": round(actual_rewards, 2),
        "actual_tx_count_12m": tx_count,
        "net_ongoing_annual": round(net_ongoing, 2),
        "net_first_year": round(net_first_year, 2),
        "net_observed_12m": round(net_observed, 2),
        "signal": signal,
        "notes": notes,
    }


# ---------- Prospect-card evaluation ----------

def evaluate_prospect_card(payload: dict[str, Any]) -> dict:
    """Compute net value for a hypothetical card from structured input.

    Expected keys: issuer, name, annual_fee, annual_fee_waiver,
    opening_bonus_value, benefits (list of {title, estimated_annual_value}).
    """
    annual_fee = float(payload.get("annual_fee") or 0)
    waiver = payload.get("annual_fee_waiver")
    opening_bonus = float(payload.get("opening_bonus_value") or 0)
    benefits = payload.get("benefits") or []

    total_benefits = sum(float(b.get("estimated_annual_value") or 0) for b in benefits)

    net_first_year = total_benefits + opening_bonus - annual_fee
    net_ongoing = total_benefits - annual_fee

    signal = "neutral"
    if net_first_year > 0 and net_ongoing > 0:
        signal = "recommend"
    elif net_first_year > 0 and net_ongoing <= 0:
        signal = "first_year_only"
    elif waiver and net_ongoing + annual_fee > 0:
        # 减免条件达成后等价于无年费
        signal = "worth_if_waiver"
    else:
        signal = "skip"

    explanation = {
        "recommend": "首年净收益为正且长期持有也划算，推荐申请。",
        "first_year_only": "首年能薅，但长期持有不划算，作为首年卡申请、到期销卡。",
        "worth_if_waiver": "年费减免条件达成时等价无年费卡，满足刷卡门槛就可以持有。",
        "skip": "首年净收益都难为正，不推荐。",
        "neutral": "信息不足或临界，自己权衡。",
    }[signal]

    return {
        "card_label": f"{payload.get('issuer','?')} {payload.get('name','?')}",
        "annual_fee": annual_fee,
        "annual_fee_waiver": waiver,
        "opening_bonus_value": opening_bonus,
        "total_benefits_estimated": round(total_benefits, 2),
        "benefits_count": len(benefits),
        "net_first_year": round(net_first_year, 2),
        "net_ongoing_annual": round(net_ongoing, 2),
        "signal": signal,
        "explanation": explanation,
    }


# ---------- Monthly / yearly report ----------

def monthly_report(db: Session, year: int, month: int) -> dict:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return _period_report(db, start, end, label=f"{year}-{month:02d}")


def yearly_report(db: Session, year: int) -> dict:
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    return _period_report(db, start, end, label=str(year))


def _period_report(db: Session, start: date, end: date, label: str) -> dict:
    rows = list(
        db.scalars(
            select(models.Transaction).where(
                and_(
                    models.Transaction.occurred_on >= start,
                    models.Transaction.occurred_on < end,
                )
            )
        )
    )

    total_spend = sum(t.amount for t in rows)
    total_reward = sum(t.reward_value or 0 for t in rows)

    by_card: dict[int, dict] = defaultdict(lambda: {"spend": 0.0, "reward": 0.0, "count": 0})
    by_merchant: dict[str, dict] = defaultdict(lambda: {"spend": 0.0, "reward": 0.0, "count": 0})
    offer_hits: dict[int, int] = defaultdict(int)

    for t in rows:
        by_card[t.card_id]["spend"] += t.amount
        by_card[t.card_id]["reward"] += t.reward_value or 0
        by_card[t.card_id]["count"] += 1
        if t.merchant:
            by_merchant[t.merchant]["spend"] += t.amount
            by_merchant[t.merchant]["reward"] += t.reward_value or 0
            by_merchant[t.merchant]["count"] += 1
        if t.offer_id:
            offer_hits[t.offer_id] += 1

    card_summary = []
    for cid, stats in by_card.items():
        card = db.get(models.Card, cid)
        card_summary.append(
            {
                "card_id": cid,
                "card_label": f"{card.issuer} {card.name}" if card else f"card#{cid}",
                "spend": round(stats["spend"], 2),
                "reward": round(stats["reward"], 2),
                "tx_count": stats["count"],
                "reward_rate": round(stats["reward"] / stats["spend"], 4) if stats["spend"] else 0,
            }
        )
    card_summary.sort(key=lambda x: x["reward"], reverse=True)

    merchant_summary = [
        {"merchant": m, "spend": round(v["spend"], 2), "reward": round(v["reward"], 2), "tx_count": v["count"]}
        for m, v in sorted(by_merchant.items(), key=lambda kv: kv[1]["reward"], reverse=True)[:10]
    ]

    offers_used = []
    for oid, count in sorted(offer_hits.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        off = db.get(models.Offer, oid)
        if off:
            offers_used.append({"offer_id": oid, "title": off.title, "hits": count})

    return {
        "period": label,
        "tx_count": len(rows),
        "total_spend": round(total_spend, 2),
        "total_reward": round(total_reward, 2),
        "reward_rate": round(total_reward / total_spend, 4) if total_spend else 0,
        "by_card": card_summary,
        "top_merchants": merchant_summary,
        "top_offers": offers_used,
    }
