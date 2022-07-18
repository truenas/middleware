import sys
import os
from contextlib import contextmanager

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import wait_on_job
from middlewared.test.integration.utils import call, ssh


@contextmanager
def create_cron_job(owner, ownerGroup, user):
    test_folder = ssh('mktemp -d').strip()
    ssh(f'chown -R {owner}:{ownerGroup} {test_folder}')
    cron = call(
        'cronjob.create', {
            'command': f'touch {test_folder}/test.txt', 'user': user, 'stderr': False, 'stdout': False}
    )
    try:
        yield cron
    finally:
        ssh(f'rm -rf {test_folder}')


@contextmanager
def run_cron_job(cron_id):
    job_id = call('cronjob.run', cron_id)
    try:
        yield wait_on_job(job_id, 300)
    finally:
        call('cronjob.delete', cron_id)


def test_01_running_as_valid_user():
    with create_cron_job(owner='apps', ownerGroup='apps', user='apps') as cron_job:
        with run_cron_job(cron_job['id']) as job_detail:
            assert job_detail['results']['error'] is None


def test_02_running_as_invalid_user():
    with create_cron_job(owner='root', ownerGroup='root', user='apps') as cron_job:
        with run_cron_job(cron_job['id']) as job_detail:
            assert f'"{cron_job["command"]}" exited with 1' in job_detail['results']['error'], job_detail
