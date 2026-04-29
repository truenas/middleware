import configparser
import io

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):
    if render_ctx["failover.status"] not in ("SINGLE", "MASTER"):
        raise FileShouldNotExist()

    net_config = render_ctx["network.configuration.config"]
    smb_config = render_ctx["smb.config"]
    interfaces = render_ctx["interface.query"]
    ds_config = render_ctx["directoryservices.config"]
    announce = net_config["service_announcement"]

    if render_ctx["failover.status"] == "MASTER":
        hostname = net_config.get("hostname_virtual") or net_config["hostname_local"]
    else:
        hostname = net_config["hostname_local"]

    iface_names = [i["name"] for i in interfaces]
    ipv4_enabled = any(middleware.call_sync("interface.ip_in_use", {"ipv4": True, "ipv6": False}))
    ipv6_enabled = any(middleware.call_sync("interface.ip_in_use", {"ipv4": False, "ipv6": True}))

    cp = configparser.ConfigParser()

    cp.add_section("discovery")
    if iface_names:
        cp.set("discovery", "interfaces", ", ".join(iface_names))
    if hostname:
        cp.set("discovery", "hostname", hostname)
    if smb_config["workgroup"]:
        cp.set("discovery", "workgroup", smb_config["workgroup"])

    cp.add_section("mdns")
    cp.set("mdns", "enabled", "yes" if announce.get("mdns") else "no")
    if ipv4_enabled or ipv6_enabled:
        cp.set("mdns", "use-ipv4", "yes" if ipv4_enabled else "no")
        cp.set("mdns", "use-ipv6", "yes" if ipv6_enabled else "no")
    cp.set("mdns", "service-dir", "/etc/truenas-discovery/services.d")

    cp.add_section("netbiosns")
    cp.set("netbiosns", "enabled", "yes" if announce.get("netbios") else "no")
    if smb_config["netbiosname"]:
        cp.set("netbiosns", "netbios-name", smb_config["netbiosname"])
    aliases = smb_config.get("netbiosalias") or []
    if aliases:
        cp.set("netbiosns", "netbios-aliases", ", ".join(aliases))
    if smb_config.get("description"):
        cp.set("netbiosns", "server-string", smb_config["description"])

    cp.add_section("wsd")
    cp.set("wsd", "enabled", "yes" if announce.get("wsd") else "no")
    if ds_config["enable"] and ds_config["service_type"] == DSType.AD.value:
        domain = ds_config["configuration"]["domain"]
        if domain:
            cp.set("wsd", "domain", domain)

    buf = io.StringIO()
    cp.write(buf)
    return buf.getvalue()
