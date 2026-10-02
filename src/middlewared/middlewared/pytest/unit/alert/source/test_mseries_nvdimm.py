import errno
from unittest.mock import Mock

import pytest

from middlewared.alert.base import UnavailableException
from middlewared.alert.source.mseries_nvdimm_and_bios import NVDIMMAndBIOSAlertSource
from middlewared.pytest.unit.middleware import Middleware


def test_failed_nvdimm_read_keeps_previous_alerts():
    """``UnavailableException`` tells the alert runtime to leave this source's alerts as they are."""
    m = Middleware()
    m["truenas.get_chassis_hardware"] = lambda: "TRUENAS-M60"
    m["mseries.bios.is_old_version"] = lambda: False
    m["mseries.nvdimm.info"] = Mock(side_effect=OSError(errno.EINVAL, "Invalid argument"))

    with pytest.raises(UnavailableException):
        NVDIMMAndBIOSAlertSource(m).check_sync()
