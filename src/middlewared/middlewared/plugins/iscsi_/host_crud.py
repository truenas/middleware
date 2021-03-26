import asyncio
from collections import defaultdict
import errno
from sqlalchemy.exc import IntegrityError

from middlewared.schema import accepts, Bool, Dict, IPAddr, Int, List, Patch, Ref, Str
from middlewared.service import CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa

LOCK = asyncio.Lock()


class iSCSIHostModel(sa.Model):
    __tablename__ = "services_iscsihost"

    id = sa.Column(sa.Integer(), primary_key=True)
    ip = sa.Column(sa.String(45), unique=True)
    description = sa.Column(sa.Text())
    added_automatically = sa.Column(sa.Boolean())


class iSCSIHostIqnModel(sa.Model):
    __tablename__ = "services_iscsihostiqn"

    id = sa.Column(sa.Integer(), primary_key=True)
    iqn = sa.Column(sa.String(223), unique=True)
    host_id = sa.Column(sa.Integer(), sa.ForeignKey("services_iscsihost.id", ondelete="CASCADE"))


class iSCSIHostService(CRUDService):

    hosts = {}

    class Config:
        namespace = "iscsi.host"
        datastore = "services.iscsihost"
        datastore_extend = "iscsi.host.extend"
        datastore_extend_context = "iscsi.host.extend_context"
        cli_namespace = "sharing.iscsi.host"

    @private
    async def extend_context(self, rows, extra):
        id_to_iqns = defaultdict(list)
        for row in await self.middleware.call("datastore.query", "services.iscsihostiqn", [], {"relationships": False}):
            id_to_iqns[row["host_id"]].append(row["iqn"])

        return {
            "id_to_iqns": id_to_iqns,
        }

    @private
    async def extend(self, row, context):
        row["iqns"] = context["id_to_iqns"][row["id"]]
        return row

    @accepts(Dict(
        "iscsi_host_create",
        IPAddr("ip", required=True),
        Str("description", default=""),
        List("iqns", items=[Str("iqn", empty=False)], default=[]),
        Bool("added_automatically", default=False),
        register=True,
    ))
    async def do_create(self, data):
        """
        Creates iSCSI host.

        `ip` indicates an IP address of the host.
        `description` is a human-readable name for the host.
        `iqns` is a list of initiator iSCSI Qualified Names.
        """
        async with LOCK:
            return await self.create_unlocked(data)

    @accepts(Ref("iscsi_host_create"))
    @private
    async def create_unlocked(self, data):
        iqns = data.pop("iqns")
        try:
            id = await self.middleware.call("datastore.insert", self._config.datastore, data)
        except IntegrityError:
            verrors = ValidationErrors()
            verrors.add("iscsi_host_create.ip", "This IP address already exists", errno.EEXIST)
            raise verrors
        await self._set_datastore_iqns(id, iqns)

        host = await self.get_instance(id)

        self.hosts[host["ip"]] = host
        self._set_cache_iqns(id, iqns)

        return host

    @accepts(
        Int("id"),
        Patch(
            "iscsi_host_create",
            "iscsi_host_update",
            ("attr", {"update": True}),
            register=True,
        )
    )
    async def do_update(self, id, data):
        """
        Update iSCSI host `id`.
        """
        async with LOCK:
            return await self.update_unlocked(id, data)

    @accepts(Int("id"), Ref("iscsi_host_update"))
    @private
    async def update_unlocked(self, id, data):
        old = await self.get_instance(id)
        new = old.copy()
        new.update(data)

        iqns = new.pop("iqns")
        try:
            await self.middleware.call("datastore.update", self._config.datastore, id, new)
        except IntegrityError:
            verrors = ValidationErrors()
            verrors.add("iscsi_host_update.ip", "This IP address already exists", errno.EEXIST)
            raise verrors
        await self._set_datastore_iqns(id, iqns)

        host = await self.get_instance(id)

        self.hosts.pop(old["ip"], None)
        self.hosts[host["ip"]] = host
        self._set_cache_iqns(id, iqns)

        return host

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Update iSCSI host `id`.
        """
        async with LOCK:
            return await self.delete_unlocked(id)

    @private
    async def delete_unlocked(self, id):
        host = await self.get_instance(id)

        await self.middleware.call("datastore.delete", self._config.datastore, id)

        self.hosts.pop(host["ip"], None)

        return host

    async def _set_datastore_iqns(self, id, iqns):
        await self.middleware.call("datastore.delete", "services.iscsihostiqn", [["iqn", "in", iqns]])
        for iqn in iqns:
            await self.middleware.call("datastore.insert", "services.iscsihostiqn", {
                "iqn": iqn,
                "host_id": id,
            })

    def _set_cache_iqns(self, id, iqns):
        for host in self.hosts.values():
            if host["id"] != id:
                for iqn in iqns:
                    try:
                        host["iqns"].remove(iqn)
                    except ValueError:
                        pass

    @private
    async def read_cache(self):
        self.hosts = {}
        for host in await self.query():
            self.hosts[host["ip"]] = host

    @accepts(
        List(
            "hosts",
            items=[
                Dict(
                    "host",
                    IPAddr("ip", required=True),
                    Str("iqn", required=True),
                    Bool("added_automatically", default=False),
                ),
            ],
        ),
    )
    @private
    async def batch_update(self, hosts):
        async with LOCK:
            try:
                for host in hosts:
                    if host["ip"] not in self.hosts:
                        await self.create_unlocked({
                            "ip": host["ip"],
                            "added_automatically": host["added_automatically"],
                        })

                    db_host = self.hosts[host["ip"]]

                    if host["iqn"] not in db_host["iqns"]:
                        await self.update_unlocked(db_host["id"], {"iqns": db_host["iqns"] + [host["iqn"]]})

            except Exception:
                await self.read_cache()
                raise


async def setup(middleware):
    await middleware.call("iscsi.host.read_cache")
