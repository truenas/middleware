from datetime import datetime, timedelta

from middlewared.service import periodic, private, Service
import middlewared.sqlalchemy as sa

PENDING_SNAPSHOT_DELETE_INTERVAL = timedelta(hours=3)
PENDING_SNAPSHOT_DELETE_LIFETIME = timedelta(days=7)


class VMWarePendingSnapshotDelete(sa.Model):
    __tablename__ = "storage_vmwarependingsnapshotdelete"

    id = sa.Column(sa.Integer(), primary_key=True)
    vmware = sa.Column(sa.JSON())
    vm_uuid = sa.Column(sa.String(200))
    snapshot_name = sa.Column(sa.String(200))
    datetime = sa.Column(sa.DateTime())


class VMWareService(Service):
    @private
    async def defer_deleting_snapshot(self, vmware, vm_uuid, snapshot_name):
        await self.middleware.call(
            "datastore.insert",
            "storage.vmwarependingsnapshotdelete",
            {
                "vmware": vmware,
                "vm_uuid": vm_uuid,
                "snapshot_name": snapshot_name,
            },
        )

    @periodic(PENDING_SNAPSHOT_DELETE_INTERVAL.total_seconds(), run_on_start=False)
    @private
    async def delete_pending_snapshots(self):
        await self.middleware.call("network.general.will_perform_activity", "vmware")

        for pending_snapshot_delete in await self.middleware.call(
            "datastore.query",
            "storage.vmwarependingsnapshotdelete",
        ):
            try:
                si = await self.middleware.call("vmware.connect", pending_snapshot_delete["vmware"])
                await self.middleware.call("vmware.delete_vmware_login_failed_alert", pending_snapshot_delete["vmware"])
            except Exception as e:
                await self.middleware.call("vmware.alert_vmware_login_failed", pending_snapshot_delete["vmware"], e)
                continue

            deleted = False
            try:
                for vm in await self.middleware.call("vmware.find_vms_by_uuid", si, pending_snapshot_delete["vm_uuid"]):
                    try:
                        await self.middleware.call(
                            "vmware.delete_snapshot",
                            vm,
                            pending_snapshot_delete["snapshot_name"],
                        )
                        deleted = True
                    except Exception:
                        pass
            except Exception:
                pass

            if deleted or datetime.utcnow() - pending_snapshot_delete["datetime"] > PENDING_SNAPSHOT_DELETE_LIFETIME:
                await self.middleware.call(
                    "datastore.delete",
                    "storage.vmwarependingsnapshotdelete",
                    pending_snapshot_delete["id"],
                )

            await self.middleware.call("vmware.disconnect", si)
