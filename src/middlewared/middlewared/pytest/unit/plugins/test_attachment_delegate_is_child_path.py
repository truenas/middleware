import pytest

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.plugins.smb import SMBFSAttachmentDelegate
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('resource, path, check_parent, exact_match, is_child, expected_output', (
    ({'path': '/mnt/tank/test'}, '/mnt/tank', False, False, True, True),
    ({'path': '/mnt/tank/test'}, '/mnt/tank', False, True, True, False),
    ({'path': '/mnt/tank'}, '/mnt/tank', False, False, True, True),
    ({'path': '/mnt/test'}, '/mnt/tank', True, False, False, False),
    ({'path': '/mnt/tank/test'}, '/mnt/tank', True, False, True, True),
))
@pytest.mark.asyncio
async def test_attachment_is_child(resource, path, check_parent, exact_match, is_child, expected_output):
    m = Middleware()
    m['filesystem.is_child'] = lambda *arg: is_child
    smb_attachment = SMBFSAttachmentDelegate(m)
    assert (await smb_attachment.is_child_of_path(resource, path, check_parent, exact_match)) == expected_output


@pytest.mark.asyncio
async def test_destroy_defaults_to_a_no_op():
    # `delete` already disposed of a share/task style attachment while the pool was still there, so
    # the default must not go looking for it again -- these stubs raise if it does.
    class Delegate(FSAttachmentDelegate):
        name = 'test'
        title = 'Test'

        async def query(self, path, enabled, options=None):
            raise AssertionError('the default destroy must not query')

        async def delete(self, attachments):
            raise AssertionError('the default destroy must not delete')

    assert await Delegate(Middleware()).destroy('/mnt/tank') is None
