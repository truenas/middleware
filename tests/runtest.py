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
    call(["py.test-3.6", "--junitxml",
          "%screate_network_result.xml" % results_xml,
          "api1/network.py"])
    if testName != 'network':
        call(["py.test-3.6", "--junitxml",
              "%sssh_result.xml" % results_xml,
              "api1/ssh.py"])
        call(["py.test-3.6", "--junitxml",
              "%sstorage_result.xml" % results_xml,
              "api1/storage.py"])
        call(["py.test-3.6", "--junitxml",
              "%sntp_result.xml" % results_xml,
              "api1/ntp.py"])
        call(["py.test-3.6", "--junitxml",
              "%sad_bsd_result.xml" % results_xml,
              "api1/ad_bsd.py"])
        call(["py.test-3.6", "--junitxml",
              "%sad_osx_result.xml" % results_xml,
              "api1/ad_osx.py"])
        call(["py.test-3.6", "--junitxml",
              "%safp_osx_result.xml" % results_xml,
              "api1/afp_osx.py"])
        call(["py.test-3.6", "--junitxml",
              "%salerts_result.xml" % results_xml,
              "api1/alerts.py"])
        call(["py.test-3.6", "--junitxml",
              "%sbootenv_result.xml" % results_xml,
              "api1/bootenv.py"])
        call(["py.test-3.6", "--junitxml",
              "%scronjob_result.xml" % results_xml,
              "api1/cronjob.py"])
        # call(["python3.6", "api1/debug.py"])
        call(["py.test-3.6", "--junitxml",
              "%sdomaincontroller_result.xml" % results_xml,
              "api1/domaincontroller.py"])
        call(["py.test-3.6", "--junitxml",
              "%sdyndns_result.xml" % results_xml,
              "api1/dyndns.py"])
        call(["py.test-3.6", "--junitxml",
              "%semails_result.xml" % results_xml,
              "api1/emails.py"])
        call(["py.test-3.6", "--junitxml",
              "%suser_result.xml" % results_xml,
              "api1/user.py"])
        call(["py.test-3.6", "--junitxml",
              "%sftp_result.xml" % results_xml,
              "api1/ftp.py"])
        call(["py.test-3.6", "--junitxml",
              "%sgroup_result.xml" % results_xml,
              "api1/group.py"])
        call(["py.test-3.6", "--junitxml",
              "%siscsi_result.xml" % results_xml,
              "api1/iscsi.py"])
        # jails API Broken
        call(["py.test-3.6", "--junitxml",
              "%sjails_result.xml" % results_xml,
              "api1/jails.py"])
        call(["py.test-3.6", "--junitxml",
              "%sldap_bsd_result.xml" % results_xml,
              "api1/ldap_bsd.py"])
        call(["py.test-3.6", "--junitxml",
              "%sldap_osx_result.xml" % results_xml,
              "api1/ldap_osx.py"])
        call(["py.test-3.6", "--junitxml",
              "%slldp_result.xml" % results_xml,
              "api1/lldp.py"])
        call(["py.test-3.6", "--junitxml",
              "%snfs_result.xml" % results_xml,
              "api1/nfs.py"])
        call(["py.test-3.6", "--junitxml",
              "%snis_bsd_result.xml" % results_xml,
              "api1/nis_bsd.py"])
        call(["py.test-3.6", "--junitxml",
              "%srsync_result.xml" % results_xml,
              "api1/rsync.py"])
        # call(["python3.6", "api1/smarttest.py"])
        call(["py.test-3.6", "--junitxml",
              "%ssmb_bsd_result.xml" % results_xml,
              "api1/smb_bsd.py"])
        call(["py.test-3.6", "--junitxml",
              "%ssmb_osx_result.xml" % results_xml,
              "api1/smb_osx.py"])
        call(["py.test-3.6", "--junitxml",
              "%ssnmp_result.xml" % results_xml,
              "api1/snmp.py"])
        call(["py.test-3.6", "--junitxml",
              "%ssystem_result.xml" % results_xml,
              "api1/system.py"])
        call(["py.test-3.6", "--junitxml",
              "%stftp_result.xml" % results_xml,
              "api1/tftp.py"])
        call(["py.test-3.6", "--junitxml",
              "%sups_result.xml" % results_xml,
              "api1/ups.py"])
        call(["py.test-3.6", "--junitxml",
              "%swebdav_bsd_result.xml" % results_xml,
              "api1/webdav_bsd.py"])
        call(["py.test-3.6", "--junitxml",
              "%swebdav_osx_result.xml" % results_xml,
              "api1/webdav_osx.py"])

        # Update test
        call(["py.test-3.6", "--junitxml",
              "%supdate_bootenv_result.xml" % results_xml,
              "api1/update/bootenv.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_cronjob_result.xml" % results_xml,
              "api1/update/cronjob.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_ftp_result.xml" % results_xml,
              "api1/update/ftp.py"])
        # call(["python3.6", "api1/update/group.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_nfs_result.xml" % results_xml,
              "api1/update/nfs.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_rsync_result.xml" % results_xml,
              "api1/update/rsync.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_storage_result.xml" % results_xml,
              "api1/update/storage.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_user_result.xml" % results_xml,
              "api1/update/user.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_webdav_bsd_result.xml" % results_xml,
              "api1/update/webdav_bsd.py"])
        call(["py.test-3.6", "--junitxml",
              "%supdate_webdav_osx_result.xml" % results_xml,
              "api1/update/webdav_osx.py"])

        # Delete test
        call(["py.test-3.6", "--junitxml",
              "%sdelete_bootenv_result.xml" % results_xml,
              "api1/delete/bootenv.py"])
        call(["py.test-3.6", "--junitxml",
              "%sdelete_cronjob_result.xml" % results_xml,
              "api1/delete/cronjob.py"])
        # call(["python3.6", "api1/delete/group.py"])
        call(["py.test-3.6", "--junitxml",
              "%sdelete_storage_result.xml" % results_xml,
              "api1/delete/storage.py"])
        call(["py.test-3.6", "--junitxml",
              "%sdelete_user_result.xml" % results_xml,
              "api1/delete/user.py"])
elif api == "2.0":
    call(["py.test-3.6", "--junitxml",
          "%sinterfaces_test_result.xml" % results_xml,
          "api2/interfaces.py"])
    call(["py.test-3.6", "--junitxml",
          "%snetwork_user_result.xml" % results_xml,
          "api2/network.py"])
    call(["py.test-3.6", "--junitxml",
          "%sdisk_test_result.xml" % results_xml,
          "api2/disk.py"])
