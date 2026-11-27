"""Service for global admin-managed UI page configuration."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.ui_config_registry import (
    ALLOWED_DENSITIES,
    SEARCH_ALLOWED_PAGE_IDS,
    SUPPORTED_PAGE_IDS,
    UI_CONFIG_SCHEMA_VERSION,
    get_builtin_page_config,
    list_builtin_pages,
)
from db.database import SessionLocal
from db.models import UiPageConfiguration


class UiConfigurationService:
    def __init__(self, db_session_factory=SessionLocal):
        self._db_session_factory = db_session_factory

    def _session(self) -> Session:
        return self._db_session_factory()

    def list_pages(self) -> list[dict[str, Any]]:
        return list_builtin_pages()

    def get_effective_config(self, page_id: str) -> dict[str, Any]:
        builtin = get_builtin_page_config(page_id)
        if not builtin:
            raise KeyError(page_id)
        db = self._session()
        try:
            row = db.query(UiPageConfiguration).filter(UiPageConfiguration.page_id == page_id).first()
            if not row:
                return self._with_metadata(builtin, source="default", updated_at=None, updated_by=None)
            try:
                saved = json.loads(row.configuration_json or "{}")
            except json.JSONDecodeError:
                saved = {}
            merged = self.merge_config(builtin, saved)
            merged = self.validate_and_normalize(page_id, merged)
            return self._with_metadata(
                merged,
                source="saved",
                updated_at=row.updated_at,
                updated_by=row.updated_by,
            )
        finally:
            db.close()

    def get_raw_saved(self, page_id: str) -> dict[str, Any] | None:
        db = self._session()
        try:
            row = db.query(UiPageConfiguration).filter(UiPageConfiguration.page_id == page_id).first()
            if not row:
                return None
            try:
                return json.loads(row.configuration_json or "{}")
            except json.JSONDecodeError:
                return {}
        finally:
            db.close()

    def save_config(self, page_id: str, config: dict[str, Any], user_id: int | None) -> dict[str, Any]:
        builtin = get_builtin_page_config(page_id)
        if not builtin:
            raise KeyError(page_id)
        self.validate_update(page_id, config)
        normalized = self.validate_and_normalize(page_id, config)
        db = self._session()
        try:
            row = db.query(UiPageConfiguration).filter(UiPageConfiguration.page_id == page_id).first()
            payload = json.dumps(self._persistable_config(normalized))
            now = datetime.now(timezone.utc)
            if row:
                row.schema_version = UI_CONFIG_SCHEMA_VERSION
                row.configuration_json = payload
                row.updated_by = user_id
                row.updated_at = now
            else:
                row = UiPageConfiguration(
                    page_id=page_id,
                    schema_version=UI_CONFIG_SCHEMA_VERSION,
                    configuration_json=payload,
                    updated_by=user_id,
                    updated_at=now,
                )
                db.add(row)
            db.commit()
            db.refresh(row)
            return self._with_metadata(normalized, source="saved", updated_at=row.updated_at, updated_by=row.updated_by)
        finally:
            db.close()

    def reset_config(self, page_id: str, user_id: int | None) -> dict[str, Any]:
        builtin = get_builtin_page_config(page_id)
        if not builtin:
            raise KeyError(page_id)
        db = self._session()
        try:
            row = db.query(UiPageConfiguration).filter(UiPageConfiguration.page_id == page_id).first()
            if row:
                db.delete(row)
                db.commit()
        finally:
            db.close()
        return self.get_effective_config(page_id)

    def validate_update(self, page_id: str, config: dict[str, Any]) -> None:
        builtin = get_builtin_page_config(page_id)
        if not builtin:
            raise KeyError(page_id)
        if not isinstance(config, dict):
            raise ValueError("Configuration must be an object")

        allowed_sizes_raw = config.get("allowedPageSizes")
        if allowed_sizes_raw is not None:
            if not isinstance(allowed_sizes_raw, list) or len(allowed_sizes_raw) == 0:
                raise ValueError("allowedPageSizes must be a non-empty list")
            normalized_sizes: list[int] = []
            for size in allowed_sizes_raw:
                if not isinstance(size, int) or size not in [25, 50, 100]:
                    raise ValueError(f"Invalid page size: {size}")
                if size not in normalized_sizes:
                    normalized_sizes.append(size)
            allowed_sizes = normalized_sizes
        else:
            allowed_sizes = list(builtin.get("allowedPageSizes", [25, 50, 100]))

        default_page_size = config.get("defaultPageSize")
        if default_page_size is not None:
            if not isinstance(default_page_size, int) or default_page_size not in allowed_sizes:
                raise ValueError("defaultPageSize must be included in allowedPageSizes")

        density = config.get("density")
        if density is not None and density not in ALLOWED_DENSITIES:
            raise ValueError("Invalid density")

        # Search restrictions
        if config.get("searchEnabled") is True and page_id not in SEARCH_ALLOWED_PAGE_IDS:
            raise ValueError("Search is not supported for this page")
        if config.get("searchField") is not None:
            sf = config.get("searchField")
            if not isinstance(sf, str) or sf not in {"symbol", "Symbol"}:
                raise ValueError("searchField is not allowed")
            if page_id not in SEARCH_ALLOWED_PAGE_IDS:
                raise ValueError("Search is not supported for this page")

        builtin_cols = {c["id"]: c for c in builtin.get("columns", [])}
        raw_cols = config.get("columns")
        if raw_cols is not None:
            if not isinstance(raw_cols, list):
                raise ValueError("columns must be a list")
            for raw in raw_cols:
                if not isinstance(raw, dict):
                    raise ValueError("Column override must be an object")
                col_id = raw.get("id")
                if not isinstance(col_id, str) or not col_id:
                    raise ValueError("Column id is required")
                if col_id not in builtin_cols:
                    # unknown column IDs ignored safely by merge; reject on explicit bad admin payload? spec says rejected or ignored safely.
                    continue
                bcol = builtin_cols[col_id]
                if raw.get("visible") is False and bcol.get("required"):
                    raise ValueError(f"Required column cannot be hidden: {col_id}")
                if raw.get("sortable") is True and not bcol.get("sortable", False):
                    raise ValueError(f"Unsupported sorting cannot be enabled: {col_id}")
                if raw.get("filterable") is True and not bcol.get("filterable", False):
                    raise ValueError(f"Unsupported filtering cannot be enabled: {col_id}")
                if "position" in raw and not isinstance(raw.get("position"), int):
                    raise ValueError(f"Invalid position for column: {col_id}")

        # Default sort validation
        ds = config.get("defaultSort")
        if ds is not None:
            if not isinstance(ds, dict):
                raise ValueError("defaultSort must be an object")
            field = ds.get("field")
            direction = ds.get("direction")
            if not isinstance(field, str) or direction not in ("asc", "desc"):
                raise ValueError("Invalid defaultSort")
            col = builtin_cols.get(field)
            if not col:
                raise ValueError("defaultSort must reference a known column")
            # check effective sortable after overrides
            effective_sortable = bool(col.get("sortable", False))
            if isinstance(raw_cols, list):
                for raw in raw_cols:
                    if isinstance(raw, dict) and raw.get("id") == field and "sortable" in raw:
                        if raw.get("sortable") is False:
                            effective_sortable = False
                        elif raw.get("sortable") is True and bool(col.get("sortable", False)):
                            effective_sortable = True
            if not effective_sortable:
                raise ValueError("defaultSort must reference a sortable column")

        for key in ("mobilePrimaryFields", "mobileDetailFields"):
            if key in config and config[key] is not None:
                if not isinstance(config[key], list) or not all(isinstance(v, str) for v in config[key]):
                    raise ValueError(f"{key} must be a list of strings")

    def merge_config(self, builtin: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(builtin)
        if not isinstance(saved, dict):
            return merged

        # Page-level scalar settings
        for key in [
            "searchEnabled",
            "searchField",
            "defaultPageSize",
            "density",
            "selectionEnabled",
            "defaultSort",
        ]:
            if key in saved:
                merged[key] = deepcopy(saved[key])

        if "allowedPageSizes" in saved:
            merged["allowedPageSizes"] = deepcopy(saved["allowedPageSizes"])

        if "mobilePrimaryFields" in saved:
            merged["mobilePrimaryFields"] = deepcopy(saved["mobilePrimaryFields"])
        if "mobileDetailFields" in saved:
            merged["mobileDetailFields"] = deepcopy(saved["mobileDetailFields"])

        # Column overrides: merge by known column ID only.
        builtin_cols = {c["id"]: deepcopy(c) for c in builtin.get("columns", [])}
        saved_cols = saved.get("columns", []) if isinstance(saved.get("columns"), list) else []
        saved_by_id = {c.get("id"): c for c in saved_cols if isinstance(c, dict) and c.get("id") in builtin_cols}

        merged_cols = []
        for col in builtin.get("columns", []):
            base = deepcopy(col)
            override = saved_by_id.get(col["id"], {})
            for field in ["visible", "sortable", "filterable", "position"]:
                if field in override:
                    base[field] = override[field]
            merged_cols.append(base)

        # Add any newly introduced builtin columns not present in saved config (already included)
        # and ignore unknown saved columns.
        merged["columns"] = merged_cols
        return merged

    def validate_and_normalize(self, page_id: str, config: dict[str, Any]) -> dict[str, Any]:
        builtin = get_builtin_page_config(page_id)
        if not builtin:
            raise KeyError(page_id)
        if not isinstance(config, dict):
            config = {}

        result = deepcopy(builtin)

        # Selection: only if supported by builtin.
        selection_supported = bool(builtin.get("selectionEnabled", False))
        result["selectionEnabled"] = bool(config.get("selectionEnabled", False)) if selection_supported else False

        # Search: restricted by registry.
        search_supported = page_id in SEARCH_ALLOWED_PAGE_IDS
        requested_search = bool(config.get("searchEnabled", False))
        requested_search_field = config.get("searchField")
        if search_supported and requested_search and isinstance(requested_search_field, str):
            # Only allow symbol identifier fields.
            allowed_search_fields = {"symbol", "Symbol"}
            if requested_search_field in allowed_search_fields and any(c["id"] == requested_search_field for c in builtin["columns"]):
                result["searchEnabled"] = True
                result["searchField"] = requested_search_field
            else:
                result["searchEnabled"] = False
                result["searchField"] = None
        else:
            result["searchEnabled"] = False
            result["searchField"] = None

        # Density
        density = config.get("density", builtin.get("density", "compact"))
        result["density"] = density if density in ALLOWED_DENSITIES else builtin.get("density", "compact")

        # Allowed page sizes
        allowed_sizes_raw = config.get("allowedPageSizes", builtin.get("allowedPageSizes", [25, 50, 100]))
        allowed_sizes = []
        if isinstance(allowed_sizes_raw, list):
            for size in allowed_sizes_raw:
                if isinstance(size, int) and size in [25, 50, 100] and size not in allowed_sizes:
                    allowed_sizes.append(size)
        if not allowed_sizes:
            allowed_sizes = list(builtin.get("allowedPageSizes", [25, 50, 100]))
        allowed_sizes.sort()
        result["allowedPageSizes"] = allowed_sizes

        default_page_size = config.get("defaultPageSize", builtin.get("defaultPageSize", 25))
        if not isinstance(default_page_size, int) or default_page_size not in allowed_sizes:
            default_page_size = builtin.get("defaultPageSize", 25)
            if default_page_size not in allowed_sizes:
                default_page_size = allowed_sizes[0]
        result["defaultPageSize"] = default_page_size

        # Columns: only known columns, normalize order/capabilities.
        builtin_cols = {c["id"]: c for c in builtin.get("columns", [])}
        raw_cols = config.get("columns", []) if isinstance(config.get("columns"), list) else []
        overrides_by_id: dict[str, dict[str, Any]] = {}
        for raw in raw_cols:
            if isinstance(raw, dict) and raw.get("id") in builtin_cols:
                overrides_by_id[raw["id"]] = raw

        cols = []
        for idx, bcol in enumerate(builtin.get("columns", [])):
            o = overrides_by_id.get(bcol["id"], {})
            required = bool(bcol.get("required"))
            visible = True if required else bool(o.get("visible", bcol.get("visible", True)))
            sortable = bool(bcol.get("sortable", True)) and bool(o.get("sortable", bcol.get("sortable", True)))
            filterable = bool(bcol.get("filterable", True)) and bool(o.get("filterable", bcol.get("filterable", True)))
            # Cannot enable unsupported capabilities.
            if not bool(bcol.get("sortable", True)):
                sortable = False
            if not bool(bcol.get("filterable", True)):
                filterable = False
            position = o.get("position", bcol.get("position", idx))
            if not isinstance(position, int):
                position = idx
            col = deepcopy(bcol)
            col["visible"] = visible
            col["sortable"] = sortable
            col["filterable"] = filterable
            col["position"] = position
            col["sortableSupported"] = bool(bcol.get("sortable", True))
            col["filterableSupported"] = bool(bcol.get("filterable", True))
            cols.append(col)

        # Normalize positions deterministically (stable by position, then builtin order/id).
        builtin_order = {c["id"]: i for i, c in enumerate(builtin.get("columns", []))}
        cols.sort(key=lambda c: (int(c.get("position", 0)), builtin_order.get(c["id"], 9999), c["id"]))
        for i, c in enumerate(cols):
            c["position"] = i
        result["columns"] = cols

        # Default sort must reference sortable visible/known column.
        default_sort = config.get("defaultSort", builtin.get("defaultSort"))
        result["defaultSort"] = None
        if isinstance(default_sort, dict):
            field = default_sort.get("field")
            direction = default_sort.get("direction")
            col = next((c for c in cols if c["id"] == field), None)
            if col and col.get("sortable") and direction in ("asc", "desc"):
                result["defaultSort"] = {"field": field, "direction": direction}
        if result["defaultSort"] is None:
            bsort = builtin.get("defaultSort")
            if isinstance(bsort, dict):
                bcol = next((c for c in cols if c["id"] == bsort.get("field")), None)
                if bcol and bcol.get("sortable") and bsort.get("direction") in ("asc", "desc"):
                    result["defaultSort"] = {"field": bsort["field"], "direction": bsort["direction"]}

        # Mobile fields: only known fields, no duplicates across primary/detail unless required identity
        known_ids = [c["id"] for c in cols]
        required_ids = [c["id"] for c in cols if c.get("required")]

        def normalize_mobile_fields(raw: Any) -> list[str]:
            if not isinstance(raw, list):
                return []
            out = []
            for v in raw:
                if isinstance(v, str) and v in known_ids and v not in out:
                    out.append(v)
            return out

        primary = normalize_mobile_fields(config.get("mobilePrimaryFields", builtin.get("mobilePrimaryFields", [])))
        detail = normalize_mobile_fields(config.get("mobileDetailFields", builtin.get("mobileDetailFields", [])))

        # Ensure required identity fields remain visible in mobile primary if not present.
        for rid in required_ids:
            if rid not in primary and rid not in detail:
                primary.insert(0, rid)
        # Remove duplicates from detail, preserve primary priority.
        detail = [f for f in detail if f not in primary]

        # Fallback to builtin if empty/missing.
        if not primary:
            primary = normalize_mobile_fields(builtin.get("mobilePrimaryFields", []))
            detail = [f for f in normalize_mobile_fields(builtin.get("mobileDetailFields", [])) if f not in primary]
        for rid in required_ids:
            if rid not in primary and rid not in detail:
                primary.insert(0, rid)
                detail = [f for f in detail if f not in primary]

        result["mobilePrimaryFields"] = primary
        result["mobileDetailFields"] = detail

        result["pageId"] = page_id
        return result

    def _persistable_config(self, config: dict[str, Any]) -> dict[str, Any]:
        # Persist only supported serializable fields.
        cols = []
        for c in config.get("columns", []):
            if not isinstance(c, dict) or "id" not in c:
                continue
            cols.append(
                {
                    "id": c["id"],
                    "visible": bool(c.get("visible", True)),
                    "sortable": bool(c.get("sortable", False)),
                    "filterable": bool(c.get("filterable", False)),
                    "position": int(c.get("position", 0)),
                }
            )
        return {
            "pageId": config.get("pageId"),
            "schemaVersion": UI_CONFIG_SCHEMA_VERSION,
            "searchEnabled": bool(config.get("searchEnabled", False)),
            "searchField": config.get("searchField"),
            "defaultPageSize": config.get("defaultPageSize"),
            "allowedPageSizes": list(config.get("allowedPageSizes", [])),
            "density": config.get("density"),
            "selectionEnabled": bool(config.get("selectionEnabled", False)),
            "defaultSort": config.get("defaultSort"),
            "mobilePrimaryFields": list(config.get("mobilePrimaryFields", [])),
            "mobileDetailFields": list(config.get("mobileDetailFields", [])),
            "columns": cols,
        }

    def _with_metadata(
        self,
        config: dict[str, Any],
        *,
        source: str,
        updated_at: Any,
        updated_by: int | None,
    ) -> dict[str, Any]:
        out = deepcopy(config)
        out["_meta"] = {
            "source": source,
            "schemaVersion": UI_CONFIG_SCHEMA_VERSION,
            "updatedAt": updated_at.isoformat() if hasattr(updated_at, "isoformat") and updated_at else None,
            "updatedBy": updated_by,
        }
        return out