from middlewared.test.integration.utils import call


def test_select_as_audit_db():
    entry = call('audit.query', {"services": ["MIDDLEWARE"], "query-options": {
        'get': True,
        'select': [['service_data.origin', 'origin']],
        'limit': 1
        }})

    assert 'origin' in entry
