from .upstox_broker import UpstoxBroker
from .zerodha_broker import ZerodhaBroker


class BrokerFactory:
    @staticmethod
    def get_broker(broker_name, broker_user_id, config):
        name = broker_name.lower()
        if name == "zerodha":
            return ZerodhaBroker(
                broker_user_id=broker_user_id,
                api_key=config.get("api_key"),
                access_token=config.get("access_token"),
            )
        if name == "upstox":
            return UpstoxBroker(
                broker_user_id=broker_user_id,
                api_key=config.get("api_key"),
                api_secret=config.get("api_secret"),
                redirect_uri=config.get("redirect_uri"),
                code=config.get("code"),
                access_token=config.get("access_token"),
            )
        raise ValueError(f"Broker '{broker_name}' is not supported.")
