from .zerodha_broker import ZerodhaBroker
from .upstox_broker import UpstoxBroker


class BrokerFactory:
    @staticmethod
    def get_broker(broker_name, user_id, config):
        name = broker_name.lower()
        if name == "zerodha":
            return ZerodhaBroker(
                user_id=user_id,
                api_key=config.get("api_key"),
                access_token=config.get("access_token"),
            )
        if name == "upstox":
            return UpstoxBroker(
                user_id=user_id,
                api_key=config.get("api_key"),
                api_secret=config.get("api_secret"),
                redirect_uri=config.get("redirect_uri"),
                code=config.get("code"),
                access_token=config.get("access_token"),
            )
        raise ValueError(f"Broker '{broker_name}' is not supported.")
