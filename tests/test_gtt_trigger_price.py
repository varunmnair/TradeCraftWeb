"""Regression tests for Zerodha GTT trigger-price normalization."""

from unittest.mock import MagicMock

from brokers.zerodha_broker import ZerodhaBroker
from core.gtt_manage import GTTManager

RAW_GTTS = [
    {
        "id": 346356626,
        "user_id": "NM9165",
        "parent_trigger": None,
        "type": "single",
        "created_at": "2026-11-25 21:07:42",
        "updated_at": "2026-11-25 21:07:42",
        "expires_at": "2027-11-25 21:07:42",
        "status": "active",
        "condition": {
            "exchange": "BSE",
            "last_price": 499.5,
            "tradingsymbol": "SANDHAR",
            "trigger_values": [510],
            "instrument_token": 138537732,
        },
        "orders": [
            {
                "exchange": "BSE",
                "tradingsymbol": "SANDHAR",
                "product": "CNC",
                "order_type": "MARKET",
                "transaction_type": "BUY",
                "quantity": 10,
                "price": 0,
                "market_protection": -1,
                "result": None,
            }
        ],
        "meta": {},
    },
    {
        "id": 345887597,
        "user_id": "NM9165",
        "parent_trigger": None,
        "type": "single",
        "created_at": "2026-11-22 13:56:53",
        "updated_at": "2026-11-24 09:02:59",
        "expires_at": "2027-11-22 13:56:53",
        "status": "active",
        "condition": {
            "exchange": "NSE",
            "last_price": 452.8,
            "tradingsymbol": "GNFC",
            "trigger_values": [460],
            "instrument_token": 300545,
        },
        "orders": [
            {
                "exchange": "NSE",
                "tradingsymbol": "GNFC",
                "product": "CNC",
                "order_type": "LIMIT",
                "transaction_type": "BUY",
                "quantity": 20,
                "price": 460,
                "result": None,
            }
        ],
        "meta": {},
    },
]


class DummyCmpManager:
    def get_cmp(self, _exchange, symbol):
        return {"SANDHAR": 499.5, "GNFC": 445.4}.get(symbol)


class DummySession:
    def __init__(self, cache):
        self.cache = cache

    def get_gtt_cache(self):
        return self.cache

    def get_entry_levels(self):
        return []

    def refresh_gtt_cache(self):
        return None


def _normalized_gtts():
    broker = ZerodhaBroker(broker_user_id="NM9165", api_key="test_key")
    kite = MagicMock()
    kite.get_gtts.return_value = RAW_GTTS
    broker.kite = kite
    return broker.get_gtt_orders()


def test_zerodha_get_gtt_orders_reads_nested_condition_fields():
    normalized = _normalized_gtts()
    sandhar = next(item for item in normalized if item["id"] == 346356626)

    assert sandhar["condition"]["exchange"] == "BSE"
    assert sandhar["condition"]["tradingsymbol"] == "SANDHAR"
    assert sandhar["condition"]["last_price"] == 499.5
    assert sandhar["condition"]["trigger_values"] == [510]


def test_gtt_analysis_uses_condition_trigger_for_market_orders():
    manager = GTTManager(
        ZerodhaBroker(broker_user_id="NM9165", api_key="test_key"),
        DummyCmpManager(),
        DummySession(_normalized_gtts()),
    )

    orders = manager.analyze_gtt_buy_orders()
    by_symbol = {order["Symbol"]: order for order in orders}

    assert by_symbol["SANDHAR"]["Trigger Price"] == 510
    assert by_symbol["SANDHAR"]["Variance (%)"] == -2.06
    assert by_symbol["SANDHAR"]["Buy Amount"] == 4995
    assert by_symbol["GNFC"]["Trigger Price"] == 460
    assert all(order["Trigger Price"] > 0 for order in orders)
