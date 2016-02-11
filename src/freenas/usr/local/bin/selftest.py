#!/usr/local/bin/python
from __future__ import print_function

import os, sys

sys.path.extend(["/usr/local/www", "/usr/local/www/freenasUI"])

import system.ixselftests as SelfTests
from system.ixselftests.TestStatus import TestStatus

def main(argv):
    import getopt
    
    def usage():
        print("usage: %s [-h|--help] [-v|--verbose] [-a|--alert] [test [...]]" % sys.argv[0],
              file=sys.stderr)
        print("\tAvailable tests:  %s" % ", ".join(SelfTests.Tests()), file=sys.stderr)

        sys.exit(1)
        
    long_options = [
        "help",
        "verbose",
        "alert",
    ]
    short_options = "hva"

    try:
        opts, args = getopt.getopt(argv, short_options, long_options)
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit(2)
        
    verbose = False
    alert = False
    
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-v', '--verbose'):
            verbose = True
        elif o in ('-a', '--alert'):
            alert = True
        else:
            usage()

    if len(args) == 0:
        tests = SelfTests.Tests()
    else:
        tests = args

    handler = TestStatus(verbose = verbose, alert = alert)

    for test in tests:
        SelfTests.RunTest(test, handler)

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
