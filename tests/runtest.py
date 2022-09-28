#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

from subprocess import call
from sys import argv
import os
import getopt
import sys
import random
import string

workdir = os.getcwd()
sys.path.append(workdir)
workdir = os.getcwd()
results_xml = f'{workdir}/results/'
localHome = os.path.expanduser('~')
dotsshPath = localHome + '/.ssh'
keyPath = localHome + '/.ssh/test_id_rsa'

ixautomation_dot_conf_url = "https://raw.githubusercontent.com/iXsystems/" \
    "ixautomation/master/src/etc/ixautomation.conf.dist"
config_file_msg = "Please add config.py to freenas/tests which can be empty " \
    f"or contain settings from {ixautomation_dot_conf_url}"

if not os.path.exists('config.py'):
    print(config_file_msg)
    exit(1)

error_msg = """Usage for %s:
Mandatory option
    --ip <###.###.###.###>     - IP of the FreeNAS
    --password <root password> - Password of the FreeNAS root user
    --interface <interface>    - The interface that FreeNAS is run one

Optional option
    --test <test name>         - Test name (Network, ALL)
    --vm-name <VM_NAME>        - Name the the Bhyve VM
    --ha                       - Run test for HA
    --dev-test                 - Run only the test that are not mark with
                                 pytestmark skipif dev_test is true.
    --debug-mode               - Start API tests with middleware debug mode
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
    "debug-mode"
]

# look if all the argument are there.
try:
    myopts, args = getopt.getopt(argv[1:], 'aipItk:vx', option_list)
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

if 'ip' not in locals() and 'passwd' not in locals() and 'interface' not in locals():
    print("Mandatory option missing!\n")
    print(error_msg)
    exit()

# create random hostname and random fake domain
digit = ''.join(random.choices(string.digits, k=2))
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
ntpServer = "10.20.20.122"
localHome = "{localHome}"
keyPath = "{keyPath}"
pool_name = "tank"
ha_pool_name = "ha"
ha = {ha}
update = {update}
dev_test = {dev_test}
debug_mode = {debug_mode}
artifacts = "{artifacts}"
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

callargs = []
if verbose:
    callargs.append("-" + "v" * verbose)
if exitfirst:
    callargs.append("-x")

# Use the right python version to start pytest with sys.executable
# So that we can support virtualenv python pytest.
call([
    sys.executable,
    '-m',
    'pytest'
] + callargs + [
    "-o", "junit_family=xunit2",
    '--timeout=300',
    "--junitxml",
    'results/api_v2_tests_result.xml',
    f"api2/{testName}"
])

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
