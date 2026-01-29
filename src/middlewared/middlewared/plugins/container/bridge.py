import ipaddress
import os
import subprocess
import tempfile
import textwrap
import threading

from truenas_pynetif.bridge import create_bridge
from truenas_pynetif.netif import get_interface

from middlewared.service import private, Service
from middlewared.utils.cgroups import move_to_root_cgroups

BRIDGE_NAME = "truenasbr0"
# This is intentionally kept on the boot drive because placing it on the system dataset prevents unmounting during
# system dataset migration.
# We don't care about DHCP lease files being persistent across updates or HA failovers.
FS_PATH = "/var/lib/dnsmasq"
DOMAIN_NAME = "tn-container"


class ContainerService(Service):
    lock = threading.Lock()

    @private
    def configure_bridge(self):
        with self.lock:
            config = self.middleware.call_sync("lxc.config")
            if config["bridge"] is not None:
                return

            if get_interface(BRIDGE_NAME, True):
                return

            # FIXME: what user and group whould we use to run dnsmasq?
            os.makedirs(FS_PATH, exist_ok=True)

            create_bridge(BRIDGE_NAME)
            interface = get_interface(BRIDGE_NAME)
            if config["v4_network"]:
                ip = ipaddress.ip_interface(config["v4_network"])
                interface.add_address(self.middleware.call_sync("interface.interface_to_addr", ip))
            if config["v6_network"]:
                ip = ipaddress.ip_interface(config["v6_network"])
                interface.add_address(self.middleware.call_sync("interface.interface_to_addr", ip))

            ipv4_masquerade = ""
            ipv6_masquerade = ""
            dnsmasq_args = []
            if config["v4_network"]:
                ip = ipaddress.ip_interface(config["v4_network"])
                ipv4_masquerade = (
                    f"ip saddr {ip.ip}/{ip.network.prefixlen} ip daddr != {ip.ip}/{ip.network.prefixlen} masquerade"
                )
                dnsmasq_args.append("--quiet-dhcp")
                dnsmasq_args.append(f"--listen-address={ip.network[1]!s}")
                dnsmasq_args.extend(["--dhcp-range", f"{ip.network[2]!s},{ip.network[-2]!s},1h"])
            if config["v6_network"]:
                ip = ipaddress.ip_interface(config["v6_network"])
                ipv6_masquerade = (
                    f"ip6 saddr {ip.ip}/{ip.network.prefixlen} ip6 daddr != {ip.ip}/{ip.network.prefixlen} masquerade"
                )
                dnsmasq_args.append("--quiet-dhcp6")
                dnsmasq_args.append("--quiet-ra")
                dnsmasq_args.append(f"--listen-address={ip.network[1]!s}")
                dnsmasq_args.append("--enable-ra")
                dnsmasq_args.extend(["--dhcp-range", f"::,constructor:{BRIDGE_NAME},ra-stateless,ra-names"])

            icmp_type = "destination-unreachable, time-exceeded, parameter-problem"
            icmpv6_type = (
                "destination-unreachable, packet-too-big, time-exceeded, parameter-problem, nd-router-solicit, "
                "nd-neighbor-solicit, nd-neighbor-advert, mld2-listener-report"
            )

            with tempfile.NamedTemporaryFile("w+") as f:
                f.write(textwrap.dedent("""\
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
                """ % {
                    "bridge_name": BRIDGE_NAME,
                    "ipv4_masquerade": ipv4_masquerade,
                    "ipv6_masquerade": ipv6_masquerade,
                    "icmp_type": icmp_type,
                    "icmpv6_type": icmpv6_type,
                }))
                f.flush()

                subprocess.check_call(["nft", "-f", f.name])

            with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                f.write("1\n")

            with open(f"{FS_PATH}/test.dnsmasq.raw", "w"):
                pass

            dnsmasq = subprocess.Popen(
                ["dnsmasq", "--keep-in-foreground", "--strict-order", "--bind-interfaces", "--except-interface=lo",
                 "--pid-file=", "--no-ping", f"--interface={BRIDGE_NAME}", "--dhcp-rapid-commit", "--no-negcache",
                 "--dhcp-no-override", "--dhcp-authoritative", f"--dhcp-leasefile={FS_PATH}/dnsmasq.leases",
                 f"--dhcp-hostsfile={FS_PATH}/test.dnsmasq.hosts"] + dnsmasq_args + [
                 "-s", DOMAIN_NAME, "--interface-name", f"_gateway.{DOMAIN_NAME},{BRIDGE_NAME}",
                 "-S", f"/{DOMAIN_NAME}/", f"--conf-file={FS_PATH}/test.dnsmasq.raw", "-u", "nobody", "-g", "nogroup"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            try:
                move_to_root_cgroups(dnsmasq.pid)
            except Exception as e:
                self.logger.warning("Unable to move dnsmasq pid=%r to root cgroups: %r", dnsmasq.pid, e)

    @private
    def bridge_name(self):
        config = self.middleware.call_sync("lxc.config")
        return config["bridge"] or BRIDGE_NAME
