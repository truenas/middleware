import ipaddress
import os
import subprocess
import tempfile
import textwrap
from truenas_pynetif.address.address import add_address
from truenas_pynetif.address.get_links import get_link
from truenas_pynetif.address.netlink import netlink_route
from truenas_pynetif.configure import BridgeConfig, configure_bridge
from truenas_pynetif.netlink import DeviceNotFound

from middlewared.service import ServiceContext
from middlewared.utils.cgroups import move_to_root_cgroups

BRIDGE_NAME = "truenasbr0"
# This is intentionally kept on the boot drive because placing
# it on the system dataset prevents unmounting during system
# dataset migration. We don't care about DHCP lease files being
# persistent across updates or HA failovers.
FS_PATH = "/var/lib/dnsmasq"
DNSMASQ_CONF_FILE = f"{FS_PATH}/test.dnsmasq.raw"
DOMAIN_NAME = "tn-container"

__all__ = (
    "container_bridge_name",
    "configure_container_bridge",
)


def _bridge_impl(
    ip4: ipaddress.IPv4Network | None, ip6: ipaddress.IPv6Network | None
) -> bool:
    was_created = False
    with netlink_route() as sock:
        try:
            get_link(sock, BRIDGE_NAME)
        except DeviceNotFound:
            # only create if doesn't already exist
            configure_bridge(
                sock,
                BridgeConfig(name=BRIDGE_NAME, members=[]),
            )
            was_created = True
            link = get_link(sock, BRIDGE_NAME)
            if ip4:
                add_address(
                    sock,
                    ip4.ip.exploded,
                    ip4.network.prefixlen,
                    index=link.index,
                    broadcast=ip4.network.broadcast_address.exploded,
                )
            if ip6:
                add_address(
                    sock,
                    ip6.ip.exploded,
                    ip6.network.prefixlen,
                    index=link.index,
                )
    return was_created


def _start_dnsmasq(ctx, dnsmasq_args) -> None:
    with open(DNSMASQ_CONF_FILE, "w"):
        pass

    cmd = [
        "dnsmasq",
        "--keep-in-foreground",
        "--strict-order",
        "--bind-interfaces",
        "--except-interface=lo",
        "--pid-file=",
        "--no-ping",
        f"--interface={BRIDGE_NAME}",
        "--dhcp-rapid-commit",
        "--no-negcache",
        "--dhcp-no-override",
        "--dhcp-authoritative",
        f"--dhcp-leasefile={FS_PATH}/dnsmasq.leases",
        f"--dhcp-hostsfile={FS_PATH}/test.dnsmasq.hosts",
    ]
    cmd.extend(dnsmasq_args)
    cmd.extend(
        [
            "-s",
            DOMAIN_NAME,
            "--interface-name",
            f"_gateway.{DOMAIN_NAME},{BRIDGE_NAME}",
            "-S",
            f"/{DOMAIN_NAME}/",
            f"--conf-file={DNSMASQ_CONF_FILE}",
            "-u",
            "nobody",
            "-g",
            "nogroup",
        ]
    )
    dnsmasq = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    try:
        move_to_root_cgroups(dnsmasq.pid)
    except Exception as e:
        ctx.logger.warning(
            "Unable to move dnsmasq pid=%r to root cgroups: %r", dnsmasq.pid, e
        )


def _configure_nft(ipv4_masquerade, ipv6_masquerade):
    with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
        f.write("1\n")

    icmp_type = "destination-unreachable, time-exceeded, parameter-problem"
    icmpv6_type = (
        "destination-unreachable, packet-too-big, time-exceeded, parameter-problem, nd-router-solicit, "
        "nd-neighbor-solicit, nd-neighbor-advert, mld2-listener-report"
    )
    with tempfile.NamedTemporaryFile("w+") as f:
        f.write(
            textwrap.dedent(
                """\
            table inet truenas {
                chain pstrt.%(bridge_name)s {
                    type nat hook postrouting priority srcnat; policy accept;
                    %(ipv4_masquerade)s
                    %(ipv6_masquerade)s
                }

                chain fwd.%(bridge_name)s {
                    type filter hook forward priority filter; policy accept;
                    ip version 4 oifname "%(bridge_name)s" accept
                    ip version 4 iifname "%(bridge_name)s" accept
                    ip6 version 6 oifname "%(bridge_name)s" accept
                    ip6 version 6 iifname "%(bridge_name)s" accept
                }

                chain in.%(bridge_name)s {
                    type filter hook input priority filter; policy accept;
                    iifname "%(bridge_name)s" tcp dport 53 accept
                    iifname "%(bridge_name)s" udp dport 53 accept
                    iifname "%(bridge_name)s" icmp type { %(icmp_type)s } accept
                    iifname "%(bridge_name)s" udp dport 67 accept
                    iifname "%(bridge_name)s" icmpv6 type { %(icmpv6_type)s } accept
                    iifname "%(bridge_name)s" udp dport 547 accept
                }

                chain out.%(bridge_name)s {
                    type filter hook output priority filter; policy accept;
                    oifname "%(bridge_name)s" tcp sport 53 accept
                    oifname "%(bridge_name)s" udp sport 53 accept
                    oifname "%(bridge_name)s" icmp type { %(icmp_type)s } accept
                    oifname "%(bridge_name)s" udp sport 67 accept
                    oifname "%(bridge_name)s" icmpv6 type { %(icmpv6_type)s } accept
                    oifname "%(bridge_name)s" udp sport 547 accept
                }
            }
        """
                % {
                    "bridge_name": BRIDGE_NAME,
                    "ipv4_masquerade": ipv4_masquerade,
                    "ipv6_masquerade": ipv6_masquerade,
                    "icmp_type": icmp_type,
                    "icmpv6_type": icmpv6_type,
                }
            )
        )
        f.flush()
        subprocess.check_call(["nft", "-f", f.name])


def configure_container_bridge(ctx: ServiceContext):
    config = ctx.middleware.call_sync("lxc.config")
    if config["bridge"] is not None:
        return

    # FIXME: what user and group whould we use to run dnsmasq?
    os.makedirs(FS_PATH, exist_ok=True)

    ip4 = None
    if config["v4_network"]:
        ip4 = ipaddress.ip_interface(config["v4_network"])
    ip6 = None
    if config["v6_network"]:
        ip6 = ipaddress.ip_interface(config["v6_network"])

    was_created = _bridge_impl(ip4, ip6)
    if not was_created:
        return

    ipv4_masquerade = ""
    ipv6_masquerade = ""
    dnsmasq_args = []
    if ip4:
        ip, prefix = ip4.ip.exploded, ip4.network.prefixlen
        ipv4_masquerade = f"ip saddr {ip}/{prefix} ip daddr != {ip}/{prefix} masquerade"
        dnsmasq_args.extend(
            [
                "--quiet-dhcp",
                f"--listen-address={ip4.network[1]!s}",
                "--dhcp-range",
                f"{ip4.network[2]!s},{ip4.network[-2]!s},1h",
            ]
        )
    if ip6:
        ip, prefix = ip6.ip.exploded, ip6.network.prefixlen
        ipv6_masquerade = (
            f"ip6 saddr {ip}/{prefix} ip6 daddr != {ip}/{prefix} masquerade"
        )
        dnsmasq_args.extend(
            [
                "--quiet-dhcp6",
                "--quiet-ra",
                f"--listen-address={ip6.network[1]!s}",
                "--enable-ra",
                "--dhcp-range",
                f"::,constructor:{BRIDGE_NAME},ra-stateless,ra-names",
            ]
        )

    _configure_nft(ipv4_masquerade, ipv6_masquerade)
    _start_dnsmasq(ctx, dnsmasq_args)


def container_bridge_name(ctx: ServiceContext):
    config = ctx.middleware.call_sync("lxc.config")
    return config["bridge"] or BRIDGE_NAME
