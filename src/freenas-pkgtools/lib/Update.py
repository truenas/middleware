import sys

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
    print >> sys.stderr, "Current sequence = %d, available sequence = %d" % (cur.Sequence(), m.Sequence()
 if m is not None else 0)
    if m is None:
        raise ValueError("Manifest could not be found!")
    if m.Sequence() <= cur.Sequence():
        return False
    if handler is not None:
        diffs = Manifest.CompareManifests(cur, m)
        for (pkg, op, old) in diffs:
            handler(op, pkg, old)
    return True


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
