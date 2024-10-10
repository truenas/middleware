import pytest

from unittest.mock import AsyncMock, patch

from middlewared.plugins.reporting.netdata.graphs import (
    CPUPlugin, CPUTempPlugin, DiskTempPlugin, DISKPlugin, InterfacePlugin, LoadPlugin, MemoryPlugin,
    UptimePlugin, ARCActualRatePlugin, ARCRatePlugin, ARCSizePlugin
)
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('obj, identifier, legend', [
    (CPUPlugin, 'cpu', ['time']),
    (CPUTempPlugin, 'cputemp', ['time']),
    (DISKPlugin, 'sda', ['time']),
    (InterfacePlugin, 'enp1s0', ['time', 'received', 'sent']),
    (LoadPlugin, 'load', ['time']),
    (MemoryPlugin, 'memory', ['time']),
    (UptimePlugin, 'uptime', ['time']),
    (ARCActualRatePlugin, 'arcactualrate', ['time']),
    (ARCRatePlugin, 'arcrate', ['time']),
    (ARCSizePlugin, 'arcsize', ['time']),
    (DiskTempPlugin, 'sda', ['time', 'temperature_value']),
])
@pytest.mark.asyncio
async def test_netdata_client_malformed_response_error(obj, identifier, legend):
    plugin_object = obj(Middleware())

    api_response = {'error': 'test error', 'data': [], 'identifier': identifier, 'uri': 'http://test_uri'}
    with patch(
        'middlewared.plugins.reporting.netdata.connector.ClientMixin.fetch', AsyncMock(return_value=api_response)
    ):
        if obj in (DISKPlugin, DiskTempPlugin):
            plugin_object.disk_mapping = {identifier: ''}
            data = await plugin_object.export_multiple_identifiers({'after': 0, 'before': 0}, [identifier])
        else:
            data = await plugin_object.export_multiple_identifiers({'after': 0, 'before': 0}, [identifier])

        assert set(data[0]['legend']) == set(legend)
        assert data[0]['identifier'] == identifier
        assert data[0]['data'] == []
