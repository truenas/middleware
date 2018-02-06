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
    --ip <###.###.###.###>     - IP of the FreeNAS
    --password <root password> - Password of the FreeNAS root user
    --interface <interface>    - The interface that FreeNAS is run one
    """ % argv[0]

# if have no argumment stop
if len(argv) == 1:
    print(error_msg)
    exit()

# look if all the argument are there.
try:
    myopts, args = getopt.getopt(argv[1:], 'ipI', ["ip=",
                                                   "password=", "interface="])
except getopt.GetoptError as e:
    print(str(e))
    print(error_msg)
    exit()

for output, arg in myopts:
    if output in ('-i', '--ip'):
        ip = arg
    elif output in ('-p', '--password'):
        passwd = arg
    elif output in ('-I', '--interface'):
        interface = arg

cfg_content = """#!/usr/bin/env python3.6

import os

user = "root"
password = "%s"
ip = "%s"
freenas_url = 'http://' + ip + '/api/v1.0'
interface = "%s"
ntpServer = "10.20.20.122"
localHome = "%s"
disk1 = "vtbd1"
disk2 = "vtbd2"
#disk1 = "da1"
#disk2 = "da2"
keyPath = "%s"
results_xml = "%s"
""" % (passwd, ip, interface, localHome, keyPath, results_xml)

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

# Create test
call(["python3.6", "create/network.py"])
call(["python3.6", "create/ssh.py"])
call(["python3.6", "create/storage.py"])
call(["python3.6", "create/ntp.py"])
call(["python3.6", "create/ad_bsd.py"])
call(["python3.6", "create/ad_osx.py"])
call(["python3.6", "create/afp_osx.py"])
# call(["python3.6", "create/alerts.py"])
call(["python3.6", "create/bootenv.py"])
call(["python3.6", "create/cronjob.py"])
# call(["python3.6", "create/debug.py"])
call(["python3.6", "create/emails.py"])
call(["python3.6", "create/domaincontroller.py"])
call(["python3.6", "create/user.py"])
call(["python3.6", "create/ftp.py"])
call(["python3.6", "create/group.py"])
call(["python3.6", "create/iscsi.py"])
# jails API Broken
# call(["python3.6", "create/jails.py"])
call(["python3.6", "create/ldap_bsd.py"])
call(["python3.6", "create/ldap_osx.py"])
call(["python3.6", "create/lldp.py"])
call(["python3.6", "create/nfs.py"])
call(["python3.6", "create/rsync.py"])
# call(["python3.6", "create/smarttest.py"])
call(["python3.6", "create/smb_bsd.py"])
call(["python3.6", "create/smb_osx.py"])
call(["python3.6", "create/snmp.py"])
call(["python3.6", "create/system.py"])
call(["python3.6", "create/tftp.py"])
call(["python3.6", "create/ups.py"])
call(["python3.6", "create/webdav_bsd.py"])
call(["python3.6", "create/webdav_osx.py"])

# Update test
call(["python3.6", "update/ad_bsd.py"])
call(["python3.6", "update/ad_osx.py"])
call(["python3.6", "update/afp_osx.py"])
# call(["python3.6", "update/alerts.py]"])
call(["python3.6", "update/bootenv.py"])
call(["python3.6", "update/cronjob.py"])
call(["python3.6", "update/ftp.py"])
# call(["python3.6", "update/group.py"])
call(["python3.6", "update/iscsi.py"])
call(["python3.6", "update/ldap_bsd.py"])
call(["python3.6", "update/ldap_osx.py"])
call(["python3.6", "update/nfs.py"])
call(["python3.6", "update/rsync.py"])
call(["python3.6", "update/smb_bsd.py"])
call(["python3.6", "update/smb_osx.py"])
call(["python3.6", "update/storage.py"])
call(["python3.6", "update/user.py"])
call(["python3.6", "update/webdav_bsd.py"])
call(["python3.6", "update/webdav_osx.py"])

# Delete test
call(["python3.6", "delete/bootenv.py"])
call(["python3.6", "delete/cronjob.py"])
# call(["python3.6", "delete/group.py"])
call(["python3.6", "delete/iscsi.py"])
# call(["python3.6", "delete/rsync.py"])
call(["python3.6", "delete/storage.py"])
call(["python3.6", "delete/user.py"])
