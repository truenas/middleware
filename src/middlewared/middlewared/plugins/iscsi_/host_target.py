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

    @accepts(Int("id"))
    async def get_targets(self, id):
        """
        Returns targets associated with host `id`.
        """
        return await self.middleware.call("iscsi.target.query", [["id", "in", [
            row["target_id"]
            for row in await self.middleware.call("datastore.query", "services.iscsihosttarget", [
                ["host_id", "=", id],
            ], {"relationships": False})
        ]]])

    @accepts(Int("id"), List("ids", items=[Int("id")]))
    async def set_targets(self, id, ids):
        """
        Associates targets `ids` with host `id`.
        """
        await self.middleware.call("datastore.delete", "services.iscsihosttarget", [["host_id", "=", id]])

        for target_id in ids:
            await self.middleware.call("datastore.insert", "services.iscsihosttarget", {
                "host_id": id,
                "target_id": target_id,
            })

        await self._service_change("iscsitarget", "reload")

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
