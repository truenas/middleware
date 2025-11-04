import os

import requests
import time
import operator
import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, url
from middlewared.test.integration.utils.audit import expect_audit_log, expect_audit_method_calls
from unittest.mock import ANY


# =====================================================================
#                     Fixtures and utilities
# =====================================================================
@pytest.fixture(scope='class')
def report_exists(request):
    report_pathname = request.config.cache.get('report_pathname', None)
    assert report_pathname is not None
    yield report_pathname


# =====================================================================
#                           Tests
# =====================================================================
@pytest.mark.parametrize('payload,success', [
    ({'retention': 20}, True),
    ({'retention': 0}, False)
])
def test_audit_config_audit(payload, success):
    '''
    Test the auditing of Audit configuration changes
    '''
    initial_audit_config = call('audit.config')
    rest_operator = operator.eq if success else operator.ne
    expected_log_template = {
        'service_data': {
            'vers': {
                'major': 0,
                'minor': 1,
            },
            'origin': ANY,
            'protocol': 'WEBSOCKET',
            'credentials': {
                'credentials': 'LOGIN_PASSWORD',
                'credentials_data': {'username': 'root', 'login_at': ANY, "login_id": ANY},
            },
        },
        'event': 'METHOD_CALL',
        'event_data': {
            'authenticated': True,
            'authorized': True,
            'method': 'audit.update',
            'params': [payload],
            'description': 'Update Audit Configuration',
        },
        'success': success
    }
    try:
        with expect_audit_log([expected_log_template]):
            if success:
                call('audit.update', payload)
            else:
                with pytest.raises(ValidationErrors):
                    call('audit.update', payload)
    finally:
        # Restore initial state
        restore_payload = {
            'retention': initial_audit_config['retention'],
        }
        call('audit.update', restore_payload)


def test_audit_export_audit(request):
    '''
    Test the auditing of the audit export function
    '''
    payload = {
        'export_format': 'CSV'
    }
    with expect_audit_method_calls([{
        'method': 'audit.export',
        'params': [payload],
        'description': 'Export Audit Data',
    }]):
        report_pathname = call('audit.export', payload, job=True)
        request.config.cache.set('report_pathname', report_pathname)


class TestAuditDownload:
    '''
    Wrap these tests in a class for the 'report_exists' fixture
    '''
    def test_audit_download_audit(self, report_exists):
        '''
        Test the auditing of the audit download function
        '''
        report_pathname = report_exists
        st = call('filesystem.stat', report_pathname)

        init_audit_query = call('audit.query', {
            'query-filters': [['event_data.method', '=', 'audit.download_report']],
            'query-options': {'select': ['event_data', 'success'], 'limit': 1000}
        })
        init_len = len(init_audit_query)

        report_name = os.path.basename(report_pathname)
        payload = {
            'report_name': report_name
        }
        job_id, download_data = call(
            'core.download', 'audit.download_report', [payload], 'report.csv'
        )
        r = requests.get(f'{url()}{download_data}')
        r.raise_for_status()
        assert len(r.content) == st['size']

        post_audit_query = call('audit.query', {
            'query-filters': [['event_data.method', '=', 'audit.download_report']],
            'query-options': {'select': ['event_data', 'success'], 'limit': 1000}
        })
        post_len = len(post_audit_query)

        # This usually requires only one cycle
        count_down = 10
        while count_down > 0 and post_len == init_len:
            time.sleep(1)
            count_down -= 1
            post_audit_query = call('audit.query', {
                'query-filters': [['event_data.method', '=', 'audit.download_report']],
                'query-options': {'select': ['event_data', 'success'], 'limit': 1000}
            })
            post_len = len(post_audit_query)

        assert count_down > 0, 'Timed out waiting for the audit entry'
        assert post_len > init_len

        # Confirm this download is recorded
        entry = post_audit_query[-1]
        event_data = entry['event_data']
        params = event_data['params'][0]
        assert report_name in params['report_name']
