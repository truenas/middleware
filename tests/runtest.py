#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

from subprocess import call
from sys import argv, exit
import os
import getopt
import sys
import secrets
import string

workdir = os.getcwd()
sys.path.append(workdir)
workdir = os.getcwd()
results_xml = f'{workdir}/results/'
localHome = os.path.expanduser('~')
dotsshPath = localHome + '/.ssh'
keyPath = localHome + '/.ssh/test_id_rsa'
isns_ip='10.234.24.50' # isns01.qe.ixsystems.net
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
    --test <test name>          - Test name (Network, ALL)
    --tests <test1>[,test2,...] - List of tests to be supplied to pytest
    --vm-name <VM_NAME>         - Name the the Bhyve VM
    --ha                        - Run test for HA
    --dev-test                  - Run only the test that are not mark with
                                  pytestmark skipif dev_test is true.
    --debug-mode                - Start API tests with middleware debug mode
    --isns_ip <###.###.###.###> - IP of the iSNS server (default: {isns_ip})
    --pool <POOL_NAME>          - Name of the ZFS pool (default: {pool_name})
    """ % argv[0]

# if have no argument stop
if len(argv) == 1:
    print(error_msg)
    exit()

option_list = [
    "ip=",
    "password=",
    "interface=",
    'test=',
    "vm-name=",
    "ha",
    "update",
    "dev-test",
    "debug-mode",
    "log-cli-level=",
    "returncode",
    "isns_ip=",
    "pool=",
    "tests=",
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
dev_test = False
debug_mode = False
verbose = 0
exitfirst = ''
returncode = False
callargs = []
tests = []
for output, arg in myopts:
    if output in ('-i', '--ip'):
        ip = arg
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
    elif output == '--update':
        update = True
    elif output == '--dev-test':
        dev_test = True
    elif output == '--debug-mode':
        debug_mode = True
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

if 'ip' not in locals() and 'passwd' not in locals() and 'interface' not in locals():
    print("Mandatory option missing!\n")
    print(error_msg)
    exit()

# create random hostname and random fake domain
digit = ''.join(secrets.choice((string.ascii_uppercase + string.digits)) for i in range(10))
hostname = f'test{digit}'
domain = f'test{digit}.nb.ixsystems.com'
artifacts = f"{workdir}/artifacts/"
if not os.path.exists(artifacts):
    os.makedirs(artifacts)

cfg_content = f"""#!{sys.executable}

user = "root"
password = "{passwd}"
ip = "{ip}"
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
update = {update}
dev_test = {dev_test}
debug_mode = {debug_mode}
artifacts = "{artifacts}"
isns_ip = "{isns_ip}"
"""

cfg_file = open("auto_config.py", 'w')
cfg_file.writelines(cfg_content)
cfg_file.close()

os.environ["MIDDLEWARE_TEST_IP"] = ip
os.environ["MIDDLEWARE_TEST_PASSWORD"] = passwd

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
    'results/api_v2_tests_result.xml',
]
if testexpr:
    pytest_command.extend(['-k', testexpr])

if tests:
    pytest_command.extend(tests)
else:
    pytest_command.append(f"api2/{testName}")

proc_returncode = call(pytest_command)

# get useful logs
logs_list = [
    "/var/log/daemon.log",
    "/var/log/debug",
    "/var/log/middlewared.log",
    "/var/log/messages",
    "/var/log/syslog",
]

get_folder('/var/log', f'{artifacts}/log', 'root', 'testing', ip)

# get dmesg and put it in artifacts
results = SSH_TEST('dmesg', 'root', 'testing', ip)
dmsg = open(f'{artifacts}/dmesg', 'w')
dmsg.writelines(results['output'])
dmsg.close()

# get core.get_jobs and put it in artifacts
results = SSH_TEST('midclt call core.get_jobs | jq .', 'root', 'testing', ip)
core_get_jobs = open(f'{artifacts}/core.get_jobs', 'w')
core_get_jobs.writelines(results['output'])
core_get_jobs.close()

if returncode:
    exit(proc_returncode)
