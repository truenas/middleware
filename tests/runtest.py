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
    call(["py.test-3.6", "-v", "--junitxml",
          "%snetwork_tests_result.xml" % results_xml,
          "api1/network.py"])
    if testName != 'network':
        call(["py.test-3.6", "-v", "--junitxml",
              "%sssh_tests_result.xml" % results_xml,
              "api1/ssh.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sstorage_tests_result.xml" % results_xml,
              "api1/storage.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sntp_tests_result.xml" % results_xml,
              "api1/ntp.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sad_bsd_tests_result.xml" % results_xml,
              "api1/ad_bsd.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sad_osx_tests_result.xml" % results_xml,
              "api1/ad_osx.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%safp_osx_tests_result.xml" % results_xml,
              "api1/afp_osx.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%salerts_tests_result.xml" % results_xml,
              "api1/alerts.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sbootenv_tests_result.xml" % results_xml,
              "api1/bootenv.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%scronjob_tests_result.xml" % results_xml,
              "api1/cronjob.py"])
        # call(["python3.6", "api1/debug.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sdomaincontroller_tests_result.xml" % results_xml,
              "api1/domaincontroller.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sdyndns_tests_result.xml" % results_xml,
              "api1/dyndns.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%semails_tests_result.xml" % results_xml,
              "api1/emails.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%suser_tests_result.xml" % results_xml,
              "api1/user.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sftp_tests_result.xml" % results_xml,
              "api1/ftp.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sgroup_tests_result.xml" % results_xml,
              "api1/group.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%siscsi_tests_result.xml" % results_xml,
              "api1/iscsi.py"])
        # jails API Broken
        call(["py.test-3.6", "-v", "--junitxml",
              "%sjails_tests_result.xml" % results_xml,
              "api1/jails.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sldap_bsd_tests_result.xml" % results_xml,
              "api1/ldap_bsd.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sldap_osx_tests_result.xml" % results_xml,
              "api1/ldap_osx.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%slldp_tests_result.xml" % results_xml,
              "api1/lldp.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%snfs_tests_result.xml" % results_xml,
              "api1/nfs.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%snis_bsd_tests_result.xml" % results_xml,
              "api1/nis_bsd.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%srsync_tests_result.xml" % results_xml,
              "api1/rsync.py"])
        # call(["python3.6", "api1/smarttest.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%ssmb_bsd_tests_result.xml" % results_xml,
              "api1/smb_bsd.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%ssmb_osx_tests_result.xml" % results_xml,
              "api1/smb_osx.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%ssnmp_tests_result.xml" % results_xml,
              "api1/snmp.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%ssystem_tests_result.xml" % results_xml,
              "api1/system.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%stftp_tests_result.xml" % results_xml,
              "api1/tftp.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%sups_tests_result.xml" % results_xml,
              "api1/ups.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%swebdav_bsd_tests_result.xml" % results_xml,
              "api1/webdav_bsd.py"])
        call(["py.test-3.6", "-v", "--junitxml",
              "%swebdav_osx_tests_result.xml" % results_xml,
              "api1/webdav_osx.py"])
elif api == "2.0":
    call(["py.test-3.6", "-v", "--junitxml",
          "%sinterfaces_tests_result.xml" % results_xml,
          "api2/interfaces.py"])
    call(["py.test-3.6", "-v", "--junitxml",
          "%snetwork_tests_result.xml" % results_xml,
          "api2/network.py"])
    call(["py.test-3.6", "-v", "--junitxml",
          "%sdisk_tests_result.xml" % results_xml,
          "api2/disk.py"])
    call(["py.test-3.6", "-v", "--junitxml",
          "%sftp_tests_result.xml" % results_xml,
          "api2/ftp.py"])
    call(["py.test-3.6", "-v", "--junitxml",
          "%sssh_tests_result.xml" % results_xml,
          "api2/ssh.py"])
