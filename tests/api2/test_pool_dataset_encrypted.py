import errno

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


PASSPHRASE = "12345678"
pytestmark = pytest.mark.zfs


def encryption_props():
    return {
        "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        "encryption": True,
        "inherit_encryption": False
    }


def test_delete_locked_dataset():
    with dataset("test_delete_locked_dataset", encryption_props()) as ds:
        call("pool.dataset.lock", ds, job=True)

    with pytest.raises(CallError) as ve:
        call("filesystem.stat", f"/mnt/{ds}")

    assert ve.value.errno == errno.ENOENT


def test_unencrypted_dataset_within_encrypted_dataset():
    with dataset("test_pool_dataset_witin_encryted", encryption_props()) as ds:
        with pytest.raises(ValidationErrors) as ve:
            call("pool.dataset.create", {
                "name": f"{ds}/child",
                "encryption": False,
                "inherit_encryption": False,
            })

        assert any(
            "Cannot create an unencrypted dataset within an encrypted dataset" in error.errmsg
            for error in ve.value.errors
        ) is True, ve
