import pytest
from time import sleep

from middlewared.test.integration.utils import call, ssh

TESTFILE = '/tmp/.testFileCreatedViaCronjob'


@pytest.fixture(scope='module')
def cronjob_dict():
    return {}


def creating_new_cron_job_which_will_run_every_minute(cronjob_dict):
    results = call("cronjob.create", {
        'user': 'root',
        'command': f'touch "{TESTFILE}"',
        'schedule': {'minute': '*/1'}
    })
    cronjob_dict.update(results)


def checking_to_see_if_cronjob_was_created_and_enabled(cronjob_dict):
    id = cronjob_dict['id']
    results = call('cronjob.query', [['id', '=', id]], {"get": True})
    assert results['enabled'] is True


def wait_a_minute():
    sleep(65)


def updating_cronjob_status_to_disabled_updating_command(cronjob_dict):
    id = cronjob_dict['id']
    call('cronjob.update', id, {'enabled': False})


def checking_that_API_reports_the_cronjob_as_updated(cronjob_dict):
    id = cronjob_dict['id']
    results = call('cronjob.query', [['id', '=', id]], {"get": True})
    assert results['enabled'] is False


def deleting_test_file_created_by_cronjob(request):
    results = ssh(f'rm "{TESTFILE}"', complete_response=True)
    assert results['result'] is True, results['output']


def delete_and_check_cron_job(cronjob_dict):
    call('cronjob.delete', cronjob_dict['id'])
    results = call('cronjob.query', [['id', '=', id]], {"get": True})
    assert results.json() == []
