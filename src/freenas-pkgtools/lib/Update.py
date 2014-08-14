import errno
import os
import sys
import logging

import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
import freenasOS.Installer as Installer


log = logging.getLogger('freenasOS.Update')

def CheckForUpdates(root = None, handler = None):
    """
    Check for an updated manifest.
    Very simple, uses the configuration module.
    Returns the new manifest if there is an update,
    and None otherwise.
    (It determines if there is an update if the latest-found
    manifest contains differences from the current system
    manifest.)
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
    log.debug("Current sequence = %d, available sequence = %d" % (cur.Sequence(), m.Sequence()
                                                                             if m is not None else 0))
    print >> sys.stderr, "Current sequence = %d, available sequence = %d" % (cur.Sequence(), m.Sequence()
                                                                             if m is not None else 0)
    if m is None:
        raise ValueError("Manifest could not be found!")
    diffs = Manifest.CompareManifests(cur, m)
    update = False
    for (pkg, op,old) in diffs:
        update = True
        if handler is not None:
            handler(op, pkg, old)
    return m if update else None


def Update(root=None, conf=None, check_handler=None, get_handler=None,
           install_handler=None):
    """
    Perform an update.  Calls CheckForUpdates() first, to see if
    there are any. If there are, then magic happens.
    """
    grub_dir = "/boot/grub"
    grub_cfg = "/boot/grub/grub.cfg"

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
        # If all that worked... we now need
        # to get /boot/grub into the clone's mount
        # point, as a nullfs mount.
        # Let's see if we need to do that
        if os.path.exists(mount_point + grub_cfg) is False:
            # Okay, it needs to be ounted
            cmd = "/sbin/mount"
            args = ["-t", "nullfs", grub_dir, mount_point + grub_dir]
            try:
                rv = RunCommand(cmd, args)
            except:
                UnmountClone(name, None)
                return False

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

    def UnmountClone(name, mount_point):
        # Unmount the given clone.  After unmounting,
        # it removes the mount directory.
        # First thing we need to do is try to unmount
        # the nullfs-mounted grub directory
        # If this fails, we ignore it for now
        if mount_point is not None:
            cmd = "umount"
            args = [mount_point + grub_dir]
            try:
                RunCommand(cmd, args)
            except:
                pass

        # Now we ask beadm to unmount it.
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
        log.debug("Updated manifest but no package differences")
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
            log.error("Unable to create boot-environment %s" % clone_name)
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
        log.debug("Want to delete package %s" % pkg.Name())
        print >> sys.stderr, "Want to delete package %s" % pkg.Name()
        if conf.PackageDB(root).RemovePackageContents(pkg) == False:
            print >> sys.stderr, "Unable to remove contents package %s" % pkg.Name()
            UnmountClone(clone_name, mount_point)
            DestroyClone(clone_name)
            raise Exception("Unable to remove contents for package %s" % pkg.Name())
        conf.PackageDB(root).RemovePackage(pkg.Name())

    installer = Installer.Installer(manifest = new_man, root = root, config = conf)
    installer.GetPackages(process_packages, handler=get_handler)

    log.debug("Packages = %s" % installer._packages)
    print >> sys.stderr, "Packages = %s" % installer._packages

    # Now let's actually install them.
    # Only change on success
    rv = False
    if installer.InstallPackages(handler=install_handler) is False:
        log.error("Unable to install packages")
        print >> sys.stderr, "Unable to install packages"
    else:
        new_man.Save(root)
        if mount_point is not None:
            if UnmountClone(clone_name, mount_point) is False:
                log.error("Unable to mount clone enivironment %s" % clone_name)
                print >> sys.stderr, "Unable to unmount clone environment %s" % clone_name
            else:
                if ActivateClone(clone_name) is False:
                    log.error("Could not activate clone environment %s" % clone_name)
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
            log.error("Unable to delete boot environment %s in failure case" % clone_name)
            print >> sys.stderr, "Unable to delete boot environment %s" % clone_name
    
    return rv

    
