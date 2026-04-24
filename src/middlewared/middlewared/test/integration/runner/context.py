import dataclasses
from ipaddress import ip_interface
import os
import random
import secrets
import socket
import string
import subprocess
import sys

from middlewared.test.integration.utils.client import client

from .args import RunArgs
from .ssh import setup_ssh_agent, create_key, add_ssh_key


@dataclasses.dataclass
class Context(RunArgs):
    workdir: str
    artifacts: str
    domain: str
    netmask: str
    gateway: str
    ns1: str | None
    ns2: str | None
    vip: str
    local_home: str
    ssh_key_path: str
    ssh_key: str


def context_from_args(args: RunArgs, workdir: str) -> Context:
    os.environ["MIDDLEWARE_TEST_IP"] = args.ip
    os.environ["MIDDLEWARE_TEST_PASSWORD"] = args.password
    os.environ["SERVER_TYPE"] = "ENTERPRISE_HA" if args.ha else "STANDARD"

    d = dataclasses.asdict(args)

    artifacts = f"{workdir}/artifacts/"
    if not os.path.exists(artifacts):
        os.makedirs(artifacts)

    if args.ha_license_path:
        with open(args.ha_license_path) as f:
            d['ha_license'] = f.read()

    # create random hostname and random fake domain
    digit = ''.join(secrets.choice((string.ascii_uppercase + string.digits)) for i in range(10))
    d['hostname'] = args.hostname or f'test{digit}'

    if args.ha and args.ip2:
        domain = 'tn.ixsystems.com'
    else:
        domain = f"{d['hostname']}.nb.ixsystems.net"

    ip_to_use = args.ip
    interface, netmask, gateway, ns1, ns2 = get_ipinfo(ip_to_use)

    if interface is None or netmask is None or gateway is None:
        print(
            f'Unable to determine interface ({interface!r}), netmask ({netmask!r}) and gateway ({gateway!r}) '
            f'for {ip_to_use!r}'
        )
        sys.exit(1)

    d['interface'] = interface

    if args.ha:
        if args.vip:
            vip = args.vip
        elif os.environ.get('virtual_ip'):
            vip = os.environ['virtual_ip']
        else:
            vip = get_random_vip(ip_to_use, netmask)
    else:
        vip = ''

    d['vip'] = vip

    # Setup ssh agent before starting test.
    local_home = os.path.expanduser('~')
    dotssh_path = local_home + '/.ssh'
    ssh_key_path = dotssh_path + '/test_id_rsa'
    setup_ssh_agent()
    os.makedirs(dotssh_path, exist_ok=True)
    if not os.path.exists(ssh_key_path):
        create_key(ssh_key_path)
    add_ssh_key(ssh_key_path)
    with open(ssh_key_path, 'r') as f:
        ssh_key = f.readlines()[0].rstrip()

    return Context(**d, workdir=workdir, artifacts=artifacts, domain=domain, netmask=netmask, gateway=gateway,
                   ns1=ns1, ns2=ns2, local_home=local_home, ssh_key_path=ssh_key_path, ssh_key=ssh_key)


def get_ipinfo(ip_to_use: str) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    iface = net = gate = ns1 = ns2 = None
    with client(host_ip=ip_to_use) as c:
        net_config = c.call('network.configuration.config')
        ns1 = net_config.get('nameserver1')
        ns2 = net_config.get('nameserver2')
        _ip_to_use = socket.gethostbyname(ip_to_use)
        for i in c.call('interface.query'):
            for j in i['state']['aliases']:
                if j.get('address') == _ip_to_use:
                    iface = i['id']
                    net = j['netmask']
                    for k in c.call('route.system_routes'):
                        if k.get('network') == '0.0.0.0' and k.get('gateway'):
                            return iface, net, k['gateway'], ns1, ns2

    return iface, net, gate, ns1, ns2


def get_random_vip(ip: str, netmask: str) -> str:
    # reduce risk of trying to assign same VIP to two VMs
    # starting at roughly the same time
    vip_pool = list(ip_interface(f'{ip}/{netmask}').network)
    random.shuffle(vip_pool)

    for i in vip_pool:
        last_octet = int(i.compressed.split('.')[-1])
        if last_octet < 15 or last_octet >= 250:
            # addresses like *.255, *.0 and any of them that
            # are < *.15 we'll ignore. Those are typically
            # reserved for routing/switch devices anyway
            continue
        elif subprocess.run(['ping', '-c', '2', '-w', '4', i.compressed]).returncode != 0:
            # sent 2 packets to the address and got no response so assume
            # it's safe to use
            return i.compressed

    raise RuntimeError('Unable to come up with vip address')
