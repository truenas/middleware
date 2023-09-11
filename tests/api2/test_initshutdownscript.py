import base64
import errno
import stat
import uuid

import pytest

from middlewared.test.integration.utils.client import client
from middlewared.service_exception import ValidationErrors, ValidationError

TEST_SCRIPT_FILE = '/tmp/.TEST_SCRIPT_FILE'
_775 = stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH


@pytest.fixture(scope='module')
def ws_client():
    with client() as c:
        yield c


def test_initshutudown_script(ws_client):
    # create the test script file first
    ws_client.call(
        'filesystem.file_receive',
        TEST_SCRIPT_FILE,
        base64.b64encode(b'echo "testing"').decode(),
        {'mode': _775},
    )
    _id = ws_client.call(
        'initshutdownscript.create',
        {
            'type': 'SCRIPT',
            'script': TEST_SCRIPT_FILE,
            'when': 'PREINIT',
        }
    )['id']
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

    # delete it
    ws_client.call('initshutdownscript.delete', _id)
    assert not ws_client.call('initshutdownscript.query', filters)


def test_initshutdown_script_bad(ws_client):
    bad_script = f'/tmp/{uuid.uuid4()}'
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
