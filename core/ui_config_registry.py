"""Built-in UI configuration registry.

This is the server-side source of truth for configurable pages/columns and
capability validation. It must stay synchronized with the frontend registry
shape (serializable fields only).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

UI_CONFIG_SCHEMA_VERSION = 1

SUPPORTED_PAGE_IDS = [
    "holdings",
    "entry_strategies",
    "entry_candidates",
    "buy_orders",
    "jobs",
]

# Pages where symbol search may be enabled by admin config. None of the currently
# supported trading table pages are approved for search.
SEARCH_ALLOWED_PAGE_IDS: set[str] = set()

ALLOWED_DENSITIES = {"compact", "comfortable"}
ALLOWED_PAGE_SIZES = [25, 50, 100]


def _col(
    col_id: str,
    label: str,
    data_type: str,
    visible: bool = True,
    sortable: bool = True,
    filterable: bool = True,
    position: int = 0,
    required: bool = False,
    mobile_primary: bool = False,
    mobile_detail: bool = False,
    width: int | None = None,
) -> dict[str, Any]:
    return {
        "id": col_id,
        "label": label,
        "dataType": data_type,
        "visible": True if required else visible,
        "sortable": bool(sortable),
        "filterable": bool(filterable),
        "position": position,
        "required": bool(required),
        "mobilePrimary": bool(mobile_primary),
        "mobileDetail": bool(mobile_detail),
        **({"width": width} if width is not None else {}),
    }


BUILTIN_UI_PAGE_CONFIGS: dict[str, dict[str, Any]] = {
    "jobs": {
        "pageId": "jobs",
        "searchEnabled": False,
        "searchField": None,
        "defaultSort": {"field": "created_at", "direction": "desc"},
        "defaultPageSize": 25,
        "allowedPageSizes": [25, 50, 100],
        "density": "compact",
        "selectionEnabled": True,
        "mobilePrimaryFields": ["job_type", "status"],
        "mobileDetailFields": ["id", "session_id", "progress", "created_at"],
        "columns": [
            _col("id", "ID", "number", position=0, width=90, mobile_detail=True),
            _col("job_type", "Type", "categorical", position=1, width=180, mobile_primary=True),
            _col("session_id", "Session", "text", position=2, mobile_detail=True),
            _col("status", "Status", "categorical", position=3, width=140, mobile_primary=True),
            _col("progress", "Progress", "number", position=4, width=110, mobile_detail=True),
            _col("created_at", "Created", "date", position=5, mobile_detail=True),
        ],
    },
    "holdings": {
        "pageId": "holdings",
        "searchEnabled": False,
        "searchField": None,
        "defaultSort": {"field": "weighted_roi", "direction": "desc"},
        "defaultPageSize": 25,
        "allowedPageSizes": [25, 50, 100],
        "density": "compact",
        "selectionEnabled": False,
        "mobilePrimaryFields": ["symbol", "exit_action", "profit_pct"],
        "mobileDetailFields": ["quantity", "average_price", "last_price", "invested", "profit"],
        "columns": [
            _col("symbol", "Symbol", "text", position=0, required=True, width=120, mobile_primary=True),
            _col("exit_action", "Signal", "categorical", position=1, width=120, mobile_primary=True),
            _col("weighted_roi", "WTD ROI", "number", position=2, width=100),
            _col("wroi_trend", "Trend", "categorical", position=3, width=110),
            _col("profit", "Profit", "number", position=4, width=100, mobile_detail=True),
            _col("profit_pct", "Profit%", "number", position=5, width=90, mobile_primary=True),
            _col("profit_per_day", "Pr/Day", "number", position=6, width=100),
            _col("age", "Age", "number", position=7, width=80),
            _col("invested", "Invested", "number", position=8, width=100, mobile_detail=True),
            _col("quantity", "Qty", "number", position=9, width=70, mobile_detail=True),
            _col("average_price", "Avg Price", "number", position=10, width=100, mobile_detail=True),
            _col("last_price", "CMP", "number", position=11, width=90, mobile_detail=True),
            _col("quality", "Quality", "categorical", position=12, width=90),
            _col("exit_score", "Score", "number", position=13, width=80),
        ],
    },
    "entry_strategies": {
        "pageId": "entry_strategies",
        "searchEnabled": False,
        "searchField": None,
        "defaultSort": None,
        "defaultPageSize": 25,
        "allowedPageSizes": [25, 50, 100],
        "density": "compact",
        "selectionEnabled": True,
        "mobilePrimaryFields": ["symbol", "review_status", "delta_pct"],
        "mobileDetailFields": ["allocated", "cmp", "updated_at"],
        "columns": [
            _col("symbol", "Symbol", "text", position=0, required=True, width=120, mobile_primary=True),
            _col("delta_pct", "Delta %", "number", position=1, width=100),
            _col("allocated", "Allocation", "number", position=2, width=110, mobile_detail=True),
            _col("entry1", "Entry 1", "number", position=3, width=100),
            _col("entry2", "Entry 2", "number", position=4, width=100),
            _col("entry3", "Entry 3", "number", position=5, width=100),
            _col("swing_eligible", "Swing", "boolean", position=6, width=90),
            _col("review_status", "Review Status", "categorical", position=7, width=140, mobile_primary=True),
            _col("updated_at", "Updated", "date", position=8, width=140, mobile_detail=True),
            _col("cmp", "CMP", "number", position=9, width=100, mobile_detail=True),
        ],
    },
    "entry_candidates": {
        "pageId": "entry_candidates",
        "searchEnabled": False,
        "searchField": None,
        "defaultSort": None,
        "defaultPageSize": 25,
        "allowedPageSizes": [25, 50, 100],
        "density": "compact",
        "selectionEnabled": True,
        "mobilePrimaryFields": ["symbol", "status", "amount"],
        "mobileDetailFields": ["strategy", "cmp", "trigger", "qty"],
        "columns": [
            _col("symbol", "Symbol", "text", position=0, required=True, width=120, mobile_primary=True),
            _col("strategy", "Strategy", "categorical", position=1, width=120, mobile_detail=True),
            _col("signal", "Signal", "categorical", position=2, width=110),
            _col("cmp", "CMP", "number", position=3, width=100, mobile_detail=True),
            _col("trigger", "Trigger", "number", position=4, width=100, mobile_detail=True),
            _col("qty", "Qty", "number", position=5, width=80, mobile_detail=True),
            _col("amount", "Amount", "number", position=6, width=110, mobile_primary=True),
            _col("delta_vs_entry", "� vs Entry", "number", position=7, width=110),
            _col("status", "Status", "categorical", position=8, width=120, mobile_primary=True),
        ],
    },
    "buy_orders": {
        "pageId": "buy_orders",
        "searchEnabled": False,
        "searchField": None,
        "defaultSort": None,
        "defaultPageSize": 25,
        "allowedPageSizes": [25, 50, 100],
        "density": "compact",
        "selectionEnabled": True,
        "mobilePrimaryFields": ["Symbol", "Status", "Trigger Price"],
        "mobileDetailFields": ["Qty", "LTP", "Variance (%)", "Buy Amount"],
        "columns": [
            _col("GTT ID", "GTT ID", "text", position=0, width=100),
            _col("Symbol", "Symbol", "text", position=1, required=True, width=120, mobile_primary=True),
            _col("Trigger Price", "Trigger", "number", position=2, width=100, mobile_primary=True),
            _col("LTP", "CMP", "number", position=3, width=100, mobile_detail=True),
            _col("Variance (%)", "Variance %", "number", position=4, width=110, mobile_detail=True),
            _col("Qty", "Qty", "number", position=5, width=80, mobile_detail=True),
            _col("Buy Amount", "Buy Amount", "number", position=6, width=120, mobile_detail=True),
            _col("Status", "Status", "categorical", position=7, width=120, mobile_primary=True),
        ],
    },
}


def get_builtin_page_config(page_id: str) -> dict[str, Any] | None:
    config = BUILTIN_UI_PAGE_CONFIGS.get(page_id)
    return deepcopy(config) if config else None


def list_builtin_pages() -> list[dict[str, Any]]:
    pages = []
    for page_id in SUPPORTED_PAGE_IDS:
        cfg = BUILTIN_UI_PAGE_CONFIGS.get(page_id)
        if not cfg:
            continue
        pages.append(
            {
                "page_id": page_id,
                "label": page_id.replace("_", " ").title(),
                "search_supported": page_id in SEARCH_ALLOWED_PAGE_IDS,
                "selection_supported": bool(cfg.get("selectionEnabled", False)),
                "column_count": len(cfg.get("columns", [])),
            }
        )
    return pages