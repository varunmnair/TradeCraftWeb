from core.services.entry_plan_service import EntryPlanService


class DummyRegistry:
    def __init__(self, context):
        self._context = context

    def get_session(self, session_id):
        return self._context


class DummyContext:
    def __init__(self, holdings, entry_levels):
        self.session_cache = DummySessionCache(holdings, entry_levels)
        self.broker = DummyBroker()
        self.broker_name = "dummy"


class DummySessionCache:
    def __init__(self, holdings, entry_levels):
        self._holdings = holdings
        self._entry_levels = entry_levels

    def get_cmp_manager(self):
        return DummyCMP()

    def get_holdings(self):
        return self._holdings

    def get_entry_levels(self):
        return self._entry_levels

    def get_gtt_cache(self):
        return []


class DummyCMP:
    def get_cmp(self, exchange, symbol):
        return 100.0


class DummyBroker:
    user_id = "user-1"

    def get_gtt_orders(self):
        return []

    def trades(self):
        return []


def test_generate_plan_from_fixture_data():
    holdings = [
        {"tradingsymbol": "ABC", "quantity": 0, "t1_quantity": 0, "average_price": 0, "exchange": "NSE"}
    ]
    entry_levels = [
        {"symbol": "ABC", "exchange": "NSE", "Allocated": 1000, "entry1": 120, "entry2": 110, "entry3": 100}
    ]
    context = DummyContext(holdings, entry_levels)
    registry = DummyRegistry(context)

    service = EntryPlanService(registry)
    plan = service.generate_plan("session-1")

    assert plan["plan"]
    assert plan["plan"][0]["symbol"] == "ABC"
