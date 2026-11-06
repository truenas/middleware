import logging
import os
from types import SimpleNamespace
from unittest.mock import Mock

from middlewared.plugins.zpool import zpool_create
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import ServiceContext


def test_sed_provisioning_precedes_fencing_and_fencing_precedes_any_write(monkeypatch):
    """Fenced racing SED provisioning corrupts controller state on some SED firmware, and the disks must be fenced
    before they are resized or formatted. pool.create and zpool.create both take their disks through here."""
    calls = []
    middleware = Middleware()

    def record(name, result=None):
        def method(*args):
            calls.append(name)
            return result

        middleware[name] = method

    middleware["failover.licensed"] = lambda: True
    record("disk.setup_sed_disks_for_pool")
    record("failover.fenced.start", 0)
    record("disk.resize", Mock())
    monkeypatch.setattr(zpool_create, "format_disks", lambda *args: calls.append("format_disks"))
    middleware.services.system.advanced.config = lambda: SimpleNamespace(overprovision=16)
    monkeypatch.setattr(zpool_create, "os", SimpleNamespace(path=os.path, makedirs=Mock()))

    zpool_create.prepare_disks(
        ServiceContext(middleware, logging.getLogger("test")),
        FakeJob(),
        {"sda": {"vdev": []}, "sdb": {"vdev": []}},
        ["sdb"],
        True,
        "zpool.create",
    )

    assert calls == [
        "disk.setup_sed_disks_for_pool",
        "failover.fenced.start",
        "disk.resize",
        "format_disks",
    ]
