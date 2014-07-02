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

    dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.dirname(dir)

    os.system("python %s/misc/check-new-images.py -f %s" % (test_dir, test_config_file))
    if os.path.exists("%s.updated" % (test_config_file)):
        print("Newer file exists, performing upgrade")
        os.system("%s/misc/run-headless.sh python %s/ui/test-upgrade-gui-001.py -f %s" % (test_dir, test_dir, test_config_file))
    else:
        print("File has not changed, skipping upgrade")

if __name__ == "__main__":
    main(sys.argv)
