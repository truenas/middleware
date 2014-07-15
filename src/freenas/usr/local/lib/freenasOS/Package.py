#!/usr/local/bin/python -R
#
# Install a file into a freenas system.
# We are given a tarball -- foo-X.txz
# TBD:  get version from manifest, or from
# name?
#

import os
import errno
import sys
import subprocess
import stat
import getopt
import json
import tarfile
import hashlib

#
# Remove a file.  This will first try to do an
# unlink, then try to change flags if there are
# permission problems.  (Think, schg)
def RemoveFile(path):
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
            return False
    return True

# Like the above, but for a directory.
def RemoveDirectory(path):
    st = None
    try:
        st = os.lstat(path)
    except os.error as e:
        return False
    try:
        os.lchflags(path, 0)
    except os.error as e:
        pass
    try:
        os.rmdir(path)
    except os.error as e:
        if st.st_flags:
            try:
                os.lchflags(path, st.st_flags)
            except os.error as e:
                pass
        return False
    return True

def EntryInDictionary(name, mDict, prefix):
    if (name in mDict):  return True
    if prefix is not None:
        if (prefix + name in mDict):
            return True
        if (prefix + name).startswith("/") == False:
            if "/" + prefix + name in mDict:
                return True
    return False
    
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
    fileName = entry.name
    if fileName.startswith("./"):
        fileName = fileName[2:]
    if fileName.startswith("/") or prefix is None:
        pass
    else:
        fileName = "%s%s%s" % (prefix, "" if prefix.endswith("/") or entry.name.startswith("/") else "/", fileName)
    full_path = "%s%s%s" % (root, "" if root.endswith("/") or fileName.startswith("/") else "/", fileName)
        
    # After that, we've got a full_path, and so we get the directory it's in,
    # and the name of the file.
    dirname = os.path.dirname(full_path)
    fname = os.path.basename(full_path)
    # Debugging stuff
    if debug > 0 or verbose: print "%s:  will be extracted as %s" % (entry.name, full_path)
    if debug > 2: print >> sys.stderr, "entry = %s" % (entry)
    
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

    # Process the entry.  We look for a file, directory,
    # or symlink.
    # XXX:  Need to handle hard link.
    if entry.isfile():
        fileData = tf.extractfile(entry)
        # Is this a problem?  Keeping the file in memory?
        buffer = fileData.read()
        hash = hashlib.sha256(buffer).hexdigest()
        # PKGNG sets hash to "-" if it's not computed.
        if mFileHash != "-":
            if hash != mFileHash:
                print >> sys.stderr, "%s hash does not match manifest" % entry.name
        type = "file"
        if dryrun == False:
            # First we try to create teh file.
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
            f.write(buffer)
            f.close()
            if newfile is not None:
                try:
                    os.rename(newfile, full_path)
                except:
                    os.rename(full_path, "%s.old" % full_path)
                    os.rename(newfile, full_path)
            SetPosix(full_path, meta)
    elif entry.isdir():
        if dryrun is False:
            # If the directory already exists, we don't care.
            try:
                os.mkdir(full_path)
            except os.error as e:
                if e[0] != errno.EEXIST:
                    raise e
            SetPosix(full_path, meta)
            
        type = "dir"
        hash = ""
    elif entry.issym():
        if mFileHash != "-":
            if entry.linkname.startswith("/"):
                hash = hashlib.sha256(entry.linkname[1:]).hexdigest()
            else:
                hash = hashlib.sha256(entry.linkname).hexdigest()
            if hash != mFileHash:
                print >> sys.stderr, "%s hash does not match manifest" % entry.name
        if dryrun is False:
            # Try to remove the symlink first.
            # Then create the new one.
            try:
                os.unlink(full_path)
            except os.error as e:
                if e[0] != errno.ENOENT:
                    raise e
            os.symlink(entry.linkname, full_path)
            SetPosix(full_path, meta)
        type = "slink"
        hash = ""
    elif entry.islnk():
#        print >> sys.stderr, "%s is a hard link to %s" % (entry.name, entry.linkname)
        if dryrun is False:
            source_file = root + "/" + entry.linkname
            try:
                st = os.lstat(source_file)
                os.lchflags(source_file, 0)
                try:
                    os.lchflags(full_path, 0)
                    os.unlink(full_path)
                except:
                    pass
                os.link(source_file, full_path)
                if st.st_flags != 0:
                    os.lchflags(source_file, st.st_flags)

            except os.error as e:
                print >> sys.stderr, "Could not link %s to %s: %s" % (source_file, full_path, str(e))
                sys.exit(1)
        # Except on mac os, hard links are always files.
        type = "file"
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

# This should go into its own file, but I'm still experimenting
import sqlite3
class PackageDB:
    DB_NAME = "var/db/ix/freenas-db"
    __db_path = None
    __db_root = ""

    def _connectdb(self, returniferror = False):
        try:
            conn = sqlite3.connect(self.__db_path)
        except Exception as err:
            print >> sys.stderr, "%s:  Cannot connect to database %s: %s" % (sys.argv[0], self.__db_path, str(err))
            if returniferror: return None
            raise err

        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        return conn

    def __init__(self, root = ""):
        self.__db_root = root
        self.__db_path = self.__db_root + "/" + PackageDB.DB_NAME
        if os.path.exists(os.path.dirname(self.__db_path)) == False:
            print >> sys.stderr, "Need to create %s" % os.path.dirname(self.__db_path)
            MakeDirs(os.path.dirname(self.__db_path))

        conn = self._connectdb(True)
        if conn is None:
            raise Exception("Cannot connect to database file %s" % self.__db_path)

        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS packages(name text primary key, version text not null, manifest text not null)")
        cur.execute("""CREATE TABLE IF NOT EXISTS
		files(package text not null,
			path text primary key,
			kind text not null,
			checksum text,
			uid integer,
			gid integer,
			flags integer,
			mode integer)""")
        conn.commit()
        conn.close()

    def FindPackage(self, pkgName):
        conn = self._connectdb()
        cur = conn.cursor()
        cur.execute("SELECT name, version, manifest FROM packages WHERE name = ?", (pkgName, ))
        rv = cur.fetchone()
        conn.close()
        if rv is None: return None
        print >> sys.stderr, "rv = %s" % rv.keys()
        m = {}
        if rv["manifest"] is not None and rv["manifest"] != "":
            m = json.loads(rv["manifest"])
        # This is slightly redundant -- the manifest has the name and version!
        return { rv["name"] : rv["version"], "manifest" : m }

    def UpdatePackage(self, pkgName, curVers, newVers, manifest):
        cur = self.FindPackage(pkgName)
        if cur is None:
            raise Exception("Package %s is not in system database, cannot update" % pkgName)
        if cur[pkgName] != curVers:
            raise Exception("Package %s is at version %s, not version %s as requested by update" % (cur[pkgName], curVers))

        if cur[pkgName] == newVers:
            print >> sys.stderr, "Package %s version %s not changing, so not updating" % (pkgName, newVers)
            return
        conn = self._connectdb()
        cur = conn.cursor()
        cur.execute("UPDATE packages SET version = ?, manifest = ?  WHERE name = ?", (newVers, manifest, pkgName))
        conn.commit()
        conn.close()

    def AddPackage(self, pkgName, vers, manifest):
        curVers = self.FindPackage(pkgName)
        if curVers is not None:
            raise Exception("Package %s is already in system database, cannot add" % pkgName)
        conn = self._connectdb()
        cur = conn.cursor()
        cur.execute("INSERT INTO packages VALUES(?, ?,? )", (pkgName, vers, manifest))
        conn.commit()
        conn.close()

    def FindFilesForPackage(self, pkgName = None):
        conn = self._connectdb()
        cur = conn.cursor()
        if pkgName is None:
            cur.execute("SELECT path, package, kind, checksum, uid, gid, flags, mode FROM files")
        else:
            cur.execute("SELECT path, package, kind, checksum, uid, gid, flags, mode FROM files WHERE package = ?", (pkgName,))

        files = cur.fetchall()
        conn.close()
        rv = []
        for f in files:
            tmp = {}
            for k in f.keys():
                tmp[k] = f[k]
            rv.append(tmp)
        return rv

    def FindFile(self, path):
        conn = self._connectdb()
        cur = conn.cursor()
        cur.execute("SELECT * FROM files WHERE path = ?", (path,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        rv = {}
        for k in row.keys():
            rv[k] = row[k]
        return rv

    def AddFilesBulk(self, list):
        conn = self._connectdb()
        cur = conn.cursor()
        stmt = "INSERT OR REPLACE INTO files(package, path, kind, checksum, uid, gid, flags, mode) VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
        cur.executemany(stmt, list)
        conn.commit()
        conn.close()

    def AddFile(self, pkgName, path, type, checksum = "", uid = 0, gid = 0, flags = 0, mode = 0):
        update = False
        if self.FindFile(path) is not None:
            update = True
        conn = self._connectdb()
        cur = conn.cursor()
        if update:
            stmt = "UPDATE files SET package = ?, kind = ?, path = ?, checksum = ?, uid = ?, gid = ?, flags = ?, mode = ? WHERE path = ?"
            args = (pkgName, type, path, checksum, uid, gid, flags, mode, path)
        else:
            stmt = "INSERT INTO files(package, kind, path, checksum, uid, gid, flags, mode) VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
            args = (pkgName, type, path, checksum, uid, gid, flags, mode)
#        print >> sys.stderr, "stmt = %s" % stmt
        cur.execute(stmt, args)
        conn.commit()
        conn.close()

    def RemoveFileEntry(self, path):
        if self.FindFile(path) is not None:
            conn = self._connectdb()
            cur = conn.cursor()
            cur.execute("DELETE FROM files WHERE path = ?", (path, ))
            conn.commit()
            conn.close()
        return

    def RemovePackageFiles(self, pkgName):
        # Remove the files in a package.  This removes them from
        # both the filesystem and database.
        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database" % pkgName
            return False

        conn = self._connectdb()
        cur = conn.cursor()

        cur.execute("SELECT path FROM files WHERE package = ? AND kind <> ?", (pkgName, "dir"))
        rows = cur.fetchall()
        file_list = []
        for row in rows:
            path = row[0]
            full_path = self.__db_root + "/" +  path
            if RemoveFile(full_path) == False:
                raise Exception("Cannot remove file %s" % path)
            file_list.append((path, ))
        cur.executemany("DELETE FROM files WHERE path = ?", file_list)
        conn.commit()
        conn.close()
        return True

    def RemovePackageDirectories(self, pkgName, failDirectoryRemoval = False):
        # Remove the directories in a package.  This removes them from
        # both the filesystem and database.  If failDirectoryRemoval is True,
        # and a directory cannot be removed, return False.  Otherwise,
        # ignore that.

        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database" % pkgName
            return False

        conn = self._connectdb()
        cur = conn.cursor()

        dir_list = []
        cur.execute("SELECT path FROM files WHERE package = ? AND kind = ?", (pkgName, "dir"))
        rows = cur.fetchall()
        for row in rows:
            path = row[0]
            full_path = self.__db_root + "/" + path
            if RemoveDirectory(full_path) == False and failDirectoryRemoval == True:
                raise Exception("Cannot remove directory %s" % path)
            dir_list.append((path, ))
        cur.executemany("DELETE FROM files WHERE path = ?", dir_list)
        conn.commit()
        conn.close()
        return True

    def RemovePackageContents(self, pkgName, failDirectoryRemoval = False):
        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database" % pkgName
            return False

        if self.RemovePackageFiles(pkgName) == False:
            return False
        if self.RemovePackageDirectories(pkgName, failDirectoryRemoval) == False:
            return False

        return True

    # Note that this just affects the database, it doesn't run any script.
    def RemovePackage(self, pkgName):
        if self.FindPackage(pkgName) is not None:
            flist = self.FindFilesForPackage(pkgName)
            if len(flist) != 0:
                print >> sys.stderr, "Can't remove package %s, it has %d files still" % (pkgName, len(flist))
                raise Exception("Cannot remove package %s if it still has files" % pkgName)
            conn = self._connectdb()
            cur = conn.cursor()
            cur.execute("DELETE FROM packages WHERE name = ?", (pkgName, ))
            conn.commit()
            conn.close()
        return

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

PKG_MANIFEST_NAME = "+MANIFEST"

# These are the keys for the scripts
PKG_SCRIPTS = [ "pre-install", "install", "post-install",
	"pre-deinstall", "deinstall", "post-deinstall",
	"pre-upgrade", "upgrade", "post-upgrade" ]

def enum(**enums):
    return type('Enum', (), enums)

PKG_SCRIPT_TYPES = enum(PKG_SCRIPT_PRE_DEINSTALL = "pre-deinstall",
                        PKG_SCRIPT_DEINSTALL = "deinstall",
                        PKG_SCRIPT_POST_DEINSTALL = "post-deinstall",
                        PKG_SCRIPT_PRE_INSTALL = "pre-install",
                        PKG_SCRIPT_INSTALL = "install",
                        PKG_SCRIPT_POST_INSTALL = "post-install")

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

# A list of architectures we consider valid.

pkg_valid_archs = [ "freebsd:9:x86:64", "freebsd:10:x86:64" ]

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

debug = 0
verbose = False
dryrun = False

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
        raise Exception("Unknown tarinfo type %s" % ti.type)
    # This appears to be how libarchive (and hence tarfile)
    # handles BSD flags.  Such a pain.
    if ti.pax_headers is not None:
        flags = 0
        if "SCHILY.fflags" in ti.pax_headers:
            for k in ti.pax_headers["SCHILY.fflags"].split(","):
                if debug > 1: print >> sys.stderr, "flag %s" % k
                if k in ext_keys:
                    flags |= ext_keys[k]
            if debug > 1: print >> sys.stderr, "flags was %s, value = %o" % (ti.pax_headers["SCHILY.fflags"], flags)
        rv[TAR_FLAGS_KEY] = flags
    return rv

def usage():
    print >> sys.stderr, "Usage: %s [-R root] [-dv] pkg [...]" % sys.argv[0]
    sys.exit(1)

def MakeDirs(dir):
    global dryrun, debug, verbose

    if debug > 0 or verbose: print >> sys.stderr, "makedirs(%s, 0755)" % dir
    try:
        os.makedirs(dir, 0755)
    except:
        pass
    return

def RunPkgScript(scripts, type, root = None, **kwargs):
    # This makes my head hurt
    if scripts is None:
        return
#    print >> sys.stderr, "scripts = %s" % (scripts.keys())
    if type not in scripts:
        print >> sys.stderr, "No %s script to run" % type
        return

    scriptName = "/%d-%s" % (os.getpid(), type)
    scriptPath = "%s%s" % ("/tmp" if root is None else root, scriptName)
    with open(scriptPath, "w") as f:
        f.write(scripts[type])
    args = ["sh", "-x", scriptName]
    if "SCRIPT_ARG" in kwargs and kwargs["SCRIPT_ARG"] is not None:
        args.append(kwargs["SCRIPT_ARG"])

    print "script (chroot to %s):  %s\n-----------" % ("/" if root is None else root, args)
    print "%s\n--------------" % scripts[type]
    if os.geteuid() != 0 and root is not None:
        print >> sys.stderr, "Installation root is set, and process is not root.  Cannot run script %s" % type
        #return
    else:
        pid = os.fork()
        if pid == 0:
            # Child
            os.chroot(root)
            if "PKG_PREFIX" in kwargs and kwargs["PKG_PREFIX"] is not None:
                os.environ["PKG_PREFIX"] = kwargs["PKG_PREFIX"]
            os.execv("/bin/sh", args)
            sys.exit(1)
        elif pid != -1:
            # Parent
            (tpid, status) = os.wait()
            if tpid != pid:
                print >> sys.stderr, "What?  I waited for process %d and I got %d instead!" % (pid, tpid)
            if status != 0:
                print >> sys.stderr, "Sub procss exited with status %#x" % status
        else:
            print >> sys.stderr, "Huh?  Got -1 from os.fork and no exception?"

    os.unlink("%s%s" % ("/tmp" if root is None else root, scriptName))

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

def install_path(pkgfile, root):
    try:
        f = open(pkgfile, "r")
    except Exception as err:
        print >> sys.stderr, "Cannot open package file %s: %s" % (pkgfile, str(err))
        return False
    else:
        return install_file(f, root)

def install_file(pkgfile, root):
    global debug, verbose, dryrun
    prefix = None
    pkgdb = PackageDB(root)
    amroot = (os.geteuid() == 0)
    pkgScripts = None
    doing_update = False

    try:
        t = tarfile.open(fileobj = pkgfile)
    except Exception as err:
        print >> sys.stderr, "Could not open package file %s: %s" % (pkgfile.name, str(err))
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
        print >> sys.stderr, "Could not find manifest in package file %s" % pkgfile.name
        return False

    # Check the architecture
    if PKG_ARCH_KEY in mjson:
        if not (mjson[PKG_ARCH_KEY] in pkg_valid_archs):
            print >> sys.stderr, "Architecture %s is not valid" % mjson[PKG_ARCH_KEY]
            return False

    if PKG_PREFIX_KEY in mjson:
        prefix = mjson[PKG_PREFIX_KEY]
        if verbose or debug: print >> sys.stderr, "prefix = %s" % prefix

    # See above for how scripts are handled.  It's a mess.
    if PKG_SCRIPTS_KEY in mjson:
        pkgScripts = mjson[PKG_SCRIPTS_KEY]

    # At this point, the tar file is at the first non-+-named files.

    pkgName = mjson[PKG_NAME_KEY]
    pkgVersion = mjson[PKG_VERSION_KEY]
    pkgDeletedFiles = []
    pkgDeletedDirs = []
    if PKG_DELTA_KEY in mjson:
        pkgDeltaVersion = mjson[PKG_DELTA_KEY]
        if PKG_REMOVED_FILES_KEY in mjson: pkgDeletedFiles = mjson[PKG_REMOVED_FILES_KEY]
        if PKG_REMOVED_DIRS_KEY in mjson: pkgDeletedDirs = mjson[PKG_REMOVED_DIRS_KEY]
        print >> sys.stderr, "Deleted files = %s, deleted dirs = %s" % (pkgDeletedFiles, pkgDeletedDirs)

    else:
        pkgDeltaVersion = None

    mfiles = mjson[PKG_FILES_KEY]
    mdirs = {}
    if PKG_DIRECTORIES_KEY in mjson:
        mdirs.update(mjson[PKG_DIRECTORIES_KEY])
    if PKG_DIRS_KEY in mjson:
        mdirs.update(mjson[PKG_DIRS_KEY])

    print "%s-%s" % (pkgName, pkgVersion)
    if debug > 1:  print >> sys.stderr, "root = %s" % root

    # Note that none of this is at all atomic.
    # To fix that, I should go to a persistent sqlite connection,
    # and use a transaction.
    old_pkg = pkgdb.FindPackage(pkgName)
    # Should DB be updated before or after installation?
    if old_pkg is not None:
        doing_update = True
        old_manifest = old_pkg["manifest"]
        old_scripts = None
        # If the new version is a delta package, we do things differently
        if pkgDeltaVersion is not None:
            if old_pkg[pkgName] != pkgDeltaVersion:
                print >> sys.stderr, "Delta package %s->%s cannot upgrade current version %s" % (
                    pkgDeltaVersion, pkgVersion, old_pkg[pkgName])
                return False
            # Next step for a delta package is to remove any removed files and directories.
            # This is done in both the database and the filesystem.
            # If we can't remove a directory due to ENOTEMPTY, we don't care.
            for file in pkgDeletedFiles:
                print >> sys.stderr, "Deleting file %s" % file
                full_path = root + "/" + file
                if RemoveFile(full_path) == False:
                    print >> sys.stderr, "Could not remove file %s" % file
                    # Ignor error for now
                pkgdb.RemoveFileEntry(file)
            # Now we try to delete the directories.
            for dir in pkgDeletedDirs:
                print >> sys.stderr, "Attempting to remove directory %s" % dir
                full_path = root + "/" + dir
                RemoveDirectory(full_path)
                pkgdb.RemoveFileEntry(dir)
        else:
            if old_scripts in old_manifest:
                old_sripts = old_manifest[PKG_SCRIPTS_KEY]
            RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_DEINSTALL, root, PKG_PREFIX=prefix)
            RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_DEINSTALL, root, PKG_PREFIX=prefix, SCRIPT_ARG="DEINSTALL")
            if pkgdb.RemovePackageFiles(pkgName) == False:
                print >> sys.stderr, "Could not remove files from package %s" % pkgName
                return False
            RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_DEINSTALL, root, PKG_PREFIX=prefix)
            RunPkgScript(old_scripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_INSTALL, root, PKG_PREFIX=prefix, SCRIPT_ARG="POST-DEINSTALL")
            if pkgdb.RemovePackageDirectories(pkgName) == False:
                print >> sys.stderr, "Could not remove directories from package %s" % pkgName
                return False
            if pkgdb.RemovePackage(pkgName) == False:
                print >> sys.stderr, "Could not remove package %s from database" % pkgName
                return False

    if pkgDeltaVersion is not None:
        if pkgdb.UpdatePackage(pkgName, pkgDeltaVersion, pkgVersion, json.dumps(mjson)) == False:
            print >> sys.stderr, "Could not update package from %s to %s in database" % (pkgDeltaVersion, pkgVersion)
            return False
        print "Updated package %s from %s to %s in database" % (pkgName, pkgDeltaVersion, pkgVersion)
    elif pkgdb.AddPackage(pkgName, pkgVersion, json.dumps(mjson)) == False:
        print >> sys.stderr, "Could not add package %s to database" % pkgName
        return False

    #
    # Start running scripts.
    # Since I can't how the code works for upgrade scripts, I will
    # have to remove the package contents, and then re-install it.
    # Scripts pre-deinstall, deinstall, post-deinstall to be run,
    # and then pre-install, install, and post-install to be run.
    #old_scripts = None
    #if doing_update:
    #old_manifest = old_pkg["manifest"]
    #print old_manifest
    #if PKG_SCRIPTS_KEY in old_manifest:
    #old_scripts = old_manifest[PKG_SCRIPTS_KEY]
    #if "pre-upgrade" in old_scripts:
    #RunPkgScript(old_scripts["pre-upgrade"], root, PKG_PREFIX=prefix)

    # Is this correct behaviour for delta packages?
    RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_PRE_INSTALL, root, PKG_PREFIX=prefix)
    RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_INSTALL, root, PKG_PREFIX=prefix, SCRIPT_ARG="PRE-INSTALL")

    # Go through the tarfile, looking for entries in the manifest list.
    pkgFiles = []
    while member is not None:
        # To figure out the hash, we need to look
        # at <file>, <prefix + file>, and both of those
        # with and without a leading "/".  (Why?  Because
        # the manifest may have relative or absolute paths,
        # and tar may remove a leading slash to make us secure.)
        # We also have to look in the directories hash
        mFileHash = "-"
        if member.name in mfiles:
            mFileHash = mfiles[member.name]
        elif prefix + member.name in mfiles:
            mFileHash = mfiles[prefix + member.name]
        elif (prefix + member.name).startswith("/") == False:
            if "/" + prefix + member.name in mfiles:
                mFileHash = mfiles["/" + prefix + member.name]
        else:
            # If it's not in the manifest, then ignore it
            # It may be a directory, however, so let's check
            if EntryInDictionary(member.name, mdirs, prefix) == False:
                continue
        if pkgDeltaVersion is not None:
            print >> sys.stderr, "Extracting %s from delta package" % member.name
        list = ExtractEntry(t, member, root, prefix, mFileHash)
        if list is not None:
            pkgFiles.append((pkgName,) + list)

#        print "prefix = %s, member = %s, hash = %s" % (prefix, member.name, mFileHash)
        member = t.next()

#    return True
#    for file in mfiles.keys() + mdirs.keys():
#        try:
#            entry = t.getmember(file)
#        except (tarfile.TarError, KeyError) as err:
#            entry = t.getmember(file[1:] if file.startswith("/") else file)
#        list = ExtractEntry(t, entry, root, prefix, mfiles[file] if file in mfiles else "-")
#        if list is not None:
#            pkgFiles.append((pkgName,) + list)

    if len(pkgFiles) > 0:
        pkgdb.AddFilesBulk(pkgFiles)

    RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_POST_INSTALL, root, PKG_PREFIX=prefix)
    RunPkgScript(pkgScripts, PKG_SCRIPT_TYPES.PKG_SCRIPT_INSTALL, root, PKG_PREFIX=prefix, SCRIPT_ARG="POST-INSTALL")
    return True

def main():
    global debug
    global verbose
    global dryrun
    root = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "R:dvN")
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        usage()

    for (o, a) in opts:
        if o == "-R": root = a
        elif o == "-d": debug += 1
        elif o == "-v": verbose = True
        elif o == "-N": dryrun = True
        else: usage()

    if root is None:  usage()
    if len(args) == 0: usage()
    for pkg in args:
        if install_path(pkg, root) == False:
            print >> sys.stderr, "Unable to install package %s" % pkg

if __name__ == "__main__":
    main()
    sys.exit(0)
