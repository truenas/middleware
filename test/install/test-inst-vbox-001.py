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

# ISO_IMAGE=$1
# 
# if [ -z "$ISO_IMAGE" ]; then
#    echo "Usage: "
#    echo    $0 "[ISO file]"
#    exit 1
# fi
# 
# set -e
# 
# ifconfig tap0
# ifconfig bridge0
# 
# VBOX_FOLDER=`VBoxManage list systemproperties | grep  "Default machine folder" | sed -e 's/^.*://' -e 's/^[[:space:]]*//'`
# 
# VBoxManage unregistervm --delete Test1
# rm -fr "$VBOX_FOLDER/Test1"
# VBoxManage createvm --name "Test1" --ostype FreeBSD_64 --register
# VBoxManage createhd --filename "$VBOX_FOLDER/Test1/disk.vdi"  --size 90000 --format VDI
# 
# VBoxManage modifyvm Test1 --cpus 2 --memory 4000 --hpet on --ioapic on --nic1 bridged --bridgeadapter1 tap0
# 
# VBoxManage storagectl Test1 --name PIIX4 --add ide --controller PIIX4
# VBoxManage storageattach Test1 --storagectl PIIX4 --port 0 --device 0 --type hdd --medium "${VBOX_FOLDER}/Test1/disk.vdi"
# VBoxManage storageattach Test1 --storagectl PIIX4 --port 1 --device 0 --type dvddrive --medium "$ISO_IMAGE"
# 
# VBoxManage startvm Test1

def runTest():
    global test_config
    global test_config_file
    global sentinel_file

    ret = os.system("ifconfig %s" % test_config['tap'])
    if ret != 0:
        exit(1)

    ret = os.system("ifconfig %s" % test_config['bridge'])
    if ret != 0:
        exit(1)


    proc = subprocess.Popen('VBoxManage list systemproperties | grep  "Default machine folder" | sed -e "s/^.*://" -e "s/^[[:space:]]*//"', stdout=subprocess.PIPE, shell=True)
    (VBOX_FOLDER, err) = proc.communicate()
    VBOX_FOLDER = VBOX_FOLDER.rstrip()

    cmd = "VBoxManage unregistervm --delete %s" % test_config['vm_name']
    print cmd 
    os.system(cmd)
    cmd = 'rm -fr "%s/%s"' % (VBOX_FOLDER,  test_config['vm_name'])
    print cmd 
    os.system(cmd)
    cmd = "VBoxManage createvm --name %s --ostype FreeBSD_64 --register" % test_config['vm_name']
    print cmd 
    os.system(cmd)
    cmd = 'VBoxManage createhd --filename "%s/%s/disk.vdi"  --size 90000 --format VDI' % (VBOX_FOLDER, test_config['vm_name'])
    print cmd 
    os.system(cmd)
    cmd = 'VBoxManage modifyvm %s --cpus 2 --memory 4000 --hpet on --ioapic on --nic1 bridged --bridgeadapter1 tap0' % test_config['vm_name']
    print cmd 
    os.system(cmd)
    cmd = 'VBoxManage storagectl %s --name PIIX4 --add ide --controller PIIX4' % test_config['vm_name']
    print cmd 
    os.system(cmd)
    cmd = 'VBoxManage storageattach %s --storagectl PIIX4 --port 0 --device 0 --type hdd --medium "%s/%s/disk.vdi"' % (test_config['vm_name'], VBOX_FOLDER, test_config['vm_name'])
    print cmd 
    os.system(cmd)
    cmd = 'VBoxManage storageattach %s --storagectl PIIX4 --port 1 --device 0 --type dvddrive --medium "%s"' % (test_config['vm_name'], test_config['iso'])
    print cmd 
    os.system(cmd)
    cmd = 'VBoxManage startvm %s' % test_config['vm_name']
    print cmd 
    os.system(cmd)


def cleanup():
    os.system("rm -f %s" % (sentinel_file))

if __name__ == "__main__":
    atexit.register(cleanup)
    main(sys.argv)
