import contextlib
import uuid
from collections import namedtuple

import pytest

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import another_pool, dataset, pool

import os
import sys
sys.path.append(os.getcwd())

Holder = namedtuple('Holder', ['pid', 'cmdline'])


@contextlib.contextmanager
def file_held_open(path):
    """Hold `path` open in a background process on the test system.

    Yields the holder's pid and the cmdline it reports through /proc, once the file is
    confirmed open. Readiness is polled rather than slept on, because interpreter
    startup on a loaded box can outrun any constant we would pick. The holder sleeps
    far longer than any caller needs and is killed on the way out, so its own timeout
    never bounds the test.
    """
    marker = f'/tmp/holder_ready_{uuid.uuid4().hex}'
    script = f'f = open("{path}", "w+"); open("{marker}", "w").close(); import time; time.sleep(600)'
    out = ssh(
        f"""python -c '{script}' > /dev/null 2>&1 & pid=$!; """
        f"""for _ in $(seq 200); do [ -e {marker} ] && break; sleep 0.05; done; """
        f"""[ -e {marker} ] && echo "$pid ready" || echo "$pid timeout" """
    ).strip()

    pid, status = out.split()
    try:
        assert pid.isdigit(), f'{pid!r} is not a digit'
        assert status == 'ready', f'holder process never opened {path!r}'
        yield Holder(pid=int(pid), cmdline=f'python -c {script}')
    finally:
        ssh(f'kill -9 {pid}; rm -f {marker}', check=False)


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
def test__open_path_and_check_proc(datasets, file_open_path, arg_path):
    with contextlib.ExitStack() as stack:
        for name, data in datasets:
            stack.enter_context(dataset(name, data))

        test_file = file_open_path
        with file_held_open(test_file) as holder:
            # have to use websocket since the method being called is private
            res = call('pool.dataset.processes_using_paths', [arg_path(ssh)])
            assert len(res) == 1

            result = res[0]
            assert result['pid'] == holder.pid, f'{result["pid"]!r} does not match {holder.pid!r}'
            assert result['cmdline'] == holder.cmdline, f'{result["cmdline"]!r} does not match {holder.cmdline!r}'
            assert 'paths' not in result

            res = call('pool.dataset.processes_using_paths', [arg_path(ssh)], True)
            assert len(res) == 1
            result = res[0]
            assert result['pid'] == holder.pid, f'{result["pid"]!r} does not match {holder.pid!r}'
            assert result['cmdline'] == holder.cmdline, f'{result["cmdline"]!r} does not match {holder.cmdline!r}'
            assert 'paths' in result
            assert len(result['paths']) == 1
            assert result['paths'][0] == test_file if test_file.startswith('/mnt') else '/dev/zd0'


@pytest.mark.parametrize("child,data,file_open_path", [
    # A file on a child filesystem
    ('parent/child', None, lambda ds: f'/mnt/{ds}/test_file'),
    # A child zvol
    ('parent/zvol', {'type': 'VOLUME', 'volsize': 1024 * 1024 * 100}, lambda ds: f'/dev/zvol/{ds}'),
])
def test__pool_processes_finds_child_dataset(child, data, file_open_path):
    """
    A pool-wide scan has to see processes holding a child dataset open.

    Every ZFS dataset is a separate filesystem with its own device id, so scanning only the
    pool root -- which is all `pool.dataset.processes` does -- never matches an open file on
    a child filesystem, and `pool.export` then fails to unmount it.
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(dataset('parent'))
        child_ds = stack.enter_context(dataset(child, data))

        with file_held_open(file_open_path(child_ds)) as holder:
            pool_id = call('pool.query', [['name', '=', pool]], {'get': True})['id']
            pool_wide = call('pool.processes', pool_id)
            assert holder.pid in [proc['pid'] for proc in pool_wide], pool_wide

            if data is None:
                # Scanning the pool root alone cannot see a file open on a child filesystem.
                # Child zvols are exempt: the root scan resolves `/dev/zvol/<pool>` as a
                # directory and walks every device node underneath it.
                root_only = call('pool.dataset.processes', pool)
                assert holder.pid not in [proc['pid'] for proc in root_only], root_only


def test__pool_export_kills_process_holding_child_dataset():
    """
    `pool.export` must terminate a process holding a file open on a child dataset,
    otherwise the export fails to unmount the child with EBUSY. This exercises the
    full export path, not just the detection that `pool.processes` reports.
    """
    with another_pool() as temp_pool:
        child = f'{temp_pool["name"]}/child'
        call('pool.dataset.create', {'name': child})

        with file_held_open(f'/mnt/{child}/test_file'):
            call('pool.export', temp_pool['id'], {'destroy': True}, job=True)
