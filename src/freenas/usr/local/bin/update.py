#!/usr/local/bin/python -R

import os, sys, getopt

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
import freenasOS.Installer as Installer

def CheckForUpdates(root = None, handler = None):
    """
    Check for an updated manifest.
    Very simple, uses the configuration module.
    Returns the new manifest if there is an update,
    and None otherwise.
    (It determines if there is an update if the latest-found
    manifeset's sequence number is larger than the current
    sequence number.)
    The optional argument handler is a function that
    will be called for each difference in the new manifest
    (if there is one); it will be called with three
    arguments:  operation, package, old package.
    operation will be "delete", "upgrade", or "install";
    old package will be None for delete and install.
    """
    conf = Configuration.Configuration(root)
    cur = conf.SystemManifest()
    m = conf.FindLatestManifest()
    print >> sys.stderr, "Current sequence = %d, available sequence = %d" % (cur.Sequence(), m.Sequence() if m is not None else 0)
    if m is not None and m.Sequence() > cur.Sequence():
        if handler is not None:
            diffs = Manifest.CompareManifests(cur, m)
            for (pkg, op, old) in diffs:
                handler(op, pkg, old)
        return m
    return None

def Update(root = None, conf = None, handler = None):
    """
    Perform an update.  Calls CheckForUpdates() first, to see if
    there are any. If there are, then magic happens.
    """

    deleted_packages = []
    other_packages = []
    def UpdateHandler(op, pkg, old):
        if op == "delete":
            deleted_packages.append(pkg)
        else:
            other_packages.append((pkg, old))
        if handler is not None:
            handler(op, pkg, old)

    new_man = CheckForUpdates(root, UpdateHandler)
    if new_man is None:
        return

    # Now we have a list of deleted packages, and a list
    # of update/install packages.
    # The task is to delete the first set of packages,
    # and then run through the others to install/update.
    # First, however, we need to get the files.
    # We want to use the system configuration, unless one has been
    # specified -- we don't want to use the target root's.
    if conf is None:
        conf = Configuration.Configuration(root = root)

    for pkg in deleted_packages:
        print >> sys.stderr, "Want to delete package %s" % pkg.Name()
        #        if conf.PackageDB().RemovePackageContents(pkg) == False:
        #            print >> sys.stderr, "Unable to remove contents package %s" % pkg.Name()
        #            sys.exit(1)
        #        conf.PackageDB().RemovePackage(pkg.Name())

    process_packages = []
    for (pkg, old) in other_packages:
        process_packages.append(pkg)

    installer = Installer.Installer(manifest = new_man, root = root, config = conf)
    installer.GetPackages(process_packages)

    print "Packages = %s" % installer._packages
    return

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

    if root is not None and os.path.isdir(root) == False:
        print >> sys.stderr, "Specified root (%s) does not exist" % root
        sys.exit(1)

    if config_file is not None:
        config = Configuration.Configuration(file = config_file, root = root)

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
        r = False if CheckForUpdates(root, pfcn) is None else True
        print >> sys.stderr, "Newer manifest found" if r else "No newer manifest found"
        if r:   
            return 0
        else:
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

