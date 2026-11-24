from unittest.mock import Mock

import pytest

from api.routes.plan import (
    latest_dynamic_averaging_plan,
    latest_dynamic_avg_plan,
    latest_multi_level_plan,
    latest_plan,
)
from core.auth.context import UserContext

USER = UserContext(user_id=1, email="test@example.com", role="user")


@pytest.mark.parametrize(
    ("handler", "expected_strategy"),
    [
        (latest_multi_level_plan, "multi_level"),
        (latest_plan, "multi_level"),
        (latest_dynamic_averaging_plan, "dynamic_averaging"),
        (latest_dynamic_avg_plan, "dynamic_averaging"),
    ],
)
def test_latest_plan_returns_empty_payload_when_no_result(handler, expected_strategy):
    registry = Mock()
    job_runner = Mock()
    job_runner.get_latest_result.return_value = None

    result = handler(
        session_id="session-1",
        registry=registry,
        job_runner=job_runner,
        current_user=USER,
    )

    assert result.strategy_type == expected_strategy
    assert result.plan == []
    assert result.skipped == []
    registry.require_access.assert_called_once_with("session-1", USER)
