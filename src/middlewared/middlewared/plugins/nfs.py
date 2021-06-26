import asyncio
import contextlib
import ipaddress
import os
import socket

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.schema import accepts, Bool, Dict, Dir, Int, IPAddr, List, Patch, returns, Str
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.validators import Match, Range
from middlewared.service import private, SharingService, SystemServiceService, ValidationError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import osc
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.path import is_child


class NFSModel(sa.Model):
    __tablename__ = 'services_nfs'

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_srv_servers = sa.Column(sa.Integer(), default=4)
    nfs_srv_udp = sa.Column(sa.Boolean(), default=False)
    nfs_srv_allow_nonroot = sa.Column(sa.Boolean(), default=False)
    nfs_srv_v4 = sa.Column(sa.Boolean(), default=False)
    nfs_srv_v4_v3owner = sa.Column(sa.Boolean(), default=False)
    nfs_srv_v4_krb = sa.Column(sa.Boolean(), default=False)
    nfs_srv_bindip = sa.Column(sa.MultiSelectField())
    nfs_srv_mountd_port = sa.Column(sa.SmallInteger(), nullable=True)
    nfs_srv_rpcstatd_port = sa.Column(sa.SmallInteger(), nullable=True)
    nfs_srv_rpclockd_port = sa.Column(sa.SmallInteger(), nullable=True)
    nfs_srv_16 = sa.Column(sa.Boolean(), default=False)
    nfs_srv_mountd_log = sa.Column(sa.Boolean(), default=True)
    nfs_srv_statd_lockd_log = sa.Column(sa.Boolean(), default=False)
    nfs_srv_v4_domain = sa.Column(sa.String(120))


class NFSService(SystemServiceService):

    class Config:
        service = "nfs"
        service_verb = "restart"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'
        cli_namespace = "service.nfs"

    ENTRY = Dict(
        'nfs_entry',
        Int('id', required=True),
        Int('servers', validators=[Range(min=1, max=256)], required=True),
        Bool('udp', required=True),
        Bool('allow_nonroot', required=True),
        Bool('v4', required=True),
        Bool('v4_v3owner', required=True),
        Bool('v4_krb', required=True),
        Str('v4_domain', required=True),
        List('bindip', items=[IPAddr('ip')], required=True),
        Int('mountd_port', null=True, validators=[Range(min=1, max=65535)], required=True),
        Int('rpcstatd_port', null=True, validators=[Range(min=1, max=65535)], required=True),
        Int('rpclockd_port', null=True, validators=[Range(min=1, max=65535)], required=True),
        Bool('mountd_log', required=True),
        Bool('statd_lockd_log', required=True),
        Bool('v4_krb_enabled', required=True),
        Bool('userd_manage_gids', required=True),
    )

    @private
    async def nfs_extend(self, nfs):
        keytab_has_nfs = await self.middleware.call("kerberos.keytab.has_nfs_principal")
        nfs["v4_krb_enabled"] = (nfs["v4_krb"] or keytab_has_nfs)
        nfs["userd_manage_gids"] = nfs.pop("16")
        return nfs

    @private
    async def nfs_compress(self, nfs):
        nfs.pop("v4_krb_enabled")
        nfs["16"] = nfs.pop("userd_manage_gids")
        return nfs

    @accepts()
    @returns(Dict(additional_attrs=True))
    async def bindip_choices(self):
        """
        Returns ip choices for NFS service to use
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True}
            )
        }

    @private
    async def bindip(self, config):
        bindip = [addr for addr in config['bindip'] if addr not in ['0.0.0.0', '::']]
        if osc.IS_LINUX:
            bindip = bindip[:1]

        if bindip:
            found = False
            for iface in await self.middleware.call('interface.query'):
                for alias in iface['state']['aliases']:
                    if alias['address'] in bindip:
                        found = True
                        break
                if found:
                    break
        else:
            found = True

        if found:
            await self.middleware.call('alert.oneshot_delete', 'NFSBindAddress', None)

            return bindip
        else:
            if await self.middleware.call('cache.has_key', 'interfaces_are_set_up'):
                await self.middleware.call('alert.oneshot_create', 'NFSBindAddress', None)

            return []

    @accepts(Patch(
        'nfs_entry', 'nfs_update',
        ('rm', {'name': 'id'}),
        ('rm', {'name': 'v4_krb_enabled'}),
        ('attr', {'update': True}),
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

        `v4_krb` will force NFS shares to fail if the Kerberos ticket is unavailable.

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

        keytab_has_nfs = await self.middleware.call("kerberos.keytab.has_nfs_principal")
        new_v4_krb_enabled = new["v4_krb"] or keytab_has_nfs

        if await self.middleware.call("failover.licensed") and new["v4"] and new_v4_krb_enabled:
            gc = await self.middleware.call("datastore.config", "network.globalconfiguration")
            if not gc["gc_hostname_virtual"] or not gc["gc_domain"]:
                verrors.add(
                    "nfs_update.v4",
                    "Enabling kerberos authentication on TrueNAS HA requires setting the virtual hostname and "
                    "domain"
                )

        if osc.IS_LINUX:
            if len(new['bindip']) > 1:
                verrors.add('nfs_update.bindip', 'Listening on more than one address is not supported')
        bindip_choices = await self.bindip_choices()
        for i, bindip in enumerate(new['bindip']):
            if bindip not in bindip_choices:
                verrors.add(f'nfs_update.bindip.{i}', 'Please provide a valid ip address')

        if new["v4"] and new_v4_krb_enabled and await self.middleware.call('activedirectory.get_state') != "DISABLED":
            """
            In environments with kerberized NFSv4 enabled, we need to tell winbindd to not prefix
            usernames with the short form of the AD domain. Directly update the db and regenerate
            the smb.conf to avoid having a service disruption due to restarting the samba server.
            """
            if await self.middleware.call('smb.get_smb_ha_mode') == 'LEGACY':
                raise ValidationError(
                    'nfs_update.v4',
                    'Enabling kerberos authentication on TrueNAS HA requires '
                    'the system dataset to be located on a data pool.'
                )
            ad = await self.middleware.call('activedirectory.config')
            await self.middleware.call(
                'datastore.update',
                'directoryservice.activedirectory',
                ad['id'],
                {'ad_use_default_domain': True}
            )
            await self.middleware.call('etc.generate', 'smb')
            await self.middleware.call('service.reload', 'cifs')

        if not new["v4"] and new["v4_v3owner"]:
            verrors.add("nfs_update.v4_v3owner", "This option requires enabling NFSv4")

        if new["v4_v3owner"] and new["userd_manage_gids"]:
            verrors.add(
                "nfs_update.userd_manage_gids", "This option is incompatible with NFSv3 ownership model for NFSv4")

        if not new["v4"] and new["v4_domain"]:
            verrors.add("nfs_update.v4_domain", "This option does not apply to NFSv3")

        if verrors:
            raise verrors

        await self.nfs_compress(new)

        await self._update_service(old, new)

        return await self.config()


class NFSShareModel(sa.Model):
    __tablename__ = 'sharing_nfs_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_paths = sa.Column(sa.JSON(type=list))
    nfs_aliases = sa.Column(sa.JSON(type=list))
    nfs_comment = sa.Column(sa.String(120))
    nfs_network = sa.Column(sa.Text())
    nfs_hosts = sa.Column(sa.Text())
    nfs_alldirs = sa.Column(sa.Boolean(), default=False)
    nfs_ro = sa.Column(sa.Boolean(), default=False)
    nfs_quiet = sa.Column(sa.Boolean(), default=False)
    nfs_maproot_user = sa.Column(sa.String(120), nullable=True, default='')
    nfs_maproot_group = sa.Column(sa.String(120), nullable=True, default='')
    nfs_mapall_user = sa.Column(sa.String(120), nullable=True, default='')
    nfs_mapall_group = sa.Column(sa.String(120), nullable=True, default='')
    nfs_security = sa.Column(sa.MultiSelectField())
    nfs_enabled = sa.Column(sa.Boolean(), default=True)


class SharingNFSService(SharingService):

    path_field = 'paths'
    share_task_type = 'NFS'

    class Config:
        namespace = "sharing.nfs"
        datastore = "sharing.nfs_share"
        datastore_prefix = "nfs_"
        datastore_extend = "sharing.nfs.extend"
        cli_namespace = "sharing.nfs"

    ENTRY = Patch(
        'sharingnfs_create', 'sharing_nfs_entry',
        ('add', Int('id')),
        ('add', Bool('locked')),
        register=True,
    )

    async def human_identifier(self, share_task):
        return ', '.join(share_task[self.path_field])

    @private
    async def sharing_task_datasets(self, data):
        return [os.path.relpath(path, '/mnt') for path in data[self.path_field]]

    @private
    async def sharing_task_determine_locked(self, data, locked_datasets):
        for path in data[self.path_field]:
            if await self.middleware.call('pool.dataset.path_in_locked_datasets', path, locked_datasets):
                return True
        else:
            return False

    @accepts(Dict(
        "sharingnfs_create",
        List("paths", items=[Dir("path")], empty=False),
        List("aliases", items=[Str("path", validators=[Match(r"^/.*")])]),
        Str("comment", default=""),
        List("networks", items=[IPAddr("network", network=True)]),
        List("hosts", items=[Str("host")]),
        Bool("alldirs", default=False),
        Bool("ro", default=False),
        Bool("quiet", default=False),
        Str("maproot_user", required=False, default=None, null=True),
        Str("maproot_group", required=False, default=None, null=True),
        Str("mapall_user", required=False, default=None, null=True),
        Str("mapall_group", required=False, default=None, null=True),
        List(
            "security",
            items=[Str("provider", enum=["SYS", "KRB5", "KRB5I", "KRB5P"])],
        ),
        Bool("enabled", default=True),
        register=True,
        strict=True,
    ))
    async def do_create(self, data):
        """
        Create a NFS Share.

        `paths` is a list of valid paths which are configured to be shared on this share.

        `aliases` is a list of aliases for each path (or an empty list if aliases are not used).

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
        data["id"] = await self.middleware.call(
            "datastore.insert", self._config.datastore, data,
            {
                "prefix": self._config.datastore_prefix
            },
        )
        await self.extend(data)

        await self._service_change("nfs", "reload")

        return await self.get_instance(data["id"])

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
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.validate(new, "sharingnfs_update", verrors, old=old)

        if verrors:
            raise verrors

        await self.compress(new)
        await self.middleware.call(
            "datastore.update", self._config.datastore, id, new,
            {
                "prefix": self._config.datastore_prefix
            }
        )

        await self._service_change("nfs", "reload")

        return await self.get_instance(id)

    @returns()
    async def do_delete(self, id):
        """
        Delete NFS Share of `id`.
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)
        await self._service_change("nfs", "reload")

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        if len(data["aliases"]):
            if not osc.IS_LINUX:
                verrors.add(
                    f"{schema_name}.aliases",
                    "This field is only supported on SCALE",
                )

            if len(data["aliases"]) != len(data["paths"]):
                verrors.add(
                    f"{schema_name}.aliases",
                    "This field should be either empty of have the same number of elements as paths",
                )

        if data["alldirs"] and len(data["paths"]) > 1:
            verrors.add(f"{schema_name}.alldirs", "This option can only be used for shares that contain single path")

        # if any of the `paths` that were passed to us by user are within the gluster volume
        # mountpoint then we need to pass the `gluster_bypass` kwarg so that we don't raise a
        # validation error complaining about using a gluster path within the zpool mountpoint
        bypass = any('.glusterfs' in i for i in data["paths"] + data["aliases"])

        # need to make sure that the nfs share is within the zpool mountpoint
        for idx, i in enumerate(data["paths"]):
            await check_path_resides_within_volume(
                verrors, self.middleware, f'{schema_name}.paths.{idx}', i, gluster_bypass=bypass
            )

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
                user = group = None
                with contextlib.suppress(KeyError):
                    user = await self.middleware.call('dscache.get_uncached_user', data[f'{k}_user'])

                if not user:
                    verrors.add(f"{schema_name}.{k}_user", "User not found")

                if data[f'{k}_group']:
                    with contextlib.suppress(KeyError):
                        group = await self.middleware.call('dscache.get_uncached_group', data[f'{k}_group'])

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
        if osc.IS_LINUX:
            # Ganesha does not have such a restriction, each path is a different share
            return

        dev = None
        for i, path in enumerate(data["paths"]):
            stat = os.stat(path)
            if dev is None:
                dev = stat.st_dev
            else:
                if dev != stat.st_dev:
                    verrors.add(
                        f'{schema_name}.paths.{i}',
                        'Paths for a NFS share must reside within the same filesystem'
                    )

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

        for host in set(data["hosts"]):
            host = dns_cache[host]
            if host is None:
                continue

            network = ipaddress.ip_network(host)
            if network in used_networks:
                verrors.add(
                    f"{schema_name}.hosts",
                    f"Another NFS share already exports this dataset for {host}"
                )

            used_networks.add(network)

        for network in set(data["networks"]):
            network = ipaddress.ip_network(network, strict=False)

            if network in used_networks:
                verrors.add(
                    f"{schema_name}.networks",
                    f"Another NFS share already exports this dataset for {network}"
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
        data["networks"] = data.pop("network").split()
        data["hosts"] = data["hosts"].split()
        data["security"] = [s.upper() for s in data["security"]]
        return data

    @private
    async def compress(self, data):
        data["network"] = " ".join(data.pop("networks"))
        data["hosts"] = " ".join(data["hosts"])
        data["security"] = [s.lower() for s in data["security"]]
        data.pop(self.locked_field, None)
        return data


async def interface_post_sync(middleware):
    if osc.IS_FREEBSD:
        if not await middleware.call('cache.has_key', 'interfaces_are_set_up'):
            await middleware.call('cache.put', 'interfaces_are_set_up', True)
            if (await middleware.call('nfs.config'))['bindip']:
                await middleware.call('service.restart', 'nfs')


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload NFS if a pool is imported and there are shares configured for it.
    """
    if pool is None:
        asyncio.ensure_future(middleware.call('etc.generate', 'nfsd'))
        return

    path = f'/mnt/{pool["name"]}'
    for share in await middleware.call('sharing.nfs.query'):
        if any(filter(lambda x: x == path or x.startswith(f'{path}/'), share['paths'])):
            asyncio.ensure_future(middleware.call('service.reload', 'nfs'))
            break


class NFSFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'nfs'
    title = 'NFS Share'
    service = 'nfs'
    service_class = SharingNFSService

    async def is_child_of_path(self, resource, path):
        return any(is_child(nfs_path, path) for nfs_path in resource[self.path_field])

    async def get_attachment_name(self, attachment):
        return ', '.join(attachment['paths'])

    async def restart_reload_services(self, attachments):
        await self._service_change('nfs', 'reload')


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenMultipleDelegate(middleware, 'nfs', 'bindip'),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', NFSFSAttachmentDelegate(middleware))

    middleware.register_hook('interface.post_sync', interface_post_sync)
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
