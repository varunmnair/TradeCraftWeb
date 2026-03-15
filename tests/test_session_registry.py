from core.runtime.session_registry import SessionRegistry


class DummyBroker:
    broker_name = "dummy"

    def __init__(self, user_id: str):
        self.user_id = user_id

    # SessionCache refresh paths expect these methods
    def get_holdings(self):
        return []

    def load_entry_levels(self, _path):
        return []

    def get_gtt_orders(self):
        return []


class DummyBrokerFactory:
    def get_broker(self, broker_name, user_id, config):
        assert broker_name == "dummy"
        return DummyBroker(user_id)


def test_create_session_records_context():
    registry = SessionRegistry(broker_factory=DummyBrokerFactory())
    context = registry.create_session(user_id="alice", broker_name="dummy", broker_config={})

    assert context.session_id
    restored = registry.get_session(context.session_id)
    assert restored is not None
    assert restored.user_id == "alice"
