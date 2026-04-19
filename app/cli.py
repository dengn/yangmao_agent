"""Command-line entry point for operational tasks.

Examples:
    python -m app.cli list-scrapers
    python -m app.cli scrape kahui --limit 20
    python -m app.cli scrape demo
    python -m app.cli runs
"""
from __future__ import annotations

import argparse
import json
import sys

from app.db import SessionLocal, init_db
from app.scrapers import registry, runner


def _list_scrapers(_):
    print(json.dumps(registry.available(), ensure_ascii=False, indent=2))


def _scrape(args):
    init_db()
    db = SessionLocal()
    try:
        result = runner.run_scraper(db, args.name, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1
    finally:
        db.close()


def _runs(args):
    init_db()
    db = SessionLocal()
    try:
        print(json.dumps(runner.list_runs(db, limit=args.limit), ensure_ascii=False, indent=2))
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-scrapers", help="列出已注册的爬虫").set_defaults(func=_list_scrapers)

    scrape = sub.add_parser("scrape", help="运行爬虫")
    scrape.add_argument("name")
    scrape.add_argument("--limit", type=int, default=None)
    scrape.set_defaults(func=_scrape)

    runs = sub.add_parser("runs", help="查看爬虫运行记录")
    runs.add_argument("--limit", type=int, default=20)
    runs.set_defaults(func=_runs)

    args = p.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
