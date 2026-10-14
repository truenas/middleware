from typing import Any

from middlewared.api.current import NFSEntry, NFSUpdate
from middlewared.async_validators import validate_port
from middlewared.plugins.rdma.constants import RDMAprotocols
from middlewared.service import ServiceContext, SystemServicePart, ValidationError, ValidationErrors
import middlewared.sqlalchemy as sa

from .utils import NFSProtocol

MAX_MANAGED_NFSD = 32


class NFSModel(sa.Model):
    __tablename__ = "services_nfs"

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_srv_servers = sa.Column(sa.Integer(), nullable=True)
    nfs_srv_allow_nonroot = sa.Column(sa.Boolean(), default=False)
    nfs_srv_protocols = sa.Column(sa.JSON(list), default=[NFSProtocol.NFSv3, NFSProtocol.NFSv4])
    nfs_srv_v4_krb = sa.Column(sa.Boolean(), default=False)
    nfs_srv_bindip = sa.Column(sa.MultiSelectField())
    nfs_srv_mountd_port = sa.Column(sa.SmallInteger(), nullable=True)
    nfs_srv_rpcstatd_port = sa.Column(sa.SmallInteger(), nullable=True)
    nfs_srv_rpclockd_port = sa.Column(sa.SmallInteger(), nullable=True)
    nfs_srv_16 = sa.Column(sa.Boolean(), default=False)
    nfs_srv_mountd_log = sa.Column(sa.Boolean(), default=True)
    nfs_srv_statd_lockd_log = sa.Column(sa.Boolean(), default=False)
    nfs_srv_v4_domain = sa.Column(sa.String(120))
    nfs_srv_rdma = sa.Column(sa.Boolean(), default=False)


async def bindip_choices(context: ServiceContext) -> dict[str, str]:
    return {
        entry["address"]: entry["address"]
        for entry in await context.middleware.call("interface.ip_in_use", {"static": True})
    }


class NFSServicePart(SystemServicePart[NFSEntry]):
    _datastore = "services.nfs"
    _datastore_prefix = "nfs_srv_"
    _entry = NFSEntry
    _service = "nfs"
    _service_verb = "restart"

    async def rdma_capable(self) -> bool:
        """Whether NFS over RDMA is available on this system, ignoring whether it is currently enabled.

        Deliberately does not read the NFS config: this is called from `extend`, so consulting the
        config here would recurse.
        """
        return RDMAprotocols.NFS.value in await self.middleware.call("rdma.capable_protocols")

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        keytab_has_nfs = await self.middleware.call("kerberos.keytab.has_nfs_principal")
        data["v4_krb_enabled"] = data["v4_krb"] or keytab_has_nfs
        data["userd_manage_gids"] = data.pop("16")
        data["keytab_has_nfs_spn"] = keytab_has_nfs

        # 'None' indicates we are to dynamically manage the number of nfsd
        data["managed_nfsd"] = data["servers"] is None
        if data["managed_nfsd"]:
            cpu_info = await self.middleware.call("system.cpu_info")
            data["servers"] = min(max(cpu_info["core_count"], 1), MAX_MANAGED_NFSD)

        # Repair inconsistencies
        data["rdma"] = data["rdma"] and await self.rdma_capable()

        return data

    async def do_update(self, data: NFSUpdate) -> NFSEntry:
        old = await self.config()
        if old.managed_nfsd:
            old = old.model_copy(update={"servers": None})

        new = old.updated(data)

        if not new.protocols:
            raise ValidationError(
                "nfs_update.protocols", 'Must specify at least one value ("NFSV3", "NFSV4") in the "protocols" list.'
            )

        new = await self._validate(new)

        update = new.model_dump()
        for field in ("id", "managed_nfsd", "v4_krb_enabled", "keytab_has_nfs_spn"):
            update.pop(field)
        update["16"] = update.pop("userd_manage_gids")

        await self._update_service(old.id, update)

        if old.mountd_log != new.mountd_log:
            await (await self.call2(self.s.service.control, "RELOAD", "syslogd")).wait(raise_error=True)

        return await self.config()

    async def _validate(self, new: NFSEntry) -> NFSEntry:
        verrors = ValidationErrors()

        keytab_has_nfs = await self.middleware.call("kerberos.keytab.has_nfs_principal")
        new_v4_krb_enabled = new.v4_krb or keytab_has_nfs

        for field in ("mountd_port", "rpcstatd_port", "rpclockd_port"):
            for bindip in new.bindip or ["0.0.0.0"]:
                verrors.extend(
                    await validate_port(self.middleware, f"nfs_update.{field}", getattr(new, field), "nfs", bindip)
                )

        if (
            await self.middleware.call("failover.licensed")
            and NFSProtocol.NFSv4 in new.protocols
            and new_v4_krb_enabled
        ):
            gc = await self.middleware.call("datastore.config", "network.globalconfiguration")
            if not gc["gc_hostname_virtual"] or not gc["gc_domain"]:
                verrors.add(
                    "nfs_update.v4",
                    "Enabling kerberos authentication on TrueNAS HA requires setting the virtual hostname and domain",
                )

        choices = await bindip_choices(self)
        for i, bindip in enumerate(new.bindip):
            if bindip not in choices:
                verrors.add(f"nfs_update.bindip.{i}", f"Cannot use {bindip}. Please provide a valid ip address.")

        if NFSProtocol.NFSv4 in new.protocols and new_v4_krb_enabled and not new.v4_domain:
            # If we're using KRB5 + NFS then we need a v4_domain defined
            # We can get this from the configured `kerberos_realm`.
            ds_config = await self.middleware.call("directoryservices.config")
            if ds_config["enable"] and ds_config["kerberos_realm"]:
                new = new.model_copy(update={"v4_domain": ds_config["kerberos_realm"]})

        if NFSProtocol.NFSv4 not in new.protocols and new.v4_domain:
            verrors.add("nfs_update.v4_domain", "This option does not apply to NFSv3")

        if new.rdma and not await self.rdma_capable():
            verrors.add(
                "nfs_update.rdma", "This platform cannot support NFS over RDMA or is missing an RDMA capable NIC."
            )

        verrors.check()

        return new
