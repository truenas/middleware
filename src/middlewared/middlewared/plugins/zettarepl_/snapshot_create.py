from middlewared.service import Service

from zettarepl.snapshot.create import create_snapshot
from zettarepl.snapshot.snapshot import Snapshot
from zettarepl.transport.local import LocalShell


class ZettareplService(Service):

    class Config:
        private = True

    def create_recursive_snapshot_with_exclude(self, dataset, snapshot, exclude):
        create_snapshot(LocalShell(), Snapshot(dataset, snapshot), True, exclude, {})
