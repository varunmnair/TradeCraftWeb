from core.services.holdings_service import HoldingsService


class StubAnalyzer:
    def __init__(self, user_id, broker_name):
        self.user_id = user_id
        self.broker_name = broker_name

    def analyze_holdings(self, broker, cmp_manager, filters=None, sort_by="ROI/Day"):
        return [{"Symbol": "AAA", "P&L": float("nan")}, {"Symbol": "BBB", "P&L": 5.0}]


class DummyContext:
    def __init__(self, holdings):
        self.session_cache = DummySessionCache(holdings)
        self.broker = DummyBroker()
        self.broker_name = "dummy"


class DummySessionCache:
    def __init__(self, holdings):
        self._holdings = holdings

    def get_holdings(self):
        return self._holdings

    def get_cmp_manager(self):
        return object()


class DummyBroker:
    user_id = "test-user"


class DummyRegistry:
    def __init__(self, context):
        self._context = context

    def get_session(self, session_id):
        return self._context


def test_holdings_service_analyze_and_snapshot():
    holdings = [{"symbol": "ABC", "pnl": float("nan")}, {"symbol": "XYZ", "pnl": 10.5}]
    context = DummyContext(holdings)
    registry = DummyRegistry(context)
    service = HoldingsService(registry, analyzer_cls=StubAnalyzer)

    snapshot = service.get_holdings_snapshot("session-1")
    assert snapshot[0]["pnl"] is None

    analysis = service.analyze_holdings("session-1")
    assert analysis["items"][0]["P&L"] is None
