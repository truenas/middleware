#!/usr/local/bin/python

import getopt
import logging
import logging.config
import os
import sys

def CacheUpdate(update, cachedir):
    import shutil
    import freenasOS.Configuration as Configuration

    if os.path.exists(cachedir):
        shutil.rmtree(cachedir)
    os.makedirs(cachedir)
    conf = Configuration.Configuration()
    # Now we want to save the manifest, and then get the package files.
    try:
        # First, save the manifest
        update.StorePath(cachedir + "/MANIFEST")
        for pkg in update.Packages():
            # Now we want to fetch each of the packages,
            # and store them in the cachedir
            pkg_file = conf.FindPackageFile(pkg, save_dir = cachedir)
            if pkg_file is None:
                raise Exception("Could not get package %s" % pkg.Name())
    except Exception as e:
        # Just clean up on all exceptions
        log.debug("Caught exception %s" % str(e))
        if os.path.exists(cachedir):
            shutil.rmtree(cachedir)
    return

def main():
    global log
    def usage():
        print >> sys.stderr, "Usage: %s [-R root] [-M manifest_file] [-c dir] <cmd>, where cmd is one of:" % sys.argv[0]
        print >> sys.stderr, "\tcheck\tCheck for updates"
        print >> sys.stderr, "\tupdate\tDo an update"
        print >> sys.stderr, "\tinstall\tInstall"
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "qvdR:M:T:C:c:")
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
    cachedir = None

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
        elif o == '-c':
            cachedir = a
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

    log = logging.getLogger('freenas-update')

    sys.path.append("/usr/local/lib")

    import freenasOS.Configuration as Configuration
    import freenasOS.Manifest as Manifest
    from freenasOS.Update import CheckForUpdates, Update

    if root is not None and os.path.isdir(root) is False:
        print >> sys.stderr, "Specified root (%s) does not exist" % root
        sys.exit(1)

    if config_file is not None:
        # We want the system configuration file
        config = Configuration.Configuration(file = config_file, root = None)
    else:
        config = Configuration.Configuration(root = root)

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
            # If we're given a root, we can't cache.
            if root is None and cachedir:
                # First thing:  is the cached version the same
                # as this version?
                if os.path.exists(cachedir + "/MANIFEST"):
                    cached_manifest = Manifest.Manifest()
                    cached_manifest.LoadPath(cachedir + "/MANIFEST")
                    if cached_manifest.Train() == update.Train() and \
                       cached_manifest.Sequence() == update.Sequence():
                        # This is the same version, so nothing else to do!
                        log.debug("Local cache manifest is same as remote LATEST, stopping happy")
                        return 0
                # If it doesn't exist, or the train/sequence are different,
                # we let CacheUpdate clean up and then save the update.
                CacheUpdate(update, cachedir)
            return 0
        else:
            print >> sys.stderr, "No newer manifest found"
            return 1
    elif args[0] == "update":
        r = Update(root, config, cache_dir = cachedir)
        if r:
            return 0
        else:
            return 1
    else:
        usage()

if __name__ == "__main__":
    sys.exit(main())

