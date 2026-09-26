import os
import tempfile

import pytest
import truenas_pypwenc

from middlewared.utils.pwenc import PWENC_CHECK, PWENC_PADDING, pwenc_secret_matches


def _secretmem_available():
    # The secret is held in a memfd_secret() region, which the kernel only provides when secretmem
    # is enabled. Container and emulated environments routinely lack it.
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            truenas_pypwenc.get_context(create=True, watch=False, secret_path=os.path.join(tmp_dir, "probe"))
    except truenas_pypwenc.PwencError:
        return False

    return True


pytestmark = pytest.mark.skipif(not _secretmem_available(), reason="kernel does not provide memfd_secret()")


@pytest.fixture
def secret(tmp_path):
    path = str(tmp_path / "pwenc_secret")
    ctx = truenas_pypwenc.get_context(create=True, watch=False, secret_path=path)
    return path, ctx


def test_secret_matches_its_own_check_value(secret):
    path, ctx = secret

    assert pwenc_secret_matches(path, ctx.encrypt(PWENC_CHECK.encode()).decode())


def test_secret_matches_legacy_padded_check_value(secret):
    path, ctx = secret
    padded = PWENC_CHECK.encode() + PWENC_PADDING * 9

    assert pwenc_secret_matches(path, ctx.encrypt(padded).decode())


def test_another_secret_does_not_match(secret, tmp_path):
    _, ctx = secret
    other_path = str(tmp_path / "other_pwenc_secret")
    truenas_pypwenc.get_context(create=True, watch=False, secret_path=other_path)

    assert not pwenc_secret_matches(other_path, ctx.encrypt(PWENC_CHECK.encode()).decode())


def test_unusable_secret_file_does_not_match(secret, tmp_path):
    _, ctx = secret
    truncated = tmp_path / "truncated_pwenc_secret"
    truncated.write_bytes(os.urandom(truenas_pypwenc.PWENC_BLOCK_SIZE - 1))

    assert not pwenc_secret_matches(str(truncated), ctx.encrypt(PWENC_CHECK.encode()).decode())
