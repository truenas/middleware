#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

from subprocess import call
from sys import argv
from os import path, getcwd, makedirs
import getopt
import sys

apifolder = getcwd()
sys.path.append(apifolder)

results_xml = getcwd() + '/results/'
localHome = path.expanduser('~')
dotsshPath = localHome + '/.ssh'
keyPath = localHome + '/.ssh/test_id_rsa'

ixautomationdotconfurl = "https://raw.githubusercontent.com/iXsystems/"
ixautomationdotconfurl += "ixautomation/master/src/etc/ixautomation.conf.dist"
config_file_msg = "Pleale add config.py to freenas/tests witch can be empty or"
config_file_msg += "contain setting from %s" % ixautomationdotconfurl

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

# look if all the argument are there.
try:
    myopts, args = getopt.getopt(argv[1:], 'aipIt', ["api=", "ip=",
                                                     "password=", "interface=",
                                                     'test='])
except getopt.GetoptError as e:
    print(str(e))
    print(error_msg)
    exit()

testName = None
api = "1.0"

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
        print(api)

if 'ip' not in locals() and 'password' not in locals() and 'interface' not in locals():
    print("Mandatory option missing!\n")
    print(error_msg)
    exit()

if interface == "vtnet0":
    disk = 'disk1 = "vtbd1"\ndisk2 = "vtbd2"'
else:
    disk = 'disk1 = "da1"\ndisk2 = "da2"'

cfg_content = """#!/usr/bin/env python3.6

user = "root"
password = "%s"
ip = "%s"
freenas_url = 'http://' + ip + '/api/v%s'
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

if api == "1.0":
    for i in (
        'network',
        'ssh',
        'storage',
        'ntp',
        'ad_bsd',
        'ad_osx',
        'afp_osx',
        'alerts',
        #'bootenv',
        'cronjob',
        'domaincontroller',
        'dyndns',
        'emails',
        'user',
        'ftp',
        'group',
        'iscsi',
        'jails',  # jails API Broken
        'ldap_bsd',
        'ldap_osx',
        'lldp',
        'nfs',
        'nis_bsd',
        'rsync',
        'smb_bsd',
        'smb_osx',
        'snmp',
        'system',
        'tftp',
        'ups',
        'webdav_bsd',
        'webdav_osx',
    ):
        if testName is not None and testName != i:
            continue
        call(["py.test-3.6", "-v", "--junitxml",
              f"{results_xml}{i}_tests_result.xml",
              f"api1/{i}.py"])
elif api == "2.0":
    for i in (
        'interfaces',
        'network',
        'disk',
        'mail',
        'ftp',
        'ssh',
        #'domaincontroller',
        'user',
        'group',
        'nfs',
        'lldp',
    ):
        if testName is not None and testName != i:
            continue
        call(["py.test-3.6", "-v", "--junitxml",
              f"{results_xml}{i}_tests_result.xml",
              f"api2/{i}.py"])
