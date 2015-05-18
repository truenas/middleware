from datetime import datetime
import ctypes
import logging
import os
import re
import signal
import subprocess
import sys

from . import Avatar
import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
import freenasOS.Installer as Installer
import freenasOS.Package as Package
from freenasOS.Exceptions import UpdateIncompleteCacheException, UpdateInvalidCacheException, UpdateBusyCacheException, UpdateBootEnvironmentException, UpdatePackageException

from freenasOS.Exceptions import ManifestInvalidSignature, UpdateManifestNotFound

log = logging.getLogger('freenasOS.Update')

debug = False

REQUIRE_REBOOT = True

# Not sure if these should go into their own file

SERVICES = {
    "gui" : {
        "Name" : "gui",
        "ServiceName": "gui",
        "Description": "Restart Web UI (forces a logout)",
        "CheckStatus" : False,
    },
    "SMB" : {
        "Name" : "CIFS",
        "ServiceName" : "cifs",
        "Description" : "Restart CIFS sharing",
        "CheckStatus" : True,
    },
    "AFP" : {
        "Name" : "AFP",
        "ServiceName" : "afp",
        "Description" : "Restart AFP sharing",
        "CheckStatus" : True,
    },
    "NFS" : {
        "Name" : "NFS",
        "ServiceName" : "nfs",
        "Description" : "Restart NFS sharing",
        "CheckStatus" : True,
    },
    "iSCSI" : {
        "Name" : "iSCSI",
        "ServiceName" : "iscsitarget",
        "Description" : "Restart iSCSI services",
        "CheckStatus" : True,
    },
    "FTP" : {
        "Name" : "FTP",
        "ServiceName" : "ftp",
        "Description" : "Restart FTP services",
        "CheckStatus" : True,
    },
    "WebDAV" : {
        "Name": "WebDAV",
        "ServiceName" : "webdav",
        "Description" : "Restart WebDAV services",
        "CheckStatus" : True,
    },
# Not sure what DirectoryServices would be
#    "DirectoryServices" : {
#        "Name" : "Restart directory services",
}

def GetServiceDescription(svc):
    if not svc in SERVICES:
        return None
    return SERVICES[svc]["Description"]

def VerifyServices(svc_names):
    """
    Verify whether the requested services are known or not.
    This is a trivial wrapper for now.
    """
    for name in svc_names:
        if not name in SERVICES:
            return False
    return True

def StopServices(svc_list):
    """
    Stop a set of services.  Returns the list of those that
    were stopped.
    """
    retval = []
    # Hm, this doesn't handle any particular ordering.
    # May need to fix this.
    # TODO: Uncomment the below when freenas10 is ready for rebootless updates
    # But also fix it for being appropriate to freenas10
    # for svc in svc_list:
    #     if not svc in SERVICES:
    #         raise ValueError("%s is not a known service" % svc)
    #     s = SERVICES[svc]
    #     svc_name = s["ServiceName"]
    #     log.debug("StopServices:  svc %s maps to %s" % (svc, svc_name))
    #     if (not s["CheckStatus"]) or n.started(svc_name):
    #         retval.append(svc)
    #         n.stop(svc_name)
    #     else:
    #         log.debug("svc %s is not started" % svc)
    return retval


def StartServices(svc_list):
    """
    Start a set of services.  THis is the output
    from StopServices
    """
    # Hm, this doesn't handle any particular ordering.
    # May need to fix this.
    # TODO: Uncomment the below when freenas10 is ready for rebootless updates
    # But also fix it for being appropriate to freenas10
    # for svc in svc_list:
    #     if not svc in SERVICES:
    #         raise ValueError("%s is not a known service" % svc)
    #     svc_name = SERVICES[svc]["ServiceName"]
    #     n.start(svc_name)
    return


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
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)
        try:
            child = subprocess.call(proc_args)
        except:
            return False
        libc.sigprocmask(signal.SIGQUIT, pomask, None)

    if child == 0:
        return True
    else:
        return False

def GetRootDataset():
    # Returns the name of the root dataset.
    # This will be of the form zroot/ROOT/<be-name>
    cmd = ["/bin/df", "/"]
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
        log.error("%s returned %d" % (cmd, p.returncode))
        return None
    lines = stdout.rstrip().split("\n")
    if len(lines) != 2:
        log.error("Unexpected output from %s, too many lines (%d):  %s" % (cmd, len(lines), lines))
        return None
    if not lines[0].startswith("Filesystem"):
        log.error("Unexpected output from %s:  %s" % (cmd, lines[0]))
        return None
    rv = lines[1].split()[0]
    return rv
                                                                                                                
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
        log.error("`%s' returned %d" %( cmd, p.returncode))
        return None

    for line in stdout.strip('\n').split('\n'):
        fields = line.split('\t')
        name = fields[0]
        if len(fields) > 5 and fields[5] != "-":
            name = fields[5]
        rv.append({
            'realname' : fields[0],
            'name': name,
            'active': fields[1],
            'mountpoint': fields[2],
            'space': fields[3],
            'created': datetime.strptime(fields[4], '%Y-%m-%d %H:%M'),
        })
    return rv

def FindClone(name):
    """
    Find a BE with the given name.  We look for nickname first,
    and then realname.  In order to do this, we first have to
    get the list of clones.
    Returns None if it can't be found, otherwise returns a
    dictionary.
    """
    rv = None
    clones = ListClones()
    for clone in clones:
        if clone["name"] == name:
            rv = clone
            break
        if clone["realname"] == name and rv is None:
            rv = clone
    return rv

"""
Notes to self:
/beadm create pre-${NEW}
zfs snapshot freenas-boot/ROOT/${CURRENT}@Pre-Upgrade-${NEW}
zfs inherit -r beadm:nickname freenas-boot/ROOT/${CURRENT}@Pre-Upgrade-${NEW}
/beadm rename -n ${CURRENT} ${NEW}
/beadm rename -n pre-{$NEW} ${CURRENT}

# Failure
	/beadm destroy -F ${CURRENT}
	/beadm rename -n ${NEW} ${CURRENT}
	zfs rollback freenas-boot/ROOT/${CURRENT}@Pre-Upgrade-${NEW}
	zfs set beadm:nickname=${CURRENT} freenas-boot/ROOT/${CURRENT}
# Success
	/beadm activate ${NEW}	# Not sure that's necessary or will work

# Either case
zfs destroy -r freenas-boot/ROOT/${CURRENT}@Pre-Upgrade-${NEW}	
"""

def CreateClone(name, snap_grub=True, bename=None, rename=None):
    # Create a boot environment from the current
    # root, using the given name.  Returns False
    # if it could not create it
    # If rename is set, we need to create the clone with
    # a temporary name, rename the root BE to its new
    # name, and then rename the new clone to the root name.
    # See above, excluding the snapshot.
    # If rename is set, then we want to create a new,
    # temporary BE, with the name pre-${name}; then
    # we rename ${rename} to ${name}, and then rename
    # pre-${name} to ${rename}.  In the event of
    # an error anywhere along, we undo as much as we can
    # and return an error.
    args = ["create"]
    if bename:
        # Due to how beadm works, if we are given a starting name,
        # we need to find the real name.
        cl = FindClone(bename)
        if cl is None:
            log.error("CreateClone:  Cannot find starting clone %s" % bename)
            return False
        log.debug("FindClone returned %s" % cl)
        args.extend(["-e", cl["realname"]])
    if rename:
        import random
        temp_name = "Pre-%s-%d" % (name, random.SystemRandom().randint(0, 1024 * 1024))
        args.append(temp_name)
        log.debug("CreateClone with rename, temp_name = %s" % temp_name)
    else:
        args.append(name)
    rv = RunCommand(beadm, args)
    if rv is False:
        return False

    if rename:
        # We've created Pre-<newname>-<random>
        # Now we want to reame the root environment, which is rename, to
        # the new name.
        args = ["rename", rename, name]
        rv = RunCommand(beadm, args)
        if rv is False:
            # We failed.  Clean up the temp one
            args = ["destroy", "-F", temp_name]
            RunCommand(beadm, args)
            return False
        # Root has been renamed, so let's rename the temporary one
        args = ["rename", temp_name, rename]
        rv = RunCommand(beadm, args)
        if rv is False:
            # We failed here.  How annoying.
            # So let's delete the newlyp-created BE
            # and rename root
            args = ["destroy", "-F", rename]
            RunCommand(beadm, args)
            args = ["rename", name, rename]
            RunCommand(beadm, args)
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
    # to set up /dev, /var/tmp, and /boot/grub.
    # Let's see if we need to do that
    if os.path.exists(grub_cfg) is True:
        if os.path.exists(mount_point + grub_cfg) is True:
            # We had a brief bit of insanity
            try:
                os.remove(mount_point + grub_cfg)
            except:
                pass
        # Okay, it needs to be mounted
        # To mount the grub fs, however, we need to unmount
        # it in root!  This is particularly annoying.
        cmd = "/sbin/umount"
        args = ["-f", grub_dir]
        rv = RunCommand(cmd, args)
        if rv is False:
            UnmountClone(name, None)
            return None
        # Now let's mount devfs, tmpfs, and grub
        args_array = [ ["-t", "devfs", "devfs", mount_point + "/dev"],
                       ["-t", "tmpfs", "tmpfs", mount_point + "/var/tmp"],
                       ["-t", "zfs", "freenas-boot/grub", mount_point + "/boot/grub" ]
                       ]
        cmd = "/sbin/mount"
        for fs_args in args_array:
            rv = RunCommand(cmd, fs_args)
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
    # the grub directory, and then remount it in its
    # proper place.  Then we can unmount /dev and /var/tmp
    # If this fails, we ignore it for now
    if mount_point is not None:
        cmd = "/sbin/umount"
        args = ["-f", mount_point + grub_dir]
        RunCommand(cmd, args)
        cmd = "/sbin/mount"
        args = ["/boot/grub"]
        rv = RunCommand(cmd, args)
        if rv is False:
            log.error("UNABLE TO MOUNT /boot/grub; SYSTEM MAY NOT BOOT")
            raise Exception("UNABLE TO REMOUNT /boot/grub; FIX MANUALLY OR SYSTEM AMY NOT BOOT")
        cmd = "/sbin/umount"
        for dir in ["/dev", "/var/tmp"]:
            args = ["-f", mount_point + dir]
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

def GetUpdateChanges(old_manifest, new_manifest, cache_dir = None):
    """
    This is used by both PendingUpdatesChanges() and CheckForUpdates().
    The difference between the two is that the latter doesn't necessarily
    have a cache directory, so if cache_dir is none, we have to assume the
    update package exists.
    This returns a dictionary that will have at least "Reboot" as a key.
    """
    def MergeServiceList(base_list, new_list):
        """
        Merge new_list into base_list.
        For each service in new_list (which is a dictionary),
        if the value is True, add it to base_list.
        If new_list is an array, simply add each item to
        base_list; if it's a dict, we check the value.
        """
        if new_list is None:
            return base_list
        if isinstance(new_list, list):
            for svc in new_list:
                if not svc in base_list:
                    base_list.append(svc)
        elif isinstance(new_list, dict):
            for svc, val in new_list.iteritems():
                if val:
                    if not svc in base_list:
                        base_list.append(svc)
        return base_list
    
    svcs = []
    diffs = Manifest.DiffManifests(old_manifest, new_manifest)
    if len(diffs) == 0:
        return None

    reboot = False
    if REQUIRE_REBOOT:
        reboot = True
        
    if "Packages" in diffs:
        # Look through the install/upgrade packages
        for pkg, op, old in diffs["Packages"]:
            if op == "delete":
                continue
            if op == "install":
                if pkg.RequiresReboot() == True:
                    reboot = True
                else:
                    pkg_services = pkg.RestartServices()
                    if pkg_services:
                        svcs = MergeServiceList(svcs, pkg_services)
            elif op == "upgrade":
                # A bit trickier.
                # If there is a list of services to restart, the update
                # path wants to look at that rather than the requires reboot.
                # However, one service could be to reboot (this is handled
                # below).
                upd = pkg.Update(old.Version())
                if cache_dir:
                    update_fname = os.path.join(cache_dir, pkg.FileName(old.Version()))
                else:
                    update_fname = None

                if upd and (update_fname is None or os.path.exists(update_fname)):
                    pkg_services = upd.RestartServices()
                    if pkg_services:
                        svcs = MergeServiceList(svcs, pkg_services)
                    else:
                        if upd.RequiresReboot() == True:
                            reboot = True
                else:
                    # Have to assume the full package exists
                    if pkg.RequiresReboot() == True:
                        reboot = True
                    else:
                        pkg_services = pkg.RestartServices()
                        if pkg_services:
                            svcs = MergeServiceList(svcs, pkg_services)
    else:
        reboot = False
    if len(diffs) == 0:
        return None
    if not reboot and svcs:
        if not VerifyServices(svcs):
            reboot = True
        else:
            diffs["Restart"] = svcs
    diffs["Reboot"] = reboot
    return diffs

def CheckForUpdates(handler = None, train = None, cache_dir = None, diff_handler = None):
    """
    Check for an updated manifest.  If cache_dir is none, then we try
    to download just the latest manifest for the given train, and
    compare it to the current system.  If cache_dir is set, then we
    use the manifest in that directory.
    """

    conf = Configuration.Configuration()
    new_manifest = None
    if cache_dir:
        try:
            mfile = VerifyUpdate(cache_dir)
            if mfile is None:
                return None
        except UpdateBusyCacheException:
            log.debug("Cache directory %s is busy, so no update available" % cache_dir)
            return None
        except (UpdateIncompleteCacheException, UpdateInvalidCacheException) as e:
            log.error("CheckForUpdate(train = %s, cache_dir = %s):  Got exception %s, removing cache" % (train, cache_dir, str(e)))
            RemoveUpdate(cache_dir)
            return None
        except BaseException as e:
            log.error("CheckForUpdate(train=%s, cache_dir = %s):  Got exception %s" % (train, cache_dir, str(e)))
            raise e
        # We always want a valid signature when doing an update
        new_manifest = Manifest.Manifest(require_signature = True)
        try:
            new_manifest.LoadFile(mfile)
        except Exception as e:
            log.error("Could not load manifest due to %s" % str(e))
            raise e
    else:
        try:
            new_manifest = conf.FindLatestManifest(train = train, require_signature = True)
        except Exception as e:
            log.error("Could not find latest manifest due to %s" % str(e))

    if new_manifest is None:
        raise UpdateManifestNotFound("Manifest could not be found!")

    # If new_manifest is not the requested train, then we don't have an update to do
    if train and train != new_manifest.Train():
        log.debug("CheckForUpdate(train = %s, cache_dir = %s):  Wrong train in caache (%s)" % (train, cache_dir, new_manifest.Train()))
        return None

    diffs = GetUpdateChanges(conf.SystemManifest(), new_manifest)
    if diffs is None or len(diffs) == 0:
        return None
    log.debug("CheckForUpdate:  diffs = %s" % diffs)
    if "Packages" in diffs:
        for (pkg, op, old) in diffs["Packages"]:
            if handler:
                handler(op, pkg, old)
    if diff_handler:
        diff_handler(diffs)
        
    return new_manifest

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
    mani = conf.SystemManifest()
    # First thing, let's get the latest manifest
    try:
        latest_mani = conf.FindLatestManifest(train, require_signature = True)
    except ManifestInvalidSignature as e:
        log.error("Latest manifest has invalid signature: %s" % str(e))
        return False

    if latest_mani is None:
        # This probably means we have no network.  Which means we have
        # to trust what we've already downloaded, if anything.
        log.error("Unable to find latest manifest for train %s" % train)
        try:
            VerifyUpdate(directory)
            log.debug("Possibly with no network, cached update looks good")
            return True
        except:
            log.debug("Possibly with no network, either no cached update or it is bad")
            return False

    cache_mani = Manifest.Manifest(require_signature = True)
    try:
        mani_file = VerifyUpdate(directory)
        if mani_file:
            cache_mani.LoadFile(mani_file)
            if cache_mani.Sequence() == latest_mani.Sequence():
                # Woohoo!
                mani_file.close()
                log.debug("DownloadUpdate:  Cache directory has latest manifest")
                return True
            # Not the latest
            mani_file.close()
        mani_file = None
    except UpdateBusyCacheException:
        log.debug("Cache directory %s is busy, so no update available" % directory)
        return False
    except (UpdateIncompleteCacheException, UpdateInvalidCacheException, ManifestInvalidSignature) as e:
        # It's incomplete, so we need to remove it
        log.error("DownloadUpdate(%s, %s):  Got exception %s; removing cache" % (train, directory, str(e)))
    except BaseException as e:
        log.error("Got exception %s while trying to prepare update cache" % str(e))
        raise e
    # If we're here, then we don't have a (valid) cached update.
    log.debug("Removing invalid or incomplete cached update")
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

    # Find out what differences there are
    diffs = Manifest.DiffManifests(mani, latest_mani)
    if diffs is None or len(diffs) == 0:
        log.debug("DownloadUpdate:  No update available")
        # Remove the cache directory and empty manifest file
        RemoveUpdate(directory)
        return False
    log.debug("DownloadUpdate:  diffs = %s" % diffs)
    
    download_packages = []
    reboot_required = True
    if "Reboot" in diffs:
        reboot_required = diffs["Reboot"]
        
    if "Packages" in diffs:
        for pkg, op, old in diffs["Packages"]:
            if op == "delete":
                continue
            log.debug("DownloadUpdate:  Will %s package %s" % (op, pkg.Name()))
            download_packages.append(pkg)

    log.debug("Update does%s seem to require a reboot" % "" if reboot_required else " not")
    
    # Next steps:  download the package files.
    for indx, pkg in enumerate(download_packages):
        # This is where we find out for real if a reboot is required.
        # To do that, we may need to know which update was downloaded.
        if check_handler:
            check_handler(indx + 1,  pkg = pkg, pkgList = download_packages)
        pkg_file = conf.FindPackageFile(pkg, save_dir = directory, handler = get_handler)
        if pkg_file is None:
            log.error("Could not download package file for %s" % pkg.Name())
            RemoveUpdate(directory)
            return False

    # Almost done:  get a changelog if one exists for the train
    # If we can't get it, we don't care.
    conf.GetChangeLog(train, save_dir = directory, handler = get_handler)
    # Then save the manifest file.
    latest_mani.StoreFile(mani_file)
    # Create the SEQUENCE file.
    with open(directory + "/SEQUENCE", "w") as f:
        f.write("%s" % conf.SystemManifest().Sequence())
    # And create the SERVER file.
    with open(directory + "/SERVER", "w") as f:
        f.write("%s" % conf.UpdateServerName())
        
    # Then return True!
    mani_file.close()
    return True

def PendingUpdates(directory):
    import traceback
    try:
        changes = PendingUpdatesChanges(directory)
        if changes is None or len(changes) <= 1:
            return False
        else:
            return True
    except:
        log.debug("PendingUpdatesChanges raised exception %s" % sys.exc_info()[0])
        traceback.print_exc()
        return False
    
def PendingUpdatesChanges(directory):
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
        raise
    except (UpdateIncompleteCacheException, UpdateInvalidCacheException) as e:
        log.error(str(e))
        RemoveUpdate(directory)
        raise
    except BaseException as e:
        log.error("Got exception %s while trying to determine pending updates" % str(e))
        raise
    if mani_file:
        new_manifest = Manifest.Manifest(require_signature = True)
        try:
            new_manifest.LoadFile(mani_file)
        except ManifestInvalidSignature as e:
            log.error("Invalid signature in cached manifest: %s" % str(e))
            raise
        # This returns a set of differences.
        # But we shouldn't rely on it until we can look at what we've
        # actually downloaded.  To do that, we need to look at any
        # package differences (diffs["Packages"]), and check the
        # updates if that's what got downloaded.
        # By definition, if there are no Packages differences, a reboot
        # isn't required.
        diffs = GetUpdateChanges(conf.SystemManifest(), new_manifest, cache_dir = directory)
        return diffs
    else:
        return None

def ServiceRestarts(directory):
    """
    Return a list of services to be stopped and started.  The paramter
    directory is the cache location; if it's not a valid cache directory,
    we return None.  (This is different from returning an empty set,
    which will be an array with no items.)  If a reboot is required,
    it returns an empty array.
    """
    changes = PendingUpdatesChanges(directory)
    if changes is None:
        return None
    retval = []
    if changes["Reboot"] is False:
        # Only look if we don't need to reboot
        if "Packages" in changes:
            # All service changes are package-specific
            for (pkg, op, old) in changes["Packages"]:
                svcs = None
                if op in ("install", "delete"):
                    # Either the service is added or removed,
                    # either way we add it to the list.
                    svcs = pkg.RestartServices()
                elif op == "upgrade":
                    # We need to see if we have the delta package
                    # file or not.
                    delta_pkg_file = os.path.join(directory, pkg.FileName(old.Version()))
                    if os.path.exists(delta_pkg_file):
                        # Okay, we're doing an update
                        upd = pkg.Update(old.Version())
                        if not upd:
                            # How can this happen?
                            raise Exception("I am confused")
                        svcs = upd.RestartServices()
                    else:
                        # Only need to the services listed at the outer level
                        svcs = pkg.RestartServices()

                if svcs:
                    for svc in svcs:
                        if not svc in retval:
                            retval.append(svc)
                                
    return retval
                    
def ApplyUpdate(directory, install_handler = None, force_reboot = False):
    """
    Apply the update in <directory>.  As with PendingUpdates(), it will
    have to verify the contents before it actually installs them, so
    it has the same behaviour with incomplete or invalid content.
    """
    rv = False
    conf = Configuration.Configuration()
    # Note that PendingUpdates may raise an exception
    changes = PendingUpdatesChanges(directory)
        
    if changes is None:
        # This means no updates to apply, and so nothing to do.
        return None

    # Do I have to worry about a race condition here?
    new_manifest = Manifest.Manifest(require_signature = True)
    try:
        new_manifest.LoadPath(directory + "/MANIFEST")
    except ManifestInvalidSignature as e:
        log.error("Cached manifest has invalid signature: %s" % str(e))
        raise e

    conf.SetPackageDir(directory)

    # If we're here, then we have some change to make.
    # PendingUpdatesChanges always sets this, unless it returns None
    reboot = changes["Reboot"]
    if force_reboot:
        # Just in case
        reboot = True
    if REQUIRE_REBOOT:
        # In case we have globally disabled rebootless updates
        reboot = True
    changes.pop("Reboot")
    if len(changes) == 0:
        # This shouldn't happen
        log.debug("ApplyUupdate:  changes only has Reboot key")
        return None

    service_list = None
    deleted_packages = []
    updated_packages = []
    if "Packages" in changes:
        for (pkg, op, old) in changes["Packages"]:
            if op == "delete":
                log.debug("Delete package %s" % pkg.Name())
                deleted_packages.append(pkg)
                continue
            elif op == "install":
                log.debug("Install package %s" % pkg.Name())
                updated_packages.append(pkg)
            elif op == "upgrade":
                log.debug("Upgrade package %s-%s to %s-%s" % (old.Name(), old.Version(), pkg.Name(), pkg.Version()))
                updated_packages.append(pkg)
            else:
                log.error("Unknown package operation %s for %s" % (op, pkg.Name()))

    if new_manifest.Sequence().startswith(Avatar() + "-"):
        new_boot_name = new_manifest.Sequence()
    else:
        new_boot_name = "%s-%s" % (Avatar(), new_manifest.Sequence())
        
    log.debug("new_boot_name = %s, reboot = %s" % (new_boot_name, reboot))
    
    mount_point = None
    if reboot:
        # Need to create a new boot environment
        try:
            if CreateClone(new_boot_name) is False:
                log.debug("Failed to create BE %s" % new_boot_name)
                # It's possible the boot environment already exists.
                s = None
                clones = ListClones()
                if clones:
                    found = False
                    for c in clones:
                        if c["name"] == new_boot_name:
                            found = True
                            if c["mountpoint"] == "/":
                                s = "Cannot create boot-environment with same name as current boot-environment (%s)" % new_boot_name
                                break
                            else:
                                # We'll have to destroy it.
                                # I'd like to rename it, but that gets tricky, due
                                # to nicknames.
                                if DeleteClone(new_boot_name) == False:
                                    s = "Cannot destroy BE %s which is necessary for upgrade" % new_boot_name
                                    log.debug(s)
                                elif CreateClone(new_boot_name) is False:
                                    s = "Cannot create new BE %s even after a second attempt" % new_boot_name
                                    log.debug(s)
                            break
                    if found is False:
                        s = "Unable to create boot-environment %s" % new_boot_name
                else:    
                    log.debug("Unable to list clones after creation failure")
                    s = "Unable to create boot-environment %s" % new_boot_name
                if s:
                    log.error(s)
                    raise UpdateBootEnvironmentException(s)
            if mount_point is None:
                mount_point = MountClone(new_boot_name)
        except:
            mount_point = None
            s = sys.exc_info()[0]
        if mount_point is None:
            s = "Unable to mount boot-environment %s" % new_boot_name
            log.error(s)
            DeleteClone(new_boot_name)
            raise UpdateBootEnvironmentException(s)
    else:
        # Need to do magic to move the current boot environment aside,
        # and assign the newname to the current boot environment.
        # Also need to make a snapshot of the current root so we can
        # clean up on error
        mount_point = None
        log.debug("We should try to do a non-rebooty update")
        root_dataset = GetRootDataset()
        if root_dataset is None:
            log.error("Unable to determine root environment name")
            raise UpdateBootEnvironmentException("Unable to determine root environment name")
        # We also want the root name
        root_env = None
        clones = ListClones()
        if clones is None:
            log.error("Unable to determine root BE")
            raise UpdateBootEnvironmentException("Unable to determine root BE")
        for clone in clones:
            if clone["mountpoint"] == "/":
                root_env = clone
                break
        if root_env is None:
            log.error("Unable to find root BE!")
            raise UpdateBootEnvironmentException("Unable to find root BE!")
        
        # Now we want to snapshot the current boot environment,
        # so we can rollback as needed.
        snapshot_name = "%s@Pre-Uprgade-%s" % (root_dataset, new_manifest.Sequence())
        cmd = "/sbin/zfs"
        args = ["snapshot", "-r", snapshot_name ]
        rv = RunCommand(cmd, args)
        if rv is False:
            log.error("Unable to create snapshot %s, bailing for now" % snapshot_name)
            raise UpdateSnapshotException("Unable to create snapshot %s" % snapshot_name)
        # We need to remove the beadm:nickname property.  I hate knowing this much
        # about the implementation
        args = ["inherit", "-r", "beadm:nickname", snapshot_name ]
        RunCommand(cmd, args)
        
        # At this point, we'd want to rename the boot environment to be the new
        # name, which would be new_manifest.Sequence()
        if CreateClone(new_boot_name, rename = root_env["name"]) is False:
            log.error("Unable to create new boot environment %s" % new_boot_name)
            # Roll back and destroy the snapshot we took
            cmd = "/sbin/zfs"
            args = ["rollback", snapshot_name ]
            RunCommand(cmd, args)
            args[0] = "destroy"
            RunCommand(cmd, args)
            # And set the beadm:nickname property back
            args = ["set", "beadm:nickname=%s" % root_env["name"]]
            RunCommand(cmd, args)
            
            raise UpdateBootEnvironmentException("Unable to create new boot environment %s" % new_boot_nam)
        if "Restart" in changes:
            service_list = StopServices(changes["Restart"])
            
    # Now we start doing the update!
    # If we have to reboot, then we need to
    # make a new boot environment, with the appropriate name.
    # If we are *not* rebooting, then we want to rename the
    # current one with the appropriate name, while at the same
    # time cloning the current one and keeping the existing name.
    # Easy peasy, right?
    
    try:
        # Remove any deleted packages
        for pkg in deleted_packages:
            log.debug("About to delete package %s" % pkg.Name())
            if conf.PackageDB(mount_point).RemovePackageContents(pkg) == False:
                s = "Unable to remove contents for packate %s" % pkg.Name()
                if mount_point:
                    UnmountClone(new_boot_name, mount_point)
                    mount_point = None
                    DeleteClone(new_boot_name)
                raise UpdatePackageException(s)
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
            raise UpdatePackageException("Unable to install packages")
        else:
            new_manifest.Save(mount_point)
            if mount_point:
                if UnmountClone(new_boot_name, mount_point) is False:
                    s = "Unable to unmount clone environment %s from mount point %s" % (new_boot_name, mount_point)
                    log.error(s)
                    raise UpdateBootEnvironmentException(s)
                mount_point = None
            if reboot:
                if ActivateClone(new_boot_name) is False:
                    s = "Unable to activate clone environment %s" % new_boot_name
                    log.error(s)
                    raise UpdateBootEnvironmentException(s)
            if not reboot:
                # Try to restart services before cleaning up.
                # Although maybe that's not the right way to go
                if service_list:
                    StartServices(service_list)
                    service_list = None
                # Clean up the emergency holographic snapshot
                cmd = "/sbin/zfs"
                args = ["destroy", "-r", snapshot_name ]
                rv = RunCommand(cmd, args)
                if rv is False:
                    log.error("Unable to destroy snapshot %s" % snapshot_name)
            RemoveUpdate(directory)
            # RunCommand("/sbin/zpool", ["scrub", "freenas-boot"])
    except BaseException as e:
        # Cleanup code is entirely different for reboot vs non reboot
        log.error("Update got exception during update: %s" % str(e))
        if reboot:
            if mount_point:
                UnmountClone(new_boot_name, mount_point)
            if new_boot_name:
                DeleteClone(new_boot_name)
        else:
            # Need to roll back
            # We also need to delete the renamed clone of /,
            # and then rename / to the original name.
            # First, however, destroy the clone
            rv = DeleteClone(root_env["name"])
            if rv:
                # Next, rename the clone
                rv = RenameClone(new_boot_name, root_env["name"])
                if rv:
                    # Now roll back the snapshot, and set the beadm:nickname value
                    cmd = "/sbin/zfs"
                    args = [ "rollback", "-r", snapshot_name]
                    rv = RunCommand(cmd, args)
                    if rv is False:
                        log.error("Unable to rollback %s" % snapshot_name)
                        # Don't know what to do then
                    args = ["set", "beadm:nickname=%s" % root_env["name"], "freenas-boot/ROOT/%s" % root_env["name"]]
                    rv = RunCommand(cmd, args)
                    if rv is False:
                        log.error("Unable to set nickname, wonder what I did wrong")
                    args = ["destroy", "-r", snapshot_name ]
                    rv = RunCommand(cmd, args)
                    if rv is False:
                        log.error("Unable to destroy snapshot %s" % snapshot_name)
            if service_list:
                StartServices(service_list)
        raise e

    return reboot

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
    # We always want a valid signature for an update.
    cached_mani = Manifest.Manifest(require_signature = True)
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

    # Second easy thing to do:  if there is a SERVER file, make sure it's the same server
    # name we're using
    cached_server = "default"
    try:
        cached_server = open(directory + "/SERVER", "r").read().rstrip()
    except (IOError, Exception) as e:
        log.debug("Could not open SERVER file in cache direcory %s: %s" % (directory, str(e)))
        cached_server = "default"

    if cached_server != conf.UpdateServerName():
        log.error("Cached server, %s, does not match system update server, %s" % (cached_server, conf.UpdateServerName()))
        raise UpdateInvalidCacheException("Cached server name does not match system update server")
    
    # Next thing to do is go through the manifest, and decide which package files we need.
    diffs = Manifest.DiffManifests(mani, cached_mani)
    # This gives us an array to examine.
    # All we care about for verification is the packages
    if "Packages" in diffs:
        for (pkg, op, old) in diffs["Packages"]:
            if op == "delete":
                # Deleted package, so we don't need to do any verification here
                continue
            if op == "install":
                # New package, being installed, so we need the full package
                cur_vers = None
            if op == "upgrade":
                # Package being updated, so we can look for the delta package.
                cur_vers = old.Version()
            new_vers = pkg.Version()
            # This is slightly redundant -- if cur_vers is None, it'll check
            # the same filename twice.
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

            if cur_vers is None:
                e = "Cache directory %s missing files for package %s" % (directory, pkg.Name())
                log.error(e)
                raise UpdateIncompleteCacheException(e)
        
            # Now we try the delta file
            # To do that, we need to find the right dictionary in the pkg
            upd_cksum = None
            update = pkg.Update(cur_vers)
            if update and update.Checksum():
                upd_cksum = update.Checksum()
                try:
                    with open(directory + "/" + pkg.FileName(cur_vers)) as f:
                        cksum = Configuration.ChecksumFile(f)
                        if upd_cksum != cksum:
                            update = None
                except:
                    update = None
            if update is None:
                # If we got here, we are missing this file
                log_msg = "Cache directory %s is missing package %s" % (directory, pkg.Name())
                log.error(log_msg)
                raise UpdateIncompleteCacheException(log_msg)
        # And end that loop
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
