#!/usr/local/bin/python

import getopt
import logging
import logging.config
import os
import sys
import tempfile

def main():
    global log
    def usage():
        print >> sys.stderr, """Usage: %s [-C cache_dir] [-d] [-T train] [-v] <cmd>, where cmd is one of:
        check\tCheck for updates
        update\tDo an update""" % sys.argv[0]
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "C:dT:v")
    except getopt.GetoptError as err:
        print str(err)
        usage()

    verbose = False
    debug = 0
    config = None
    cache_dir = None
    train = None

    for o, a in opts:
        if o == "-v":
            verbose = True
        elif o == "-d":
            debug += 1
        elif o == '-C':
            cache_dir = a
        elif o == "-T":
            train = a
        elif o == '-c':
            cachedir = a
        else:
            assert False, "unhandled option %s" % o

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

    log = logging.getLogger('freenas-update')

    sys.path.append("/usr/local/lib")

    import freenasOS.Configuration as Configuration
    import freenasOS.Manifest as Manifest
    import freenasOS.Update as Update

    config = Configuration.Configuration()
    if train is None:
        train = config.SystemManifest().Train()

    if len(args) != 1:
        usage()

    if args[0] == "check":
        # To see if we have an update available, we
        # call Update.DownloadUpdate.  If we have been
        # given a cache directory, we pass that in; otherwise,
        # we make a temporary directory and use that.  We
        # have to clean up afterwards in that case.
        
        if cache_dir is None:
            download_dir = tempfile.mkdtemp(prefix = "UpdateCheck-", dir = config.TemporaryDirectory())
            if download_dir is None:
                print >> sys.stderr, "Unable to create temporary directory"
                sys.exit(1)
        else:
            download_dir = cache_dir

        rv = Update.DownloadUpdate(train, download_dir)
        if rv is False:
            if verbose:
                print "No updates available"
                if cache_dir is None:
                    Update.RemoveUpdate(download_dir)
                sys.exit(1)
        else:
            if verbose:
                diffs = Update.PendingUpdates(download_dir)
                for (pkg, op, old) in diffs:
                    if op == "delete":
                        print >> sys.stderr, "Delete package %s" % pkg.Name()
                    elif op == "install":
                        print >> sys.stderr, "Install package %s-%s" % (pkg.Name(), pkg.Version())
                    elif op == "upgrade":
                        print >> sys.stderr, "Upgrade package %s %s->%s" % (pkg.Name(), old.Version(), pkg.Version())
            if cache_dir is None:
                Update.RemoveUpdate(download_dir)
            sys.exit(0)

    elif args[0] == "update":
        # This will attempt to apply an update.
        # If cache_dir is given, then we will only check that directory,
        # not force a download if it is already there.  If cache_dir is not
        # given, however, then it downloads.  (The reason is that you would
        # want to run "freenas-update -c /foo check" to look for an update,
        # and it will download the latest one as necessary, and then run
        # "freenas-update -c /foo update" if it said there was an update.
        if cache_dir is None:
            download_dir = tempfile.mkdtemp(prefix = "UpdateUpdate-", dir = config.TemporaryDirectory())
            if download_dir is None:
                print >> sys.stderr, "Unable to create temporary directory"
                sys.exit(1)
            rv = Update.DownloadUpdate(train, download_dir)
            if rv is False:
                if verbose or debug:
                    print >> sys.stderr, "DownloadUpdate returned False"
                sys.exit(1)
        else:
            download_dir = cache_dir
        
        diffs = Update.PendingUpdates(download_dir)
        if diffs is None or diffs == {}:
            if verbose:
                print >> sys.stderr, "No updates to apply"
        else:
            if verbose:
                for (pkg, op, old) in diffs:
                    if op == "delete":
                        print >> sys.stderr, "Delete package %s" % pkg.Name()
                    elif op == "install":
                        print >> sys.stderr, "Install package %s-%s" % (pkg.Name(), pkg.Version())
                    elif op == "upgrade":
                        print >> sys.stderr, "Upgrade package %s %s -> %s" % (pkg.Name(), old.Version(), pkg.Version())
            rv = Update.ApplyUpdate(download_dir)
            if rv is False:
                if verbose:
                    print >> sys.stderr, "ApplyUpdates failed"
                if cache_dir is None:
                    Update.RemoveUpdate(download_dir)
                sys.exit(1)
            Update.RemoveUpdate(download_dir)
            # Change this if/when we can do an update without a reboot.
            print >> sys.stderr, "System should be rebooted now"
            sys.exit(0)
    else:
        usage()

if __name__ == "__main__":
    sys.exit(main())

