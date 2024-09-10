import pytest

from middlewared.test.integration.utils import call, ssh

DESTINATION = '127.1.1.1'
GATEWAY = '127.0.0.1'

@pytest.fixture(scope='module')
def sr_dict():
    return {}


def test_creating_staticroute(sr_dict):
    sr_dict['newroute'] = call('staticroute.create', {
        'destination': DESTINATION,
        'gateway': GATEWAY,
        'description': 'test route',
    })


def test_check_staticroute_configured_using_api(sr_dict):
    data = call('staticroute.query', [['id', '=', sr_dict['newroute']['id']]], {'get': True})
    assert DESTINATION in data['destination']
    assert data['gateway'] == GATEWAY


def test_checking_staticroute_configured_using_ssh(request):
    results = ssh(f'netstat -4rn|grep -E ^{DESTINATION}', complete_response=True)
    assert results['result'] is True
    assert results['stdout'].strip().split()[1] == GATEWAY


def test_delete_staticroute(sr_dict):
    call('staticroute.delete', sr_dict['newroute']['id'])


def test_check_staticroute_unconfigured_using_api(sr_dict):
    call('staticroute.query', [['destination', '=', DESTINATION]])


def test_checking_staticroute_unconfigured_using_ssh(request):
    results = ssh(f'netstat -4rn|grep -E ^{DESTINATION}', complete_response=True)
    assert results['result'] is False
