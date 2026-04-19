"""Claude-powered yangmao agent.

Exposes DB-backed tools to the model so the user can manage cards/benefits/
offers and get recommendations in natural language.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import anthropic
from sqlalchemy.orm import Session

from app import crud, models
from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL


SYSTEM_PROMPT = """\
你是一个中文信用卡薅羊毛助手（yangmao agent），帮用户管理他手头的信用卡、权益和优惠活动。

你的主要能力：
1. 管理信用卡：新增、查询、删除、修改持有的信用卡。
2. 管理权益：记录每张卡的固定权益（例如贵宾厅、酒店会籍、生日积分等）。
3. 管理优惠：记录限时优惠活动（例如某商户双倍积分、笔笔返现等），包含有效期。
4. 推荐用卡：根据商户/金额/类型，结合当前生效的优惠，推荐最该刷的卡。
5. 持卡评估：用 evaluate_owned_card 算某张已有卡的净年价值，判断要不要继续留。
6. 新卡评估：用 evaluate_prospect_card 算年费 + 开卡礼 + 权益 的净收益。
   信息不足时用 web_search 查公开资料（银行官网/媒体评测）。
7. 报告：用 monthly_report / yearly_report 汇总实际薅到的价值。
8. 数据抓取：可调用 run_scraper 让爬虫抓最新优惠。

原则：
- 回复使用简体中文，除非用户明确用英文。
- 信息不明确时先用工具查询 DB，不要凭空捏造。
- 新增任何数据前，先把你要存的关键字段复述给用户确认，除非用户已经明确同意。
- 涉及金额/日期时，如果用户只给了模糊信息（"下个月"、"几百块"），主动澄清。
- 新卡评估时如果用户只给了卡名，先 web_search 查年费/权益，结果写成结构化输入再调 evaluate_prospect_card。
- 回答简洁，不要啰嗦；关键数据用表格或列表。
"""


# ---------- Tool definitions (JSON Schema for Claude) ----------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_cards",
        "description": "列出用户持有的信用卡。可按状态过滤。",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "closed", "pending"],
                    "description": "卡片状态过滤，留空则返回全部。",
                },
            },
        },
    },
    {
        "name": "create_card",
        "description": "新增一张信用卡。",
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer": {"type": "string", "description": "发卡行（招商、中信、平安等）"},
                "name": {"type": "string", "description": "卡种名（如 经典白金、YOUNG卡）"},
                "level": {"type": "string"},
                "network": {"type": "string", "description": "VISA/MasterCard/UnionPay/JCB/AmericanExpress"},
                "annual_fee": {"type": "number", "description": "年费（人民币）"},
                "annual_fee_waiver": {"type": "string", "description": "年费减免规则，自由文本"},
                "points_rule": {"type": "string", "description": "积分规则，自由文本"},
                "opened_at": {"type": "string", "description": "开卡日期 YYYY-MM-DD"},
                "notes": {"type": "string"},
            },
            "required": ["issuer", "name"],
        },
    },
    {
        "name": "update_card",
        "description": "更新已有信用卡的信息。",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["active", "closed", "pending"]},
                "annual_fee": {"type": "number"},
                "annual_fee_waiver": {"type": "string"},
                "points_rule": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["card_id"],
        },
    },
    {
        "name": "delete_card",
        "description": "删除一张信用卡（级联删除其权益）。",
        "input_schema": {
            "type": "object",
            "properties": {"card_id": {"type": "integer"}},
            "required": ["card_id"],
        },
    },
    {
        "name": "list_benefits",
        "description": "列出权益。可按卡或类别过滤。",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "integer"},
                "category": {"type": "string"},
            },
        },
    },
    {
        "name": "create_benefit",
        "description": "为某张卡新增固定权益。",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "integer"},
                "category": {
                    "type": "string",
                    "description": "lounge/hotel/dining/points/insurance/other",
                },
                "title": {"type": "string"},
                "description": {"type": "string"},
                "times_per_cycle": {"type": "integer"},
                "reset_cycle": {"type": "string", "enum": ["annual", "monthly", "quarterly"]},
                "valid_from": {"type": "string", "description": "YYYY-MM-DD"},
                "valid_until": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["category", "title"],
        },
    },
    {
        "name": "list_offers",
        "description": "查询优惠活动。可按卡/发卡行/商户/关键词/是否生效过滤。",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "integer"},
                "issuer": {"type": "string"},
                "merchant": {"type": "string"},
                "q": {"type": "string", "description": "关键词全文搜索"},
                "active_only": {"type": "boolean", "description": "只返回当前生效的"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "create_offer",
        "description": "新增一个优惠活动。",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "integer"},
                "issuer": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "offer_type": {
                    "type": "string",
                    "enum": ["cashback", "discount", "points_multiplier", "installment", "gift", "other"],
                },
                "merchant": {"type": "string"},
                "min_spend": {"type": "number"},
                "reward_value": {"type": "number"},
                "reward_cap": {"type": "number"},
                "starts_at": {"type": "string", "description": "YYYY-MM-DD"},
                "ends_at": {"type": "string", "description": "YYYY-MM-DD"},
                "source_url": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "offer_type"],
        },
    },
    {
        "name": "delete_offer",
        "description": "删除一条优惠活动。",
        "input_schema": {
            "type": "object",
            "properties": {"offer_id": {"type": "integer"}},
            "required": ["offer_id"],
        },
    },
    {
        "name": "recommend_card",
        "description": "根据商户/金额/消费类型，推荐该刷哪张卡（基于当前生效的优惠）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant": {"type": "string"},
                "amount": {"type": "number"},
                "category": {"type": "string", "description": "消费类型关键词，例如 餐饮/超市/线上/加油"},
            },
        },
    },
    {
        "name": "today",
        "description": "获取今天的日期。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_scrapers",
        "description": "列出可用的爬虫数据源。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_scraper",
        "description": "运行指定名字的爬虫，抓取最新优惠并写入数据库（会去重）。可能较慢。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "爬虫 name，例如 kahui / demo"},
                "limit": {"type": "integer", "description": "最多抓多少条"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_scrape_runs",
        "description": "查看最近的爬虫运行记录（成功/失败/条数）。",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
    },
    {
        "name": "evaluate_owned_card",
        "description": "评估用户手里某张卡的净年价值：年费 vs 权益 vs 实际消费返利，给出保留/销卡建议。",
        "input_schema": {
            "type": "object",
            "properties": {"card_id": {"type": "integer"}},
            "required": ["card_id"],
        },
    },
    {
        "name": "evaluate_prospect_card",
        "description": (
            "评估一张尚未申请的新卡：输入年费、开卡礼、权益（每项给 title 和预估年价值），"
            "输出首年净收益、长期净收益、是否推荐。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer": {"type": "string"},
                "name": {"type": "string"},
                "annual_fee": {"type": "number"},
                "annual_fee_waiver": {"type": "string"},
                "opening_bonus_value": {"type": "number"},
                "benefits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "estimated_annual_value": {"type": "number"},
                        },
                        "required": ["title"],
                    },
                },
            },
            "required": ["annual_fee", "benefits"],
        },
    },
    {
        "name": "monthly_report",
        "description": "月度薅羊毛报告：按卡/商户/优惠汇总该月消费与返利。",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
        },
    },
    {
        "name": "yearly_report",
        "description": "年度薅羊毛报告。",
        "input_schema": {
            "type": "object",
            "properties": {"year": {"type": "integer"}},
        },
    },
    # Anthropic server-side tool: 让模型联网查新卡资料
    {"type": "web_search_20260209", "name": "web_search"},
]


# ---------- Tool implementations ----------

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _card_to_dict(c: models.Card) -> dict:
    return {
        "id": c.id,
        "issuer": c.issuer,
        "name": c.name,
        "level": c.level,
        "network": c.network,
        "annual_fee": c.annual_fee,
        "annual_fee_waiver": c.annual_fee_waiver,
        "points_rule": c.points_rule,
        "opened_at": c.opened_at.isoformat() if c.opened_at else None,
        "status": c.status,
        "notes": c.notes,
    }


def _benefit_to_dict(b: models.Benefit) -> dict:
    return {
        "id": b.id,
        "card_id": b.card_id,
        "category": b.category,
        "title": b.title,
        "description": b.description,
        "times_per_cycle": b.times_per_cycle,
        "reset_cycle": b.reset_cycle,
        "valid_from": b.valid_from.isoformat() if b.valid_from else None,
        "valid_until": b.valid_until.isoformat() if b.valid_until else None,
    }


def _offer_to_dict(o: models.Offer) -> dict:
    return {
        "id": o.id,
        "card_id": o.card_id,
        "issuer": o.issuer,
        "title": o.title,
        "description": o.description,
        "offer_type": o.offer_type,
        "merchant": o.merchant,
        "min_spend": o.min_spend,
        "reward_value": o.reward_value,
        "reward_cap": o.reward_cap,
        "starts_at": o.starts_at.isoformat() if o.starts_at else None,
        "ends_at": o.ends_at.isoformat() if o.ends_at else None,
        "source": o.source,
        "source_url": o.source_url,
        "tags": o.tags,
    }


def execute_tool(db: Session, name: str, input_: dict) -> Any:
    if name == "today":
        return {"date": date.today().isoformat()}

    if name == "list_cards":
        cards = crud.list_cards(db, status=input_.get("status"))
        return [_card_to_dict(c) for c in cards]

    if name == "create_card":
        data = dict(input_)
        if "opened_at" in data:
            data["opened_at"] = _parse_date(data.get("opened_at"))
        card = crud.create_card(db, data)
        return _card_to_dict(card)

    if name == "update_card":
        card_id = input_.pop("card_id")
        card = crud.update_card(db, card_id, input_)
        return _card_to_dict(card) if card else {"error": "card not found"}

    if name == "delete_card":
        ok = crud.delete_card(db, input_["card_id"])
        return {"ok": ok}

    if name == "list_benefits":
        bs = crud.list_benefits(db, card_id=input_.get("card_id"), category=input_.get("category"))
        return [_benefit_to_dict(b) for b in bs]

    if name == "create_benefit":
        data = dict(input_)
        data["valid_from"] = _parse_date(data.get("valid_from"))
        data["valid_until"] = _parse_date(data.get("valid_until"))
        b = crud.create_benefit(db, data)
        return _benefit_to_dict(b)

    if name == "list_offers":
        offers = crud.list_offers(
            db,
            card_id=input_.get("card_id"),
            issuer=input_.get("issuer"),
            merchant=input_.get("merchant"),
            active_only=input_.get("active_only", False),
            q=input_.get("q"),
            limit=input_.get("limit", 50),
        )
        return [_offer_to_dict(o) for o in offers]

    if name == "create_offer":
        data = dict(input_)
        data["starts_at"] = _parse_date(data.get("starts_at"))
        data["ends_at"] = _parse_date(data.get("ends_at"))
        data.setdefault("source", "manual")
        o = crud.create_offer(db, data)
        return _offer_to_dict(o)

    if name == "delete_offer":
        ok = crud.delete_offer(db, input_["offer_id"])
        return {"ok": ok}

    if name == "recommend_card":
        return _recommend_card(
            db,
            merchant=input_.get("merchant"),
            amount=input_.get("amount"),
            category=input_.get("category"),
        )

    if name == "list_scrapers":
        from app.scrapers import registry

        return registry.available()

    if name == "run_scraper":
        from app.scrapers import runner

        return runner.run_scraper(db, input_["name"], limit=input_.get("limit"))

    if name == "list_scrape_runs":
        from app.scrapers import runner

        return runner.list_runs(db, limit=input_.get("limit", 10))

    if name == "evaluate_owned_card":
        from app import analysis

        return analysis.evaluate_owned_card(db, input_["card_id"])

    if name == "evaluate_prospect_card":
        from app import analysis

        return analysis.evaluate_prospect_card(input_)

    if name == "monthly_report":
        from app import analysis
        from datetime import date as _d

        today = _d.today()
        return analysis.monthly_report(
            db, input_.get("year", today.year), input_.get("month", today.month)
        )

    if name == "yearly_report":
        from app import analysis
        from datetime import date as _d

        return analysis.yearly_report(db, input_.get("year", _d.today().year))

    return {"error": f"unknown tool: {name}"}


def _recommend_card(db: Session, merchant: str | None, amount: float | None, category: str | None):
    """Naive scoring: find active offers matching the query, then rank."""
    q_terms = [t for t in [merchant, category] if t]
    hits: list[tuple[models.Offer, float]] = []
    offers = crud.list_offers(db, active_only=True, limit=500)
    for o in offers:
        score = 0.0
        haystack = " ".join(
            filter(None, [o.title, o.description, o.merchant, " ".join(o.tags or [])])
        ).lower()
        for term in q_terms:
            if term and term.lower() in haystack:
                score += 1
        if merchant and o.merchant and merchant.lower() in o.merchant.lower():
            score += 2
        if score == 0:
            continue
        # estimated value
        value = o.reward_value or 0
        if amount and o.offer_type == "cashback" and o.reward_value and o.reward_value < 1:
            value = min(amount * o.reward_value, o.reward_cap or float("inf"))
        hits.append((o, score + value / 100.0))

    hits.sort(key=lambda x: x[1], reverse=True)
    top = hits[:5]
    return [
        {
            "offer": _offer_to_dict(o),
            "card": _card_to_dict(o.card) if o.card else None,
            "score": round(s, 2),
        }
        for o, s in top
    ]


# ---------- Chat loop ----------

def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run_chat(db: Session, user_message: str, history: list[dict] | None = None) -> dict:
    """Run one turn of the agent.

    history: list of {"role": "user"|"assistant", "content": ...} following
    Anthropic's message format; content can be a string or the full block list.
    """
    client = _get_client()
    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": user_message})

    tool_calls_log: list[dict] = []
    final_text = ""

    # Agentic loop — up to 8 iterations for safety.
    for _ in range(8):
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        # Record assistant's content blocks (preserves tool_use for next turn).
        messages.append({"role": "assistant", "content": [b.model_dump() for b in response.content]})

        if response.stop_reason == "pause_turn":
            # server-side tool (e.g. web_search) hit its internal limit; resume.
            continue

        if response.stop_reason != "tool_use":
            final_text = "\n".join(
                b.text for b in response.content if b.type == "text"
            )
            break

        # Execute every client-side tool_use block; pack results into a single user message.
        # Server-side tool results (web_search_tool_result etc.) come back inline and
        # should not be echoed as tool_result by us.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = execute_tool(db, block.name, dict(block.input))
                tool_calls_log.append({"name": block.name, "input": block.input, "result": result})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            except Exception as exc:  # surface errors back to the model
                tool_calls_log.append({"name": block.name, "input": block.input, "error": str(exc)})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"tool error: {exc}",
                        "is_error": True,
                    }
                )

        messages.append({"role": "user", "content": tool_results})
    else:
        final_text = "（达到工具调用上限，请拆分请求。）"

    return {
        "reply": final_text,
        "history": messages,
        "tool_calls": tool_calls_log,
    }
