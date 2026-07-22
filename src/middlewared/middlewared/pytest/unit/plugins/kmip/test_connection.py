from unittest.mock import MagicMock

import pytest

from middlewared.plugins.kmip.connection import kmip_connection
from middlewared.service import CallError


def test_kmip_connection_refused_raised_as_callerror():
    # PyKMIP re-raises the bare ConnectionRefusedError when the server refuses the connection,
    # and that type is not one `kmip_connection` used to catch. It must still be surfaced as a
    # CallError so every caller sees a uniform "Failed to connect to KMIP Server" error rather
    # than a leaked socket error. Port 2 on loopback has nothing listening, so the connection
    # is refused.
    context = MagicMock()
    with pytest.raises(CallError, match="Failed to connect to KMIP Server"):
        with kmip_connection(context, {"server": "127.0.0.1", "port": 2}):
            pass
