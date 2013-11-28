from optparse import OptionParser
import atexit
import getopt
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


# The following script:
#   (1) sets up a tap interface
#   (2) associates the tap interface with a bridge
#
# This tap interface can be used by BHyve VMs. 

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

    setup_interface()

def setup_interface():
    global test_config
    global test_config_file

    euid = os.geteuid()
    if euid != 0:
        raise EnvironmentError, "this script need to be run as root"
        sys.exit()

    print "Setting up %s with %s, using %s" % \
        (test_config["tap"], test_config["interface"], test_config["bridge"])
    os.system("ifconfig %s create" % (test_config["bridge"]))
    os.system("ifconfig %s create" % (test_config["tap"]) )
    os.system("ifconfig %s addm %s addm %s up" %
                  (test_config["bridge"], test_config["interface"], test_config["tap"]))
    os.system("sysctl net.link.tap.user_open=1")
    os.system("sysctl net.link.tap.up_on_open=1") 

if __name__ == "__main__":
    main(sys.argv)

