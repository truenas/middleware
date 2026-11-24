import os
import sys
import time

from .call import call
from .client import truenas_server
from .ha import settle_ha
from .pool import pool
from .pytest import fail

sys.path.append(os.getcwd())
from auto_config import domain, gateway, ha, ha_license, hostname, interface, netmask  # noqa: E402


def setup_ssh():
    root_id = call("user.query", [["username", "=", "root"]], {"get": True})["id"]
    call("user.update", root_id, {"ssh_password_enabled": True})
    call("service.control", "START", "ssh", job=True)
    call("service.update", "ssh", {"enable": True})
    call("ssh.update", {"passwordauth": True})


def apply_and_verify_license():
    if ha_license:
        license_string = ha_license
    else:
        with open(os.environ.get("license_file", "/root/license.txt")) as f:
            license_string = f.read()

    call("truenas.license.upload", license_string)
    assert call("failover.licensed") is True

    for _ in range(30):
        if call("failover.call_remote", "failover.licensed"):
            return
        # A background hook syncs the license to the standby controller.
        # On the CI VMs this takes from under a second to more than 10 seconds.
        time.sleep(1)

    raise AssertionError("Timed out after 30s waiting on license to sync to standby")


def set_netinfo():
    info = {
        "domain": domain,
        "ipv4gateway": gateway,
        "hostname": os.environ["hostname"],
        "hostname_b": os.environ["hostname_b"],
        "hostname_virtual": os.environ["hostname_virtual"],
        "nameserver1": os.environ["primary_dns"],
        "nameserver2": os.environ.get("secondary_dns", ""),
    }
    call("network.configuration.update", info)
    call("smb.update", {"netbiosname": info["hostname_virtual"]})


def set_netinfo_single():
    call("smb.update", {"netbiosname": hostname})
    call("network.configuration.update", {"hostname": hostname})


def set_interfaces():
    payload = {
        "ipv4_dhcp": False,
        "ipv6_auto": False,
        "failover_critical": True,
        "failover_group": 1,
        "aliases": [{"type": "INET", "address": os.environ["controller1_ip"], "netmask": int(netmask)}],
        "failover_aliases": [{"type": "INET", "address": os.environ["controller2_ip"]}],
        "failover_virtual_aliases": [{"type": "INET", "address": os.environ["virtual_ip"]}],
    }
    call("failover.update", {"disabled": True, "master": True})
    call("interface.update", interface, payload)
    call("interface.commit")
    call("interface.checkin")

    time.sleep(3)
    truenas_server.ip = os.environ["virtual_ip"]
    truenas_server.nodea_ip = os.environ["controller1_ip"]
    truenas_server.nodeb_ip = os.environ["controller2_ip"]
    truenas_server.server_type = os.environ["SERVER_TYPE"]

    try:
        call("failover.sync_to_peer", {"reboot": True})
    except Exception:
        pass


def set_static_interface():
    # Keep the DHCP-provided default route and DNS after DHCP turns off.
    payload = {}
    conf = call("network.configuration.config")
    for key, val in conf.get("state", {}).items():
        if val and key in conf:
            payload[key] = val
    call("network.configuration.update", payload)

    payload = {
        "ipv4_dhcp": False,
        "ipv6_auto": False,
        "aliases": [{"type": "INET", "address": os.environ["MIDDLEWARE_TEST_IP"], "netmask": int(netmask)}],
    }
    call("interface.update", interface, payload)
    call("interface.commit")
    call("interface.checkin")
    time.sleep(3)


def create_permanent_pool():
    if not call("pool.query", [["name", "=", pool]]):
        unused_disks = call("disk.get_unused")
        assert len(unused_disks) > 0
        call(
            "pool.create",
            {"name": pool, "topology": {"data": [{"type": "STRIPE", "disks": [unused_disks[0]["name"]]}]}},
            job=True,
        )

    if ha:
        call("failover.update", {"disabled": False, "master": True})


def setup_server_ha():
    stage = None
    try:
        stage = "SETUP_SSH"
        setup_ssh()
        stage = "APPLY_LICENSE"
        apply_and_verify_license()
        stage = "SETUP_NETINFO"
        set_netinfo()
        stage = "SETUP_INTERFACES"
        set_interfaces()
        stage = "SETUP_POOL"
        create_permanent_pool()
        settle_ha()
    except Exception as exc:
        fail(f"{stage}: failed to set up truenas server: {exc}")


def setup_server_single(static_ip):
    stage = None
    try:
        stage = "SETUP_SSH"
        setup_ssh()
        stage = "SETUP_NETINFO"
        set_netinfo_single()
        if static_ip:
            stage = "SETUP_INTERFACE"
            set_static_interface()
        stage = "SETUP_POOL"
        create_permanent_pool()
    except Exception as exc:
        fail(f"{stage}: failed to set up truenas server: {exc}")


def setup_server(*, static_ip=False):
    if ha:
        setup_server_ha()
    else:
        setup_server_single(static_ip)
