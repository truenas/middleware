from datetime import datetime
import logging
import os
import re
import subprocess
import sys

from . import Avatar
import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
import freenasOS.Installer as Installer
import freenasOS.Package as Package
from freenasOS.Exceptions import UpdateIncompleteCacheException, UpdateInvalidCacheException, UpdateBusyCacheException

log = logging.getLogger('freenasOS.Update')

debug = False

# Used by the clone functions below
beadm = "/usr/local/sbin/beadm"
grub_dir = "/boot/grub"
grub_cfg = "/boot/grub/grub.cfg"
freenas_pool = "freenas-boot"
def _grub_snapshot(name):
    return "%s/grub@Pre-Upgrade-%s" % (freenas_pool, name)

def RunCommand(command, args):
    # Run the given command.  Uses subprocess module.
    # Returns True if the command exited with 0, or
    # False otherwise.
    import subprocess

    proc_args = [ command ]
    if args is not None:  proc_args.extend(args)
    log.debug("RunCommand(%s, %s)" % (command, args))
    if debug:
        print >> sys.stderr, proc_args
        child = 0
    else:
        try:
            child = subprocess.call(proc_args)
        except:
            return False

    if child == 0:
        return True
    else:
        return False


def ListClones():
    # Return a list of boot-environment clones.
    # This is just a simple wrapper for
    # "beadm list -H"
    # Because of that, it can't use RunCommand
    cmd = [beadm, "list", "-H" ]
    rv = []
    if debug:
        print >> sys.stderr, cmd
        return None
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except:
        log.error("Could not run %s", cmd)
        return None
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        log.error("`%s' returned %d", cmd, p.returncode)
        return None

    for line in stdout.strip('\n').split('\n'):
        fields = line.split('\t')
        rv.append({
            'name': fields[0],
            'active': fields[1],
            'mountpoint': fields[2],
            'space': fields[3],
            'created': datetime.strptime(fields[4], '%Y-%m-%d %H:%M'),
        })
    return rv


def CreateClone(name, snap_grub=True, bename=None):
    # Create a boot environment from the current
    # root, using the given name.  Returns False
    # if it could not create it
    if bename:
        args = ["create", "-e", bename, name]
    else:
        args = ["create", name]
    rv = RunCommand(beadm, args)
    if rv is False:
        return False

    if snap_grub:
        # Also create a snapshot of the grub filesystem,
        # but we don't do anything with it
        zfs = "/sbin/zfs"
        args = ["snapshot", _grub_snapshot(name)]
        if RunCommand(zfs, args) is False:
            log.debug("Unable to create grub snapshot Pre-Upgrade-%s", name)

    return True


def RenameClone(oldname, newname):
    # Create a boot environment from the current
    # root, using the given name.  Returns False
    # if it could not create it
    args = ["rename", oldname, newname]
    rv = RunCommand(beadm, args)
    if rv is False:
        return False
    return True


def MountClone(name, mountpoint = None):
    # Mount the given boot environment.  It will
    # create a random name in /tmp.  Returns the
    # name of the mountpoint, or None on error.
    if mountpoint is None:
        import tempfile
        try:
            mount_point = tempfile.mkdtemp()
        except:
            return None
    else:
        mount_point = mountpoint

    if mount_point is None:
        return None
    args = ["mount", name, mount_point ]
    rv = RunCommand(beadm, args)
    if rv is False:
        try:
            os.rmdir(mount_point)
        except:
            pass
        return None

    # If all that worked... we now need
    # to get /boot/grub into the clone's mount
    # point, as a nullfs mount.
    # Let's see if we need to do that
    if os.path.exists(grub_cfg) is True and \
       os.path.exists(mount_point + grub_cfg) is False:
        # Okay, it needs to be ounted
        cmd = "/sbin/mount"
        args = ["-t", "nullfs", grub_dir, mount_point + grub_dir]
        rv = RunCommand(cmd, args)
        if rv is False:
            UnmountClone(name, None)
            return None

    return mount_point

def ActivateClone(name):
    # Set the clone to be active for the next boot
    args = ["activate", name]
    return RunCommand(beadm, args)

def UnmountClone(name, mount_point = None):
    # Unmount the given clone.  After unmounting,
    # it removes the mount directory.
    # First thing we need to do is try to unmount
    # the nullfs-mounted grub directory
    # If this fails, we ignore it for now
    if mount_point is not None:
        cmd = "umount"
        args = [mount_point + grub_dir]
        RunCommand(cmd, args)

    # Now we ask beadm to unmount it.
    args = ["unmount", "-f", name]
    
    if RunCommand(beadm, args) is False:
        return False

    if mount_point is not None:
        try:
            os.rmdir(mount_point)
        except:
            pass
    return True
        
def DeleteClone(name, delete_grub = False):
    # Delete the clone we created.
    args = ["destroy", "-F", name]
    rv = RunCommand(beadm, args)
    if rv is False:
        return rv

    if delete_grub:
        zfs = "/sbin/zfs"
        args = ["destroy", _grub_snapshot(name)]
        if RunCommand(zfs, args) is False:
            log.debug("Unable to delete grub snapshot Pre-Upgrade-%s" % name)

    return rv

def CheckForUpdates(root = None, handler = None, train = None, cache_dir = None):
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
    The optional cache_dir parameter indicates that it
    should look in that directory first, rather than
    going over the network.  (Unlike the similar code
    in freenas-update, this will not [at this time]
    download the package files and store them in
    cache_dir.)
    """
    conf = Configuration.Configuration(root)
    cur = conf.SystemManifest()
    m = None
    # Let's check cache_dir if it is set
    if cache_dir and (not train or train == cur.Train()):
        if os.path.exists(cache_dir + "/MANIFEST"):
            # Okay, let's load it up.
            m = Manifest.Manifest()
            try:
                m.LoadPath(cache_dir + "/MANIFEST")
                if m.Train() != cur.Train():
                    # Should we get rid of the cache?
                    m = None
            except:
                m = None

    if m is None:
        m = conf.FindLatestManifest(train = train)

    log.debug("Current sequence = %s, available sequence = %s" % (cur.Sequence(), m.Sequence()
                                                                             if m is not None else "None"))
    if m is None:
        raise ValueError("Manifest could not be found!")
    diffs = Manifest.CompareManifests(cur, m)
    update = False
    for (pkg, op,old) in diffs:
        update = True
        if handler is not None:
            handler(op, pkg, old)
    return m if update else None


def Update(root=None, conf=None, train = None, check_handler=None, get_handler=None,
           install_handler=None, cache_dir = None):
    """
    Perform an update.  If cache_dir is set, and contains a valid
    set of files (MANIFEST exists, and is for the current train, and
    the sequence is not the same as the system sequence), it will
    use that, rather than downloading.  It calls CheckForUpdates() otherwise,
    to see if there are any. If there are, then magic happens.
    """

    log.debug("Update(root = %s, conf = %s, train = %s, cache_dir = %s)" % (root, conf, train, cache_dir))
    if conf is None:
        conf = Configuration.Configuration(root)

    deleted_packages = []
    process_packages = []
    def UpdateHandler(op, pkg, old):
        if op == "delete":
            deleted_packages.append(pkg)
        else:
            process_packages.append(pkg)
        if check_handler is not None:
            check_handler(op, pkg, old)

    new_man = None
    if cache_dir:
        if os.path.exists(cache_dir + "/MANIFEST"):
            try:
                cur = conf.SystemManifest()
                new_man = Manifest.Manifest()
                new_man.LoadPath(cache_dir + "/MANIFEST")
                if new_man.Train() != cur.Train():
                    new_man = None
                    cache_dir = None
                else:
                    diffs = Manifest.CompareManifests(cur, new_man)
                    for (pkg, op, old) in diffs:
                        UpdateHandler(op, pkg, old)
                    conf.SetPackageDir(cache_dir)
            except Exception as e:
                log.debug("Caught exception %s" % str(e))
                new_man = None
                cache_dir = None

    if new_man is None:
        new_man = CheckForUpdates(root, handler = UpdateHandler, train = train)

    if new_man is None:
        return

    if len(deleted_packages) == 0 and len(process_packages) == 0:
        # We have a case where a manifest was updated, but we
        # don't actually have any changes to the packages.  We
        # should install the new manifest, and be done -- it
        # may have new release notes, or other issues.
        # Right now, I'm not quite sure how to do this.
        log.debug("Updated manifest but no package differences")
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
    clone_name = None
    try:
        if root is None:
            # We clone the existing boot environment to
            # "Avatar()-<sequence>"
            clone_name = "%s-%s" % (Avatar(), new_man.Sequence())
            if CreateClone(clone_name) is False:
                log.error("Unable to create boot-environment %s" % clone_name)
                raise Exception("Unable to create new boot-environment %s" % clone_name)

            mount_point = MountClone(clone_name)
            if mount_point is None:
                log.error("Unable to mount boot-environment %s" % clone_name)
                DeleteClone(clone_name)
                raise Exception("Unable to mount boot-environment %s" % clone_name)
            else:
                root = mount_point
        else:
            mount_point = None

        for pkg in deleted_packages:
            log.debug("Want to delete package %s" % pkg.Name())
            if conf.PackageDB(root).RemovePackageContents(pkg) == False:
                log.error("Unable to remove contents package %s" % pkg.Name())
                if mount_point:
                    UnmountClone(clone_name, mount_point)
                    mount_point = None
                    DeleteClone(clone_name)
                raise Exception("Unable to remove contents for package %s" % pkg.Name())
            conf.PackageDB(root).RemovePackage(pkg.Name())

        installer = Installer.Installer(manifest = new_man, root = root, config = conf)
        installer.GetPackages(process_packages, handler=get_handler)

        log.debug("Packages = %s" % installer._packages)

        # Now let's actually install them.
        # Only change on success
        rv = False
        if installer.InstallPackages(handler=install_handler) is False:
            log.error("Unable to install packages")
        else:
            new_man.Save(root)
            if mount_point is not None:
                if UnmountClone(clone_name, mount_point) is False:
                    log.error("Unable to mount clone enivironment %s" % clone_name)
                else:
                    mount_point = None
                    if ActivateClone(clone_name) is False:
                        log.error("Could not activate clone environment %s" % clone_name)
                    else:
                        # Downloaded package files are open-unlinked, so don't
                        # have to be cleaned up.  If there's a cache directory,
                        # however, we need to get rid of it.
                        if cache_dir:
                            import shutil
                            if os.path.exists(cache_dir):
                                try:
                                    shutil.rmtree(cache_dir)
                                except Exception as e:
                                    # If that doesn't work, for now at least we'll
                                    # simply ignore the error.
                                    log.debug("Tried to remove cache directory %s, got exception %s" % (cache_dir, str(e)))
                        rv = True
                        # Start a scrub.  We ignore the return value.
                        RunCommand("/sbin/zpool", ["scrub", "freenas-boot"])

    except BaseException as e:
        log.error("Update got exception during update: %s" % str(e))
        if clone_name:
            if mount_point:
                # Ignore the error here
                UnmountClone(clone_name, mount_point)
            DeleteClone(clone_name)
        raise e
            
    # Clean up
    # That just leaves the clone, which
    # we should unmount, and destroy if necessary.
    # Unmounting attempts to delete the mount point that was created.
    if rv is False:
        if clone_name and DeleteClone(clone_name) is False:
            log.error("Unable to delete boot environment %s in failure case" % clone_name)
    
    return rv

def DownloadUpdate(train, directory, get_handler = None, check_handler = None):
    """
    Download, if necessary, the LATEST update for train; download
    delta packages if possible.  Checks to see if the existing content
    is the right version.  In addition to the current caching code, it
    will also stash the current sequence when it downloads; this will
    allow it to determine if a reboot into a different boot environment
    has happened.  This will remove the existing content if it decides
    it has to redownload for any reason.
    """
    import shutil
    import fcntl

    conf = Configuration.Configuration()
    # First thing, let's get the latest manifest
    latest_mani = conf.FindLatestManifest(train)
    if latest_mani is None:
        # That really shouldnt happen
        log.error("Unable to find latest manifest for train %s" % train)
        return False

    cache_mani = Manifest.Manifest()
    try:
        mani_file = VerifyUpdate(directory)
        if mani_file:
            cache_mani.LoadFile(mani_file)
            if cache_mani.Sequence() == latest_mani.Sequence():
                # Woohoo!
                mani_file.close()
                return True
            # Not the latest
            mani_file.close()
        RemoveUpdate(directory)
        mani_file = None
    except UpdateBusyCacheException:
        log.debug("Cache directory %s is busy, so no update available" % directory)
        return False
    except (UpdateIncompleteCacheException, UpdateInvalidCacheException) as e:
        # It's incomplete, so we need to remove it
        log.error("DownloadUpdate(%s, %s):  Got exception %s; removing cache" % (train, directory, str(e)))
        RemoveUpdate(directory)
    except BaseException as e:
        log.error("Got exception %s while trying to prepare update cache" % str(e))
        raise e
    # If we're here, then we don't have a (valid) cached update.
    RemoveUpdate(directory)
    try:
        os.makedirs(directory)
    except BaseException as e:
        log.error("Unable to create directory %s: %s" % (directory, str(e)))
        return False

    try:
        mani_file = open(directory + "/MANIFEST", "wxb")
    except (IOError, Exception) as e:
        log.error("Unale to create manifest file in directory %s" % (directory, str(e)))
        return False
    try:
        fcntl.lockf(mani_file, fcntl.LOCK_EX | fcntl.LOCK_NB, 0, 0)
    except (IOError, Exception) as e:
        log.debug("Unable to lock manifest file: %s" % str(e))
        mani_file.close()
        return False

    # Next steps:  download the package files.
    for indx, pkg in enumerate(latest_mani.Packages()):
        if check_handler:
            check_handler(indx + 1,  pkg = pkg, pkgList = latest_mani.Packages())
        pkg_file = conf.FindPackageFile(pkg, save_dir = directory, handler = get_handler)
        if pkg_file is None:
            log.error("Could not download package file for %s" % pkg.Name())
            RemoveUpdate(directory)
            return False

    # Then save the manifest file.
    latest_mani.StoreFile(mani_file)
    # Create the SEQUENCE file.
    with open(directory + "/SEQUENCE", "w") as f:
        f.write("%s" % conf.SystemManifest().Sequence())
    # Then return True!
    mani_file.close()
    return True

def PendingUpdates(directory):
    """
    Return a list (a la CheckForUpdates handler right now) of
    changes between the currently installed system and the
    downloaded contents in <directory>.  If <directory>'s values
    are incomplete or invalid for whatever reason, return
    None.  "Incomplete" means a necessary file for upgrading
    from the current system is not present; "Invalid" means that
    one part of it is invalid -- manifest is not valid, signature isn't
    valid, checksum for a file is invalid, or the stashed sequence
    number does not match the current system's sequence.
    """
    mani_file = None
    conf = Configuration.Configuration()
    try:
        mani_file = VerifyUpdate(directory)
    except UpdateBusyCacheException:
        log.debug("Cache directory %s is busy, so no update available" % directory)
        return None
    except (UpdateIncompleteCacheException, UpdateInvalidCacheException) as e:
        log.error(str(e))
        RemoveUpdate(directory)
        return None
    except BaseException as e:
        log.error("Got exception %s while trying to determine pending updates" % str(e))
        return None
    if mani_file:
        new_manifest = Manifest.Manifest()
        new_manifest.LoadFile(mani_file)
        diffs = Manifest.CompareManifests(conf.SystemManifest(), new_manifest)
        return diffs
    return None

def ApplyUpdate(directory, install_handler = None):
    """
    Apply the update in <directory>.  As with PendingUpdates(), it will
    have to verify the contents before it actually installs them, so
    it has the same behaviour with incomplete or invalid content.
    """
    rv = False
    conf = Configuration.Configuration()
    changes = PendingUpdates(directory)
    if changes is None:
        # That could have happened for multiple reasons.
        # PendingUpdates should probably throw an exception
        # on error
        return False
    # Do I have to worry about a race condition here?
    new_manifest = Manifest.Manifest()
    new_manifest.LoadPath(directory + "/MANIFEST")
    conf.SetPackageDir(directory)

    deleted_packages = []
    updated_packages = []
    for (pkg, op, old) in changes:
        if op == "delete":
            log.debug("Delete package %s" % pkg.Name())
            deleted_packages.append(pkg)
        elif op == "install":
            log.debug("Install package %s" % pkg.Name())
        else:
            log.debug("Upgrade package %s-%s to %s-%s" % (old.Name(), old.Version(), pkg.Name(), pkg.Version()))
            updated_packages.append(pkg)

    if len(deleted_packages) == 0 and len(updated_packages) == 0:
        # The manifest may have other differences, so we should
        # probably do something.
        log.debug("New manifest has no package changes, what should we do?")
        RemoveUpdate(directory)
        return True

    # Now we start doing the update!
    clone_name = None
    mount_point = None
    try:
        clone_name = "%s-%s" % (Avatar(), new_manifest.Sequence())
        if CreateClone(clone_name) is False:
            s = "Unable to create boot-environment %s" % clone_name
            log.error(s)
            raise Exception(s)
        mount_point = MountClone(clone_name)
        if mount_point is None:
            s = "Unable to mount boot-environment %s" % clone_name
            log.error(s)
            DeleteClone(clone_name)
            raise Exception(s)

        # Remove any deleted packages
        for pkg in deleted_packages:
            log.debug("About to delete package %s" % pkg.Name())
            if conf.PackageDB(mount_point).RemovePackageContents(pkg) == False:
                s = "Unable to remove contents for packate %s" % pkg.Name()
                if mount_point:
                    UnmountClone(clone_name, mount_point)
                    mount_point = None
                    DeleteClone(clone_name)
                raise Exception(s)
            conf.PackageDB(mount_point).RemovePackage(pkg.Name())

        installer = Installer.Installer(manifest = new_manifest,
                                        root = mount_point,
                                        config = conf)
        installer.GetPackages(pkgList = updated_packages)
        log.debug("Installer got packages %s" % installer._packages)
        # Now to start installing them
        rv = False
        if installer.InstallPackages(handler = install_handler) is False:
            log.error("Unable to install packages")
            raise Exception("Unable to install packages")
        else:
            new_manifest.Save(mount_point)
            if mount_point:
                if UnmountClone(clone_name, mount_point) is False:
                    s = "Unable to unmount clone environment %s from mount point %s" % (clone_name, mount_point)
                    log.error(s)
                    raise Exception(s)
                mount_point = None
                if ActivateClone(clone_name) is False:
                    s = "Unable to activate clone environment %s" % clone_name
                    log.error(s)
                    raise Exception(s)
                RemoveUpdate(directory)
                rv = True
                RunCommand("/sbin/zpool", ["scrub", "freenas-boot"])
    except BaseException as e:
        log.error("Update got exception during update: %s" % str(e))
        if mount_point:
            UnmountClone(clone_name, mount_point)
        if clone_name:
            DeleteClone(clone_name)
        raise e

    return rv

def VerifyUpdate(directory):
    """
    Verify the update in the directory is valid -- the manifest
    is sane, any signature is valid, the package files necessary to
    update are present, and have a valid checksum.  Returns either
    a file object if it's valid (the file object is locked), None
    if it doesn't exist, or it raises an exception -- one of
    UpdateIncompleteCacheException or UpdateInvalidCacheException --
    if necessary.
    """
    import fcntl

    # First thing we do is get the systen configuration and
    # systen manifest
    conf = Configuration.Configuration()
    mani = conf.SystemManifest()

    # Next, let's see if the directory exists.
    if not os.path.exists(directory):
        return None
    # Open up the manifest file.  Assuming it exists.
    try:
        mani_file = open(directory + "/MANIFEST", "r+")
    except:
        # Doesn't exist.  Or we can't get to it, which would be weird.
        return None
    # Let's try getting an exclusive lock on the manifest
    try:
        fcntl.lockf(mani_file, fcntl.LOCK_EX | fcntl.LOCK_NB, 0, 0)
    except:
        # Well, if we can't acquire the lock, someone else has it.
        # Throw an incomplete exception
        raise UpdateBusyCacheException("Cache directory %s is being modified" % directory)
    cached_mani = Manifest.Manifest()
    try:
        cached_mani.LoadFile(mani_file)
    except Exception as e:
        # If we got an exception, it's invalid.
        log.error("Could not load cached manifest file: %s" % str(e))
        raise UpdateInvalidCacheException
    
    # First easy thing to do:  look for the SEQUENCE file.
    try:
        cached_sequence = open(directory + "/SEQUENCE", "r").read().rstrip()
    except (IOError, Exception) as e:
        log.error("Could not sequence file in cache directory %s: %s" % (directory, str(e)))
        raise UpdateIncompleteCacheException("Cache directory %s does not have a sequence file" % directory)

    # Now let's see if the sequence matches us.
    if cached_sequence != mani.Sequence():
        log.error("Cached sequence, %s, does not match system sequence, %s" % (cached_sequence, mani.Sequence()))
        raise UpdateInvalidCacheException("Cached sequence does not match system sequence")

    # Next thing to do is go through the manifest, and decide which package files we need.
    # For each package, we want to see if we have a delta package that matches, and
    # has the right checksum, or the full package, that has the right checksum.
    # If neither file exists, then we have an incomplete situation; if both exist,
    # but don't have a valid checksum, we have an invalid situation.  If only one
    # exists, but has an invalid checksum, then we'll call it incomplete.
    for pkg in cached_mani.Packages():
        cur_vers = conf.CurrentPackageVersion(pkg.Name())
        new_vers = pkg.Version()
        if not os.path.exists(directory + "/" + pkg.FileName())  and \
           not os.path.exists(directory + "/" + pkg.FileName(cur_vers)):
            # Neither exists, so incoplete
            log.error("Cache %s  directory missing files for package %s" % (directory, pkg.Name()))
            raise UpdateIncompleteCacheException("Cache directory %s missing files for package %s" % (directory, pkg.Name()))
        # Okay, at least one of them exists.
        # Let's try the full file first
        try:
            with open(directory + "/" + pkg.FileName()) as f:
                if pkg.Checksum():
                    cksum = Configuration.ChecksumFile(f)
                    if cksum == pkg.Checksum():
                        continue
                else:
                    continue
        except:
            pass

        # Now we try the delta file
        # To do that, we need to find the right dictionary in the pkg
        upd_cksum = None
        found = False
        for update_dict in pkg.Updates():
            if update_dict[Package.VERSION_KEY] == cur_vers:
                if Package.CHECKSUM_KEY in update_dict:
                    upd_cksum = update_dict[Package.CHECKSUM_KEY]
                    try:
                        with open(directory + "/" + pkg.FileName(cur_vers)) as f:
                            cksum = Configuration.ChecksumFile(f)
                            if upd_cksum == cksum:
                                found = True
                                break
                    except:
                        pass
                else:
                    found = True
                    break
        if found is False:
            # If we got here, we are missing this file
            log_msg = "Cache directory %s is missing package %s" % (directory, pkg.Name())
            log.error(log_msg)
            raise UpdateIncompleteCacheException(log_msg)
    # And if we got here, then we have found all of the packages, the manifest is fine,
    # and the sequence tag is correct.
    mani_file.seek(0)
    return mani_file

def RemoveUpdate(directory):
    import shutil
    try:
        shutil.rmtree(directory)
    except:
        pass
    return
