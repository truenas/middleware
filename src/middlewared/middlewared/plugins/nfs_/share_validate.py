from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from truenas_pylicensed.features import LicenseFeature

from middlewared.alert.source.nfs_host import NFSHostListExcessiveAlert, NFSNetworkListExcessiveAlert
from middlewared.api.current import QueryOptions, SharingNFSEntry
from middlewared.service import ValidationErrors

from .share_hosts import resolve_hostnames, share_realpath, validate_hosts_and_networks, validate_share_networks
from .utils import NFSProtocol
from .validators import confirm_unique, sanitize_hosts, sanitize_networks

if TYPE_CHECKING:
    from .share_crud import SharingNFSServicePart

NETWORKS_WARNING_THRESHOLD = 100
HOSTS_WARNING_THRESHOLD = 100


async def validate_nfs_share(
    part: SharingNFSServicePart,
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
    exclude_id: int | None = None,
) -> None:
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

    `exclude_id` is the share being updated, which must not be compared against itself.

    Sanitation and path resolution are applied to `data` in place, so the caller stores
    what this validated.
    """
    if data.aliases:
        # This feature was originally intended to be provided by nfs-ganesha. Since we no longer have
        # ganesha, planning will need to be made about how to implement for kernel NFS server. One
        # candidate is using bind mounts, but this will require careful design and testing. For now we
        # will keep it disabled.
        data.aliases = []

    # Data validation and sanitization
    await sanitize_share_networks_and_hosts(part, data, schema_name, verrors)
    # User must clean these up before proceeding
    verrors.check()

    await resolve_share_path(part, data, schema_name, verrors)

    filters: list[Any] = []
    if exclude_id is not None:
        filters.append(["id", "!=", exclude_id])

    other_shares = await part.query(filters, QueryOptions(extra={"retrieve_locked_info": False}))

    dns_cache = await resolve_hostnames(part, [host for share in other_shares for host in share.hosts] + data.hosts)

    validate_share_networks(data.networks, dns_cache, schema_name, verrors)
    # Stop here if the input generated errors for the user to fix
    verrors.check()

    await validate_hosts_and_networks(part, other_shares, data, schema_name, verrors, dns_cache)
    # Stop here if the input generated errors for the user to fix
    verrors.check()

    # Confirm the share will not collide with an existing share
    await validate_share_path(part, other_shares, data, schema_name, verrors)
    # Stop here if the input generated errors for the user to fix
    verrors.check()

    await validate_mappings(part, data, schema_name, verrors)

    await validate_security(part, data, schema_name, verrors)

    await validate_expose_snapshots(part, data, schema_name, verrors)


async def resolve_share_path(
    part: SharingNFSServicePart,
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    """Validate the exported path and record the dataset it resolved to."""
    path_data: dict[str, Any] = {"path": data.path, "ro": data.ro}
    await part.validate_path_field(path_data, schema_name, verrors, split_path=True)
    data.dataset = path_data.get("dataset")
    data.relative_path = path_data.get("relative_path")


async def sanitize_share_networks_and_hosts(
    part: SharingNFSServicePart,
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    """
    Perform input sanitation
        - Network and host must contain unique items.
        - Network must contain network types.
        - Host must not include quotes or spaces.

    An excessively long host or network list raises a warning level alert.
    """
    confirm_unique(schema_name, "networks", data.networks, verrors)
    confirm_unique(schema_name, "hosts", data.hosts, verrors)

    # Validate networks and sanitize: Convert IP addresses CIDR format
    data.networks = sanitize_networks(schema_name, data.networks, verrors)

    if (netlen := len(data.networks)) >= NETWORKS_WARNING_THRESHOLD:
        await part.call2(
            part.s.alert.oneshot_create, NFSNetworkListExcessiveAlert(sharePath=data.path, numEntries=netlen)
        )
    else:
        await part.call2(part.s.alert.oneshot_delete, "NFSNetworkListExcessive", {"sharePath": data.path})

    # Validate hosts: no spaces or quotes
    sanitize_hosts(schema_name, data.hosts, verrors)

    if (hostlen := len(data.hosts)) >= HOSTS_WARNING_THRESHOLD:
        await part.call2(
            part.s.alert.oneshot_create, NFSHostListExcessiveAlert(sharePath=data.path, numEntries=hostlen)
        )
    else:
        await part.call2(part.s.alert.oneshot_delete, "NFSHostListExcessive", {"sharePath": data.path})


async def validate_share_path(
    part: SharingNFSServicePart,
    other_shares: Sequence[SharingNFSEntry],
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    """
    A share path centric test. Checks new share path against existing.
    This function checks for common conditions.
    """
    tgt_stat = await part.middleware.call("filesystem.stat", data.path)

    if tgt_stat.type == "SYMLINK":
        verrors.add(f"{schema_name}.path", f"Symbolic links are not allowed: {data.path}.")

    tgt_realpath = tgt_stat.realpath

    for share in other_shares:
        if tgt_realpath != await share_realpath(part, share.path):
            continue

        # An empty 'hosts' list == '*' == 'everybody'. Workaround: remove '*' as a host entry
        common_hosts = {host for host in data.hosts if host != "*"} & {host for host in share.hosts if host != "*"}
        common_networks = set(data.networks) & set(share.networks)

        if not common_hosts and not common_networks:
            continue

        if common_hosts:
            reason = str(common_hosts)
        else:
            reason = str(common_networks)

        verrors.add(
            f"{schema_name}.path",
            f"ERROR - Export conflict. Another share with the same path exports {share.path} for {reason}",
        )
        # Found an export of the same path to the same 'hosts'. Report it.
        break


async def validate_mappings(
    part: SharingNFSServicePart,
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    for k in ("maproot", "mapall"):
        map_user = getattr(data, f"{k}_user")
        map_group = getattr(data, f"{k}_group")
        if not map_user and not map_group:
            continue

        if not map_user:
            verrors.add(f"{schema_name}.{k}_user", "This field is required when map group is specified")
            continue

        try:
            await part.middleware.call("user.get_user_obj", {"username": map_user})
        except KeyError:
            verrors.add(f"{schema_name}.{k}_user", f"User not found: {map_user}")

        if map_group:
            try:
                await part.middleware.call("group.get_group_obj", {"groupname": map_group})
            except KeyError:
                verrors.add(f"{schema_name}.{k}_group", f"Group not found: {map_group}")

    if data.maproot_user and data.mapall_user:
        verrors.add(f"{schema_name}.mapall_user", "maproot_user disqualifies mapall_user")


async def validate_security(
    part: SharingNFSServicePart,
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    v4_sec = [sec for sec in data.security if sec != "SYS"]
    if not v4_sec:
        return

    nfs_config = await part.call2(part.s.nfs.config)
    if NFSProtocol.NFSv4 not in nfs_config.protocols:
        verrors.add(
            f"{schema_name}.security",
            f"The following security flavor(s) require NFSv4 to be enabled: {','.join(v4_sec)}.",
        )


async def validate_expose_snapshots(
    part: SharingNFSServicePart,
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    if not data.expose_snapshots:
        return

    entitlement = await part.call2(part.s.truenas.entitlements.check, LicenseFeature.NFS_SNAPSHOT)
    if not entitlement.entitled:
        verrors.add(f"{schema_name}.expose_snapshots", entitlement.message)
        return

    try:
        # We're using statfs output because in future it should expose whether snapdir is enabled
        sfs = await part.middleware.call("filesystem.statfs", data.path)
    except Exception:
        # we can't get info on unmounted / locked datasets but this doesn't have to be perfect.
        return

    if sfs.dest != data.path:
        verrors.add(
            f"{schema_name}.expose_snapshots",
            f"{data.path}: export path is not the root directory of a dataset.",
        )
