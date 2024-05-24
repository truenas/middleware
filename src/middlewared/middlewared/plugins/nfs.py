import enum
import errno
import ipaddress
import itertools
import os
import pathlib
import shutil

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.schema import accepts, Bool, Dict, Dir, Int, IPAddr, List, Patch, returns, Str
from middlewared.async_validators import check_path_resides_within_volume, validate_port
from middlewared.validators import Match, NotMatch, Range, IpAddress
from middlewared.service import private, SharingService, SystemServiceService
from middlewared.service import CallError, ValidationError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.plugins.nfs_.utils import get_domain, leftmost_has_wildcards, get_wildcard_domain
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH


class NFSServicePathInfo(enum.Enum):
    # nfs conf sections that use STATEDIR: exportd, mountd, statd
    STATEDIR = (os.path.join(SYSDATASET_PATH, 'nfs'), 0o755, True, {'uid': 0, 'gid': 0})
    CLDDIR = (os.path.join(SYSDATASET_PATH, 'nfs', 'nfsdcld'), 0o700, True, {'uid': 0, 'gid': 0})
    CLDTRKDIR = (os.path.join(SYSDATASET_PATH, 'nfs', 'nfsdcltrack'), 0o700, True, {'uid': 0, 'gid': 0})
    # Fix up the uid and gid in setup_directories
    SMDIR = (os.path.join(SYSDATASET_PATH, 'nfs', 'sm'), 0o755, True, {'uid': 'statd', 'gid': 'nogroup'})
    SMBAKDIR = (os.path.join(SYSDATASET_PATH, 'nfs', 'sm.bak'), 0o755, True, {'uid': 'statd', 'gid': 'nogroup'})
    V4RECOVERYDIR = (os.path.join(SYSDATASET_PATH, 'nfs', 'v4recovery'), 0o755, True, {'uid': 0, 'gid': 0})

    def path(self):
        return self.value[0]

    def mode(self):
        return self.value[1]

    def is_dir(self):
        return self.value[2]

    def owner(self):
        return self.value[3]


class NFSProtocol(str, enum.Enum):
    NFSv3 = 'NFSV3'
    NFSv4 = 'NFSV4'

    def choices():
        return [x.value for x in NFSProtocol]


class NFSModel(sa.Model):
    __tablename__ = 'services_nfs'

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_srv_servers = sa.Column(sa.Integer(), nullable=True)
    nfs_srv_allow_nonroot = sa.Column(sa.Boolean(), default=False)
    nfs_srv_protocols = sa.Column(sa.JSON(list), default=[NFSProtocol.NFSv3, NFSProtocol.NFSv4])
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
    nfs_srv_v4_owner_major = sa.Column(sa.String(1023), default='')


class NFSService(SystemServiceService):

    class Config:
        service = "nfs"
        service_verb = "restart"
        datastore = "services.nfs"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'
        cli_namespace = "service.nfs"
        role_prefix = "SHARING_NFS"

    ENTRY = Dict(
        'nfs_entry',
        Int('id', required=True),
        Int('servers', null=True, validators=[Range(min_=1, max_=256)], required=True),
        Bool('allow_nonroot', required=True),
        List('protocols', items=[Str('protocol', enum=NFSProtocol.choices())], required=True),
        Bool('v4_v3owner', required=True),
        Bool('v4_krb', required=True),
        Str('v4_domain', required=True),
        List('bindip', items=[IPAddr('ip')], required=True),
        Int('mountd_port', null=True, validators=[Range(min_=1, max_=65535)], required=True),
        Int('rpcstatd_port', null=True, validators=[Range(min_=1, max_=65535)], required=True),
        Int('rpclockd_port', null=True, validators=[Range(min_=1, max_=65535)], required=True),
        Bool('mountd_log', required=True),
        Bool('statd_lockd_log', required=True),
        Bool('v4_krb_enabled', required=True),
        Bool('userd_manage_gids', required=True),
        Bool('keytab_has_nfs_spn', required=True),
        Bool('managed_nfsd', default=True),
    )

    @private
    def name_to_id_conversion(self, name, name_type='user'):
        ''' Convert built-in user or group name to associated UID or GID '''
        if any((not isinstance(name, str), isinstance(name, int))):
            # it's not a string (NoneType, float, w/e) or it's an int
            # so there is nothing to do
            return name

        if name_type == 'user':
            method = 'user.get_builtin_user_id'
        elif name_type == 'group':
            method = 'group.get_builtin_group_id'
        else:
            self.logger.error('Unexpected name_type (%r)', name_type)
            return name
        try:
            return self.middleware.call_sync(method, name)
        except Exception as e:
            if hasattr(e, 'errno') and e.errno == errno.ENOENT:
                self.logger.error('Failed to resolve builtin %s %r', name_type, name)
            else:
                self.logger.error('Unexpected error resolving builtin %s %r', name_type, name, exc_info=True)
            return name

    @private
    def setup_directories(self):
        '''
        We are moving the NFS state directory from /var/lib/nfs to
        the system dataset: /var/db/system/nfs.
        When setup_directories is called /var/db/system/nfs is expected to exist.

        If STATEDIR is empty, then this might be an initialization
        and there might be current info in /var/lib/nfs.

        We always make sure the expected directories are present
        '''

        # Initialize the system dataset NFS state directory
        state_dir = NFSServicePathInfo.STATEDIR.path()
        try:
            shutil.copytree('/var/lib/nfs', state_dir)
        except FileExistsError:
            # destination file/dir already exists so ignore error
            pass
        except Exception:
            self.logger.error('Unexpected error initializing %r', state_dir, exc_info=True)

        # Make sure we have the necessary directories
        for i in NFSServicePathInfo:
            uid = self.name_to_id_conversion(i.owner()['uid'], name_type='user')
            gid = self.name_to_id_conversion(i.owner()['gid'], name_type='group')
            path = i.path()
            if i.is_dir():
                os.makedirs(path, exist_ok=True)

            try:
                os.chmod(path, i.mode())
                os.chown(path, uid, gid)
            except Exception:
                self.logger.error('Unexpected failure initializing %r', path, exc_info=True)

        procfs_path = '/proc/fs/nfsd/nfsv4recoverydir'
        try:
            with open(procfs_path, 'r+') as fp:
                fp.write(f'{NFSServicePathInfo.V4RECOVERYDIR.path()}\n')
        except FileNotFoundError:
            # When this is removed from the kernel we will have a gentle reminder
            self.logger.info("%r: Proc file has been removed", procfs_path)
        except Exception:
            self.logger.error("Unexpected failure updating %r", procfs_path, exc_info=True)

    @private
    async def nfs_extend(self, nfs):
        keytab_has_nfs = await self.middleware.call("kerberos.keytab.has_nfs_principal")
        nfs["v4_krb_enabled"] = (nfs["v4_krb"] or keytab_has_nfs)
        nfs["userd_manage_gids"] = nfs.pop("16")
        nfs["v4_owner_major"] = nfs.pop("v4_owner_major")
        nfs["keytab_has_nfs_spn"] = keytab_has_nfs

        # 'None' indicates we are to dynamically manage the number of nfsd
        if nfs['servers'] is None:
            nfs['managed_nfsd'] = True
            cpu_info = await self.middleware.call("system.cpu_info")

            # Default calculation:
            #     Number of nfsd == number of cores, but not zero or greater than 32
            nfs['servers'] = min(max(cpu_info['core_count'], 1), 32)
        else:
            nfs['managed_nfsd'] = False

        return nfs

    @private
    async def nfs_compress(self, nfs):
        nfs.pop('managed_nfsd')
        nfs.pop("v4_krb_enabled")
        nfs.pop("keytab_has_nfs_spn")
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

    @accepts(
        Patch(
            'nfs_entry', 'nfs_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'v4_krb_enabled'}),
            ('rm', {'name': 'keytab_has_nfs_spn'}),
            ('rm', {'name': 'managed_nfsd'}),
            ('attr', {'update': True}),
        ),
        audit='Update NFS configuration',
    )
    async def do_update(self, data):
        """
        Update NFS Service Configuration.

        `servers` - Represents number of servers to create.
                    By default, the number of nfsd is determined by the capabilities of the system.
                    To specify the number of nfsd, set a value between 1 and 256.
                    'Unset' the field to return to default.
                    This field will always report the number of nfsd to start.

                    INPUT: 1 .. 256 or 'unset'
                        where unset will enable the automatic determination
                        and 1 ..256 will set the number of nfsd
                    Default: Number of nfsd is automatically determined and will be no less
                        than 1 and no more than 32

                    The number of mountd will be 1/4 the number of reported nfsd.

        `allow_nonroot` - If 'enabled' it allows non-root mount requests to be served.

                        INPUT: enable/disable (True/False)
                        Default: disabled

        `bindip` -  Limit the server IP addresses available for NFS
                    By default, NFS will listen on all IP addresses that are active on the server.
                    To specify the server interface or a set of interfaces provide a list of IP's.
                    If the field is unset/empty, NFS listens on all available server addresses.

                    INPUT: list of IP addresses available configured on the server
                    Default: Use all available addresses (empty list)

        `protocols` - enable/disable NFSv3, NFSv4
                    Both can be enabled or NFSv4 or NFSv4 by themselves.  At least one must be enabled.
                    Note:  The 'showmount' command is available only if NFSv3 is enabled.

                    INPUT: Select NFSv3 or NFSv4 or NFSv3,NFSv4
                    Default: NFSv3,NFSv4

        `v4_v3owner` - when set means that system will use NFSv3 ownership model for NFSv4.
                    (Deprecated)

        `v4_krb` -  Force Kerberos authentication on NFS shares
                    If enabled, NFS shares will fail if the Kerberos ticket is unavilable

                    INPUT: enable/disable
                    Default: disabled

        `v4_domain` -   Specify a DNS domain (NFSv4 only)
                    If set, the value will be used to override the default DNS domain name for NFSv4.
                    Specifies the 'Domain' idmapd.conf setting.

                    INPUT: a string
                    Default: unset, i.e. an empty string.

        `mountd_port` - mountd port binding
                    The value set specifies the port mountd(8) binds to.

                    INPUT: unset or an integer between 1 .. 65535
                    Default: unset

        `rpcstatd_port` - statd port binding
                    The value set specifies the port rpc.statd(8) binds to.

                    INPUT: unset or an integer between 1 .. 65535
                    Default: unset

        `rpclockd_port` - lockd port binding
                    The value set specifies the port rpclockd_port(8) binds to.

                    INPUT: unset or an integer between 1 .. 65535
                    Default: unset

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
                    "protocols": ["NFSV3", "NFSV4"]
                }]
            }
        """
        if 'protocols' in data:
            if not data['protocols']:
                raise ValidationError(
                    'nfs_update.protocols',
                    'Must specify at least one value ("NFSV3", "NFSV4") in the "protocols" list.'
                )
            if NFSProtocol.NFSv4 not in data.get("protocols"):
                data.setdefault("v4_v3owner", False)

        old = await self.config()

        # Fixup old 'servers' entry before processing changes
        if old['managed_nfsd']:
            old['servers'] = None

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        keytab_has_nfs = await self.middleware.call("kerberos.keytab.has_nfs_principal")
        new_v4_krb_enabled = new["v4_krb"] or keytab_has_nfs

        for k in ['mountd_port', 'rpcstatd_port', 'rpclockd_port']:
            for bindip in (new['bindip'] or ['0.0.0.0']):
                verrors.extend(await validate_port(self.middleware, f'nfs_update.{k}', new[k], 'nfs', bindip))

        if await self.middleware.call("failover.licensed") and NFSProtocol.NFSv4 in new["protocols"] and new_v4_krb_enabled:
            gc = await self.middleware.call("datastore.config", "network.globalconfiguration")
            if not gc["gc_hostname_virtual"] or not gc["gc_domain"]:
                verrors.add(
                    "nfs_update.v4",
                    "Enabling kerberos authentication on TrueNAS HA requires setting the virtual hostname and "
                    "domain"
                )

        bindip_choices = await self.bindip_choices()
        for i, bindip in enumerate(new['bindip']):
            if bindip not in bindip_choices:
                verrors.add(f'nfs_update.bindip.{i}', 'Please provide a valid ip address')

        if NFSProtocol.NFSv4 not in new["protocols"] and new["v4_v3owner"]:
            verrors.add("nfs_update.v4_v3owner", "This option requires enabling NFSv4")

        if new["v4_v3owner"] and new["userd_manage_gids"]:
            verrors.add(
                "nfs_update.userd_manage_gids", "This option is incompatible with NFSv3 ownership model for NFSv4")

        if NFSProtocol.NFSv4 not in new["protocols"] and new["v4_domain"]:
            verrors.add("nfs_update.v4_domain", "This option does not apply to NFSv3")

        verrors.check()

        await self.nfs_compress(new)

        await self._update_service(old, new, "restart")

        if old['mountd_log'] != new['mountd_log']:
            await self.middleware.call('service.reload', 'syslogd')

        return await self.config()


class NFSShareModel(sa.Model):
    __tablename__ = 'sharing_nfs_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_path = sa.Column(sa.Text())
    nfs_aliases = sa.Column(sa.JSON(list))
    nfs_comment = sa.Column(sa.String(120))
    nfs_network = sa.Column(sa.Text())
    nfs_hosts = sa.Column(sa.Text())
    nfs_ro = sa.Column(sa.Boolean(), default=False)
    nfs_maproot_user = sa.Column(sa.String(120), nullable=True, default='')
    nfs_maproot_group = sa.Column(sa.String(120), nullable=True, default='')
    nfs_mapall_user = sa.Column(sa.String(120), nullable=True, default='')
    nfs_mapall_group = sa.Column(sa.String(120), nullable=True, default='')
    nfs_security = sa.Column(sa.MultiSelectField())
    nfs_enabled = sa.Column(sa.Boolean(), default=True)


class SharingNFSService(SharingService):

    share_task_type = 'NFS'

    class Config:
        namespace = "sharing.nfs"
        datastore = "sharing.nfs_share"
        datastore_prefix = "nfs_"
        datastore_extend = "sharing.nfs.extend"
        cli_namespace = "sharing.nfs"
        role_prefix = "SHARING_NFS"

    ENTRY = Patch(
        'sharingnfs_create', 'sharing_nfs_entry',
        ('add', Int('id')),
        ('add', Bool('locked')),
        register=True,
    )

    @accepts(
        Dict(
            "sharingnfs_create",
            Dir("path", required=True),
            List("aliases", items=[Str("path", validators=[Match(r"^/.*")])]),
            Str("comment", default=""),
            List("networks", items=[IPAddr("network", network=True)], unique=True),
            List(
                "hosts", items=[Str("host", validators=[NotMatch(
                    r'.*[\s"]', explanation='Name cannot contain spaces or quotes')]
                )],
                unique=True
            ),
            Bool("ro", default=False),
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
        ),
        audit='NFS share create', audit_extended=lambda data: data["path"]
    )
    async def do_create(self, data):
        """
        Create a NFS Share.

        `path` local path to be exported.

        `aliases` IGNORED, for now.

        `networks` is a list of authorized networks that are allowed to access the share having format
        "network/mask" CIDR notation. If empty, all networks are allowed.

        `hosts` is a list of IP's/hostnames which are allowed to access the share. If empty, all IP's/hostnames are
        allowed.

        """
        verrors = ValidationErrors()

        await self.validate(data, "sharingnfs_create", verrors)

        verrors.check()

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
        ),
        audit='NFS share update',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update NFS Share of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id_)
        audit_callback(old['path'])

        new = old.copy()
        new.update(data)

        await self.validate(new, "sharingnfs_update", verrors, old=old)

        verrors.check()

        await self.compress(new)
        await self.middleware.call(
            "datastore.update", self._config.datastore, id_, new,
            {
                "prefix": self._config.datastore_prefix
            }
        )

        await self._service_change("nfs", "reload")

        return await self.get_instance(id_)

    @accepts(
        Int("id"),
        audit='NFS share delete',
        audit_callback=True,
    )
    @returns()
    async def do_delete(self, audit_callback, id_):
        """
        Delete NFS Share of `id`.
        """
        nfs_share = await self.get_instance(id_)
        audit_callback(nfs_share['path'])
        await self.middleware.call("datastore.delete", self._config.datastore, id_)
        await self._service_change("nfs", "reload")

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        if len(data["aliases"]):
            data['aliases'] = []
            # This feature was originally intended to be provided by nfs-ganesha
            # since we no longer have ganesha, planning will need to be made about
            # how to implement for kernel NFS server. One candidate is using bind mounts,
            # but this will require careful design and testing. For now we will keep it disabled.
            """
            if len(data["aliases"]) != len(data["paths"]):
                verrors.add(
                    f"{schema_name}.aliases",
                    "This field should be either empty of have the same number of elements as paths",
                )
            """

        # need to make sure that the nfs share is within the zpool mountpoint
        await check_path_resides_within_volume(
            verrors, self.middleware, f'{schema_name}.path', data['path'],
        )

        filters = []
        if old:
            filters.append(["id", "!=", old["id"]])
        other_shares = await self.middleware.call(
            "sharing.nfs.query", filters, {"extra": {"retrieve_locked_info": False}}
        )

        dns_cache = await self.resolve_hostnames(
            sum([share["hosts"] for share in other_shares], []) + data['hosts']
        )

        self.validate_share_networks_input(data['networks'], dns_cache, schema_name, verrors)
        # Stop here if the input generated errors for the user to fix
        verrors.check()

        await self.validate_hosts_and_networks(
            other_shares, data, schema_name, verrors, dns_cache
        )
        # Stop here if the input generated errors for the user to fix
        verrors.check()

        # Confirm the share will not collide with an existing share
        await self.validate_share_path(other_shares, data, schema_name, verrors)
        # Stop here if the input generated errors for the user to fix
        verrors.check()

        for k in ["maproot", "mapall"]:
            map_user = data[f"{k}_user"]
            map_group = data[f"{k}_group"]
            if not map_user and not map_group:
                pass
            elif not map_user and map_group:
                verrors.add(f"{schema_name}.{k}_user", "This field is required when map group is specified")
            else:
                try:
                    await self.middleware.call('user.get_user_obj', {'username': map_user})
                except KeyError:
                    verrors.add(f"{schema_name}.{k}_user", f"User not found: {map_user}")

                if map_group:
                    try:
                        await self.middleware.call('group.get_group_obj', {'groupname': map_group})
                    except KeyError:
                        verrors.add(f"{schema_name}.{k}_group", f"Group not found: {map_group}")

        if data["maproot_user"] and data["mapall_user"]:
            verrors.add(f"{schema_name}.mapall_user", "maproot_user disqualifies mapall_user")

        v4_sec = list(filter(lambda sec: sec != "SYS", data.get("security", [])))
        if v4_sec:
            nfs_config = await self.middleware.call("nfs.config")
            if NFSProtocol.NFSv4 not in nfs_config["protocols"]:
                verrors.add(
                    f"{schema_name}.security",
                    f"The following security flavor(s) require NFSv4 to be enabled: {','.join(v4_sec)}."
                )

    @private
    def validate_share_networks_input(self, networks, dns_cache, schema_name, verrors):
        """
        The network field is strictly limited to CIDR formats:
        The input validator should enforce the CIDR format and a single address per entry.
        This validation is limited to:
            * Collisions with resolved hostnames
            * Overlapping subnets.
        NOTE: hosts input should be processed and resolved first
        """
        dns_cache_values = list(dns_cache.values())
        for IPaddr in networks:
            IPinterface = ipaddress.ip_interface(IPaddr)

            if str(IPinterface.ip) in dns_cache_values:
                key = next(key for key, value in dns_cache.items() if value == str(IPinterface.ip))
                verrors.add(
                    f"{schema_name}.networks",
                    f"ERROR - Resolved hostname to duplicate address: host '{key}' resolves to '{IPaddr}'"
                )

        overlaps = self.test_for_overlapped_networks(networks)
        if overlaps:
            verrors.add(
                f"{schema_name}.networks",
                f"ERROR - Overlapped subnets: {overlaps}"
            )

    @private
    def test_for_overlapped_networks(self, networks, this_network=None):
        """
        INPUT: networks         a list of ip_networks
               this_network     optional ip_network to test against networks

        if this_network is None, then check networks list for overlaps
        else check this_network for overlaps with entries in networks
        We set strict to False to allow entries like: 1.2.3.4/24
        """
        overlaps = []
        if this_network is not None:
            this_network = ipaddress.ip_network(this_network, strict=False)
            for that_network in networks:
                that_network = ipaddress.ip_network(that_network, strict=False)
                if this_network.overlaps(that_network):
                    overlaps.append((this_network, that_network))
        else:
            for n1, n2 in itertools.combinations(networks, 2):
                # Check for overlapped networks
                ipn1 = ipaddress.ip_network(n1, strict=False)
                ipn2 = ipaddress.ip_network(n2, strict=False)
                if ipn1.overlaps(ipn2):
                    overlaps.append((n1, n2))

        return overlaps if overlaps else None

    @private
    async def resolve_hostnames(self, hostnames):
        hostnames = list(set(hostnames))

        async def resolve(hostname):
            try:
                try:
                    # If this is an IP address, just return it
                    ip = IpAddress()
                    ip(hostname)
                    return hostname
                except ValueError:
                    # Not an IP address, should be a name
                    if domain := get_wildcard_domain(hostname):
                        hostname = domain

                    if leftmost_has_wildcards(hostname):
                        # We know this will not resolve
                        return None
                    else:
                        try:
                            dns_addresses = [x['address'] for x in await self.middleware.call('dnsclient.forward_lookup', {
                                'names': [hostname]
                            })]
                            # We might get both IPv4 and IPv6 addresses, the caller expects a single response
                            return dns_addresses[0]
                        except Exception as e:
                            self.logger.warning("Unable to resolve host %r: %r", hostname, e)
                            return None
            except Exception as e:
                self.logger.warning("Unable to resolve or invalid host %r: %r", hostname, e)
                return None

        resolved_hostnames = await asyncio_map(resolve, hostnames, 8)

        return dict(zip(hostnames, resolved_hostnames))

    @private
    async def validate_hosts_and_networks(self, other_shares, data, schema_name, verrors, dns_cache):
        """
        We attempt to prevent share situation where the same host is provided access to a
        share but with potentially different permissions.
        This module does checks that encompass both hosts and networks.
        """
        # Sharing to 'everybody' obviates other host or network settings for a path
        # if '*' in hosts and (len(set(hosts)) > 1 or len(set(networks)) > 0):
        if ('*' in data['hosts'] and (len(set(data['hosts'])) > 1 or len(set(data['networks'])) > 0)):
            verrors.add(
                f"{schema_name}.hosts",
                "ERROR - '*', i.e. 'everybody', cannot be included with other entries on same share path"
            )

        tgt_realpath = (await self.middleware.call('filesystem.stat', data['path']))['realpath']

        used_networks = set()
        used_hosts = set()  # host names without an entry in the cache
        for share in other_shares:
            try:
                shr_realpath = (await self.middleware.call('filesystem.stat', share['path']))['realpath']
            except CallError as e:
                if e.errno != errno.ENOENT:
                    raise
                # Allow for locked filesystems
                shr_realpath = share['path']

            if tgt_realpath == shr_realpath:
                for host in share["hosts"]:
                    host_ip = dns_cache.get(host)
                    if host_ip is None:
                        used_hosts.add(host)
                        continue

                    if host.startswith('@'):
                        continue

                    try:
                        network = ipaddress.ip_network(host_ip, strict=False)
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

        for network in set(data["networks"]):
            network = ipaddress.ip_network(network, strict=False)

            # Look for exact match.  This also works for IPv6
            if network in used_networks:
                verrors.add(
                    f"{schema_name}.networks",
                    f"ERROR - Another NFS share exports {data['path']} for {network}"
                )

            # Look for subnet or supernet overlaps
            # Works for IPv4 and IPv6, but ignores mixed tests
            overlaps = self.test_for_overlapped_networks(used_networks, network)
            if overlaps:
                # Each overlap entry is a tuple:  'this' is overlapped by 'that'
                # There may well be more than one entry, but it's more clear to present only one.
                verrors.add(
                    f"{schema_name}.networks",
                    f"ERROR - This or another NFS share exports {data['path']} to {str(overlaps[0][1])} "
                    f"and overlaps {network}"
                )

            used_networks.add(network)

        for host in set(data["hosts"]):
            # check for duplicate 'hosts' in other shares
            # netgroups are valid, but limited to same duplicate restrictions
            if host in used_hosts:
                verrors.add(
                    f"{schema_name}.hosts",
                    f"ERROR - Another NFS share already exports {data['path']} for {str(host)}"
                )
                continue

            if host.startswith('@'):
                continue

            # wildcarded names without a 'domain' are valid
            if leftmost_has_wildcards(host) and get_domain(host) is None:
                continue

            # Everything else should be resolvable
            host_ip = dns_cache[host]
            if host_ip is None:
                verrors.add(
                    f"{schema_name}.hosts",
                    f"Unable to resolve host '{host}'"
                )
                continue

            # Nothing more to check with wildcard names
            if leftmost_has_wildcards(host):
                continue

            overlaps = self.test_for_overlapped_networks(used_networks, host_ip)
            if overlaps:
                verrors.add(
                    f"{schema_name}.hosts",
                    f"ERROR - This or another NFS share exports {data['path']} to {str(overlaps[0][1])} "
                    f"and overlaps host {host} (host IP: {host_ip})"
                )

            used_networks.add(ipaddress.ip_network(host_ip, strict=False))

    @private
    async def validate_share_path(self, other_shares, data, schema_name, verrors):
        """
        A share path centric test. Checks new share path against existing.
        There are multiple ways to get duplicate entries for a given share path
        1) A share path could be set for everyone and another host entries only, e.g.
            /mnt/tank/dataset 192.168.1.1(rw)
            /mnt/tank/dataset *(ro)
        2) A host could be part of a network subnet, e.g.
            /mnt/tank/dataset 192.168.1.1(rw)
            /mnt/tank/dataset 192.168.1.0/24(ro)
            Note: The 192.168.1.0/24 is a 'networks' specification
        This function checks for common conditions.
        """
        # We test other shares that are sharing the same path
        tgt_stat = await self.middleware.call('filesystem.stat', data["path"])

        # Sanity check: no symlinks
        if tgt_stat['type'] == "SYMLINK":
            verrors.add(
                f"{schema_name}.path",
                f"Symbolic links are not allowed: {data['path']}."
            )

        tgt_realpath = tgt_stat['realpath']

        for share in other_shares:
            try:
                shr_realpath = (await self.middleware.call('filesystem.stat', share['path']))['realpath']
            except CallError as e:
                if e.errno != errno.ENOENT:
                    raise
                # Allow for locked filesystems
                shr_realpath = share['path']

            if tgt_realpath == shr_realpath:
                # Test hosts
                # An empty 'hosts' list == '*' == 'everybody.  Workaround: remove '*' as a host entry
                datahosts = [host for host in data["hosts"] if host != "*"]
                sharehosts = [host for host in share["hosts"] if host != "*"]

                commonHosts = set(datahosts) & set(sharehosts)
                commonNetworks = set(data["networks"]) & set(share["networks"])
                other_share_everybody = not bool(set(sharehosts) | set(share['networks']))
                this_share_everybody = not bool(datahosts) and not bool(data['networks'])
                everybody = other_share_everybody or this_share_everybody

                if bool(commonHosts) | bool(commonNetworks) | everybody:
                    reason = "'everybody', i.e. '*'"
                    other_share_desc = "Another share with the same path"
                    this_share_desc = "This share is exported to everybody and another share"
                    if commonHosts:
                        desc = other_share_desc
                        reason = str(commonHosts)
                    elif commonNetworks:
                        desc = other_share_desc
                        reason = str(commonNetworks)
                    elif this_share_everybody and not other_share_everybody:
                        # Already trapped the 'everyone' exact match condition in the host check
                        desc = this_share_desc
                        all_hosts = set(datahosts) | set(sharehosts)
                        all_networks = set(data["networks"]) | set(share["networks"])

                        # 'everyone' does not play well with anyone
                        # Present which ever list has entries
                        if all_hosts:
                            # reason = f"{', '.join(sharehosts)}"
                            reason = f"{', '.join(all_hosts)}"
                        else:
                            reason = f"{', '.join(all_networks)}"
                    else:
                        desc = other_share_desc
                    verrors.add(
                        f"{schema_name}.path",
                        f"ERROR - Export conflict. {desc} exports {share['path']} for {reason}"
                    )
                    # Found an export of the same path to the same 'hosts'. Report it.
                    break

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


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload NFS if a pool is imported and there are shares configured for it.
    """
    if pool is None:
        middleware.create_task(middleware.call('etc.generate', 'nfsd'))
        return

    path = f'/mnt/{pool["name"]}'
    for share in await middleware.call('sharing.nfs.query', [], {'select': ['path']}):
        if share['path'].startswith(path):
            middleware.create_task(middleware.call('service.reload', 'nfs'))
            break


class NFSFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'nfs'
    title = 'NFS Share'
    service = 'nfs'
    service_class = SharingNFSService
    resource_name = 'path'

    async def restart_reload_services(self, attachments):
        await self._service_change('nfs', 'reload')


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenMultipleDelegate(middleware, 'nfs', 'bindip'),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', NFSFSAttachmentDelegate(middleware))

    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
