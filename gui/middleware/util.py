import json
import requests
import time

from freenasUI.middleware.client import client


class JobAborted(Exception):
    pass


class JobFailed(Exception):
    def __init__(self, value):
        self.value = value


def run_alerts():
    with client as c:
        c.call('alert.process_alerts')


def wait_job(client, job_id):
    assert isinstance(job_id, int)
    while True:
        job = client.call('core.get_jobs', [('id', '=', job_id)])
        if job:
            job = job[0]
            if job['state'] == 'FAILED':
                raise JobFailed(job['error'])
            elif job['state'] == 'ABORTED':
                raise JobAborted()
            elif job['state'] == 'SUCCESS':
                return job
        time.sleep(0.5)


def upload_job_and_wait(fileobj, method_name, *args):

    with client as c:
        token = c.call('auth.generate_token')
        r = requests.post(
            'http://127.0.0.1/_upload/',
            files={
                'file': fileobj,
                'data': json.dumps({
                    'method': method_name,
                    'params': args,
                }),
            },
            headers={
                'Authorization': f'Token {token}',
            },
        )
        job_id = r.json()['job_id']
        return wait_job(c, job_id)
