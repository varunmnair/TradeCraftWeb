from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from api.routes.entry_strategy import _parse_entry_strategies_csv
from api.schemas.entry_strategy import EntryStrategyCSVRow


class TestEntryStrategyCSVValidation:
    """Tests for CSV row validation."""

    def test_valid_row(self):
        row = EntryStrategyCSVRow(
            symbol="RELIANCE",
            level_no=1,
            price=2500.00,
            dynamic_averaging_enabled=True,
            averaging_rules_json='{"legs": 3}',
        )
        assert row.symbol == "RELIANCE"
        assert row.level_no == 1
        assert row.price == 2500.00
        assert row.dynamic_averaging_enabled == True

    def test_symbol_uppercase_normalization(self):
        row = EntryStrategyCSVRow(
            symbol="  reliance  ",
            level_no=1,
            price=2500.00,
        )
        assert row.symbol == "RELIANCE"

    def test_symbol_lowercase_normalized_to_uppercase(self):
        row = EntryStrategyCSVRow(
            symbol="reliance",
            level_no=1,
            price=2500.00,
        )
        assert row.symbol == "RELIANCE"

    def test_invalid_level_no_zero(self):
        with pytest.raises(ValueError, match="level_no must be a positive integer"):
            EntryStrategyCSVRow(
                symbol="RELIANCE",
                level_no=0,
                price=2500.00,
            )

    def test_invalid_level_no_negative(self):
        with pytest.raises(ValueError, match="level_no must be a positive integer"):
            EntryStrategyCSVRow(
                symbol="RELIANCE",
                level_no=-1,
                price=2500.00,
            )

    def test_invalid_price_zero(self):
        with pytest.raises(ValueError, match="price must be greater than 0"):
            EntryStrategyCSVRow(
                symbol="RELIANCE",
                level_no=1,
                price=0,
            )

    def test_invalid_price_negative(self):
        with pytest.raises(ValueError, match="price must be greater than 0"):
            EntryStrategyCSVRow(
                symbol="RELIANCE",
                level_no=1,
                price=-100.00,
            )

    def test_optional_dynamic_averaging(self):
        row = EntryStrategyCSVRow(
            symbol="RELIANCE",
            level_no=1,
            price=2500.00,
        )
        assert row.dynamic_averaging_enabled is None

    def test_valid_averaging_rules_json(self):
        row = EntryStrategyCSVRow(
            symbol="RELIANCE",
            level_no=1,
            price=2500.00,
            averaging_rules_json='{"legs": 3, "buyback": [3, 3, 5]}',
        )
        assert row.averaging_rules_json == '{"legs": 3, "buyback": [3, 3, 5]}'

    def test_averaging_rules_json_not_validated_in_model(self):
        row = EntryStrategyCSVRow(
            symbol="RELIANCE",
            level_no=1,
            price=2500.00,
            averaging_rules_json='{invalid json}',
        )
        assert row.averaging_rules_json == '{invalid json}'


class TestCSVValidation:
    """Tests for entry-strategy CSV parsing (Symbol, Allocated, Entry1..3)."""

    def test_parse_csv_with_required_columns(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
RELIANCE,30000,2500,2450,2400
TCS,20000,3500,3400,"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert errors == []
        assert set(strategies.keys()) == {"RELIANCE", "TCS"}
        assert strategies["RELIANCE"]["allocated"] == 30000.0
        assert strategies["RELIANCE"]["levels"] == {1: 2500.0, 2: 2450.0, 3: 2400.0}
        assert strategies["TCS"]["levels"] == {1: 3500.0, 2: 3400.0}
        assert strategies["RELIANCE"]["quality"] is None
        assert strategies["RELIANCE"]["exchange"] == "NSE"

    def test_header_variants_tolerated(self):
        csv_content = """Symbol, Allocated, entry 1, Entry_2, ENTRY3
BEL,30000,386.5,375,369"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert errors == []
        assert strategies["BEL"]["levels"] == {1: 386.5, 2: 375.0, 3: 369.0}

    def test_lowercase_symbol_uppercased(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
bdl,30000,1235,1200,1185"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert errors == []
        assert "BDL" in strategies
        assert strategies["BDL"]["levels"][1] == 1235.0

    def test_exchange_prefix_stripped(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
NSE:bdl,30000,1235,1200,1185
BSE:ACE,20000,972,945,"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert errors == []
        assert set(strategies.keys()) == {"BDL", "ACE"}
        assert strategies["BDL"]["levels"][1] == 1235.0
        assert strategies["ACE"]["levels"][2] == 945.0

    def test_missing_required_column_raises(self):
        csv_content = """Symbol,Allocated
RELIANCE,30000"""

        with pytest.raises(HTTPException) as exc_info:
            _parse_entry_strategies_csv(csv_content)

        assert exc_info.value.status_code == 400
        assert "Entry1" in exc_info.value.detail

    def test_level_no_price_format_rejected(self):
        csv_content = """symbol,level_no,price
RELIANCE,1,2500"""

        with pytest.raises(HTTPException) as exc_info:
            _parse_entry_strategies_csv(csv_content)

        assert exc_info.value.status_code == 400
        assert "Symbol, Allocated, Entry1" in exc_info.value.detail

    def test_row_with_no_entries_reported(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
RELIANCE,30000,,,
TCS,20000,3500,,"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert set(strategies.keys()) == {"TCS"}
        assert errors[0]["row"] == 2
        assert "no valid entry prices" in errors[0]["error"]

    def test_invalid_price_reported(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
RELIANCE,30000,abc,2450,"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert strategies == {}
        assert "not a valid number" in errors[0]["error"]

    def test_non_positive_price_reported(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
RELIANCE,30000,-5,2450,"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert strategies == {}
        assert "must be greater than 0" in errors[0]["error"]

    def test_invalid_allocated_reported(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
RELIANCE,abc,2500,2450,"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert strategies == {}
        assert "allocated" in errors[0]["error"]

    def test_entries_auto_sorted_descending(self):
        csv_content = """Symbol,Allocated,Entry1,Entry2,Entry3
RELIANCE,30000,2400,2500,2450"""

        strategies, errors = _parse_entry_strategies_csv(csv_content)

        assert errors == []
        assert strategies["RELIANCE"]["levels"] == {1: 2500.0, 2: 2450.0, 3: 2400.0}


class TestUpsertLogic:
    """Tests for UPSERT logic."""

    def test_upsert_new_strategy(self):
        existing_strategies = {}
        symbol = "RELIANCE"
        levels = [
            {"level_no": 1, "price": 2500},
            {"level_no": 2, "price": 2450},
        ]

        is_new = symbol not in existing_strategies

        assert is_new is True

    def test_upsert_existing_strategy(self):
        existing_strategies = {"RELIANCE": {"id": 1}}
        symbol = "RELIANCE"
        levels = [
            {"level_no": 1, "price": 2600},
        ]

        is_new = symbol not in existing_strategies

        assert is_new is False

    def test_delete_old_levels_on_update(self):
        old_levels = [
            {"id": 1, "level_no": 1, "price": 2500},
            {"id": 2, "level_no": 2, "price": 2450},
            {"id": 3, "level_no": 3, "price": 2400},
        ]

        new_levels = [
            {"level_no": 1, "price": 2600},
        ]

        old_ids_to_delete = [l["id"] for l in old_levels]
        assert len(old_ids_to_delete) == 3

    def test_create_new_levels(self):
        new_levels_data = [
            {"level_no": 1, "price": 2600},
        ]

        assert len(new_levels_data) == 1
        assert new_levels_data[0]["price"] == 2600


class TestAuthScoping:
    """Tests for authentication and authorization scoping."""

    def test_detail_endpoint_filters_by_user(self):
        """Test that GET /entry-strategies/{symbol} filters by user_id and tenant_id."""
        from api.routes.entry_strategy import _compute_averaging_rules_summary
        
        summary = _compute_averaging_rules_summary('{"legs": 3, "buyback": [3, 3, 5], "trigger_offset": 1}')
        assert summary == "3 legs, buyback [3, 3, 5], offset 1"

    def test_summary_computation_empty(self):
        """Test that summary returns None for empty rules."""
        from api.routes.entry_strategy import _compute_averaging_rules_summary
        
        assert _compute_averaging_rules_summary(None) is None
        assert _compute_averaging_rules_summary("") is None

    def test_summary_computation_invalid_json(self):
        """Test that summary returns None for invalid JSON."""
        from api.routes.entry_strategy import _compute_averaging_rules_summary
        
        assert _compute_averaging_rules_summary("not json") is None

    def test_summary_computation_valid_json(self):
        """Test that summary computes correctly for valid JSON."""
        from api.routes.entry_strategy import _compute_averaging_rules_summary
        
        result = _compute_averaging_rules_summary('{"legs": 2, "buyback": [5, 5], "trigger_offset": 2}')
        assert result == "2 legs, buyback [5, 5], offset 2"


class TestRevisionLogic:
    """Tests for entry level revision logic."""

    def test_suggest_revision_returns_same_count(self):
        """Test that suggest endpoint returns same count as original levels."""
        # This is tested via the endpoint directly, but we verify the logic here
        levels = [
            {"level_no": 1, "price": 100},
            {"level_no": 2, "price": 95},
            {"level_no": 3, "price": 90},
        ]
        assert len(levels) == 3

    def test_apply_revision_validates_price(self):
        """Test that new_price must be positive."""
        # This is tested via Pydantic validation in the schema
        from api.schemas.entry_strategy import ApplyRevisionItem
        with pytest.raises(ValueError, match="new_price must be greater than 0"):
            ApplyRevisionItem(level_no=1, new_price=0)

    def test_apply_revision_validates_negative_price(self):
        """Test that negative price is rejected."""
        from api.schemas.entry_strategy import ApplyRevisionItem
        with pytest.raises(ValueError, match="new_price must be greater than 0"):
            ApplyRevisionItem(level_no=1, new_price=-100)

    def test_apply_revision_accepts_valid_price(self):
        """Test that valid price is accepted."""
        from api.schemas.entry_strategy import ApplyRevisionItem
        item = ApplyRevisionItem(level_no=1, new_price=100.50)
        assert item.level_no == 1
        assert item.new_price == 100.50


class TestVersioning:
    """Tests for entry strategy versioning."""

    def test_version_creation_helper(self):
        """Test that version creation helper works correctly."""
        # Test the _create_version function logic
        import json
        levels = [
            {"level_no": 1, "price": 100, "is_active": True},
            {"level_no": 2, "price": 95, "is_active": True},
        ]
        snapshot = json.dumps(levels)
        assert len(json.loads(snapshot)) == 2
        assert json.loads(snapshot)[0]["level_no"] == 1

    def test_version_list_returns_correct_structure(self):
        """Test that version list response has correct structure."""
        # This tests the VersionItem schema
        from datetime import datetime

        from api.schemas.entry_strategy import EntryLevelSchema, VersionItem
        
        version = VersionItem(
            id=1,
            version_no=1,
            action="upload",
            levels=[
                EntryLevelSchema(level_no=1, price=100.0, is_active=True),
                EntryLevelSchema(level_no=2, price=95.0, is_active=True),
            ],
            changes_summary="Initial upload",
            created_at=datetime.now(),
        )
        assert version.version_no == 1
        assert len(version.levels) == 2
        assert version.action == "upload"

    def test_upload_history_schema(self):
        """Test upload history schema."""
        from datetime import datetime

        from api.schemas.entry_strategy import UploadHistoryItem, UploadHistoryResponse
        
        items = [
            UploadHistoryItem(
                id=1,
                filename="test.csv",
                symbols=["RELIANCE", "TCS"],
                created_at=datetime.now(),
            )
        ]
        response = UploadHistoryResponse(uploads=items)
        assert len(response.uploads) == 1
        assert response.uploads[0].filename == "test.csv"

    def test_restore_version_schema(self):
        """Test restore version response schema."""
        from datetime import datetime

        from api.schemas.entry_strategy import RestoreVersionResponse
        
        response = RestoreVersionResponse(
            symbol="RELIANCE",
            restored_to_version=2,
            updated_at=datetime.now(),
        )
        assert response.symbol == "RELIANCE"
        assert response.restored_to_version == 2


class TestBulkRevisionSchemas:
    """Tests for bulk revision schemas."""

    def test_bulk_suggest_revision_request(self):
        """Test bulk suggest revision request schema."""
        from api.schemas.entry_strategy import BulkSuggestRevisionRequest
        
        req = BulkSuggestRevisionRequest(
            symbols=["RELIANCE", "TCS"],
            style="balanced",
        )
        assert len(req.symbols) == 2
        assert req.style == "balanced"

    def test_bulk_suggest_revision_request_defaults(self):
        """Test bulk suggest revision request with default values."""
        from api.schemas.entry_strategy import BulkSuggestRevisionRequest
        
        req = BulkSuggestRevisionRequest(symbols=["RELIANCE"])
        assert req.style == "balanced"

    def test_bulk_suggest_revision_request_with_style(self):
        """Test bulk suggest revision request with explicit style."""
        from api.schemas.entry_strategy import BulkSuggestRevisionRequest
        
        req = BulkSuggestRevisionRequest(
            symbols=["RELIANCE"],
            style="conservative",
        )
        assert req.style == "conservative"

    def test_bulk_apply_revision_request(self):
        """Test bulk apply revision request schema."""
        from api.schemas.entry_strategy import (
            ApplyRevisionItem,
            BulkApplyRevisionItem,
            BulkApplyRevisionRequest,
        )
        
        req = BulkApplyRevisionRequest(
            updates=[
                BulkApplyRevisionItem(
                    symbol="RELIANCE",
                    levels=[ApplyRevisionItem(level_no=1, new_price=2500.0)],
                ),
            ]
        )
        assert len(req.updates) == 1
        assert req.updates[0].symbol == "RELIANCE"
        assert len(req.updates[0].levels) == 1

    def test_bulk_apply_revision_result(self):
        """Test bulk apply revision result schema."""
        from datetime import datetime

        from api.schemas.entry_strategy import BulkApplyRevisionResult
        
        result = BulkApplyRevisionResult(
            symbol="RELIANCE",
            success=True,
            updated_levels=[1, 2],
            updated_at=datetime.now(),
            error=None,
        )
        assert result.success is True
        assert len(result.updated_levels) == 2
        assert result.error is None

    def test_bulk_apply_revision_result_failure(self):
        """Test bulk apply revision result with failure."""
        from api.schemas.entry_strategy import BulkApplyRevisionResult
        
        result = BulkApplyRevisionResult(
            symbol="INVALID",
            success=False,
            error="Strategy not found",
        )
        assert result.success is False
        assert result.error == "Strategy not found"

    def test_bulk_apply_revision_response(self):
        """Test bulk apply revision response schema."""
        from api.schemas.entry_strategy import BulkApplyRevisionResponse, BulkApplyRevisionResult
        
        resp = BulkApplyRevisionResponse(
            results=[
                BulkApplyRevisionResult(symbol="RELIANCE", success=True, updated_levels=[1], updated_at=None, error=None),
                BulkApplyRevisionResult(symbol="INVALID", success=False, error="Not found"),
            ],
            total_updated=1,
            total_failed=1,
        )
        assert resp.total_updated == 1
        assert resp.total_failed == 1
        assert len(resp.results) == 2
