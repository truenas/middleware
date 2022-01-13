import sys
import os
sys.path.append(os.getcwd())

from functions import POST, make_ws_request
from auto_config import pool_name, ip
from middlewared.test.integration.utils import ssh

TEST_DATASET = f'{pool_name}/testing_processes'


def test_01_create_dataset():
    results = POST('/pool/dataset', {'name': TEST_DATASET})
    assert results.status_code == 200, results.text


def test_02_open_path_and_check_proc():
    path = f'/mnt/{TEST_DATASET}'
    test_file = f'{path}/test_file'
    open_pid = ssh(f'python -c "import time; f = open(\"{test_file}\", \"w+\"); time.sleep(10)" & echo $!')
    assert open_pid.isdigit()

    payload = {'msg': 'method', 'method': 'pool.dataset.processes_using_paths', 'params': list(path)}
    res = make_ws_request(ip, payload)
    assert int(res[0]['pid']) == int(open_pid), res
