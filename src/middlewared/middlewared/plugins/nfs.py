import errno
import ipaddress
import itertools

from truenas_pylicensed.features import LicenseFeature

from middlewared.alert.source.nfs_host import NFSHostListExcessiveAlert, NFSNetworkListExcessiveAlert
from middlewared.api import api_method
from middlewared.api.current import (
    SharingNFSCreateArgs,
    SharingNFSCreateResult,
    SharingNFSDeleteArgs,
    SharingNFSDeleteResult,
    SharingNFSEntry,
    SharingNFSUpdateArgs,
    SharingNFSUpdateResult,
)
from middlewared.plugins.dns_client import DNSClientForwardLookupData
from middlewared.plugins.nfs_.utils import (
    NFSProtocol,
    get_domain,
    get_wildcard_domain,
    leftmost_has_wildcards,
)
from middlewared.plugins.nfs_.validators import confirm_unique, sanitize_hosts, sanitize_networks
from middlewared.service import (
    CallError,
    SharingService,
    ValidationErrors,
    private,
)
import middlewared.sqlalchemy as sa
from middlewared.utils.asyncio_ import asyncio_map


class NFSShareModel(sa.Model):
    __tablename__ = 'sharing_nfs_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_path = sa.Column(sa.Text())
    nfs_dataset = sa.Column(sa.String(255), nullable=True)
    nfs_relative_path = sa.Column(sa.String(255), nullable=True)
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
    nfs_expose_snapshots = sa.Column(sa.Boolean(), default=False)
    nfs_enabled = sa.Column(sa.Boolean(), default=True)


class SharingNFSService(SharingService):

    include_tier_info = True
    share_task_type = 'NFS'
    readonly_field = 'ro'

    @private
    async def human_identifier(self, share_task):
        return await self.get_path_field(share_task)

    class Config:
        namespace = "sharing.nfs"
        datastore = "sharing.nfs_share"
        datastore_prefix = "nfs_"
        datastore_extend = "sharing.nfs.extend"
        cli_namespace = "sharing.nfs"
        role_prefix = "SHARING_NFS"

        entry = SharingNFSEntry

    @api_method(
        SharingNFSCreateArgs, SharingNFSCreateResult,
        audit='NFS share create', audit_extended=lambda data: data["path"]
    )
    async def do_create(self, data):
        """
        Create a NFS Share.
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

    @api_method(
        SharingNFSUpdateArgs, SharingNFSUpdateResult,
        audit='NFS share update', audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update NFS Share of ``id``.
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

    @api_method(
        SharingNFSDeleteArgs, SharingNFSDeleteResult,
        audit='NFS share delete', audit_callback=True
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete NFS Share of ``id``.
        """
        nfs_share = await self.get_instance(id_)
        audit_callback(nfs_share['path'])
        res = await self.middleware.call("datastore.delete", self._config.datastore, id_)
        # Remove alerts that might be associated with this share
        await self.call2(
            self.s.alert.oneshot_delete, 'NFSNetworkListExcessive', {'sharePath': nfs_share['path']}
        )
        await self.call2(
            self.s.alert.oneshot_delete, 'NFSHostListExcessive', {'sharePath': nfs_share['path']}
        )
        await self._service_change("nfs", "reload")
        return res

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        """
        Perform advanced validation that does not get trapped by the schema checks
        * Path must reside within a user volume
        * Networks and users: Mostly follow overlap rules from exports man page.
            The order of precedence for match is:
                single host, IP networks, wildcards, netgroups, anonymous
            Rule from exports man page:
                If a client matches more than one of the specifications above, then
                the first match from the above list order takes precedence - regardless
                of the order they appear on the  export line. However, if a client matches
                more than one of the same type of specification (e.g. two netgroups), then
                the first match from the order they appear on the export line takes precedence.
            Notes:
            - Those rules apply to a 'single' entry in the exports.
            Our rules:
            - Host cannot be specified more than once for the same share.
            - Networks cannot overlap on the same share.
        """
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

        # Data validation and sanitization
        await self.sanitize_share_networks_and_hosts(data, schema_name, verrors)
        # User must clean these up before proceeding
        verrors.check()

        await self.validate_path_field(data, schema_name, verrors, split_path=True)

        filters = []
        if old:
            filters.append(["id", "!=", old["id"]])

        other_shares = await self.middleware.call(
            "sharing.nfs.query", filters, {"extra": {"retrieve_locked_info": False}}
        )

        dns_cache = await self.resolve_hostnames(
            sum([share["hosts"] for share in other_shares], []) + data['hosts']
        )

        self.validate_share_networks(data['networks'], dns_cache, schema_name, verrors)
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
            nfs_config = await self.call2(self.s.nfs.config)
            if NFSProtocol.NFSv4 not in nfs_config.protocols:
                verrors.add(
                    f"{schema_name}.security",
                    f"The following security flavor(s) require NFSv4 to be enabled: {','.join(v4_sec)}."
                )

        if data["expose_snapshots"]:
            entitlement = await self.call2(self.s.truenas.entitlements.check, LicenseFeature.NFS_SNAPSHOT)
            if entitlement.entitled:
                # check if mountpoint and whether snapdir is enabled
                try:
                    # We're using statfs output because in future it should expose
                    # whether snapdir is enabled
                    sfs = await self.middleware.call("filesystem.statfs", data["path"])
                    if sfs.dest != data["path"]:
                        verrors.add(
                            f"{schema_name}.expose_snapshots",
                            f"{data['path']}: export path is not the root directory of a dataset."
                        )
                except Exception:
                    # we can't get info on unmounted / locked datasets but this
                    # doesn't have to be perfect.
                    pass
            else:
                verrors.add(f"{schema_name}.expose_snapshots", entitlement.message)

    @private
    async def sanitize_share_networks_and_hosts(self, data, schema_name, verrors):
        """
        Perform input sanitation
            - Network and host must contain unique items.
            - Network must contain network types.
            - Host must not include quotes or spaces.
        """
        # Generate warning alert if a share host or network list is excessively long
        NFS_NETWORKS_WARNING_THRESHOLD = 100
        NFS_HOSTS_WARNING_THRESHOLD = 100

        # Flag non-unique items in hosts and networks
        confirm_unique(schema_name, 'networks', data, verrors)
        confirm_unique(schema_name, 'hosts', data, verrors)

        # Validate networks and sanitize: Convert IP addresses CIDR format
        data['networks'] = sanitize_networks(schema_name, data['networks'], verrors)

        # Register a warning level alert for excessively long list of network entries
        if (netlen := len(data['networks'])) >= NFS_NETWORKS_WARNING_THRESHOLD:
            await self.call2(
                self.s.alert.oneshot_create, NFSNetworkListExcessiveAlert(sharePath=data['path'], numEntries=netlen)
            )
        else:
            await self.call2(
                self.s.alert.oneshot_delete, 'NFSNetworkListExcessive', {'sharePath': data['path']}
            )

        # Validate hosts: no spaces or quotes
        sanitize_hosts(schema_name, data['hosts'], verrors)

        # Register a warning level alert for excessively long list of host entries
        if (hostlen := len(data['hosts'])) >= NFS_HOSTS_WARNING_THRESHOLD:
            await self.call2(
                self.s.alert.oneshot_create, NFSHostListExcessiveAlert(sharePath=data['path'], numEntries=hostlen)
            )
        else:
            await self.call2(
                self.s.alert.oneshot_delete, 'NFSHostListExcessive', {'sharePath': data['path']}
            )

    @private
    def validate_share_networks(self, networks, dns_cache, schema_name, verrors):
        """
        The network field is strictly limited to CIDR formats:
        The input validator should enforce the CIDR format and a single address per entry.
        This validation is limited to:
            * Collisions with resolved hostnames
            * Overlapping subnets
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
                    ipaddress.ip_address(hostname)
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
                            dns_addresses = [
                                x.address for x in await self.call2(
                                    self.s.dnsclient.forward_lookup, DNSClientForwardLookupData(names=[hostname]),
                                )
                            ]
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

        tgt_realpath = (await self.middleware.call('filesystem.stat', data['path'])).realpath

        used_networks = set()
        used_hosts = set()  # host names without an entry in the cache
        for share in other_shares:
            try:
                shr_realpath = (await self.middleware.call('filesystem.stat', share['path'])).realpath
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
                        used_hosts.add(str(network))

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
                    f"ERROR - Another NFS share already exports {data['path']} for network {network}"
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
                    f"and overlaps network {network}"
                )

            used_networks.add(network)

        for host in set(data["hosts"]):
            # check for duplicate 'hosts' in other shares
            # netgroups are valid, but limited to same duplicate restrictions
            if host in used_hosts:
                verrors.add(
                    f"{schema_name}.hosts",
                    f"ERROR - Another NFS share already exports {data['path']} for host {str(host)}"
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

    @private
    async def validate_share_path(self, other_shares, data, schema_name, verrors):
        """
        A share path centric test. Checks new share path against existing.
        This function checks for common conditions.
        """
        # We test other shares that are sharing the same path
        tgt_stat = await self.middleware.call('filesystem.stat', data["path"])

        # Sanity check: no symlinks
        if tgt_stat.type == "SYMLINK":
            verrors.add(
                f"{schema_name}.path",
                f"Symbolic links are not allowed: {data['path']}."
            )

        tgt_realpath = tgt_stat.realpath

        for share in other_shares:
            try:
                shr_realpath = (await self.middleware.call('filesystem.stat', share['path'])).realpath
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

                if bool(commonHosts) | bool(commonNetworks):
                    reason = "'everybody', i.e. '*'"
                    other_share_desc = "Another share with the same path"
                    if commonHosts:
                        desc = other_share_desc
                        reason = str(commonHosts)
                    else:
                        desc = other_share_desc
                        reason = str(commonNetworks)
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
        data.pop('tier', None)
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
            # No need to wait for this to complete
            await middleware.call2(middleware.services.service.control, 'RELOAD', 'nfs')
            break


async def setup(middleware):
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
