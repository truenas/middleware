import os
import sys
import ConfigParser
import json
import hashlib
import urllib2
import tempfile
import sqlite3

import Exceptions
import Installer
import Train
import Package
import Manifest

CONFIG_DEFAULT = "Defaults"
CONFIG_SEARCH = "Search"

TRAIN_DESC_KEY = "Descripton"
TRAIN_SEQ_KEY = "Sequence"
TRAIN_CHECKED_KEY = "LastChecked"

def ChecksumFile(fobj):
    # Produce a SHA256 checksum of a file.
    # Read it in chunk
    def readchunk():
        chunksize = 1024 * 1024
        return fobj.read(chunksize)
    hash = hashlib.sha256()
    fobj.seek(0)
    for piece in iter(readchunk, ''):
        hash.update(piece)
    fobj.seek(0)
    return hash.hexdigest()

    
def TryOpenFile(path):
    try:
        f = open(path, "r")
    except:
        return None
    else:
        return f

def TryGetNetworkFile(url, tmp, current_version = "1"):
    FREENAS_VERSION = "X-FreeNAS-Manifest-Version"
    try:
        req = urllib2.Request(url)
        req.add_header(FREENAS_VERSION, current_version)
        # Hack for debugging
        req.add_header("User-Agent", FREENAS_VERSION + "=" + current_version)
        furl = urllib2.urlopen(req)
    except:
        print >> sys.stderr, "Unable to load %s" % url
        return None
    retval = tempfile.TemporaryFile(dir = tmp)
    retval.write(furl.read())
    retval.seek(0)
    return retval

class PackageDB:
#    DB_NAME = "var/db/ix/freenas-db"
    DB_NAME = "data/pkgdb/freenas-db"
    __db_path = None
    __db_root = ""
    __conn = None
    __close = True

    def __init__(self, root = ""):
        self.__db_root = root
        self.__db_path = self.__db_root + "/" + PackageDB.DB_NAME
        if os.path.exists(os.path.dirname(self.__db_path)) == False:
            print >> sys.stderr, "Need to create %s" % os.path.dirname(self.__db_path)
            os.makedirs(os.path.dirname(self.__db_path))

        if self._connectdb(returniferror = True, cursor = False) is None:
            raise Exception("Cannot connect to database file %s" % self.__db_path)

        cur = self.__conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS packages(name text primary key, version text not null)")
        cur.execute("CREATE TABLE IF NOT EXISTS scripts(package text not null, type text not null, script text not null)")
        cur.execute("""CREATE TABLE IF NOT EXISTS
		files(package text not null,
			path text primary key,
			kind text not null,
			checksum text,
			uid integer,
			gid integer,
			flags integer,
			mode integer)""")
        self._closedb()
        return

    def _connectdb(self, returniferror = False, cursor = False):
        if self.__conn is not None:
            if cursor:
                return self.__conn.cursor()
            return True
        try:
            conn = sqlite3.connect(self.__db_path)
        except Exception as err:
            print >> sys.stderr, "%s:  Cannot connect to database %s: %s" % (sys.argv[0], self.__db_path, str(err))
            if returniferror: return None
            raise err

        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        self.__conn = conn
        if cursor:
            return self.__conn.cursor()
        return True

    def _closedb(self):
        if self.__conn is not None:
            self.__conn.commit()
            self.__conn.close()
            self.__conn = None
        return

    def FindPackage(self, pkgName):
        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("SELECT name, version FROM packages WHERE name = ?", (pkgName, ))
        rv = cur.fetchone()
        self._closedb()
        if rv is None: return None
        print >> sys.stderr, "rv = %s" % rv.keys()
        m = {}
        return { rv["name"] : rv["version"] }

    def UpdatePackage(self, pkgName, curVers, newVers, scripts):
        cur = self.FindPackage(pkgName)
        if cur is None:
            raise Exception("Package %s is not in system database, cannot update" % pkgName)
        if cur[pkgName] != curVers:
            raise Exception("Package %s is at version %s, not version %s as requested by update" % (cur[pkgName], curVers))

        if cur[pkgName] == newVers:
            print >> sys.stderr, "Package %s version %s not changing, so not updating" % (pkgName, newVers)
            return
        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("UPDATE packages SET version = ? WHERE name = ?", (newVers, manifest, pkgName))
        cur.execute("DELETE FROM scripts WHERE package = ?", (pkgName,))
        if scripts is not None:
            for scriptType in scripts.keys():
                cur.execute("INSERT INTO scripts(package, type, script) VALUES(?, ?, ?)",
                            (pkgName, scriptType, scripts[scriptType]))

        self.__closedb()

    def AddPackage(self, pkgName, vers, scripts):
        curVers = self.FindPackage(pkgName)
        if curVers is not None:
            raise Exception("Package %s is already in system database, cannot add" % pkgName)
        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("INSERT INTO packages VALUES(?, ?)", (pkgName, vers))
        if scripts is not None:
            for scriptType in scripts.keys():
                cur.execute("INSERT INTO scripts(package, type, script) VALUES(?, ?, ?)",
                            (pkgName, scriptType, scripts[scriptType]))
        self._closedb()


    def FindScriptForPackage(self, pkgName, scriptType = None):
        cur = self._connectdb(cursor = True)
        if scriptType is None:
            cur.execute("SELECT type, script FROM scripts WHERE package = ?", (pkgName, ))
        else:
            cur.execute("SELECT type, script FROM scripts WHERE package = ? and type = ?",
                        (pkgName, scriptType))

        scripts = cur.fetchall()
        self._closedb()
        rv = {}
        for s in scripts:
            rv[s["type"]] = s["script"]

        return rv

    def FindFilesForPackage(self, pkgName = None):
        self._connectdb()
        cur = self.__conn.cursor()
        if pkgName is None:
            cur.execute("SELECT path, package, kind, checksum, uid, gid, flags, mode FROM files")
        else:
            cur.execute("SELECT path, package, kind, checksum, uid, gid, flags, mode FROM files WHERE package = ?", (pkgName,))

        files = cur.fetchall()
        self._closedb()
        rv = []
        for f in files:
            tmp = {}
            for k in f.keys():
                tmp[k] = f[k]
            rv.append(tmp)
        return rv

    def FindFile(self, path):
        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("SELECT * FROM files WHERE path = ?", (path,))
        row = cur.fetchone()
        self._closedb()
        if row is None:
            return None
        rv = {}
        for k in row.keys():
            rv[k] = row[k]
        return rv

    def AddFilesBulk(self, list):
        self._connectdb()
        cur = self.__conn.cursor()
        stmt = "INSERT OR REPLACE INTO files(package, path, kind, checksum, uid, gid, flags, mode) VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
        cur.executemany(stmt, list)
        self._closedb()

    def AddFile(self, pkgName, path, type, checksum = "", uid = 0, gid = 0, flags = 0, mode = 0):
        update = False
        if self.FindFile(path) is not None:
            update = True
        self._connectdb()
        cur = self.__conn.cursor()
        if update:
            stmt = "UPDATE files SET package = ?, kind = ?, path = ?, checksum = ?, uid = ?, gid = ?, flags = ?, mode = ? WHERE path = ?"
            args = (pkgName, type, path, checksum, uid, gid, flags, mode, path)
        else:
            stmt = "INSERT INTO files(package, kind, path, checksum, uid, gid, flags, mode) VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
            args = (pkgName, type, path, checksum, uid, gid, flags, mode)
#        print >> sys.stderr, "stmt = %s" % stmt
        cur.execute(stmt, args)
        self._closedb()

    def RemoveFileEntry(self, path):
        if self.FindFile(path) is not None:
            self._connectdb()
            cur = self.__conn.cursor()
            cur.execute("DELETE FROM files WHERE path = ?", (path, ))
            self._closedb()
        return

    def RemovePackageFiles(self, pkgName):
        # Remove the files in a package.  This removes them from
        # both the filesystem and database.
        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database" % pkgName
            return False

        self._connectdb()
        cur = self.__conn.cursor()

        cur.execute("SELECT path FROM files WHERE package = ? AND kind <> ?", (pkgName, "dir"))
        rows = cur.fetchall()
        file_list = []
        for row in rows:
            path = row[0]
            full_path = self.__db_root + "/" +  path
            if Installer.RemoveFile(full_path) == False:
                raise Exception("Cannot remove file %s" % path)
            file_list.append((path, ))
        cur.executemany("DELETE FROM files WHERE path = ?", file_list)
        cur.execute("VACUUM")
        self._closedb()
        return True

    def RemovePackageDirectories(self, pkgName, failDirectoryRemoval = False):
        # Remove the directories in a package.  This removes them from
        # both the filesystem and database.  If failDirectoryRemoval is True,
        # and a directory cannot be removed, return False.  Otherwise,
        # ignore that.

        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database" % pkgName
            return False

        self._connectdb()
        cur = self.__conn.cursor()

        dir_list = []
        cur.execute("SELECT path FROM files WHERE package = ? AND kind = ?", (pkgName, "dir"))
        rows = cur.fetchall()
        for row in rows:
            path = row[0]
            full_path = self.__db_root + "/" + path
            if Installer.RemoveDirectory(full_path) == False and failDirectoryRemoval == True:
                raise Exception("Cannot remove directory %s" % path)
            dir_list.append((path, ))
        cur.executemany("DELETE FROM files WHERE path = ?", dir_list)
        cur.execute("VACUUM")
        self._closedb()
        return True

    def RemovePackageScripts(self, pkgName):
        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database, cannot remove scripts" % pkgName
            return False

        cur = self._connectdb(cursor = True)
        cur.execute("DELETE FROM scripts WHERE package = ?", (pkgName, ))
        self._closedb()
        return True

    def RemovePackageContents(self, pkgName, failDirectoryRemoval = False):
        if self.FindPackage(pkgName) is None:
            print >> sys.stderr, "Package %s is not in database" % pkgName
            return False

        if self.RemovePackageFiles(pkgName) == False:
            return False
        if self.RemovePackageDirectories(pkgName, failDirectoryRemoval) == False:
            return False
        if self.RemovePackageScripts(pkgName) == False:
            return False

        return True

    # Note that this just affects the database, it doesn't run any script.
    def RemovePackage(self, pkgName):
        if self.FindPackage(pkgName) is not None:
            flist = self.FindFilesForPackage(pkgName)
            if len(flist) != 0:
                print >> sys.stderr, "Can't remove package %s, it has %d files still" % (pkgName, len(flist))
                raise Exception("Cannot remove package %s if it still has files" % pkgName)
            dlist = self.FindScriptForPackage(pkgName)
            if dlist is not None and len(dlist) != 0:
                print >> sys.stderr, "Cannot remove package %s, it still has scripts" % pkgName
                raise Exception("Cannot remove package %s as it still has scripts" % pkgName)

        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("DELETE FROM packages WHERE name = ?", (pkgName, ))
        self._closedb()
        return

class Configuration(object):
    _root = ""
    _config_path = "/etc/freenas.conf"
    _search = None
    _trains = None
    _temp = "/tmp"
    _dirty = False
    _nopkgdb = False

    def __init__(self, root = None, file = None, nopkgdb = False):
        if root is not None: self._root = root
        if file is not None: self._config_path = file
        self._nopkgdb = nopkgdb
        self.LoadConfigurationFile(self._config_path)

    def SystemManifest(self):
        man = Manifest.Manifest(self)
        try:
            man.LoadPath(self._root + Manifest.SYSTEM_MANIFEST_FILE)
        except:
            man = None
        return man

    def StoreConfigurationFile(self, path):
        # I'm not really sure this'll work in reality;
        # it may need to be handled through the database.
        cfp = ConfigParser.SafeConfigParser()
        cfp.add_section(CONFIG_DEFAULT)
        if self._search is not None:
            cfp.set(CONFIG_DEFAULT, "search", " ".join(self._search))
        if self._trains is not None:
            for train in self._trains:
                cfp.add_section(train.Name())
                if cfp.has_option(train.Name, TRAIN_SEQ_KEY):
                    cfp.set(train.Name(), TRAIN_SEQ_KEY, train.LastSequence())
                if cfp.has_option(train.Name(), TRAIN_DESC_KEY):
                    cfp.set(train.Name(), TRAIN_DESC_KEY, train.Description())
                if cfp.has_option(train.Name(), TRAIN_CHECKED_KEY):
                    cfp.set(train.Name(), TRAIN_CHECKED_KEY, train.LastCheckedTime())
        with open(path, "w") as f:
            cfp.write(f)
        return

    def PackageDB(self):
        return PackageDB(self._root)

    def LoadConfigurationFile(self, path):
        self._search = None
        self._trains = None
        cfp = None
        try:
            with open(self._root + path, "r") as f:
                cfp = ConfigParser.SafeConfigParser()
                cfp.readfp(f)
        except:
            return

        if cfp is None:
            return

        for section in cfp.sections():
            if section == CONFIG_DEFAULT:
                # Default, used to set search paths
                if cfp.has_option(section, "search"):
                    sp = cfp.get(section, "search")
                    spa = sp.split()
                    # Handle backslash for line continuation
                    for L in spa:
                        if L == "\\":
                            continue
                        self.AddSearchLocation(L)
                # Also see if it has a temp location defined
                if cfp.has_option(section, "Temp Directory"):
                    self._temp = cfp.get(section, "Temp Directory")
            else:
                # This is a train name
                try:
                    train = Train(section, cfp.get(section, TRAIN_DESC_KEY))
                    train.SetLastSequence(cfp.get(section, TRAIN_SEQ_KEY))
                    train.SetLastCheckedTime(cfp.get(section, TRAIN_CHECKED_KEY))
                    self.AddTrain(train)
                except:
                    # Ignore errors (for now at least)
                    pass

        self.MarkDirty()
        return

    def MarkDirty(self):
        self._dirty = True
        return

    def AddSearchLocation(self, loc, insert = False):
        if self._search is None:  self._search = []
        if insert is True:
            self._search.insert(0, loc)
        else:
            self._search.append(loc)
        self.MarkDirty()
        return

    def SetSearchLocations(self, list):
        self._search = list
        self.MarkDirty()
        return
    
    def SearchLocations(self):
        if self._search is None: return []
        return self._search

    def AddTrain(self, train):
        self._trains.append(train)
        self.MarkDirty()
        return

    def ListTrains(self):
        # I'm not sure how to do this.  This should allow
        # the program to query the search locations, and see
        # what trains are available.  Should this be done by
        # getdirentries / http-search?  Or should there be a
        # file somewhere indicating which trains are availbale?
        raise Exception("Not implemented yet")

    def Trains(self):
        return self._trains

    def SetTrains(self, list):
        self._trains = list
        self.MarkDirty()
        return

    def TemporaryDirectory(self):
        return self._temp

    def SetTemporaryDirectory(self, path):
        self._temp = path
        return

    def CreateTemporaryFile(self):
        return tempfile.TemporaryFile(dir = self._temp)

    def SearchForFile(self, path):
        # Iterate through the search locations,
        # looking for $loc/$path.
        # If we find the file, we return a file-like
        # object for it.
        sys_mani = self.SystemManifest()
        if sys_mani is None:
            current_version = "unknown"
        else:
            current_version = str(sys_mani.Sequence())

        for location in self.SearchLocations():
            # A location will either be a path (beginning
            # with a "/", a file url (beginning with
            # "file://"), or a network URL.
            # For files, we simply open it, and return
            # that.
            # For networking, we download it to a
            # temporary location, and return a reference
            # to that.
            # We yield, so it can continue searching for
            # more correct files.
            if location.endswith("/") or path.startswith("/"):
                full_pathname = location + path
            else:
                full_pathname = location + "/" + path
            if full_pathname.startswith("/"):
                file_ref = TryOpenFile(full_pathname)
            elif full_pathname.startswith("file://"):
                file_ref = TryOpenFile(full_pathname[len("file://"):])
            else:
                file_ref = TryGetNetworkFile(full_pathname, self._temp, current_version)
            if file_ref is not None:
                yield file_ref
        return
            
    def FindLatestManifest(self, train = None):
        # Finds the latest (largest sequence number)
        # manifest for a given train, iterating through
        # the search locations.
        # Returns a manifest, or None.
        rv = None
        if train is None:
            temp_mani = self.SystemManifest()
            if temp_mani is None:
                # I give up
                raise ConfigurationInvalidException
            train = temp_mani.Train()
        for file in self.SearchForFile(train + "/LATEST"):
            temp_mani = Manifest.Manifest(self)
            temp_mani.LoadFile(file)
            if rv is None or temp_mani.Sequence() > rv.Sequence():
                rv = temp_mani

        return rv

    def FindPackageFile(self, package, upgrade_from = None):
        # Given a package, and optionally a version to upgrade from, find
        # the package file for it.  Returns a file-like
        # object for the package file.
        # If the package object has a checksum set, it
        # attempts to verify the checksum; if it doesn't match,
        # it goes onto the next one.
        # If upgrade_from is set, it tries to find delta packages
        # first, and will verify the checksum for that.  If the
        # package does not have an upgrade field set, or it does
        # but there's no checksum, then we are probably creating
        # the manifest file, so we won't do the checksum verification --
        # we'll only go by name.
        # If it can't find one, it returns None
        rv = None
        # If we don't have a packagedb on the system,
        # that's not fatal -- it just means we can't do an upgrade.
        curVers = None
        if upgrade_from is None:
            pkgInfo = None
            pkgdb = None
            if self._nopkgdb == False:
                try:
                    pkgdb = self.PackageDB()
                except:
                    pass
                
            if pkgdb is not None:
                pkgInfo = pkgdb.FindPackage(package.Name())
                if pkgInfo is not None:
                    curVers = pkgInfo[package.Name()]
        else:
            curVers = upgrade_from

        # If it's the same version, then we don't want to look
        # for an upgrade, obviously.
        if curVers == package.Version():
            curVers = None

        if curVers is not None:
            # We want to look for an old version
            # o is "old version", h is "hash".
            o = curVers
            h = None
            # If there are no updates listed in the package,
            # but an upgrade_from was given, or one is listed in
            # the package database, then we use that.  Otherwise,
            # iterate through the updates listed for the package,
            # looking for a version that matches
            for upgrade in package.Updates():
                if upgrade[Package.VERSION_KEY] == curVers:
                    o = upgrade[Package.VERSION_KEY]
                    h = upgrade[Package.CHECKSUM_KEY]
                    break
                    
            # If we have an old version, look for that.
            if o is not None:
                # Figure out the name.
                upgrade_name = package.FileName(curVers)
                for file in self.SearchForFile("Packages/%s" % upgrade_name):
                    if h is not None:
                        hash = ChecksumFile(file)
                        if hash == h:
                            return file
                    else:
                        return file
        # All that, and now we do much of it again with the full version
        new_name = package.FileName()
        for file in self.SearchForFile("Packages/%s" % new_name):
            if package.Checksum() is not None:
                hash = ChecksumFile(file)
                if hash == package.Checksum():
                    return file
            else:
                # If there's no checksum, and we found something with the
                # right name, return that.
                return file

        return rv

    def CreateInstallClone(self, name):
        raise Exception("Not implemented")

if __name__ == "__main__":
    conf = Configuration()

    pkg = Package.Package("freenas", "1.0", "abcd")
    pkg.AddUpdate("0.9", "1234")

    manifest = Manifest.Manifest(conf)
    manifest.SetSequence(100)
    manifest.SetTrain("FreeNAS-ALPHA")
    manifest.SetVersion("FreeNAS-9.3-ALPHA")
    manifest.AddPackage(pkg)
    manifest.SetSignature()

    if manifest.Validate() != True:
        print "Validation failed"

    print manifest.String()
    manifest.StorePath("manifest")
    new_manifest = Manifest.Manifest(conf)
    new_manifest.LoadPath("manifest")
    if new_manifest.Validate() == True:
        print "Re-loaded manifest validated"

    test_conf = Configuration("root")
    test_conf.AddSearchLocation("file:///cdrom/FreeNAS")
#    test_conf.AddSearchLocation("http://www.freenas.org/Downloads/FreeNAS")
#    test_conf.AddSearchLocation("http://k3/~sef/FreeNAS")
    test_conf.AddSearchLocation("http://www.kithrup.com/~sef/FreeNAS")
    test_conf.AddSearchLocation("/tmp")

    test_mani = test_conf.SystemManifest()
    print "System manifest = %s" % test_mani.String()

    test_conf.StoreConfigurationFile("freenas.conf")

    for file in test_conf.SearchForFile("sef.iso"):
        print "Found %s" % file.name

    latest = test_conf.FindLatestManifest(test_mani.Train())
    if latest is None:
        print >> sys.stderr, "Could not find latest manifest for train %s" % test_mani.Train()
    else:
        print "Train %s:  current = %d, latest = %d" % (test_mani.Train(), test_mani.Sequence(), latest.Sequence())

    test_conf.FindPackageFile(pkg)

    pkgdb = PackageDB("root")
    pkgdb.AddPackage("freenas", "1.0", "")
    pkgdb.AddFile("freenas", "/bin/sh", "file")
