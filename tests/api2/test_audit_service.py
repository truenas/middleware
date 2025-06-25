import pytest
import random
import string

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_log


@pytest.fixture(scope="module")
def admin_client():
    builtin_administrators_group_id = call(
        "datastore.query",
        "account.bsdgroups",
        [["group", "=", "builtin_administrators"]],
        {"get": True, "prefix": "bsdgrp_"},
    )["id"]

    wg_user = "wiseguy_" + ''.join(random.choices(string.digits, k=4))
    with user({
        "username": wg_user,
        "full_name": "Lucky Luciano",
        "group_create": True,
        "password": "SwimsWithFishes",
        "groups": [builtin_administrators_group_id],
    }) as wg:
        with client(auth=(wg['username'], wg['password'])) as wg_c:
            yield (wg_user, wg_c)
        # These will auto clean


@pytest.fixture(scope='module')
def nfs_state():
    # Setup to restore NFS to original run state
    nfs = call('service.query', [['service', '=', 'nfs']], {'get': True})
    restore_state = 'STOP'
    if 'RUNNING' == nfs['state']:
        restore_state = 'START'
        # Start in stopped state
        call('service.control', 'STOP', 'nfs', job=True)

    yield call('service.query', [['service', '=', 'nfs']], {'get': True})['state']

    # Return NFS to original run state
    call('service.control', restore_state, 'nfs', job=True)


@pytest.mark.parametrize('ctrl', ['START', 'RELOAD', 'RESTART', 'STOP'])
def test_audit_service_control(nfs_state, admin_client, ctrl):
    ''' Confirm service.control methods are audited '''
    assert 'STOPPED' == nfs_state
    wg_user, wg_clnt = admin_client

    # Confirm we audit the who and what
    with expect_audit_log([{
        'event': 'METHOD_CALL',
        'service': 'MIDDLEWARE',
        'event_data': {
            'authenticated': True,
            'authorized': True,
            'method': 'service.control',
            'params': [ctrl, 'nfs'],
            'description': f'Service Control: {ctrl} nfs',
        },
        'username': f'{wg_user}',
    }]):
        wg_clnt.call('service.control', ctrl, 'nfs', job=True)
