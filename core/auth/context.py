from dataclasses import dataclass


@dataclass
class UserContext:
    user_id: int | None
    tenant_id: int | None
    email: str
    role: str
    is_dev: bool = False

    def is_admin(self) -> bool:
        return self.role.lower() == "admin"
