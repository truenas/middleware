import logging
from unittest.mock import Mock

import pytest

from middlewared.api.current import ContainerEntry, ContainerStatus
from middlewared.plugins.container import lifecycle
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext


@pytest.mark.parametrize(
    "entry,expected",
    [
        (lifecycle.start_on_boot, ["reconcile", ("start", 1)]),
        (lifecycle.autostart, [("start", 1)]),
    ],
)
def test_only_boot_path_reconciles_runtime_state(monkeypatch, entry, expected):
    events = []
    m = Middleware()
    m.libvirt_domains_manager = Mock()
    m.libvirt_domains_manager.reconcile_runtime_state = lambda: events.append("reconcile")
    m.services.truenas.entitlements.serving = lambda feature: True
    m.services.container.query = lambda *args: [
        ContainerEntry.model_construct(
            id=1,
            name="c1",
            autostart=True,
            status=ContainerStatus.model_construct(state="STOPPED"),
        )
    ]
    monkeypatch.setattr(lifecycle, "start", lambda context, id_: events.append(("start", id_)))

    entry(ServiceContext(m, logging.getLogger("test_container_start_on_boot")))

    assert events == expected
