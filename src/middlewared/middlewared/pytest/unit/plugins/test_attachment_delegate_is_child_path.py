import pytest

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
