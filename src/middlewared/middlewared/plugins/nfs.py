import asyncio
import ipaddress
import os
import socket
import subprocess

import sysctl

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import accepts, Bool, Dict, Dir, Int, IPAddr, List, Patch, Str
from middlewared.validators import Range
from middlewared.service import private, CRUDService, SystemServiceService, ValidationErrors
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.path import is_child


class NFSService(SystemServiceService):

    class Config:
        service = "nfs"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'

    @private
    def nfs_extend(self, nfs):
        nfs["userd_manage_gids"] = nfs.pop("16")
        return nfs

    @private
    def nfs_compress(self, nfs):
        nfs["16"] = nfs.pop("userd_manage_gids")
        return nfs

    @accepts(Dict(
        'nfs_update',
        Int('servers', validators=[Range(min=1, max=256)]),
        Bool('udp'),
        Bool('allow_nonroot'),
        Bool('v4'),
        Bool('v4_v3owner'),
        Bool('v4_krb'),
        Str('v4_domain'),
        List('bindip', items=[IPAddr('ip')]),
        Int('mountd_port', null=True, validators=[Range(min=1, max=65535)]),
        Int('rpcstatd_port', null=True, validators=[Range(min=1, max=65535)]),
        Int('rpclockd_port', null=True, validators=[Range(min=1, max=65535)]),
        Bool('userd_manage_gids'),
        Bool('mountd_log'),
        Bool('statd_lockd_log'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update NFS Service Configuration.

        `servers` represents number of servers to create.

        When `allow_nonroot` is set, it allows non-root mount requests to be served.

        `bindip` is a list of IP's on which NFS will listen for requests. When it is unset/empty, NFS listens on
        all available addresses.

        `v4` when set means that we switch from NFSv3 to NFSv4.

        `v4_v3owner` when set means that system will use NFSv3 ownership model for NFSv4.

        `v4_domain` overrides the default DNS domain name for NFSv4.

        `mountd_port` specifies the port mountd(8) binds to.

        `rpcstatd_port` specifies the port rpc.statd(8) binds to.

        `rpclockd_port` specifies the port rpclockd_port(8) binds to.

        .. examples(websocket)::

          Update NFS Service Configuration to listen on 192.168.0.10 and use NFSv4

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.resilver.update",
                "params": [{
                    "bindip": [
                        "192.168.0.10"
                    ],
                    "v4": true
                }]
            }
        """
        if data.get("v4") is False:
            data.setdefault("v4_v3owner", False)

        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new["v4"] and new["v4_krb"] and not await self.middleware.call("system.is_freenas"):
            if await self.middleware.call("failover.licensed"):
                gc = await self.middleware.call("datastore.config", "network.globalconfiguration")
                if not gc["gc_hostname_virtual"] or gc["gc_domain"]:
                    verrors.add(
                        "nfs_update.v4",
                        "Enabling kerberos authentication on TrueNAS HA requires setting the virtual hostname and "
                        "domain"
                    )

        if not new["v4"] and new["v4_v3owner"]:
            verrors.add("nfs_update.v4_v3owner", "This option requires enabling NFSv4")

        if new["v4_v3owner"] and new["userd_manage_gids"]:
            verrors.add(
                "nfs_update.userd_manage_gids", "This option is incompatible with NFSv3 ownership model for NFSv4")

        if not new["v4"] and new["v4_domain"]:
            verrors.add("nfs_update.v4_domain", "This option does not apply to NFSv3")

        if verrors:
            raise verrors

        self.nfs_compress(new)

        await self._update_service(old, new)

        self.nfs_extend(new)

        return new

    @private
    def setup_v4(self):
        config = self.middleware.call_sync("nfs.config")

        if config["v4_krb"]:
            subprocess.run(["service", "gssd", "onerestart"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["service", "gssd", "forcestop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if config["v4"]:
            sysctl.filter("vfs.nfsd.server_max_nfsvers")[0].value = 4
            if config["v4_v3owner"]:
                # Per RFC7530, sending NFSv3 style UID/GIDs across the wire is now allowed
                # You must have both of these sysctl"s set to allow the desired functionality
                sysctl.filter("vfs.nfsd.enable_stringtouid")[0].value = 1
                sysctl.filter("vfs.nfs.enable_uidtostring")[0].value = 1
                subprocess.run(["service", "nfsuserd", "forcestop"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                sysctl.filter("vfs.nfsd.enable_stringtouid")[0].value = 0
                sysctl.filter("vfs.nfs.enable_uidtostring")[0].value = 0
                subprocess.run(["service", "nfsuserd", "onerestart"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        else:
            sysctl.filter("vfs.nfsd.server_max_nfsvers")[0].value = 3
            if config["userd_manage_gids"]:
                subprocess.run(["service", "nfsuserd", "onerestart"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["service", "nfsuserd", "forcestop"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)


class SharingNFSService(CRUDService):
    class Config:
        namespace = "sharing.nfs"
        datastore = "sharing.nfs_share"
        datastore_prefix = "nfs_"
        datastore_extend = "sharing.nfs.extend"

    @accepts(Dict(
        "sharingnfs_create",
        List("paths", items=[Dir("path")], empty=False),
        Str("comment"),
        List("networks", items=[IPAddr("network", network=True)], default=[]),
        List("hosts", items=[Str("host")], default=[]),
        Bool("alldirs"),
        Bool("ro"),
        Bool("quiet"),
        Str("maproot_user", required=False, default=None, null=True),
        Str("maproot_group", required=False, default=None, null=True),
        Str("mapall_user", required=False, default=None, null=True),
        Str("mapall_group", required=False, default=None, null=True),
        List(
            "security",
            default=[],
            items=[Str("provider", enum=["SYS", "KRB5", "KRB5I", "KRB5P"])],
        ),
        Bool("enabled", default=True),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a NFS Share.

        `paths` is a list of valid paths which are configured to be shared on this share.

        `networks` is a list of authorized networks that are allowed to access the share having format
        "network/mask" CIDR notation. If empty, all networks are allowed.

        `hosts` is a list of IP's/hostnames which are allowed to access the share. If empty, all IP's/hostnames are
        allowed.

        `alldirs` is a boolean value which when set indicates that the client can mount any subdirectories of the
        selected pool or dataset.
        """
        verrors = ValidationErrors()

        await self.validate(data, "sharingnfs_create", verrors)

        if verrors:
            raise verrors

        await self.compress(data)
        paths = data.pop("paths")
        data["id"] = await self.middleware.call(
            "datastore.insert", self._config.datastore, data,
            {
                "prefix": self._config.datastore_prefix
            },
        )
        for path in paths:
            await self.middleware.call(
                "datastore.insert", "sharing.nfs_share_path",
                {
                    "share_id": data["id"],
                    "path": path,
                },
            )
        await self.extend(data)

        await self._service_change("nfs", "reload")

        return data

    @accepts(
        Int("id"),
        Patch(
            "sharingnfs_create",
            "sharingnfs_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        """
        Update NFS Share of `id`.
        """
        verrors = ValidationErrors()
        old = await self._get_instance(id)

        new = old.copy()
        new.update(data)

        await self.validate(new, "sharingnfs_update", verrors, old=old)

        if verrors:
            raise verrors

        await self.compress(new)
        paths = new.pop("paths")
        await self.middleware.call(
            "datastore.update", self._config.datastore, id, new,
            {
                "prefix": self._config.datastore_prefix
            }
        )
        await self.middleware.call("datastore.delete", "sharing.nfs_share_path", [["share_id", "=", id]])
        for path in paths:
            await self.middleware.call(
                "datastore.insert", "sharing.nfs_share_path",
                {
                    "share_id": id,
                    "path": path,
                },
            )

        await self.extend(new)
        new["paths"] = paths

        await self._service_change("nfs", "reload")

        return new

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Delete NFS Share of `id`.
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)
        await self._service_change("nfs", "reload")

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        if data["alldirs"] and len(data["paths"]) > 1:
            verrors.add(f"{schema_name}.alldirs", "This option can only be used for shares that contain single path")

        await self.middleware.run_in_thread(self.validate_paths, data, schema_name, verrors)

        filters = []
        if old:
            filters.append(["id", "!=", old["id"]])
        other_shares = await self.middleware.call("sharing.nfs.query", filters)
        dns_cache = await self.resolve_hostnames(
            sum([share["hosts"] for share in other_shares], []) + data["hosts"]
        )
        await self.middleware.run_in_thread(
            self.validate_hosts_and_networks, other_shares,
            data, schema_name, verrors, dns_cache
        )

        for k in ["maproot", "mapall"]:
            if not data[f"{k}_user"] and not data[f"{k}_group"]:
                pass
            elif not data[f"{k}_user"] and data[f"{k}_group"]:
                verrors.add(f"{schema_name}.{k}_user", "This field is required when map group is specified")
            else:
                user = await self.middleware.call("notifier.get_user_object", data[f"{k}_user"])
                if not user:
                    verrors.add(f"{schema_name}.{k}_user", "User not found")

                if data[f"{k}_group"]:
                    group = await self.middleware.call("notifier.get_group_object", data[f"{k}_group"])
                    if not group:
                        verrors.add(f"{schema_name}.{k}_group", "Group not found")

        if data["maproot_user"] and data["mapall_user"]:
            verrors.add(f"{schema_name}.mapall_user", "maproot_user disqualifies mapall_user")

        if data["security"]:
            nfs_config = await self.middleware.call("nfs.config")
            if not nfs_config["v4"]:
                verrors.add(f"{schema_name}.security", "This is not allowed when NFS v4 is disabled")

    @private
    def validate_paths(self, data, schema_name, verrors):
        dev = None
        for i, path in enumerate(data["paths"]):
            stat = os.stat(path)
            if dev is None:
                dev = stat.st_dev
            else:
                if dev != stat.st_dev:
                    verrors.add(f"{schema_name}.paths.{i}",
                                "Paths for a NFS share must reside within the same filesystem")

    @private
    async def resolve_hostnames(self, hostnames):
        hostnames = list(set(hostnames))

        async def resolve(hostname):
            try:
                return (
                    await asyncio.wait_for(self.middleware.run_in_thread(socket.getaddrinfo, hostname, None), 5)
                )[0][4][0]
            except Exception as e:
                self.logger.warning("Unable to resolve host %r: %r", hostname, e)
                return None

        resolved_hostnames = await asyncio_map(resolve, hostnames, 8)

        return dict(zip(hostnames, resolved_hostnames))

    @private
    def validate_hosts_and_networks(self, other_shares, data, schema_name, verrors, dns_cache):
        dev = os.stat(data["paths"][0]).st_dev

        used_networks = set()
        for share in other_shares:
            try:
                share_dev = os.stat(share["paths"][0]).st_dev
            except Exception:
                self.logger.warning("Failed to stat first path for %r", share, exc_info=True)
                continue

            if share_dev == dev:
                for host in share["hosts"]:
                    host = dns_cache[host]
                    if host is None:
                        continue

                    try:
                        network = ipaddress.ip_network(host)
                    except Exception:
                        self.logger.warning("Got invalid host %r", host)
                        continue
                    else:
                        used_networks.add(network)

                for network in share["networks"]:
                    try:
                        network = ipaddress.ip_network(network, strict=False)
                    except Exception:
                        self.logger.warning("Got invalid network %r", network)
                        continue
                    else:
                        used_networks.add(network)

                if not share["hosts"] and not share["networks"]:
                    used_networks.add(ipaddress.ip_network("0.0.0.0/0"))
                    used_networks.add(ipaddress.ip_network("::/0"))

        for i, host in enumerate(data["hosts"]):
            host = dns_cache[host]
            if host is None:
                continue

            network = ipaddress.ip_network(host)
            if network in used_networks:
                verrors.add(
                    f"{schema_name}.hosts.{i}",
                    "Another NFS share already exports this dataset for this host"
                )

            used_networks.add(network)

        for i, network in enumerate(data["networks"]):
            network = ipaddress.ip_network(network, strict=False)

            if network in used_networks:
                verrors.add(
                    f"{schema_name}.networks.{i}",
                    "Another NFS share already exports this dataset for this network"
                )

            used_networks.add(network)

        if not data["hosts"] and not data["networks"]:
            if used_networks:
                verrors.add(
                    f"{schema_name}.networks",
                    "Another NFS share already exports this dataset for some network"
                )

    @private
    async def extend(self, data):
        data["paths"] = [path["path"]
                         for path in await self.middleware.call("datastore.query", "sharing.nfs_share_path",
                                                                [["share_id", "=", data["id"]]])]
        data["networks"] = data.pop("network").split()
        data["hosts"] = data["hosts"].split()
        data["security"] = [s.upper() for s in data["security"]]
        return data

    @private
    async def compress(self, data):
        data["network"] = " ".join(data.pop("networks"))
        data["hosts"] = " ".join(data["hosts"])
        data["security"] = [s.lower() for s in data["security"]]
        return data


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload NFS if a pool is imported and there are shares configured for it.
    """
    path = f'/mnt/{pool["name"]}'
    for share in await middleware.call('sharing.nfs.query'):
        if any(filter(lambda x: x == path or x.startswith(f'{path}/'), share['paths'])):
            asyncio.ensure_future(middleware.call('service.reload', 'nfs'))
            break


class NFSFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'nfs'
    title = 'NFS Share'
    service = 'nfs'

    async def query(self, path, enabled):
        results = []
        for nfs in await self.middleware.call('sharing.nfs.query', [['enabled', '=', enabled]]):
            if any(is_child(nfs_path, path) for nfs_path in nfs['paths']):
                results.append(nfs)

        return results

    async def get_attachment_name(self, attachment):
        return ', '.join(attachment['paths'])

    # NFS share can only contain paths from single dataset, that's why we can delete/disable entire share
    # if even one path matches
    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', 'sharing.nfs_share', attachment['id'])

        await self._service_change('nfs', 'reload')

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.middleware.call('datastore.update', 'sharing.nfs_share', attachment['id'],
                                       {'nfs_enabled': enabled})

        await self._service_change('nfs', 'reload')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', NFSFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import_pool', pool_post_import, sync=True)
