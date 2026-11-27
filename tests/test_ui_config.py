from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import sessionmaker

from api.dependencies import get_current_user, get_ui_configuration_service, require_admin
from core.auth.context import UserContext
from core.services.ui_configuration_service import UiConfigurationService
from core.ui_config_registry import get_builtin_page_config
from db.models import UiPageConfiguration


def _admin_user() -> UserContext:
    return UserContext(user_id=1, email='admin@test.local', role='admin', trading_enabled=True, is_premium=True)


def _normal_user() -> UserContext:
    return UserContext(user_id=2, email='user@test.local', role='user', trading_enabled=True, is_premium=False)


@pytest.fixture
def ui_service(db_session):
    bind = db_session.get_bind()
    SessionTesting = sessionmaker(bind=bind)
    return UiConfigurationService(db_session_factory=SessionTesting)


@pytest.fixture
def authed_client(client, ui_service):
    app = client.app
    app.dependency_overrides[get_ui_configuration_service] = lambda: ui_service
    app.dependency_overrides[get_current_user] = lambda: _normal_user()
    yield client
    app.dependency_overrides.pop(get_ui_configuration_service, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def admin_client(client, ui_service):
    app = client.app
    admin = _admin_user()
    app.dependency_overrides[get_ui_configuration_service] = lambda: ui_service
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_admin] = lambda: admin
    yield client
    app.dependency_overrides.pop(get_ui_configuration_service, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin, None)


def test_read_builtin_defaults(admin_client):
    res = admin_client.get('/ui-config/jobs')
    assert res.status_code == 200
    body = res.json()
    assert body['pageId'] == 'jobs'
    assert body['_meta']['source'] == 'default'
    assert body['defaultPageSize'] == 25


def test_save_configuration(admin_client):
    payload = {
        'defaultPageSize': 50,
        'allowedPageSizes': [25, 50, 100],
        'density': 'comfortable',
        'columns': [
            {'id': 'id', 'visible': False, 'sortable': True, 'filterable': True, 'position': 1},
            {'id': 'job_type', 'visible': True, 'sortable': True, 'filterable': True, 'position': 0},
        ],
    }
    res = admin_client.put('/admin/ui-config/jobs', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body['defaultPageSize'] == 50
    assert body['density'] == 'comfortable'
    assert body['_meta']['source'] == 'saved'
    assert body['columns'][0]['id'] == 'job_type'


def test_read_saved_configuration(admin_client):
    admin_client.put('/admin/ui-config/jobs', json={'defaultPageSize': 50, 'allowedPageSizes': [25, 50, 100]})
    res = admin_client.get('/ui-config/jobs')
    assert res.status_code == 200
    assert res.json()['defaultPageSize'] == 50
    assert res.json()['_meta']['source'] == 'saved'


def test_reset_to_defaults(admin_client):
    admin_client.put('/admin/ui-config/jobs', json={'defaultPageSize': 50, 'allowedPageSizes': [25, 50, 100]})
    res = admin_client.post('/admin/ui-config/jobs/reset')
    assert res.status_code == 200
    body = res.json()
    assert body['defaultPageSize'] == 25
    assert body['_meta']['source'] == 'default'


def test_unknown_page_rejection(admin_client):
    res = admin_client.get('/ui-config/unknown_page')
    assert res.status_code == 404
    res = admin_client.put('/admin/ui-config/unknown_page', json={'defaultPageSize': 25})
    assert res.status_code == 404


def test_unknown_column_handling(admin_client, ui_service):
    payload = {
        'columns': [
            {'id': 'id', 'visible': True, 'sortable': True, 'filterable': True, 'position': 0},
            {'id': 'not_a_real_column', 'visible': False, 'sortable': False, 'filterable': False, 'position': 1},
        ]
    }
    res = admin_client.put('/admin/ui-config/jobs', json=payload)
    assert res.status_code == 200
    ids = [c['id'] for c in res.json()['columns']]
    assert 'not_a_real_column' not in ids
    assert 'id' in ids


def test_required_column_protection(admin_client):
    # holdings.symbol is required in registry
    res = admin_client.put('/admin/ui-config/holdings', json={
        'columns': [{'id': 'symbol', 'visible': False, 'sortable': True, 'filterable': True, 'position': 0}]
    })
    assert res.status_code == 400


def test_unsupported_sorting_rejection(ui_service):
    import core.ui_config_registry as reg
    original = reg.BUILTIN_UI_PAGE_CONFIGS['jobs']['columns'][0]['sortable']
    try:
        reg.BUILTIN_UI_PAGE_CONFIGS['jobs']['columns'][0]['sortable'] = False
        with pytest.raises(ValueError):
            ui_service.validate_update('jobs', {'columns': [{'id': 'id', 'sortable': True}]})
    finally:
        reg.BUILTIN_UI_PAGE_CONFIGS['jobs']['columns'][0]['sortable'] = original


def test_unsupported_filtering_rejection(admin_client, ui_service):
    import core.ui_config_registry as reg
    original = reg.BUILTIN_UI_PAGE_CONFIGS['jobs']['columns'][0]['filterable']
    try:
        reg.BUILTIN_UI_PAGE_CONFIGS['jobs']['columns'][0]['filterable'] = False
        with pytest.raises(ValueError):
            ui_service.validate_update('jobs', {'columns': [{'id': 'id', 'filterable': True}]})
    finally:
        reg.BUILTIN_UI_PAGE_CONFIGS['jobs']['columns'][0]['filterable'] = original


def test_invalid_page_size_rejection(admin_client):
    res = admin_client.put('/admin/ui-config/jobs', json={'allowedPageSizes': [25, 50, 999]})
    assert res.status_code == 400
    res = admin_client.put('/admin/ui-config/jobs', json={'allowedPageSizes': []})
    assert res.status_code == 400
    res = admin_client.put('/admin/ui-config/jobs', json={'defaultPageSize': 100, 'allowedPageSizes': [25, 50]})
    assert res.status_code == 400


def test_duplicate_position_normalization(ui_service):
    cfg = get_builtin_page_config('jobs')
    assert cfg is not None
    cfg['columns'][0]['position'] = 1
    cfg['columns'][1]['position'] = 1
    cfg['columns'][2]['position'] = 1
    normalized = ui_service.validate_and_normalize('jobs', cfg)
    positions = [c['position'] for c in normalized['columns']]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)


def test_non_admin_update_rejection(authed_client):
    res = authed_client.put('/admin/ui-config/jobs', json={'defaultPageSize': 50, 'allowedPageSizes': [25, 50, 100]})
    assert res.status_code == 403


def test_non_admin_can_read_effective_config(authed_client):
    res = authed_client.get('/ui-config/jobs')
    assert res.status_code == 200
    assert res.json()['pageId'] == 'jobs'


def test_configuration_schema_version_handling(ui_service, db_session):
    # Simulate old saved config with missing schema/new fields
    old_payload = {
        'pageId': 'jobs',
        'schemaVersion': 0,
        'columns': [{'id': 'job_type', 'visible': False, 'sortable': True, 'filterable': True, 'position': 0}],
    }
    row = UiPageConfiguration(page_id='jobs', schema_version=0, configuration_json=json.dumps(old_payload))
    db_session.add(row)
    db_session.commit()
    cfg = ui_service.get_effective_config('jobs')
    assert cfg['pageId'] == 'jobs'
    # missing columns should be present with defaults
    ids = [c['id'] for c in cfg['columns']]
    assert 'id' in ids and 'status' in ids
    # old override applied
    job_type = next(c for c in cfg['columns'] if c['id'] == 'job_type')
    assert job_type['visible'] is False


def test_new_column_added_after_saved_config(ui_service, db_session):
    # Save config without a column that exists in builtin, then ensure it appears
    builtin = get_builtin_page_config('jobs')
    assert builtin is not None
    saved_cols = [c for c in builtin['columns'] if c['id'] != 'progress']
    payload = {
        'pageId': 'jobs',
        'schemaVersion': 1,
        'defaultPageSize': 25,
        'allowedPageSizes': [25, 50, 100],
        'density': 'compact',
        'selectionEnabled': True,
        'searchEnabled': False,
        'searchField': None,
        'defaultSort': {'field': 'created_at', 'direction': 'desc'},
        'mobilePrimaryFields': ['job_type', 'status'],
        'mobileDetailFields': ['id', 'created_at'],
        'columns': [{'id': c['id'], 'visible': c['visible'], 'sortable': c['sortable'], 'filterable': c['filterable'], 'position': i} for i, c in enumerate(saved_cols)],
    }
    db_session.add(UiPageConfiguration(page_id='jobs', schema_version=1, configuration_json=json.dumps(payload)))
    db_session.commit()
    cfg = ui_service.get_effective_config('jobs')
    ids = [c['id'] for c in cfg['columns']]
    assert 'progress' in ids


def test_database_failure_handling(admin_client, monkeypatch):
    class BrokenService:
        def get_effective_config(self, page_id):
            raise RuntimeError('db down')
        def save_config(self, page_id, config, user_id):
            raise RuntimeError('db down')
        def reset_config(self, page_id, user_id):
            raise RuntimeError('db down')
        def list_pages(self):
            raise RuntimeError('db down')

    admin_client.app.dependency_overrides[get_ui_configuration_service] = lambda: BrokenService()
    res = admin_client.get('/ui-config/jobs')
    assert res.status_code == 500
    res = admin_client.put('/admin/ui-config/jobs', json={'defaultPageSize': 25, 'allowedPageSizes': [25, 50, 100]})
    assert res.status_code == 500
    res = admin_client.post('/admin/ui-config/jobs/reset')
    assert res.status_code == 500
