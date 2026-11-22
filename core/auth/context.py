from dataclasses import dataclass


@dataclass
class UserContext:
    user_id: int | None
    email: str
    role: str
    is_dev: bool = False
    device_id: str | None = None
    active_broker_connection_id: int | None = None
    trading_enabled: bool = False
    is_premium: bool = False

    def is_admin(self) -> bool:
        return self.role.lower() == "admin"
