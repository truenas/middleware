from __future__ import annotations

import errno
import ipaddress
import itertools
from typing import Iterable, Sequence, TypeAlias, cast

from middlewared.api.current import SharingNFSEntry
from middlewared.plugins.dns_client import DNSClientForwardLookupData, DNSClientLookupItem
from middlewared.service import CallError, ServiceContext, ValidationErrors
from middlewared.utils.asyncio_ import asyncio_map

from .utils import get_domain, get_wildcard_domain, leftmost_has_wildcards

IPNetwork: TypeAlias = ipaddress.IPv4Network | ipaddress.IPv6Network
DNSCache: TypeAlias = dict[str, str | None]


def overlapping_network_pairs(networks: Sequence[str]) -> list[tuple[str, str]]:
    """Every pair of entries in `networks` that overlap each other. Mixed address families never do.

    `strict` is False so that an entry like 1.2.3.4/24 is accepted.
    """
    return [
        (n1, n2)
        for n1, n2 in itertools.combinations(networks, 2)
        if ipaddress.ip_network(n1, strict=False).overlaps(ipaddress.ip_network(n2, strict=False))
    ]


def networks_overlapped_by(networks: Iterable[IPNetwork], network: IPNetwork) -> list[IPNetwork]:
    """The entries of `networks` that `network` overlaps, subnets and supernets alike."""
    return [other for other in networks if network.overlaps(other)]


async def resolve_hostnames(context: ServiceContext, hostnames: Iterable[str]) -> DNSCache:
    """Each hostname mapped to a single address, or to None where it does not resolve."""
    unique = list(set(hostnames))

    async def resolve(hostname: str) -> str | None:
        try:
            try:
                ipaddress.ip_address(hostname)
                return hostname
            except ValueError:
                pass

            if domain := get_wildcard_domain(hostname):
                hostname = domain

            if leftmost_has_wildcards(hostname):
                # We know this will not resolve
                return None

            try:
                lookup = cast(
                    list[DNSClientLookupItem],
                    await context.call2(
                        context.s.dnsclient.forward_lookup, DNSClientForwardLookupData(names=[hostname])
                    ),
                )
            except Exception as e:
                context.logger.warning("Unable to resolve host %r: %r", hostname, e)
                return None

            # We might get both IPv4 and IPv6 addresses, the caller expects a single response
            return lookup[0].address
        except Exception as e:
            context.logger.warning("Unable to resolve or invalid host %r: %r", hostname, e)
            return None

    resolved = await asyncio_map(resolve, unique, 8)

    return dict(zip(unique, resolved))


def validate_share_networks(
    networks: Sequence[str],
    dns_cache: DNSCache,
    schema_name: str,
    verrors: ValidationErrors,
) -> None:
    """
    The network field is strictly limited to CIDR formats:
    The input validator should enforce the CIDR format and a single address per entry.
    This validation is limited to:
        * Collisions with resolved hostnames
        * Overlapping subnets
    """
    resolved_addresses = list(dns_cache.values())
    for entry in networks:
        address = str(ipaddress.ip_interface(entry).ip)

        if address in resolved_addresses:
            host = next(key for key, value in dns_cache.items() if value == address)
            verrors.add(
                f"{schema_name}.networks",
                f"ERROR - Resolved hostname to duplicate address: host '{host}' resolves to '{entry}'",
            )

    if overlaps := overlapping_network_pairs(networks):
        verrors.add(f"{schema_name}.networks", f"ERROR - Overlapped subnets: {overlaps}")


async def share_realpath(context: ServiceContext, path: str) -> str:
    try:
        return str((await context.middleware.call("filesystem.stat", path)).realpath)
    except CallError as e:
        if e.errno != errno.ENOENT:
            raise
        # Allow for locked filesystems
        return path


async def validate_hosts_and_networks(
    context: ServiceContext,
    other_shares: Sequence[SharingNFSEntry],
    data: SharingNFSEntry,
    schema_name: str,
    verrors: ValidationErrors,
    dns_cache: DNSCache,
) -> None:
    """
    We attempt to prevent share situation where the same host is provided access to a
    share but with potentially different permissions.
    This module does checks that encompass both hosts and networks.
    """
    tgt_realpath = (await context.middleware.call("filesystem.stat", data.path)).realpath

    used_networks: set[IPNetwork] = set()
    used_hosts: set[str] = set()  # host names without an entry in the cache
    for share in other_shares:
        if tgt_realpath != await share_realpath(context, share.path):
            continue

        for host in share.hosts:
            host_ip = dns_cache.get(host)
            if host_ip is None:
                used_hosts.add(host)
                continue

            if host.startswith("@"):
                continue

            try:
                used_hosts.add(str(ipaddress.ip_network(host_ip, strict=False)))
            except Exception:
                context.logger.warning("Got invalid host %r", host)

        for entry in share.networks:
            try:
                used_networks.add(ipaddress.ip_network(entry, strict=False))
            except Exception:
                context.logger.warning("Got invalid network %r", entry)

        if not share.hosts and not share.networks:
            used_networks.add(ipaddress.ip_network("0.0.0.0/0"))
            used_networks.add(ipaddress.ip_network("::/0"))

    for entry in set(data.networks):
        network = ipaddress.ip_network(entry, strict=False)

        # Look for exact match.  This also works for IPv6
        if network in used_networks:
            verrors.add(
                f"{schema_name}.networks",
                f"ERROR - Another NFS share already exports {data.path} for network {network}",
            )

        # Look for subnet or supernet overlaps
        # Works for IPv4 and IPv6, but ignores mixed tests
        if overlaps := networks_overlapped_by(used_networks, network):
            # There may well be more than one overlap, but it is more clear to present only one.
            verrors.add(
                f"{schema_name}.networks",
                f"ERROR - This or another NFS share exports {data.path} to {overlaps[0]} "
                f"and overlaps network {network}",
            )

        used_networks.add(network)

    for host in set(data.hosts):
        # check for duplicate 'hosts' in other shares
        # netgroups are valid, but limited to same duplicate restrictions
        if host in used_hosts:
            verrors.add(
                f"{schema_name}.hosts",
                f"ERROR - Another NFS share already exports {data.path} for host {host}",
            )
            continue

        if host.startswith("@"):
            continue

        # wildcarded names without a 'domain' are valid
        if leftmost_has_wildcards(host) and get_domain(host) is None:
            continue

        # Everything else should be resolvable
        if dns_cache[host] is None:
            verrors.add(f"{schema_name}.hosts", f"Unable to resolve host '{host}'")
