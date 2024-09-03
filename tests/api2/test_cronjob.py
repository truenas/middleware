from time import sleep

import pytest

from middlewared.test.integration.utils import call, ssh

TESTFILE = '/tmp/.testFileCreatedViaCronjob'


def test_create_check_update_verify_cron_job():
    cronjob_dict = {}

    # create job
    results = call("cronjob.create", {
        'user': 'root',
        'command': f'touch "{TESTFILE}"',
        'schedule': {'minute': '*/1'}
    })
    cronjob_dict.update(results)

    # verify job creation
    id = cronjob_dict['id']
    results = call('cronjob.query', [['id', '=', id]], {"get": True})
    assert results['enabled'] is True

    # wait so job can run
    sleep(65)

    # disable job
    id = cronjob_dict['id']
    call('cronjob.update', id, {'enabled': False})

    # remove test file
    results = ssh(f'rm "{TESTFILE}"', complete_response=True)
    assert results['result'] is True, results['output']

    # delete job
    call('cronjob.delete', cronjob_dict['id'])
    results = call('cronjob.query', [['id', '=', id]], {"get": True})
    assert results.json() == []
