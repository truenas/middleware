#!/usr/local/bin/python

import getopt
import logging
import logging.config
import os
import sys


def main():
    def usage():
        print >> sys.stderr, "Usage: %s [-R root] [-M manifest_file] <cmd>, where cmd is one of:" % sys.argv[0]
        print >> sys.stderr, "\tcheck\tCheck for updates"
        print >> sys.stderr, "\tupdate\tDo an update"
        print >> sys.stderr, "\tinstall\tInstall"
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "qvdR:M:T:")
    except getopt.GetoptError as err:
        print str(err)
        usage()

    root = None
    manifile = None
    verbose = 0
    debug = 0
    tmpdir = None
    config_file = None
    config = None

    for o, a in opts:
        if o == "-v":
            verbose += 1
        elif o == "-q":
            quiet = True
        elif o == "-d":
            debug += 1
        elif o == "-R":
            root = a
        elif o == "-M":
            manifile = a
        elif o == '-C':
            config_file = a
        elif o == "-T":
            tmpdir = a
        else:
            assert False, "unhandled option"

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'simple': {
                'format': '[%(name)s:%(lineno)s] %(message)s',
            },
        },
        'handlers': {
            'std': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'stream': 'ext://sys.stdout',
            },
        },
        'loggers': {
            '': {
                'handlers': ['std'],
                'level': 'DEBUG',
                    'propagate': True,
            },
        },
    })

    sys.path.append("/usr/local/lib")

    import freenasOS.Configuration as Configuration
    from freenasOS.Update import CheckForUpdates, Update

    if root is not None and os.path.isdir(root) is False:
        print >> sys.stderr, "Specified root (%s) does not exist" % root
        sys.exit(1)

    if config_file is not None:
        # We want the system configuration file
        config = Configuration.Configuration(file = config_file, root = None)

    if len(args) != 1:
        usage()

    if args[0] == "check":
        def Handler(op, pkg, old):
            if op == "upgrade":
                print "%s:  %s -> %s" % (pkg.Name(), old.Version(), pkg.Version())
            else:
                print "%s:  %s %s" % (pkg.Name(), op, pkg.Version())
                
        if verbose > 0 or debug > 0:
            pfcn = Handler
        else:
            pfcn = None
        try:
            update = CheckForUpdates(root, pfcn)
        except ValueError:
            print >> sys.stderr, "No manifest found"
            return 1
        if update is not None:
            print >> sys.stderr, "Newer manifest found"
            return 0
        else:
            print >> sys.stderr, "No newer manifest found"
            return 1
    elif args[0] == "update":
        r = Update(root, config)
        if r:
            return 0
        else:
            return 1
    else:
        usage()

if __name__ == "__main__":
    sys.exit(main())

