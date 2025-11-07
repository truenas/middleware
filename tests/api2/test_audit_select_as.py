from middlewared.test.integration.utils import call


def test_select_as_audit_db():
    entry = call('audit.query', {
        'services': ['MIDDLEWARE'],
        'query-options': {
            'get': True,
            'select': [
                'service_data',
                ['service_data.credentials', 'credentials'],
                ['service_data.origin', 'origin']
            ],
            'limit': 1,
            'order_by': ['-message_timestamp']
        }
    })

    assert 'origin' in entry
    assert isinstance(entry['origin'], str), entry

    assert 'credentials' in entry
    assert isinstance(entry['credentials'], dict), entry
