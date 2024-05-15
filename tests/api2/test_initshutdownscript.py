import base64
import contextlib
import errno
import stat
import time

import pytest

from middlewared.test.integration.utils import client, ssh
from middlewared.service_exception import ValidationErrors, ValidationError

TEST_SCRIPT_FILE = '/root/.TEST_SCRIPT_FILE'
_775 = stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH


@pytest.fixture(scope='module')
def ws_client():
    with client() as c:
        yield c


@contextlib.contextmanager
def initshutudown_script(ws_client, contents, extra=None):
    extra = extra or {}

    ws_client.call(
        'filesystem.file_receive',
        TEST_SCRIPT_FILE,
        base64.b64encode(contents.encode('utf-8')).decode(),
        {'mode': _775},
    )
    script = ws_client.call(
        'initshutdownscript.create',
        {
            'type': 'SCRIPT',
            'script': TEST_SCRIPT_FILE,
            'when': 'PREINIT',
            **extra,
        }
    )
    try:
        yield script
    finally:
        ws_client.call('initshutdownscript.delete', script['id'])


def test_initshutudown_script(ws_client):
    with initshutudown_script(ws_client, 'echo "testing"') as script:
        _id = script['id']
        filters = [['id', '=', _id]]
        opts = {'get': True}

        # verify
        assert ws_client.call('initshutdownscript.query', filters, opts)['script'] == TEST_SCRIPT_FILE

        # add a comment
        ws_client.call('initshutdownscript.update', _id, {'comment': 'test_comment'})
        assert ws_client.call('initshutdownscript.query', filters, opts)['comment'] == 'test_comment'

        # disable it
        ws_client.call('initshutdownscript.update', _id, {'enabled': False})
        assert ws_client.call('initshutdownscript.query', filters, opts)['enabled'] is False

    assert not ws_client.call('initshutdownscript.query', filters)


def test_initshutdown_script_bad(ws_client):
    bad_script = f'/root/nonexistent-script'
    with pytest.raises(ValidationErrors) as e:
        ws_client.call(
            'initshutdownscript.create',
            {
                'type': 'SCRIPT',
                'script': bad_script,
                'when': 'PREINIT',
            }
        )

    assert e.value.errors == [
        ValidationError(
            'init_shutdown_script_create.script',
            f'Path {bad_script} not found',
            errno.ENOENT
        )
    ]


def test_initshutdownscript_success(ws_client):
    ssh("rm /tmp/flag", check=False)

    with initshutudown_script(ws_client, 'echo ok > /tmp/flag'):
        ws_client.call('initshutdownscript.execute_init_tasks', 'PREINIT', job=True)

    assert ssh("cat /tmp/flag") == "ok\n"


def test_initshutdownscript_timeout(ws_client):
    ssh("rm /tmp/flag", check=False)

    with initshutudown_script(ws_client, 'sleep 10', {"timeout": 2}):
        start = time.monotonic()
        ws_client.call('initshutdownscript.execute_init_tasks', 'PREINIT', job=True)

        assert time.monotonic() - start < 5

    assert f"Timed out running SCRIPT: {TEST_SCRIPT_FILE!r}" in ssh("cat /var/log/middlewared.log")


def test_initshutdownscript_failure(ws_client):
    ssh("rm /tmp/flag", check=False)

    with initshutudown_script(ws_client, 'echo everything went wrong > /dev/stderr; exit 1'):
        ws_client.call('initshutdownscript.execute_init_tasks', 'PREINIT', job=True)

    assert (
        f"Failed to execute 'exec {TEST_SCRIPT_FILE}' with error 'everything went wrong\\n'" in
        ssh("cat /var/log/middlewared.log")
    )
