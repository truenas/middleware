import os
import sys
import errno
import stat
import json
import tarfile
import hashlib
import logging
import tempfile

# And now freenas modules
import Configuration

debug = 0
verbose = False

log = logging.getLogger('freenasOS.Installer')

class InstallerConfigurationException(Exception):
    pass

class InstallerPackageNotFoundException(Exception):
    pass

class InstallerInsufficientSpaceException(Exception):
    pass

class InstallerUnknownFileTypeException(Exception):
    pass

class InstallerUnknownDeltaStyleException(Exception):
    pass

# A list of architectures we consider valid.
        
pkg_valid_archs = [ "freebsd:9:x86:64", "freebsd:10:x86:64" ]
# Some constants for the manifest JSON.
# The ones we care about (for now) are
# the package name, version, set of files, set
# of directories, prefix, architecture, and
# installation scripts.

PKG_NAME_KEY = "name"
PKG_VERSION_KEY = "version"
PKG_SCRIPTS_KEY = "scripts"
PKG_FILES_KEY = "files"
PKG_DIRECTORIES_KEY = "directories"
PKG_DIRS_KEY = "dirs"
PKG_REMOVED_FILES_KEY = "removed-files"
PKG_REMOVED_DIRS_KEY = "removed-directories"
PKG_PREFIX_KEY = "prefix"
PKG_ARCH_KEY = "arch"
PKG_DELTA_KEY = "delta-version"

PKG_DELTA_VERSION_KEY = PKG_VERSION_KEY
PKG_DELTA_STYLE_KEY = "style"

PKG_MANIFEST_NAME = "+MANIFEST"

# These are the keys for the scripts
PKG_SCRIPTS = [ "pre-install", "install", "post-install",
                "pre-deinstall", "deinstall", "post-deinstall",
                "pre-upgrade", "upgrade", "post-upgrade",
                "pre-delta", "post-delta"
            ]
        
def enum(**enums):
    return type('Enum', (), enums)

PKG_SCRIPT_TYPES = enum(PKG_SCRIPT_PRE_DEINSTALL = "pre-deinstall",
                        PKG_SCRIPT_DEINSTALL = "deinstall",
                        PKG_SCRIPT_POST_DEINSTALL = "post-deinstall",
                        PKG_SCRIPT_PRE_INSTALL = "pre-install",
                        PKG_SCRIPT_INSTALL = "install",
                        PKG_SCRIPT_POST_INSTALL = "post-install",
                        PKG_SCRIPT_PRE_UPGRADE = "pre-upgrade",
                        PKG_SCRIPT_UPGRADE = "upgrade",
                        PKG_SCRIPT_POST_UPGRADE = "post-upgrade",
                        PKG_SCRIPT_PRE_DELTA = "pre-delta",
                        PKG_SCRIPT_POST_DELTA = "post-delta",
                    )

SCRIPT_INSTALL = [ ["pre_install"],
                   ["install", "PRE-INSTALL"],
                   ["post_install"],
                   ["install", "POST-INSTALL"],
                   ]
SCRIPT_UPGRADE = [ ["pre_upgrade"],
                   ["upgrade", "PRE-UPGRADE"],
                   ["post_upgrade"],
                   ["upgrade", "POST-UPGRADE"],
                   ]

"""
This is how installs should be done, according to the pkgng wiki:
                        
Installing a package with pkgng
                        
        execute pre_install script if any exists
        execute install script with PRE-INSTALL argument
        extract files directly to the right place
        extract directories directly to the right place
        execute post_install script if any exists
        execute install script with POST-INSTALL arguments
    
Deinstalling a package with pkgng
        
        execute pre_deinstall script if any exists
        execute deinstall script with DEINSTALL argument
        removes files
        execute post_deinstall script if any exists
        execute install script with POST-DEINSTALL arguments
        extract directories

Upgrading a package with pkgng

A package can be in version 1: not upgrade aware, or in version 2: upgrade aware.
If both the installed package and the new package are upgrade aware:

        execute pre_upgrade script from the old package
        execute upgrade script with PRE-UPGRADE argument from the old package
        remove files from the old package
        remove directories from the old package
        extract files and directories from the new package
        execute post_upgrade script from the new package
        execute upgrade script with POST-UPGRADE argument from the new package
        
otherwise if falls back to the dumb way:

        deinstall the old package
        install the new one
                        
SEF:  This would require keeping old manifest file around.
Also, I don't think removing the files works too well with us.  Certainly
can't remove the directories from the base-os package!  I also do not see how
it works in the pkgng code.
"""
#
# Remove a file.  This will first try to do an
# unlink, then try to change flags if there are
# permission problems.  (Think, schg)
def RemoveFile(path):
    global debug
    try:
        os.lchflags(path, 0)
    except os.error as e:
        pass
    try:
        os.unlink(path)
    except  os.error as e:
        if e[0] == errno.ENOENT:
            return True
        else:
            if debug: log.debug("RemoveFile(%s):  errno = %d" % (path, e[0]))
            return False
    if os.path.exists(path):
	raise Exception("After removal, %s still exists" % path)
    return True

# Like the above, but for a directory.
def RemoveDirectory(path):
    st = None
    try:
        st = os.lstat(path)
    except os.error:
        return False
    try:
        os.lchflags(path, 0)
    except os.error:
        pass
    try:
        os.rmdir(path)
    except os.error:
        if st.st_flags:
            try:
                os.lchflags(path, st.st_flags)
            except os.error:
                pass
        return False
    return True

def MakeDirs(dir):
    try:
        os.makedirs(dir, 0755)
    except:
        pass
    return

def SetPosix(path, meta):
    amroot = os.geteuid() == 0
    try:
        os.lchown(path, meta[TAR_UID_KEY], meta[TAR_GID_KEY])
    except os.error as e:
        # If we're not root, we can't do the chown
        if e[0] != errno.EPERM and amroot:
            raise e
    os.lchmod(path, meta[TAR_MODE_KEY])
    if meta[TAR_FLAGS_KEY] != 0:
        try:
            os.lchflags(path, meta[TAR_FLAGS_KEY])
        except os.error as e:
            # If we're not root, we can't do some of this, either
            if e[0] != errno.EPERM and amroot:
                raise e

def EntryInDictionary(name, mDict, prefix):
    if (name in mDict):  return True
    if prefix is not None:
        if (prefix + name in mDict):
            return True
        if (prefix + name).startswith("/") == False:
            if "/" + prefix + name in mDict:
                return True
    return False

# Constants used for tar meta dictionaries.
TAR_UID_KEY = "uid"
TAR_GID_KEY = "gid"
TAR_MODE_KEY = "mode"
TAR_FLAGS_KEY = "flags"
# This will be file, dir, slink, link; anything else will throw an exception
TAR_TYPE_KEY = "type"

def GetTarMeta(ti):
    global debug, verbose
    ext_keys = {
        "nodump" : stat.UF_NODUMP,
        "sappnd" : stat.SF_APPEND,
        "schg" : stat.SF_IMMUTABLE,
        "sunlnk" : stat.SF_NOUNLINK,
        "uchg" : stat.UF_IMMUTABLE,
        }
    rv = {}
    rv[TAR_UID_KEY] = ti.uid
    rv[TAR_GID_KEY] = ti.gid
    rv[TAR_MODE_KEY] = stat.S_IMODE(int(ti.mode))
    rv[TAR_FLAGS_KEY] = 0
    if ti.isfile():
        rv[TAR_TYPE_KEY] = "file"
    elif ti.isdir():
        rv[TAR_TYPE_KEY] = "dir"
    elif ti.issym():
        rv[TAR_TYPE_KEY] = "slink"
    elif ti.islnk():
        rv[TAR_TYPE_KEY] = "link"
    else:
        raise InstallerUnknownFileTypeException("Unknown tarinfo type %s" % ti.type)

    # This appears to be how libarchive (and hence tarfile)
    # handles BSD flags.  Such a pain.
    if ti.pax_headers is not None:
        flags = 0
        if "SCHILY.fflags" in ti.pax_headers:
            for k in ti.pax_headers["SCHILY.fflags"].split(","):
                if debug > 1: log.debug("flag %s" % k)
                if k in ext_keys:
                    flags |= ext_keys[k]
            if debug > 1: log.debug("flags was %s, value = %o" % (ti.pax_headers["SCHILY.fflags"], flags))
        rv[TAR_FLAGS_KEY] = flags
    return rv


def RunPkgScript(scripts, type, root = None, **kwargs):
    # This makes my head hurt
    if scripts is None:
        return
    if type not in scripts:
        if verbose or debug:  log.debug("No %s script to run" % type)
        return
    
    scriptName = "/%d-%s" % (os.getpid(), type)
    if root and root != "":
        scriptPath = "%s%s" % (root, scriptName)
    else:
        # Writing to root isn't ideal, so this should be re-examined
        scriptName = "/tmp" + scriptName
        scriptPath = scriptName
        
    with open(scriptPath, "w") as f:
        f.write(scripts[type])
    args = ["sh", "-x", scriptName]
    if "SCRIPT_ARG" in kwargs and kwargs["SCRIPT_ARG"] is not None:
        args.append(kwargs["SCRIPT_ARG"])
        
    print "script (chroot to %s):  %s\n-----------" % ("/" if root is None else root, args)
    print "%s\n--------------" % scripts[type]
    if os.geteuid() != 0 and root is not None:
        log.error("Installation root is set, and process is not root.  Cannot run script %s" % type)
        if debug < 4:
            return
    else:
        pid = os.fork()
        if pid == 0:
            # Child
            if root:
                os.chroot(root)
            if "PKG_PREFIX" in kwargs and kwargs["PKG_PREFIX"] is not None:
                os.environ["PKG_PREFIX"] = kwargs["PKG_PREFIX"]
            os.execv("/bin/sh", args)
            sys.exit(1)
        elif pid != -1:
            # Parent
            (tpid, status) = os.wait()
            if tpid != pid:
                log.error("What?  I waited for process %d and I got %d instead!" % (pid, tpid))
            if status != 0:
                # Should I raise an exception?
                log.error("Sub procss exited with status %#x" % status)
        else:
            log.error("Huh?  Got -1 from os.fork and no exception?")

    os.unlink(scriptPath)
        
    return

# This function does the bulk of the work for installation.
# It is given a tarfile object, an entry object into it, a
# root directory, and an optional prefix and hash.

def ExtractEntry(tf, entry, root, prefix = None, mFileHash = None):
    # This bit of code tries to turn the
    # mixture of root, prefix, and pathname into something
    # we can both manipulate, and something we can put into
    # the database.
    # The database should have absolute paths, with no duplicate
    # slashes and whatnot.  manifest paths come in one of two
    # formats, generally:  beginning with "./", or beginning with "/"
    # So those are the two we look for.
    # We also check for root and prefix ending in "/", but the root
    # checking is just for prettiness while debugging.
    global debug, verbose
    TYPE_DIR = "dir"
    TYPE_FILE = "file"
    TYPE_SLNK = "slink"
    TYPE_OTHER = "unknown"

    orig_type = None
    new_type = None

    fileName = entry.name
    if fileName.startswith("./"):
        fileName = fileName[2:]
    if fileName.startswith("/") or prefix is None:
        pass
    else:
        fileName = "%s%s%s" % (prefix, "" if prefix.endswith("/") or entry.name.startswith("/") else "/", fileName)
    if root:
        full_path = "%s%s%s" % (root, "" if root.endswith("/") or fileName.startswith("/") else "/", fileName)
    else:
        full_path = "%s%s" % ("" if fileName.startswith("/") else "/", fileName)
        root = ""
    try:
	import stat
	m = os.lstat(full_path).st_mode
	if stat.S_ISDIR(m):
	    orig_type = TYPE_DIR
	elif stat.S_ISREG(m):
	    orig_type = TYPE_FILE
	elif stat.S_ISLNK(m):
	    orig_type = TYPE_SLNK
	else:
	    orig_type = TYPE_OTHER
    except:
	orig_type = None

    # After that, we've got a full_path, and so we get the directory it's in,
    # and the name of the file.
    dirname = os.path.dirname(full_path)
    # Debugging stuff
    if debug > 0 or verbose: log.debug("%s:  will be extracted as %s" % (entry.name, full_path))
    if debug > 2: log.debug("entry = %s" % (entry))
        
    # Get the metainformation from the TarInfo entry.  This is complicated
    # because of how flags are done.  Note that we don't bother with time
    # information.
    meta = GetTarMeta(entry)
    
    # Make sure the directory we're creating in exists.
    # We don't bother with ownership/mode of the intermediate paths,
    # because either it will exist already, or will be part of the
    # manifest, in which case posix information will be set.  (We
    # do use a creation mask of 0755.)
    if not os.path.isdir(dirname):
        MakeDirs(dirname)
    type = None
    hash = ""
    
    if entry.isfile() or entry.islnk():
	new_type = TYPE_FILE
    elif entry.isdir():
	new_type = TYPE_DIR
    elif entry.issym():
	new_type = TYPE_SLNK
    else:
	new_type = TYPE_OTHER

    # If the type of the entry changed, but it didn't get removed,
    # then bad things could happen.  Especially if it changed from
    # a symlink to a file or directory.
    if orig_type is not None and orig_type != new_type:
	log.debug("Original type = %s, new type = %s, path = %s" % (orig_type, new_type, full_path))
	log.debug("Removing original entry")
	if os.path.islink(full_path) or os.path.isfile(full_path):
	    RemoveFile(full_path)
	elif os.path.isdir(full_path):
	    import shutil
	    try:
		shutil.rmtree(full_path)
	    except BaseException as e:
		log.error("Couldn't remove old directory %s: %s" % (full_path, str(e)))
		raise e
    # Process the entry.  We look for a file, directory,
    # symlink, or hard link.
    if entry.isfile():
        fileData = tf.extractfile(entry)
        # Is this a problem?  Keeping the file in memory?
        # Note that we write the file out later, so this allows
        # us to not worry about the buffer.
        try:
            temp_entry = tempfile.TemporaryFile(dir = os.path.dirname(full_path))
        except:
            s = "Cannot crate temporary file in %s" % os.path.dirname(full_path)
            log.error(s)
            raise
        hash = hashlib.sha256()
        while True:
            d = fileData.read(1024 * 1024)
            if d:
                hash.update(d)
                temp_entry.write(d)
            else:
                break
        hash = hash.hexdigest()
        temp_entry.seek(0)
        # PKGNG sets hash to "-" if it's not computed.
        if mFileHash != "-":
            if hash != mFileHash:
                log.error("%s hash does not match manifest" % entry.name)
        type = "file"
        # First we try to create the file.
        # If that doesn't work, we try to create a
        # new file (how would this get cleaned up?),
        # and then rename it in place.
        # We remove any flags on it -- if there are
        # supposed to be any, SetPosix() will get them.
        # (We hope.)
        try:
            os.lchflags(full_path, 0)
        except:
            pass
        newfile = None
        try:
            f = open(full_path, "w")
        except:
            newfile = full_path + ".new"
            f = open(newfile, "w")
        while True:
            d = temp_entry.read(1024 * 1024)
            if d:
                f.write(d)
            else:
                break
        f.close()
        temp_entry.close()
        if newfile is not None:
            try:
                os.rename(newfile, full_path)
            except:
                os.rename(full_path, "%s.old" % full_path)
                os.rename(newfile, full_path)
        SetPosix(full_path, meta)
    elif entry.isdir():
        # If the directory already exists, we don't care.
        try:
            os.makedirs(full_path)
        except os.error as e:
            if e[0] != errno.EEXIST:
                raise e
        SetPosix(full_path, meta)
        
        type = "dir"
        hash = ""
    elif entry.issym():
        if mFileHash != "-":
            # pkgng now does checksums of symlinks.
            # But they remove the leading / for the target,
            # so we have to do the same.
            if entry.linkname.startswith("/"):
                hash = hashlib.sha256(entry.linkname[1:]).hexdigest()
            else:
                hash = hashlib.sha256(entry.linkname).hexdigest()
            if hash != mFileHash:
                log.error("%s hash does not match manifest" % entry.name)
                hash = ""
        else:
            # Setting it to '-' will let us know why the entry has no
            # checksum.
            hash = "-"
        # Try to remove the symlink first.
        # Then create the new one.
        try:
            os.unlink(full_path)
        except os.error as e:
            if e[0] == errno.EPERM and os.path.isdir(full_path):
                # You can't unlink a directory these days.
                import shutil
                try:
                    # This is a truly terrifying thing to do
                    shutil.rmtree(full_path)
                except BaseException as e2:
                    log.error("Couldn't rmtree %s: %s" % (full_path, str(e2)))
                    raise e2
            elif e[0] != errno.ENOENT:
                log.error("Couldn't unlink %s: %s" % (full_path, e[0]))
                raise e
        os.symlink(entry.linkname, full_path)
        SetPosix(full_path, meta)
        type = "slink"
    elif entry.islnk():
        source_file = root + "/" + entry.linkname
        try:
            st = os.lstat(source_file)
            os.lchflags(source_file, 0)
            try:
                os.lchflags(full_path, 0)
                os.unlink(full_path)
            except:
                pass
            try:
                os.link(source_file, full_path)
            except os.error as e:
                if e[0] == errno.EXDEV:
                    log.debug("Unable to link %s -> %s, trying a copy" % (source_file, full_path))
                    # Cross-device link, so we'll just copy it
                    try:
                        kBufSize = 1024 * 1024
                        source = open(source_file, "rb")
                        dest = open(full_path, "wb")
                        while True:
                            buffer = source.read(kBufSize)
                            if buffer:
                                dest.write(buffer)
                            else:
                                break
                        os.lchmod(full_path, st.st_mode)
                    except:
                        log.error("Couldn't copy %s to %s" % (source_file, full_path))
                        raise
                else:
                    log.error("Couldn't link %s to %s: %s" % (source_file, full_path, e[0]))
                    raise e
            if st.st_flags != 0:
                os.lchflags(source_file, st.st_flags)
        
        except os.error as e:
            log.error("Could not link %s to %s: %s" % (source_file, full_path, str(e)))
            sys.exit(1)
        # Except on mac os, hard links are always files.
        type = "file"
        # Cheating a bit:  we'll use the same hash for the hard-link file that's in the pkgng manifest.
        hash = mFileHash
            
    if type is not None:
        return (fileName,
                type,
                hash,
                meta[TAR_UID_KEY],
                meta[TAR_GID_KEY],
                meta[TAR_FLAGS_KEY],
                meta[TAR_MODE_KEY])
    else:
        return None

def install_path(pkgfile, dest):
    try:
        f = open(pkgfile, "r")
    except Exception as err:
        log.error("Cannot open package file %s: %s" % (pkgfile, str(err)))
        return False
    else:
        return install_file(f, dest)
            
def install_file(pkgfile, dest):
    global debug, verbose, dryrun
    prefix = None
    # We explicitly want to use the pkgdb from the destination
    pkgdb = Configuration.PackageDB(dest)
    pkgScripts = None
    upgrade_aware = False

    try:
        t = tarfile.open(fileobj = pkgfile)
    except Exception as err:
        log.error("Could not open package file %s: %s" % (pkgfile.name, str(err)))
        return False

    member = None
    mjson = None
    # Skip past entries with '#', except for
    # the manifest file
    for member in t:
        if not member.name.startswith("+"): break
        if member.name == PKG_MANIFEST_NAME:
            manifest = t.extractfile(member)
            mjson = json.load(manifest)
            manifest.close()

    # All packages must have a +MANIFEST file.
    # (We don't support +COMPACT_MANIFEST, at least not yet)
    if mjson is None:
        log.error("Could not find manifest in package file %s" % pkgfile.name)
        return False
    
    # Check the architecture
    if PKG_ARCH_KEY in mjson:
        if not (mjson[PKG_ARCH_KEY] in pkg_valid_archs):
            log.error("Architecture %s is not valid" % mjson[PKG_ARCH_KEY])
            return False

    if PKG_PREFIX_KEY in mjson:
        prefix = mjson[PKG_PREFIX_KEY]
        if verbose or debug: log.debug("prefix = %s" % prefix)
    
    # See above for how scripts are handled.  It's a mess.
    if PKG_SCRIPTS_KEY in mjson:
        pkgScripts = mjson[PKG_SCRIPTS_KEY]
    else:
        pkgScripts = {}

    # At this point, the tar file is at the first non-+-named files.
    
    pkgName = mjson[PKG_NAME_KEY]
    pkgVersion = mjson[PKG_VERSION_KEY]
    pkgDeletedFiles = []
    pkgDeletedDirs = []
    if PKG_DELTA_KEY in mjson:
        pkgDeltaDict = mjson[PKG_DELTA_KEY]
        # This will throw an exception if it's not there,
        # but that's okay -- it needs to be.
        # See diff_packages (should they coordinate?).
        if pkgDeltaDict[PKG_DELTA_STYLE_KEY] != "file":
            raise InstallerUnknownDeltaStyleException

        pkgDeltaVersion = pkgDeltaDict[PKG_DELTA_VERSION_KEY]

        if PKG_REMOVED_FILES_KEY in mjson: pkgDeletedFiles = mjson[PKG_REMOVED_FILES_KEY]
        if PKG_REMOVED_DIRS_KEY in mjson: pkgDeletedDirs = mjson[PKG_REMOVED_DIRS_KEY]
        if verbose or debug:  log.debug("Deleted files = %s, deleted dirs = %s" % (pkgDeletedFiles, pkgDeletedDirs))
        
    else:
        pkgDeltaVersion = None
            
    mfiles = mjson[PKG_FILES_KEY]
    mdirs = {}
    if PKG_DIRECTORIES_KEY in mjson:
        mdirs.update(mjson[PKG_DIRECTORIES_KEY])
    if PKG_DIRS_KEY in mjson:
        mdirs.update(mjson[PKG_DIRS_KEY])
    
    print "%s-%s" % (pkgName, pkgVersion)
    if debug > 1:  log.debug("installation target = %s" % dest)
        
    # Note that none of this is at all atomic.
    # To fix that, I should go to a persistent sqlite connection,
    # and use a transaction.
    old_pkg = pkgdb.FindPackage(pkgName)
    # Should DB be updated before or after installation?
    if old_pkg is not None:
        old_scripts = pkgdb.FindScriptForPackage(pkgName)

        # pkgScripts is never None, but it may be empty
        if old_scripts is not None:
            upgrade_aware = ((PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_UPGRADE in old_scripts) or \
                            (PKG_SCRIPT_TYPES.PKG_SCRIPT_UPGRADE in old_scripts) or \
                            (PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_UPGRADE in old_scripts)) and \
                ((PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_UPGRADE in pkgScripts) or \
                 (PKG_SCRIPT_TYPES.PKG_SCRIPT_UPGRADE in pkgScripts) or \
                 (PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_UPGRADE in pkgScripts)) or \
                (((PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_DELTA in pkgScripts) or \
                  (PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_DELTA in pkgScripts)) and \
                 pkgDeltaVersion is not None)

        print "upgrade_aware = %s" % upgrade_aware
        # First thing we do, if we're upgrade-aware, is to run the
        # upgrade scripts from the old version.
        if upgrade_aware:
            RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_UPGRADE, dest, PKG_PREFIX=prefix)
            RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_UPGRADE, dest, PKG_PREFIX=prefix,
                         SCRIPT_ARG="PRE-UPGRADE")

        # If the new version is a delta package, we do things differently
        if pkgDeltaVersion is not None:
            if old_pkg[pkgName] != pkgDeltaVersion:
                log.error("Delta package %s->%s cannot upgrade current version %s" % (
                    pkgDeltaVersion, pkgVersion, old_pkg[pkgName]))
                return False
            # Run a pre-delta script if any, but only if dest is none
            if dest is None:
                RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_DELTA, dest, PKG_PREFIX=prefix)
            
            # Next step for a delta package is to remove any removed files and directories.
            # This is done in both the database and the filesystem.
            # If we can't remove a directory due to ENOTEMPTY, we don't care.
            for file in pkgDeletedFiles:
                if dest:
                    full_path = dest + "/" + file
                else:
                    full_path = "/" + file
                if RemoveFile(full_path) == False:
                    if debug:  log.debug("Could not remove file %s" % file)
                    # Ignor error for now
                pkgdb.RemoveFileEntry(file)
            # Now we try to delete the directories.
            for dir in pkgDeletedDirs:
                if verbose or debug:  log.debug("Attempting to remove directory %s" % dir)
                if dest:
                    full_path = dest + "/" + dir
                else:
                    full_path = "/" + dir
                RemoveDirectory(full_path)
                pkgdb.RemoveFileEntry(dir)
            # Later on, when the package is upgraded, the scripts in the database are deleted.
            # So we don't have to do that now.
        else:
            if not upgrade_aware:
                RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_DEINSTALL, dest, PKG_PREFIX=prefix)
                RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_DEINSTALL, dest, PKG_PREFIX=prefix,
                             SCRIPT_ARG="DEINSTALL")

            if pkgdb.RemovePackageFiles(pkgName) == False:
                log.error("Could not remove files from package %s" % pkgName)
                return False

            if pkgdb.RemovePackageDirectories(pkgName) == False:
                log.error("Could not remove directories from package %s" % pkgName)
                return False
            if pkgdb.RemovePackageScripts(pkgName) == False:
                log.error("Could not remove scripts for package %s" % pkgName)
                return False

            if pkgdb.RemovePackage(pkgName) == False:
                log.error("Could not remove package %s from database" % pkgName)
                return False

            if not upgrade_aware:
                RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_DEINSTALL, dest, PKG_PREFIX=prefix)
                RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_INSTALL, dest, PKG_PREFIX=prefix,
                             SCRIPT_ARG="POST-DEINSTALL")


    if pkgDeltaVersion is not None:
        if pkgdb.UpdatePackage(pkgName, pkgDeltaVersion, pkgVersion, pkgScripts) == False:
            log.error("Could not update package from %s to %s in database" % (pkgDeltaVersion, pkgVersion))
            return False
        log.debug("Updated package %s from %s to %s in database" % (pkgName, pkgDeltaVersion, pkgVersion))
    elif pkgdb.AddPackage(pkgName, pkgVersion, pkgScripts) == False:
        log.debug("Could not add package %s to database" % pkgName)
        return False

    # Is this correct behaviour for delta packages?
    if upgrade_aware == False:
        RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_INSTALL,
                     dest, PKG_PREFIX=prefix)
        RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_INSTALL,
                     dest, PKG_PREFIX=prefix, SCRIPT_ARG="PRE-INSTALL")
            
    # Go through the tarfile, looking for entries in the manifest list.
    pkgFiles = []
    while member is not None:
        # To figure out the hash, we need to look
        # at <file>, <prefix + file>, and both of those
        # with and without a leading "/".  (Why?  Because
        # the manifest may have relative or absolute paths,
        # and tar may remove a leading slash to make us secure.)
        # We also have to look in the directories hash
        # print >> sys.stderr, "member = %s, prefix = %s" % (member.name, prefix)
        mFileHash = "-"
        if member.name in mfiles:
            mFileHash = mfiles[member.name]
        elif member.name.startswith("/") == False and ("/" + member.name) in mfiles:
            mFileHash = mfiles["/" + member.name]
        elif prefix + member.name in mfiles:
            mFileHash = mfiles[prefix + member.name]
        elif (prefix + member.name).startswith("/") == False:
            if "/" + prefix + member.name in mfiles:
                mFileHash = mfiles["/" + prefix + member.name]
        else:
            # If it's not in the manifest, then ignore it
            # It may be a directory, however, so let's check
            if EntryInDictionary(member.name, mdirs, prefix) == False:
                # If we don't skip it, we infinite loop.  That's bad.
                member = t.next()
                continue
        if pkgDeltaVersion is not None:
            if verbose or debug: log.debug("Extracting %s from delta package" % member.name)
        list = ExtractEntry(t, member, dest, prefix, mFileHash)
        if list is not None:
            pkgFiles.append((pkgName,) + list)
    
        member = t.next()
    
    if len(pkgFiles) > 0:
        pkgdb.AddFilesBulk(pkgFiles)
        
    if upgrade_aware:
        RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_UPGRADE, dest, PKG_PREFIX=prefix)
        RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_UPGRADE, dest, PKG_PREFIX=prefix, SCRIPT_ARG="POST-UPGRADE")
        if dest is None and pkgDeltaVersion is not None:
            RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_DELTA, dest, PKG_PREFIX=prefix)
    else:
        RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_INSTALL, dest, PKG_PREFIX=prefix)
        RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_INSTALL, dest, PKG_PREFIX=prefix, SCRIPT_ARG="POST-INSTALL")
    return True

class Installer(object):
    _root = None
    _conf = None
    _manifest = None
    _packages = []

    def __init__(self, config = None, manifest = None, root = None):
        self._conf = config
        self._manifest = manifest
        if root is not None: self._root = root

        if self._conf is None:
            # Get the system configuration
            self._conf = Configuration.Configuration()
        if self._manifest is None:
            self._manifest = self._conf.SystemManifest()
        if self._manifest is None:
            raise InstallerConfigurationException("No manifest file")
        return

    def SetDebug(self, level):
        global debug
        debug = level
        return

    def SetVerbose(self, b):
        global verbose
        verbose = b
        return

    def GetPackages(self, pkgList=None, handler=None):
        # Load the packages in pkgList.  If pkgList is not
        # given, it loads the packages in the manifest.
        # This should change.
        self._packages = []
        if pkgList is None:
            pkgList = self._manifest.Packages()
        for i, pkg in enumerate(pkgList):
            if handler is not None:
                get_file_handler = handler(index=i + 1, pkg=pkg, pkgList=pkgList)
            else:
                get_file_handler = None
            pkgFile = self._conf.FindPackageFile(pkg, handler=get_file_handler)
            if pkgFile is None:
                raise InstallerPackageNotFoundException("%s-%s" % (pkg.Name(), pkg.Version()))
            self._packages.append({ pkg.Name() : pkgFile})
        # At this point, self._packages has all of the packages we want to install,
        # ready for installation
        return True

    def InstallPackages(self, progressFunc=None, handler=None):
        for i, pkg in enumerate(self._packages):
            for pkgname in pkg:
                log.debug("Installing package %s" % pkg)
                if handler is not None:
                    handler(index=i + 1, name=pkgname, packages=self._packages)
                if install_file(pkg[pkgname], self._root) is False:
                    log.error("Unable to install package %s" % pkgname)
                    return False
        return True



