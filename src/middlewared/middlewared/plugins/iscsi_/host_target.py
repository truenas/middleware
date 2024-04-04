from collections import defaultdict

from middlewared.schema import accepts, Int, List
from middlewared.service import private, Service, ServiceChangeMixin
import middlewared.sqlalchemy as sa


class iSCSIHostTargetModel(sa.Model):
    __tablename__ = "services_iscsihosttarget"

    id = sa.Column(sa.Integer(), primary_key=True)
    host_id = sa.Column(sa.Integer(), sa.ForeignKey("services_iscsihost.id", ondelete="CASCADE"))
    target_id = sa.Column(sa.Integer(), sa.ForeignKey("services_iscsitarget.id", ondelete="CASCADE"))


class iSCSIHostService(Service, ServiceChangeMixin):

    class Config:
        namespace = "iscsi.host"

    @accepts(Int("id"), roles=['SHARING_ISCSI_HOST_READ'])
    async def get_targets(self, id_):
        """
        Returns targets associated with host `id`.
        """
        return await self.middleware.call("iscsi.target.query", [["id", "in", [
            row["target_id"]
            for row in await self.middleware.call("datastore.query", "services.iscsihosttarget", [
                ["host_id", "=", id_],
            ], {"relationships": False})
        ]]])

    @accepts(Int("id"),
             List("ids", items=[Int("id")]),
             audit='Set iSCSI host targets',
             audit_callback=True,
             roles=['SHARING_ISCSI_HOST_WRITE'])
    async def set_targets(self, audit_callback, id_, ids):
        """
        Associates targets `ids` with host `id`.
        """
        audit_callback(await self._audit_summary(id_, ids))
        await self.middleware.call("datastore.delete", "services.iscsihosttarget", [["host_id", "=", id_]])

        for target_id in ids:
            await self.middleware.call("datastore.insert", "services.iscsihosttarget", {
                "host_id": id_,
                "target_id": target_id,
            })

        await self._service_change("iscsitarget", "reload")

    async def _audit_summary(self, id_, ids):
        """
        Return a summary string of the data provided, to be used in the audit summary.
        """
        try:
            host = (await self.middleware.call('iscsi.host.query', [['id', '=', id_]], {'get': True}))['ip']
        except Exception:
            host = id_
        try:
            targets = [target['name'] for target in await self.middleware.call('iscsi.target.query', [['id', 'in', ids]], {'select': ['name']})]
        except Exception:
            targets = ids
        if len(targets) > 3:
            return f'{host}: {",".join(targets[:3])},...'
        else:
            return f'{host}: {",".join(targets)}'

    @private
    async def get_target_hosts(self):
        target_hosts = defaultdict(list)
        for row in await self.middleware.call("datastore.query", "services.iscsihosttarget"):
            target_hosts[row["target"]["id"]].append(row["host"])
        return target_hosts

    @private
    async def get_hosts_iqns(self):
        hosts_iqns = defaultdict(list)
        for row in await self.middleware.call("datastore.query", "services.iscsihostiqn", [], {"relationships": False}):
            hosts_iqns[row["host_id"]].append(row["iqn"])
        return hosts_iqns
