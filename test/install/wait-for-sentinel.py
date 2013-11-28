from optparse import OptionParser
import atexit
import getopt
import json
import os
import sys
import subprocess
import tempfile
import time

test_config = None
test_config_file = None
sentinel_file = None

def usage(argv):
    print "Usage:"
    print "    %s -f [JSON config file]" % argv[0]


# The following test
#   (1) reads a json file specified by the -f flag.
#   (2) waits for a sentinel file to exit 

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

    runTest()

def runTest():
    while True:
        config_file = open(test_config_file, "r")
        test_config = json.load(config_file)
        config_file.close()
        time.sleep(1)
        if os.path.exists(test_config['sentinel_file']):
            break


def checkpreReqBhyve():
    # Check if Bhyve module is loaded, and if we ran the script as superuser.
    # If not, silently kill the application.
    # XXX: Maybe this should not be so silent?
    euid = os.geteuid()
    if euid != 0:
        raise EnvironmentError, "this script need to be run as root"
        sys.exit()
    ret = os.system("kldload -n vmm")
    if ret != 0:
        raise EnvironmentError, "missing vmm.ko"
        sys.exit()
    ret = os.system("kldload -n if_tap")
    if ret != 0:
        raise EnvironmentError, "missing if_tap.ko"
        sys.exit()

def cleanup():
    os.system("rm -f %s" % (sentinel_file))

if __name__ == "__main__":
    atexit.register(cleanup)
    main(sys.argv)
