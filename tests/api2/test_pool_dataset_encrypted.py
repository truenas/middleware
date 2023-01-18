import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


PASSPHRASE = "12345678"


def encryption_props():
    return {
        "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        "encryption": True,
        "inherit_encryption": False
    }


def test_delete_locked_dataset():
    with dataset("test", encryption_props()) as ds:
        call("pool.dataset.lock", ds, job=True)

    with pytest.raises(CallError) as ve:
        call("filesystem.stat", f"/mnt/{ds}")

    assert ve.value.errno == errno.ENOENT
