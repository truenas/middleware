import pytest

from middlewared.api.current import DockerStatusInfo
from middlewared.plugins.docker import DockerLicenseDelegate
from middlewared.pytest.unit.middleware import Middleware, fake_service_control


@pytest.mark.asyncio
async def test_revoke_stops_docker_when_unit_is_up_but_status_is_failed():
    """A crash-looping dockerd reported FAILED must still be stopped on revoke."""
    m = Middleware()
    m["failover.in_progress"] = lambda: False
    m["failover.status.get_local"] = lambda cached: "SINGLE"
    m["interface.query"] = lambda filters: []
    m.services.service.started = lambda service: True
    m.services.docker.status = lambda: DockerStatusInfo(status="FAILED", description="")
    calls = fake_service_control(m, True)

    await DockerLicenseDelegate(m).apply({"APPS": False})

    assert [(verb, service) for verb, service, options in calls] == [("STOP", "docker")]
