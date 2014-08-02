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
        return None
    if handler is not None:
        diffs = Manifest.CompareManifests(cur, m)
        for (pkg, op, old) in diffs:
            handler(op, pkg, old)
    return m


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
        if root is None:
            prefix = ""
        else:
            prefix = root
        manifest.StorePath(prefix + Manifest.SYSTEM_MANIFEST_FILE)
        # See if the primary and backup file are the same
        # If this raises an exception we deserve it
        primary = os.stat(prefix + Manifest.SYSTEM_MANIFEST_FILE)
        try:
            secondary = os.stat(prefix + Manifest.BACKUP_MANIFEST_FILE)
        except:
            secondary = None

        if secondary is None or \
           primary.st_dev != secondary.st_dev or \
            primary.st_ino != secondary.st_ino:
            try:
                # This could cause problems if /etc is a tmpfs
                os.unlink(prefix + Manifest.BACKUP_MANIFEST_FILE)
            except:
                pass
            try:
                os.link(prefix + Manifest.SYSTEM_MANIFEST_FILE,
                        prefix + Manifest.BACKUP_MANIFEST_FILE)
            except OSError as e:
                if e[0] == errno.EXDEV:
                    # Just write it out to the backup location
                    manifest.StorePath(prefix + Manifest.BACKUP_MANIFEST_FILE)
            except:
                raise e

    def RunCommand(command, args):
        # Run the given command.  Uses subprocess module.
        # Returns True if the command exited with 0, or
        # False otherwise.
        import subprocess

        proc_args = [ command ]
        if args is not None:  proc_args.extend(args)
        child = subprocess.call(proc_args)
        if child == 0:
            return True
        else:
            return False

    def CreateClone(name):
        # Create a boot environment from the current
        # root, using the given name.  Returns False
        # if it could not create it
        beadm = "/usr/local/sbin/beadm"
        args = ["create", name]
        try:
            rv = RunCommand(beadm, args)
        except:
            return False
        return rv

    def MountClone(name):
        # Mount the given boot environment.  It will
        # create a random name in /tmp.  Returns the
        # name of the mountpoint, or None on error.
        import tempfile
        try:
            mount_point = tempfile.mkdtemp()
        except:
            return None

        if mount_point is None:
            return None
        beadm = "/usr/local/sbin/beadm"
        args = ["mount", name, mount_point ]
        try:
            rv = RunCommand(beadm, args)
        except:
            try:
                os.rmdir(mount_point)
            except:
                pass
            return None
        return mount_point

    def ActivateClone(name):
        # Set the clone to be active for the next boot
        beadm = "/usr/local/sbin/beadm"
        args = ["activate", name]
        try:
            rv = RunCommand(beadm, args)
        except:
            return False
        return True

    def UnmountClone(name):
        # Unmount the given clone.  After unmounting,
        # it removes the mount directory.
        beadm = "/usr/local/sbin/beadm"
        args = ["unmount", "-f", name]

        try:
            rv = RunCommand(beadm, args)
        except:
            return False
        try:
            os.rmdir(mount_point)
        except:
            pass
        return True
        
    def DeleteClone(name):
        # Delete the clone we created.
        beadm = "/usr/local/sbin/beadm"
        args = ["destroy", "-F", name]
        try:
            rv = RunCommand(beadm, args)
        except:
            return False
        return rv;

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

    # If root is None, then we will try to create a clone
    # environment.  (If the caller wants to install into the
    # current boot environment, set root = "" or "/".)
    if root is None:
        # We clone the existing boot environment to
        # "FreeNAS-<sequence>"
        clone_name = "FreeNAS-%d" % new_man.Sequence()
        if CreateClone(clone_name) is False:
            print >> sys.stderr, "Unable to create boot-environment %s" % clone_name
            raise Exception("Unable to create new boot-environment %s" % clone_name)

        mount_point = MountClone(clone_name)
        if mount_point is None:
            print >> sys.stderr, "Unable to mount boot-environment %s" % clone_name
            raise Exception("Unable to mount boot-environment %s" % clone_name)
        else:
            root = mount_point
    else:
        mount_point = None

    for pkg in deleted_packages:
        print >> sys.stderr, "Want to delete package %s" % pkg.Name()
        if conf.PackageDB(root).RemovePackageContents(pkg) == False:
            print >> sys.stderr, "Unable to remove contents package %s" % pkg.Name()
            UnmountClone(clone_name)
            DestroyClone(clone_name)
            raise Exception("Unable to remove contents for package %s" % pkg.Name())
        conf.PackageDB(root).RemovePackage(pkg.Name())

    installer = Installer.Installer(manifest = new_man, root = root, config = conf)
    installer.GetPackages(process_packages, handler=get_handler)

    print >> sys.stderr, "Packages = %s" % installer._packages

    # Now let's actually install them.
    # Only change on success
    rv = False
    if installer.InstallPackages(handler=install_handler) is False:
        print >> sys.stderr, "Unable to install packages"
    else:
        SaveManifest(new_man)
        if mount_point is not None:
            if UnmountClone(clone_name) is False:
                print >> sys.stderr, "Unable to unmount clone environment %s" % clone_name
            else:
                if ActivateClone(clone_name) is False:
                    print >> sys.stderr, "Could not activate clone environment %s" % clone_name
                else:
                    rv = True

    # Clean up
    # The package files are open-unlinked, so should be removed
    # automatically under *nix.  That just leaves the clone, which
    # we should unmount, and destroy if necessary.
    # Unmounting attempts to delete the mount point that was created.
    if rv is False:
        if DeleteClone(clone_name) is False:
            print >> sys.stderr, "Unable to delete boot environment %s" % clone_name
    
    return rv

    
