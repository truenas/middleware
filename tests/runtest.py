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

try:
    import xmlrunner
except ImportError:
    cmd = "pip-3.6 install unittest-xml-reporting"
    call(cmd, shell=True)

results_xml = getcwd() + '/results/'
localHome = path.expanduser('~')
dotsshPath = localHome + '/.ssh'
keyPath = localHome + '/.ssh/test_id_rsa'

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
    myopts, args = getopt.getopt(argv[1:], 'aipIt', ["api=", "ip=", "password=",
                                                     "interface=", 'test='])
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

if interface == "vtnet0":
    disk = 'disk1 = "vtbd1"\ndisk2 = "vtbd2"'
else:
    disk = 'disk1 "da1"\ndisk2 = "da2"'

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
    # Create test
    call(["python3.6", "api1/create/network.py"])
    if testName != 'network':
        call(["python3.6", "api1/create/ssh.py"])
        call(["python3.6", "api1/create/storage.py"])
        call(["python3.6", "api1/create/ntp.py"])
        call(["python3.6", "api1/create/ad_bsd.py"])
        call(["python3.6", "api1/create/ad_osx.py"])
        call(["python3.6", "api1/create/afp_osx.py"])
        # call(["python3.6", "api1/create/alerts.py"])
        call(["python3.6", "api1/create/bootenv.py"])
        call(["python3.6", "api1/create/cronjob.py"])
        # call(["python3.6", "api1/create/debug.py"])
        call(["python3.6", "api1/create/emails.py"])
        call(["python3.6", "api1/create/domaincontroller.py"])
        call(["python3.6", "api1/create/user.py"])
        call(["python3.6", "api1/create/ftp.py"])
        call(["python3.6", "api1/create/group.py"])
        call(["python3.6", "api1/create/iscsi.py"])
        # jails API Broken
        # call(["python3.6", "api1/create/jails.py"])
        call(["python3.6", "api1/create/ldap_bsd.py"])
        call(["python3.6", "api1/create/ldap_osx.py"])
        call(["python3.6", "api1/create/lldp.py"])
        call(["python3.6", "api1/create/nfs.py"])
        call(["python3.6", "api1/create/rsync.py"])
        # call(["python3.6", "api1/create/smarttest.py"])
        call(["python3.6", "api1/create/smb_bsd.py"])
        call(["python3.6", "api1/create/smb_osx.py"])
        call(["python3.6", "api1/create/snmp.py"])
        call(["python3.6", "api1/create/system.py"])
        call(["python3.6", "api1/create/tftp.py"])
        call(["python3.6", "api1/create/ups.py"])
        call(["python3.6", "api1/create/webdav_bsd.py"])
        call(["python3.6", "api1/create/webdav_osx.py"])

        # Update test
        call(["python3.6", "api1/update/ad_bsd.py"])
        call(["python3.6", "api1/update/ad_osx.py"])
        call(["python3.6", "api1/update/afp_osx.py"])
        # call(["python3.6", "api1/update/alerts.py]"])
        call(["python3.6", "api1/update/bootenv.py"])
        call(["python3.6", "api1/update/cronjob.py"])
        call(["python3.6", "api1/update/ftp.py"])
        # call(["python3.6", "api1/update/group.py"])
        call(["python3.6", "api1/update/iscsi.py"])
        call(["python3.6", "api1/update/ldap_bsd.py"])
        call(["python3.6", "api1/update/ldap_osx.py"])
        call(["python3.6", "api1/update/nfs.py"])
        call(["python3.6", "api1/update/rsync.py"])
        call(["python3.6", "api1/update/smb_bsd.py"])
        call(["python3.6", "api1/update/smb_osx.py"])
        call(["python3.6", "api1/update/storage.py"])
        call(["python3.6", "api1/update/user.py"])
        call(["python3.6", "api1/update/webdav_bsd.py"])
        call(["python3.6", "api1/update/webdav_osx.py"])

        # Delete test
        call(["python3.6", "api1/delete/bootenv.py"])
        call(["python3.6", "api1/delete/cronjob.py"])
        # call(["python3.6", "api1/delete/group.py"])
        call(["python3.6", "api1/delete/iscsi.py"])
        # call(["python3.6", "api1/delete/rsync.py"])
        call(["python3.6", "api1/delete/storage.py"])
        call(["python3.6", "api1/delete/user.py"])
elif api == "2.0":
    call(["python3.6", "api2/interfaces.py"])
    call(["python3.6", "api2/network.py"])
    call(["python3.6", "api2/disk.py"])
