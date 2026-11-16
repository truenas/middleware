"""
Tests of the system dataset that the pwenc secret encrypts. TrueSearch keeps its indexes on it. The tests that need an
encrypted dataset are in tests/api2/test_system_dataset_pwenc.py.
"""

import pytest

from middlewared.plugins.system_dataset.encryption import setup_pwenc_dataset
from middlewared.plugins.system_dataset.hierarchy import get_system_dataset_spec
from middlewared.service_exception import CallError


def test_only_the_index_dataset_is_encrypted_with_the_pwenc_secret():
    spec = get_system_dataset_spec("tank", "uuid")
    assert [ds["name"] for ds in spec if ds.get("pwenc_encrypted")] == ["tank/.system/truesearchd"]


def test_the_boot_pool_has_no_index_dataset():
    names = [ds["name"] for ds in get_system_dataset_spec("boot-pool", "uuid")]
    assert "boot-pool/.system" in names
    assert "boot-pool/.system/truesearchd" not in names


def test_a_dataset_that_is_not_encrypted_is_refused():
    with pytest.raises(CallError, match="is not encrypted. Destroy it"):
        setup_pwenc_dataset(None, "tank/.system/truesearchd", {}, "off")
