#!/usr/bin/env python
"""Query order history from database."""
import argparse
import csv
import sys

from db.database import SessionLocal
from db.models import UserTrade


def query_orders(broker: str, symbol: str = None, limit: int = 50):
    db = SessionLocal()
    try:
        query = db.query(UserTrade).filter(UserTrade.broker == broker)
        if symbol:
            query = query.filter(UserTrade.symbol == symbol.upper())
        return query.order_by(UserTrade.trade_date.desc()).limit(limit).all()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Query order history from database")
    parser.add_argument("--broker", "-b", required=True, help="Broker name (e.g., upstox, zerodha)")
    parser.add_argument("--symbol", "-s", help="Filter by symbol")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Number of trades to show")
    parser.add_argument("--export", "-e", action="store_true", help="Export to CSV file")
    args = parser.parse_args()

    trades = query_orders(args.broker, args.symbol, args.limit)

    if args.export:
        filename = f"data/order_history_{args.broker}_{args.symbol or 'all'}.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "trade_date", "symbol", "side", "quantity", "price",
                "trade_id", "order_id", "exchange", "segment", "source", "captured_at"
            ])
            for t in trades:
                writer.writerow([
                    t.trade_date, t.symbol, t.side, t.quantity, t.price,
                    t.trade_id, t.order_id, t.exchange, t.segment, t.source, t.captured_at
                ])
        print(f"Exported {len(trades)} trades to {filename}")
    else:
        print(f"\nOrder History ({args.broker}) - {len(trades)} trades")
        print("-" * 90)
        for t in trades:
            print(f"  {t.trade_date} | {t.symbol:10} | {t.side:4} | {t.quantity:4} @ {t.price:8} | ID:{t.trade_id}")


if __name__ == "__main__":
    main()