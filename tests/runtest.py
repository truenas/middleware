#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

from subprocess import call
from sys import argv
from os import path, getcwd, makedirs, listdir
import getopt
import sys
import re

apifolder = getcwd()
sys.path.append(apifolder)

results_xml = getcwd() + '/results/'
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
    --api <version number>     - API version number (1.0, 2.0)
    """ % argv[0]

# if have no argument stop
if len(argv) == 1:
    print(error_msg)
    exit()

option_list = ["api=", "ip=", "password=", "interface=", 'test=']

# look if all the argument are there.
try:
    myopts, args = getopt.getopt(argv[1:], 'aipItk:', option_list)
except getopt.GetoptError as e:
    print(str(e))
    print(error_msg)
    exit()

testName = None
api = "1.0"
testexpr = None

for output, arg in myopts:
    if output in ('-i', '--ip'):
        ip = arg
    elif output in ('-p', '--password'):
        passwd = arg
    elif output in ('-I', '--interface'):
        interface = arg
    elif output in ('-t', '--test'):
        testName = arg
    elif output in ('-a', '--api'):
        api = arg
    elif output == '-k':
        testexpr = arg

if ('ip' not in locals() and
        'password' not in locals() and
        'interface' not in locals()):
    print("Mandatory option missing!\n")
    print(error_msg)
    exit()

if interface == "vtnet0":
    disk = 'disk0 = "vtbd0"\ndisk1 = "vtbd1"\ndisk2 = "vtbd2"'
elif api == "1.0":
    disk = 'disk0 = "da0"\ndisk1 = "da1"\ndisk2 = "da2"'
else:
    disk = 'disk0 = "ada0"\ndisk1 = "ada1"\ndisk2 = "ada2"'

cfg_content = """#!/usr/bin/env python3.6

user = "root"
password = "%s"
ip = "%s"
default_api_url = 'http://' + ip + '/api/v%s'
api1_url = 'http://' + ip + '/api/v1.0'
api2_url = 'http://' + ip + '/api/v2.0'
interface = "%s"
ntpServer = "10.20.20.122"
localHome = "%s"
%s
keyPath = "%s"
results_xml = "%s"
""" % (passwd, ip, api, interface, localHome, disk, keyPath, results_xml)

cfg_file = open("auto_config.py", 'w')
cfg_file.writelines(cfg_content)
cfg_file.close()

from functions import setup_ssh_agent, create_key, add_ssh_key

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
    skip_tests = []

    if api == '1.0':
        skip_tests = ['bootenv', 'jails', 'alerts', 'smarttest']
        apidir = 'api1/'
        rv = ['network', 'ssh', 'storage']
    elif api == '2.0':
        apidir = 'api2/'
        rv = ['interfaces', 'network', 'ssh', 'volume']

    for filename in listdir(apidir):
        if filename.endswith('.py') and \
                not filename.startswith('__init__'):
            filename = re.sub('.py$', '', filename)
            if filename not in skip_tests and filename not in rv:
                rv.append(filename)
    return rv


if api == "1.0":
    for i in get_tests():
        if testName is not None and testName != i:
            continue
        call(["py.test-3.6", "-v", "--junitxml",
              f"{results_xml}{i}_tests_result.xml"] + (
                  ["-k", testexpr] if testexpr else []
        ) + [f"api1/{i}.py"])
elif api == "2.0":
    for i in get_tests():
        if testName is not None and testName != i:
            continue
        call(["py.test-3.6", "-v", "--junitxml",
              f"{results_xml}{i}_tests_result.xml"] + (
                  ["-k", testexpr] if testexpr else []
        ) + [f"api2/{i}.py"])
