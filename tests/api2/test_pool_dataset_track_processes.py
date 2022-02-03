import sys
import os
import time
sys.path.append(os.getcwd())

from functions import make_ws_request
from auto_config import ip
from middlewared.test.integration.utils import ssh
from middlewared.test.integration.assets.pool import dataset

TEST_DATASET = 'testing_processes'


def test__open_path_and_check_proc():
    with dataset(TEST_DATASET) as ds:
        opened = False
        try:
            path = f'/mnt/{ds}'
            test_file = f'{path}/test_file'
            cmdline = f'python -c "import time; f = open(\"{test_file}\", \"w+\"); time.sleep(10)"'
            open_pid = ssh(cmdline + ' & echo $!')
            assert open_pid.strip().isdigit(), open_pid
            opened = True

            # spinning up python interpreter could take some time on busy system so sleep
            # for a couple seconds to give it time
            time.sleep(2)

            # have to use websocket since the method being called is private
            payload = {'msg': 'method', 'method': 'pool.dataset.processes_using_paths', 'params': [path]}
            res = make_ws_request(ip, payload)
            assert len(res) == 1, res
            assert int(res[0]['pid']) == int(open_pid), res
            assert res[0]['cmdline'] == cmdline, res
        finally:
            if opened:
                ssh(f'kill -9 {open_pid}')
