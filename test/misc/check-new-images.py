from optparse import OptionParser
import atexit
import getopt
import glob
import json
import os
import pexpect
import sys
import subprocess
import tempfile
import time

# 
# (1)  Parse a JSON config file
# (2)  Look for the "upgrade_file" and "iso" parameters
# (3)  Take the dirname of the above parameters.  Look in that directory, and see
#      if there is a newer GUI_Upgrade.txz or .iso file
# (4)  If there is a newer file, write out an "updated" file.  This
#      signals that a newer image is available for test of upgrade.
test_config = None
test_config_file = None

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
    os.system("rm -f %s.updated" % (test_config_file))

    find_images()


def find_images():
    global test_config
    global test_config_file

    update_config_file = False

    iso = ""
    if test_config.has_key('iso'):
        iso = test_config['iso']

    upgrade_file = ""
    if test_config.has_key('upgrade_file'):
        upgrade_file = test_config['upgrade_file']
    
    iso_dirname = os.path.dirname(iso)
    upgrade_file_dirname = os.path.dirname(upgrade_file)

    new_iso=""
    new_upgrade_file = ""
    l = glob.glob('%s/*.iso' % (iso_dirname))
    for i in l:
        new_iso = i
        break

    l = glob.glob('%s/*.GUI_Upgrade*.txz' % (upgrade_file_dirname))
    for i in l:
        new_upgrade_file = i
        break

    if iso != new_iso: 
        test_config['iso'] = new_iso
        update_config_file = True

    if upgrade_file != new_upgrade_file:
        test_config['upgrade_file'] = new_upgrade_file
        update_config_file = True

    if not update_config_file:
       return

    with open(test_config_file, 'w') as outfile:
        json.dump(test_config, outfile, indent=4)
        outfile.close()

    os.system("touch %s.updated" % (test_config_file))


if __name__ == "__main__":
    main(sys.argv)
