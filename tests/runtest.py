#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

from middlewared.test.integration.utils import client
from ipaddress import ip_interface
from subprocess import run, call
from sys import argv, exit
import os
import getopt
import random
import socket
import sys
import secrets
import string

TEST_DIR_TO_RESULT = {
    'api2': 'results/api_v2_tests_result.xml',
    'directory_services': 'results/directoryservices_tests_result.xml',
    'stig': 'results/stig_tests_result.xml',
    'sharing_protocols': 'results/sharing_protocols_tests_result.xml',
    'cloud': 'results/cloud_tests_result.xml',
}

workdir = os.getcwd()
sys.path.append(workdir)
workdir = os.getcwd()
results_xml = f'{workdir}/results/'
localHome = os.path.expanduser('~')
dotsshPath = localHome + '/.ssh'
keyPath = localHome + '/.ssh/test_id_rsa'
isns_ip = '10.234.24.50'  # isns01.qe.ixsystems.net
pool_name = "tank"

ixautomation_dot_conf_url = "https://raw.githubusercontent.com/iXsystems/" \
    "ixautomation/master/src/etc/ixautomation.conf.dist"
config_file_msg = "Please add config.py to freenas/tests which can be empty " \
    f"or contain settings from {ixautomation_dot_conf_url}"

if not os.path.exists('config.py'):
    print(config_file_msg)
    exit(1)

error_msg = f"""Usage for %s:
Mandatory option
    --ip <###.###.###.###>      - IP of the TrueNAS
    --password <root password>  - Password of the TrueNAS root user
    --interface <interface>     - The interface that TrueNAS is run one

Optional option
    --ip2                       - B controller IPv4 of TrueNAS HA machine
    --vip                       - VIP (ipv4) of TrueNAS HA machine
    --test <test name>          - Test name (Network, ALL)
    --tests <test1>[,test2,...] - List of tests to be supplied to pytest
    --vm-name <VM_NAME>         - Name the the Bhyve VM
    --ha                        - Run test for HA
    --ha_license                - The base64 encoded string of an HA license
    --isns_ip <###.###.###.###> - IP of the iSNS server (default: {isns_ip})
    --pool <POOL_NAME>          - Name of the ZFS pool (default: {pool_name})
    --test_dir <api2>           - Name of the tests directory from which to run tests
    """ % argv[0]

# if have no argument stop
if len(argv) == 1:
    print(error_msg)
    exit()

option_list = [
    "ip=",
    "ip2=",
    "vip=",
    "password=",
    "interface=",
    'test=',
    "vm-name=",
    "ha",
    "update",
    "dev-test",
    "log-cli-level=",
    "returncode",
    "isns_ip=",
    "pool=",
    "test_dir=",
    "tests=",
    "ha_license=",
    "hostname=",
    "show_locals"
]

# look if all the argument are there.
try:
    myopts, args = getopt.getopt(argv[1:], 'aipItk:vxs', option_list)
except getopt.GetoptError as e:
    print(str(e))
    print(error_msg)
    exit()

vm_name = None
testName = ''
testexpr = None
ha = False
update = False
verbose = 0
exitfirst = ''
returncode = False
callargs = []
tests = []
test_dir = 'api2'
ip2 = vip = ''
netmask = None
gateway = None
ha_license = ''
hostname = None
show_locals = False
for output, arg in myopts:
    if output in ('-i', '--ip'):
        ip = arg
    elif output == '--ip2':
        ip2 = arg
    elif output == '--vip':
        vip = arg
    elif output in ('-p', '--password'):
        passwd = arg
    elif output in ('-I', '--interface'):
        interface = arg
    elif output in ('-t', '--test'):
        testName = arg
    elif output == '-k':
        testexpr = arg
    elif output in ('--vm-name',):
        vm_name = f"'{arg}'"
    elif output == '--ha':
        ha = True
    elif output == '--hostname':
        hostname = arg
    elif output == '--update':
        update = True
    elif output == '-v':
        verbose += 1
    elif output == '-x':
        exitfirst = True
    elif output == '--log-cli-level':
        callargs.append('--log-cli-level')
        callargs.append(arg)
    elif output == '--returncode':
        returncode = True
    elif output == '--isns_ip':
        isns_ip = arg
    elif output == '--pool':
        pool_name = arg
    elif output == '-s':
        callargs.append('-s')
    elif output == '--tests':
        tests.extend(arg.split(','))
    elif output == '--test_dir':
        test_dir = arg
    elif output == '--ha_license':
        ha_license = arg
    elif output == '--show_locals':
        show_locals = True

if 'ip' not in locals() and 'passwd' not in locals() and 'interface' not in locals():
    print("Mandatory option missing!\n")
    print(error_msg)
    exit()

# create random hostname and random fake domain
digit = ''.join(secrets.choice((string.ascii_uppercase + string.digits)) for i in range(10))
if not hostname:
    hostname = f'test{digit}'
domain = f'{hostname}.nb.ixsystems.com'
artifacts = f"{workdir}/artifacts/"
if not os.path.exists(artifacts):
    os.makedirs(artifacts)

os.environ["MIDDLEWARE_TEST_IP"] = ip
os.environ["MIDDLEWARE_TEST_PASSWORD"] = passwd
os.environ["SERVER_TYPE"] = "ENTERPRISE_HA" if ha else "STANDARD"

ip_to_use = ip
if ha and ip2:
    domain = 'tn.ixsystems.com'
    os.environ['controller1_ip'] = ip
    os.environ['controller2_ip'] = ip2


def get_ipinfo(ip_to_use):
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


interface, netmask, gateway, ns1, ns2 = get_ipinfo(ip_to_use)
if not all((interface, netmask, gateway)):
    print(f'Unable to determine interface ({interface!r}), netmask ({netmask!r}) and gateway ({gateway!r}) for {ip_to_use!r}')
    exit()

if ha:
    if vip:
        os.environ['virtual_ip'] = vip
    elif os.environ.get('virtual_ip'):
        vip = os.environ['virtual_ip']
    else:
        # reduce risk of trying to assign same VIP to two VMs
        # starting at roughly the same time
        vip_pool = list(ip_interface(f'{ip}/{netmask}').network)
        random.shuffle(vip_pool)

        for i in vip_pool:
            last_octet = int(i.compressed.split('.')[-1])
            if last_octet < 15 or last_octet >= 250:
                # addresses like *.255, *.0 and any of them that
                # are < *.15 we'll ignore. Those are typically
                # reserved for routing/switch devices anyways
                continue
            elif run(['ping', '-c', '2', '-w', '4', i.compressed]).returncode != 0:
                # sent 2 packets to the address and got no response so assume
                # it's safe to use
                os.environ['virtual_ip'] = i.compressed
                vip = i.compressed
                break

    # Set various env variables for HA, if not already set
    if not os.environ.get('domain'):
        os.environ['domain'] = domain
    if not os.environ.get('hostname_virtual'):
        os.environ['hostname_virtual'] = hostname
    if not os.environ.get('hostname'):
        os.environ['hostname'] = f'{hostname}-nodea'
    if not os.environ.get('hostname_b'):
        os.environ['hostname_b'] = f'{hostname}-nodeb'
    if not os.environ.get('primary_dns'):
        os.environ['primary_dns'] = ns1 or '10.230.0.10'
    if not os.environ.get('secondary_dns'):
        os.environ['secondary_dns'] = ns2 or '10.230.0.11'

cfg_content = f"""#!{sys.executable}

user = "root"
password = "{passwd}"
netmask = "{netmask}"
gateway = "{gateway}"
vip = "{vip}"
vm_name = {vm_name}
hostname = "{hostname}"
domain = "{domain}"
api_url = 'http://{ip}/api/v2.0'
interface = "{interface}"
badNtpServer = "10.20.20.122"
localHome = "{localHome}"
keyPath = "{keyPath}"
pool_name = "{pool_name}"
ha_pool_name = "ha"
ha = {ha}
ha_license = "{ha_license}"
update = {update}
artifacts = "{artifacts}"
isns_ip = "{isns_ip}"
"""

cfg_file = open("auto_config.py", 'w')
cfg_file.writelines(cfg_content)
cfg_file.close()

from functions import setup_ssh_agent, create_key, add_ssh_key, get_folder
from functions import SSH_TEST
# Setup ssh agent before starting test.
setup_ssh_agent()
if os.path.isdir(dotsshPath) is False:
    os.makedirs(dotsshPath)
if os.path.exists(keyPath) is False:
    create_key(keyPath)
add_ssh_key(keyPath)

f = open(keyPath + '.pub', 'r')
Key = f.readlines()[0].rstrip()

cfg_file = open("auto_config.py", 'a')
cfg_file.writelines(f'sshKey = "{Key}"\n')
cfg_file.close()

if verbose:
    callargs.append("-" + "v" * verbose)
if exitfirst:
    callargs.append("-x")

if show_locals:
    callargs.append('--showlocals')

# Use the right python version to start pytest with sys.executable
# So that we can support virtualenv python pytest.
pytest_command = [
    sys.executable,
    '-m',
    'pytest'
] + callargs + [
    "-o", "junit_family=xunit2",
    '--timeout=300',
    "--junitxml",
    TEST_DIR_TO_RESULT.get(test_dir),
]
if testexpr:
    pytest_command.extend(['-k', testexpr])


def parse_test_name(test):
    test = test.removeprefix(f"{test_dir}/")
    test = test.removeprefix(f"{test_dir}.")
    if ".py" not in test and test.count(".") == 1:
        # Test name from Jenkins
        filename, testname = test.split(".")
        return f"{filename}.py::{testname}"
    return test


def parse_test_name_prefix_dir(test_name):
    name = parse_test_name(test_name)
    if name.startswith('/'):
        return name
    else:
        return f"{test_dir}/{name}"


if tests:
    pytest_command.extend(list(map(parse_test_name_prefix_dir, tests)))
else:
    pytest_command.append(parse_test_name_prefix_dir(testName))

proc_returncode = call(pytest_command)


def get_cmd_result(cmd: str, target_file: str, target_ip: str):
    try:
        results = SSH_TEST(cmd, 'root', 'testing', target_ip)
    except Exception as exc:
        with open(f'{target_file}.error.txt', 'w') as f:
            f.write(f'{target_ip}: command [{cmd}] failed: {exc}\n')
            f.flush()
    else:
        with open(target_file, 'w') as f:
            f.writelines(results['stdout'])
            f.flush()


if ha:
    get_folder('/var/log', f'{artifacts}/log_nodea', 'root', 'testing', ip)
    get_folder('/var/log', f'{artifacts}/log_nodeb', 'root', 'testing', ip2)
    get_cmd_result('midclt call core.get_jobs | jq .', f'{artifacts}/core.get_jobs_nodea.json', ip)
    get_cmd_result('midclt call core.get_jobs | jq .', f'{artifacts}/core.get_jobs_nodeb.json', ip2)
    get_cmd_result('dmesg', f'{artifacts}/dmesg_nodea.json', ip)
    get_cmd_result('dmesg', f'{artifacts}/dmesg_nodeb.json', ip2)
else:
    get_folder('/var/log', f'{artifacts}/log', 'root', 'testing', ip)
    get_cmd_result('midclt call core.get_jobs | jq .', f'{artifacts}/core.get_jobs.json', ip)
    get_cmd_result('dmesg', f'{artifacts}/dmesg.json', ip)

if returncode:
    exit(proc_returncode)
