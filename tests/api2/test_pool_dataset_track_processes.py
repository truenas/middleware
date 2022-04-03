import sys
import os
import time
sys.path.append(os.getcwd())

import pytest

from functions import make_ws_request
from auto_config import ip
from middlewared.test.integration.utils import ssh
from middlewared.test.integration.assets.pool import dataset

TEST_DATASET = 'testing_processes'


@pytest.mark.parametrize("data,file_open_path,arg_path", [
    (None, lambda ds: f'/mnt/{ds}/test_file', lambda ds, ssh: f'/mnt/{ds}'),
    ({'type': 'VOLUME', 'volsize': 1024 * 1024 * 100}, lambda ds: f'/dev/zvol/{ds}', lambda ds, ssh: f'/dev/zvol/{ds}'),
    ({'type': 'VOLUME', 'volsize': 1024 * 1024 * 100}, lambda ds: f'/dev/zvol/{ds}',
     lambda ds, ssh: ssh(f'readlink -f /dev/zvol/{ds}').strip()),
])
def test__open_path_and_check_proc(data, file_open_path, arg_path):
    with dataset(TEST_DATASET, data) as ds:
        opened = False
        try:
            test_file = file_open_path(ds)
            open_pid = ssh(f"""python -c 'import time; f = open("{test_file}", "w+"); time.sleep(10)' > /dev/null 2>&1 & echo $!""")
            open_pid = open_pid.strip()
            assert open_pid.isdigit(), f'{open_pid!r} is not a digit'
            opened = True

            # spinning up python interpreter could take some time on busy system so sleep
            # for a couple seconds to give it time
            time.sleep(2)

            # what the cmdline output is formatted to
            cmdline = f"""python -c import time; f = open(\"{test_file}\", \"w+\"); time.sleep(10)"""

            # have to use websocket since the method being called is private
            payload = {'msg': 'method', 'method': 'pool.dataset.processes_using_paths', 'params': [[arg_path(ds, ssh)]]}
            res = make_ws_request(ip, payload)
            assert len(res['result']) == 1, f'Length of the result should only be 1 but is {len(res["result"])!r}'

            result = res['result'][0]
            assert result['pid'] == open_pid, f'{result["pid"]!r} does not match {open_pid!r}'
            assert result['cmdline'] == cmdline, f'{result["cmdline"]!r} does not match {cmdline!r}'
        finally:
            if opened:
                ssh(f'kill -9 {open_pid}', check=False)
