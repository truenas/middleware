#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

from subprocess import call
from sys import argv
from os import path, getcwd, makedirs, listdir
import getopt
import sys
import re
import random
import string

major_v = sys.version_info.major
minor_v = sys.version_info.minor
version = f"{major_v}.{minor_v}"
apifolder = getcwd()
sys.path.append(apifolder)
workdir = getcwd()
results_xml = f'{workdir}/results/'
localHome = path.expanduser('~')
dotsshPath = localHome + '/.ssh'
keyPath = localHome + '/.ssh/test_id_rsa'

ixautomationdotconfurl = "https://raw.githubusercontent.com/iXsystems/"
ixautomationdotconfurl += "ixautomation/master/src/etc/ixautomation.conf.dist"
config_file_msg = "Please add config.py to freenas/tests which can be empty " \
    f"or contain settings from {ixautomationdotconfurl}"

try:
    import config
except ImportError:
    raise ImportError(config_file_msg)

error_msg = """Usage for %s:
Mandatory option
    --ip <###.###.###.###>     - IP of the FreeNAS
    --password <root password> - Password of the FreeNAS root user
    --interface <interface>    - The interface that FreeNAS is run one

Optional option
    --test <test name>         - Test name (Network, ALL)
    --vm-name <VM_NAME>        - Name the the Bhyve VM
    --ha                       - Run test for HA
    --scale                    - Run test for Scale
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
    "scale"
]

# look if all the argument are there.
try:
    myopts, args = getopt.getopt(argv[1:], 'aipItk:', option_list)
except getopt.GetoptError as e:
    print(str(e))
    print(error_msg)
    exit()

vm_name = None
testName = None
testexpr = None
ha = False
scale = False

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
    elif output in ('--vm-name'):
        vm_name = f"'{arg}'"
    elif output == '--ha':
        ha = True
    elif output == '--scale':
        scale = True

if 'ip' not in locals() and 'passwd' not in locals() and 'interface' not in locals():
    print("Mandatory option missing!\n")
    print(error_msg)
    exit()

# create random hostname and random fake domain
digit = ''.join(random.choices(string.digits, k=2))
hostname = f'test{digit}'
domain = f'test{digit}.nb.ixsystems.com'

cfg_content = f"""#!/usr/bin/env python3.6

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
ha = {ha}
scale = {scale}
"""

cfg_file = open("auto_config.py", 'w')
cfg_file.writelines(cfg_content)
cfg_file.close()

from functions import setup_ssh_agent, create_key, add_ssh_key, get_file
from functions import SSH_TEST
# Setup ssh agent befor starting test.
setup_ssh_agent()
if path.isdir(dotsshPath) is False:
    makedirs(dotsshPath)
if path.exists(keyPath) is False:
    create_key(keyPath)
add_ssh_key(keyPath)

f = open(keyPath + '.pub', 'r')
Key = f.readlines()[0].rstrip()

cfg_file = open("auto_config.py", 'a')
cfg_file.writelines('sshKey = "%s"\n' % Key)
cfg_file.close()


def get_tests():
    rv = []
    sv = []
    ev = []
    skip_tests = []

    if ha is True:
        skip_tests += ['interfaces', 'network', 'delete_interfaces']
    if scale is True:
        skip_tests += ['jail', 'plugin']
    apidir = 'api2/'
    if ha is True:
        sv = ['ssh', 'pool', 'user']
        ev = ['update', 'delete_user']
    else:
        sv = ['ssh', 'interfaces', 'network', 'pool', 'user']
        ev = ['update', 'delete_interfaces', 'delete_user']
    for filename in listdir(apidir):
        if filename.endswith('.py') and not filename.startswith('__init__'):
            filename = re.sub('.py$', '', filename)
            if filename not in skip_tests and filename not in sv and filename not in ev:
                rv.append(filename)
    rv.sort()
    return sv + rv + ev


for i in get_tests():
    if testName is not None and testName != i:
        continue
    call([f"py.test-{version}", "-v", "--junitxml",
          f"{results_xml}{i}_tests_result.xml"] + (
              ["-k", testexpr] if testexpr else []
    ) + [f"api2/{i}.py"])

# get useful logs
artifacts = f"{workdir}/artifacts/"
logs_list = [
    "/var/log/middlewared.log",
    "/var/log/messages",
    "/var/log/debug.log",
    "/var/log/console.log"
]
if not path.exists(artifacts):
    makedirs(artifacts)

for log in logs_list:
    get_file(log, artifacts, 'root', 'testing', ip)

# get dmesg and put it in artifacs
results = SSH_TEST('dmesg -a', 'root', 'testing', ip)
dmsg = open(f'{artifacts}/dmesg', 'w')
dmsg.writelines(results['output'])
dmsg.close()

# get core.get_jobs and put it in artifacs
results = SSH_TEST('midclt call core.get_jobs | jq .', 'root', 'testing', ip)
dmsg = open(f'{artifacts}/core_get_job', 'w')
dmsg.writelines(results['output'])
dmsg.close()
