from dataclasses import dataclass


@dataclass
class UserContext:
    user_id: int | None
    tenant_id: int | None
    email: str
    role: str
    is_dev: bool = False
    active_broker_connection_id: int | None = None
    trading_enabled: bool = False

    def is_admin(self) -> bool:
        return self.role.lower() == "admin"
