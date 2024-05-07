import pytest

from middlewared.service_exception import ValidationErrors, ValidationError
from middlewared.test.integration.utils import call


def test_valid_kernel_options():
    call("system.advanced.update", {"kernel_extra_options": "zfs_arc_min=21474836480"})
    call("system.advanced.update", {"kernel_extra_options": ""})


def test_invalid_kernel_options():
    with pytest.raises(ValidationErrors) as ve:
        call("system.advanced.update", {"kernel_extra_options": "zfs_arc_min=<21474836480>"})

    assert ve.value.errors == [
        ValidationError("kernel_extra_options", "Invalid syntax"),
    ]
