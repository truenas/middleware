# INSTALL TEST WITH VIRTUALBOX
#
# The following test:
#   (1) takes an ISO image
#   (2) installs it into a disk image
#   (3) boots the disk image
#

from optparse import OptionParser
import atexit
import getopt
import json
import os
import sys
import subprocess
import tempfile
import time

# Escape codes for cursor movements.
# XXX: I'm not sure this is the best way to deal with this.
cursor_up = '\x1b[A'
cursor_down = '\x1b[B'
cursor_right = '\x1b[C'
cursor_left = '\x1b[D'

test_config = None
test_config_file = None
sentinel_file = None

def usage(argv):
    print "Usage:"
    print "    %s -f [JSON config file]" % argv[0]


def main(argv):

    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:")
    except getopt.GetoptError as err:
        sys.exit(2)

    global test_config
    global test_config_file

    for o, a in opts:
        if o == "-f":
            test_config_file = a
        else:
            assert False, "unhandled option"

    if test_config_file is None:
        usage(argv)
        sys.exit(1)

    config_file = open(test_config_file, "r")
    test_config = json.load(config_file)
    config_file.close()
    runTest()

def runTest():
    global test_config
    global test_config_file
    global sentinel_file

    ret = os.system("ifconfig %s" % test_config['tap'])
    if ret != 0:
        print "Run setup-tap.py script to set up tap and bridge devices"
        exit(1)

    ret = os.system("ifconfig %s" % test_config['bridge'])
    if ret != 0:
        print "Run setup-tap.py script to set up tap and bridge devices"
        exit(1)


    proc = subprocess.Popen('VBoxManage list systemproperties | grep  "Default machine folder" | sed -e "s/^.*://" -e "s/^[[:space:]]*//"', stdout=subprocess.PIPE, shell=True)
    (VBOX_FOLDER, err) = proc.communicate()
    VBOX_FOLDER = VBOX_FOLDER.rstrip()

    cmd = "VBoxManage unregistervm --delete %s" % test_config['vm_name']
    print cmd 
    os.system(cmd)
    cmd = 'rm -fr "%s/%s"' % (VBOX_FOLDER,  test_config['vm_name'])
    print cmd 
    ret = os.system(cmd)
    cmd = "VBoxManage createvm --name %s --ostype FreeBSD_64 --register" % test_config['vm_name']
    if ret != 0:
        sys.exit(ret)

    print cmd 
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(ret)

    for d in test_config['disks']:
        cmd = "rm -f %s" % d
        print cmd
        os.system(cmd)
        cmd = 'VBoxManage createhd --filename "%s"  --size 90000 --format VDI' % d
        print cmd 
        os.system(cmd)

    macaddress = ""
    if test_config.has_key('mac'):
        macaddress = "--macaddress1 %s" % test_config['mac'].replace(":", "")

    cmd = 'VBoxManage modifyvm %s --cpus 2 --memory 4000 --hpet on --ioapic on --nic1 bridged --bridgeadapter1 %s %s' % (test_config['vm_name'], test_config['tap'], macaddress)
    print cmd 
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(ret)

    cmd = 'VBoxManage storagectl %s --name SATA --add sata --controller IntelAHCI' % test_config['vm_name']
    print cmd 
    ret = os.system(cmd)
    cmd = 'VBoxManage storageattach %s --storagectl SATA --port 0 --device 0 --type dvddrive --medium "%s"' % (test_config['vm_name'], test_config['iso'])
    if ret != 0:
        sys.exit(ret)

    print cmd 
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(ret)



    port = 1
    for d in test_config['disks']:
        cmd = 'VBoxManage storageattach %s --storagectl SATA --port %d --device 0 --type hdd --medium "%s"' % (test_config['vm_name'], port, d)
        print cmd 
        os.system(cmd)
        port = port + 1

    cmd = 'VBoxManage startvm %s' % test_config['vm_name']
    print cmd 
    os.system(cmd)


def cleanup():
    os.system("rm -f %s" % (sentinel_file))

if __name__ == "__main__":
    atexit.register(cleanup)
    main(sys.argv)
