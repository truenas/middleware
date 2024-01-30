import contextlib
import time

import pytest
from pytest_dependency import depends
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import dataset, pool

import os
import sys
sys.path.append(os.getcwd())

pytestmark = pytest.mark.zfs


@pytest.mark.parametrize("datasets,file_open_path,arg_path", [
    # A file on a dataset
    (
        [('test', None)],
        f'/mnt/{pool}/test/test_file',
        lambda ssh: f'/mnt/{pool}/test',
    ),
    # zvol
    (
        [('test', {'type': 'VOLUME', 'volsize': 1024 * 1024 * 100})],
        f'/dev/zvol/{pool}/test',
        lambda ssh: f'/dev/zvol/{pool}/test'
    ),
    # zvol with /dev/zd* path
    (
        [('test', {'type': 'VOLUME', 'volsize': 1024 * 1024 * 100})],
        f'/dev/zvol/{pool}/test',
        lambda ssh: ssh(f'readlink -f /dev/zvol/{pool}/test').strip(),
    ),
    # A dataset with nested zvol
    (
        [
            ('test', None),
            ('test/zvol', {'type': 'VOLUME', 'volsize': 1024 * 1024 * 100}),
        ],
        f'/dev/zvol/{pool}/test/zvol',
        lambda ssh: f'/dev/zvol/{pool}/test',
    ),
])
def test__open_path_and_check_proc(request, datasets, file_open_path, arg_path):
    with contextlib.ExitStack() as stack:
        for name, data in datasets:
            stack.enter_context(dataset(name, data))

        opened = False
        try:
            test_file = file_open_path
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
            res = call('pool.dataset.processes_using_paths', [arg_path(ssh)])
            assert len(res) == 1

            result = res[0]
            assert result['pid'] == open_pid, f'{result["pid"]!r} does not match {open_pid!r}'
            assert result['cmdline'] == cmdline, f'{result["cmdline"]!r} does not match {cmdline!r}'
        finally:
            if opened:
                ssh(f'kill -9 {open_pid}', check=False)
