import json
import os
import sys
import tempfile

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import wait_on_job, POST
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def upload_file(file_path, file_path_on_tn):
    data = {'method': 'filesystem.put', 'params': [file_path_on_tn]}
    with open(file_path, 'rb') as f:
        response = POST(
            '/_upload/',
            files={'data': json.dumps(data), 'file': f},
            use_ip_only=True,
            force_new_headers=True,
        )

    job_id = json.loads(response.text)['job_id']
    return wait_on_job(job_id, 300)


def file_exists(file_path):
    return any(
        entry for entry in call('filesystem.listdir', os.path.dirname(file_path))
        if entry['name'] == os.path.basename(file_path) and entry['type'] == 'FILE'
    )


def test_put_file():
    upload_file_impl(False)


def test_put_file_in_locked_dataset():
    upload_file_impl(True)


def upload_file_impl(lock):
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write('filesystem.put test')
        f.flush()

        with dataset(
            'test_filesystem_put', data={
                'encryption': True,
                'inherit_encryption': False,
                'encryption_options': {'passphrase': '12345678'}
            },
        ) as test_dataset:
            if lock:
                call('pool.dataset.lock', test_dataset, job=True)
            file_path_on_tn = f'/mnt/{test_dataset}/testfile'
            job_detail = upload_file(f.name,file_path_on_tn)
            assert job_detail['results']['state'] == ('FAILED' if lock else 'SUCCESS')
            assert file_exists(file_path_on_tn) is not lock
