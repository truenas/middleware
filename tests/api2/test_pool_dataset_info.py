import pytest
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import pool

pytestmark = pytest.mark.zfs


def test_recommended_zvol_blocksize():
    assert call("pool.dataset.recommended_zvol_blocksize", pool) == "16K"
