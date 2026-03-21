from core.runtime.session_registry import SessionRegistry


class DummyBroker:
    broker_name = "dummy"

    def __init__(self, broker_user_id: str):
        self.broker_user_id = broker_user_id

    def get_holdings(self):
        return []

    def load_entry_levels(self, _path):
        return []

    def get_gtt_orders(self):
        return []


class DummyBrokerFactory:
    def get_broker(self, broker_name, broker_user_id, config):
        assert broker_name == "dummy"
        return DummyBroker(broker_user_id)


def test_create_session_records_context():
    registry = SessionRegistry(broker_factory=DummyBrokerFactory())
    context = registry.create_session(broker_user_id="alice", broker_name="dummy", broker_config={})

    assert context.session_id
    restored = registry.get_session(context.session_id)
    assert restored is not None
    assert restored.broker_user_id == "alice"
