import errno
import os
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


def Update(root=None, conf=None, check_handler=None, get_handler=None,
           install_handler=None):
    """
    Perform an update.  Calls CheckForUpdates() first, to see if
    there are any. If there are, then magic happens.
    """

    def SaveManifest(manifest):
        # Need to write out the manifest
        # It needs to to into the specified root; however,
        # if root is none, we can't then link to the backup.
        manifest.StorePath(root + Manifest.SYSTEM_MANIFEST_FILE)
        try:
            os.link(root + Manifest.SYSTEM_MANIFEST_FILE,
                    root + Manifest.BACKUP_MANIFEST_FILE)
        except OSError as e:
            if e[0] == errno.EXDEV:
                # Just write it out to the backup location
                manifest.StorePath(root + Manifest.BACKUP_MANIFEST_FILE)
            else:
                raise e
        except:
            raise

    deleted_packages = []
    process_packages = []
    def UpdateHandler(op, pkg, old):
        if op == "delete":
            deleted_packages.append(pkg)
        else:
            process_packages.append(pkg)
        if check_handler is not None:
            check_handler(op, pkg, old)

    new_man = CheckForUpdates(root, UpdateHandler)
    if new_man is None:
        return

    if len(deleted_packages) == 0 and len(process_packages) == 0:
        # We have a case where a manifest was updated, but we
        # don't actually have any changes to the packages.  We
        # should install the new manifest, and be done -- it
        # may have new release notes, or other issues.
        # Right now, I'm not quite sure how to do this.
        # I should also learn how to log from python.
        print >> sys.stderr, "Updated manifest but no package differences"
        return

    # Now we have a list of deleted packages, and a list
    # of update/install packages.
    # The task is to delete the first set of packages,
    # and then run through the others to install/update.
    # First, however, we need to get the files.
    # We want to use the system configuration, unless one has been
    # specified -- we don't want to use the target root's.
    if conf is None:  
        conf = Configuration.Configuration()

    for pkg in deleted_packages:
        print >> sys.stderr, "Want to delete package %s" % pkg.Name()
        if conf.PackageDB().RemovePackageContents(pkg) == False:
            print >> sys.stderr, "Unable to remove contents package %s" % pkg.Name()
            raise Exception("Unable to remove contents for package %s" % pkg.Name())
        conf.PackageDB().RemovePackage(pkg.Name())

    installer = Installer.Installer(manifest = new_man, root = root, config = conf)
    installer.GetPackages(process_packages, handler=get_handler)

    print >> sys.stderr, "Packages = %s" % installer._packages

    # Now let's actually install them.
    if installer.InstallPackages(handler=install_handler) is False:
        print >> sys.stderr, "Unable to install packages"
    else:
        SaveManifest(new_man)

    return True
