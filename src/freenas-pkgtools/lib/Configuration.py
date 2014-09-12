import ConfigParser
import hashlib
import logging
import os
import sys
import tempfile
import time
import urllib2

from . import Avatar
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

log = logging.getLogger('freenasOS.Configuration')

# Change this for release
# Need to change search code since it isn't really
# searching any longer.
# We may want to use a different update server for
# TrueNAS.
UPDATE_SERVER = "http://beta-update.freenas.org/" + Avatar()
SEARCH_LOCATIONS = [ "http://beta-update.freenas.org/" + Avatar() ]

# List of trains
TRAIN_FILE = UPDATE_SERVER + "/trains.txt"

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

def TryGetNetworkFile(url, tmp, current_version="1", handler=None):
    AVATAR_VERSION = "X-%s-Manifest-Version" % Avatar()
    try:
        req = urllib2.Request(url)
        req.add_header(AVATAR_VERSION, current_version)
        # Hack for debugging
        req.add_header("User-Agent", "%s=%s" % (AVATAR_VERSION, current_version))
        furl = urllib2.urlopen(req, timeout=5)
    except:
        log.warn("Unable to load %s", url)
        return None
    try:
        totalsize = int(furl.info().getheader('Content-Length').strip())
    except:
        totalsize = None
    chunk_size = 64 * 1024
    retval = tempfile.TemporaryFile(dir = tmp)
    read = 0
    lastpercent = percent = 0
    lasttime = time.time()
    while True:
        data = furl.read(chunk_size)
        tmptime = time.time()
        downrate = int(chunk_size / (tmptime - lasttime))
        lasttime = tmptime
        if not data:
            break
        read += len(data)
        if handler and totalsize:
            percent = int((float(read) / float(totalsize)) * 100.0)
            if percent != lastpercent:
                handler(
                   'network',
                    url,
                    size=totalsize,
                    progress=percent,
                    download_rate=downrate,
                )
            lastpercent = percent
        retval.write(data)

    retval.seek(0)
    return retval

class PackageDB:
#    DB_NAME = "var/db/ix/freenas-db"
    DB_NAME = "data/pkgdb/freenas-db"
    __db_path = None
    __db_root = ""
    __conn = None
    __close = True

    def __init__(self, root = "", create = True):
        self.__db_root = root
        self.__db_path = self.__db_root + "/" + PackageDB.DB_NAME
        if os.path.exists(os.path.dirname(self.__db_path)) == False:
            if create is False:
                raise Exception("Cannot connect to database file %s" % self.__db_path)
            log.debug("Need to create %s", os.path.dirname(self.__db_path))
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
	import sqlite3
        if self.__conn is not None:
            if cursor:
                return self.__conn.cursor()
            return True
        try:
            conn = sqlite3.connect(self.__db_path)
        except Exception as err:
            log.error(
                "%s:  Cannot connect to database %s: %s",
                sys.argv[0],
                self.__db_path,
                str(err),
            )
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
        log.debug("rv = %s", rv.keys())
        m = {}
        return { rv["name"] : rv["version"] }

    def UpdatePackage(self, pkgName, curVers, newVers, scripts):
        cur = self.FindPackage(pkgName)
        if cur is None:
            raise Exception("Package %s is not in system database, cannot update" % pkgName)
        if cur[pkgName] != curVers:
            raise Exception("Package %s is at version %s, not version %s as requested by update" % (cur[pkgName], curVers))

        if cur[pkgName] == newVers:
            log.warn(
                "Package %s version %s not changing, so not updating",
                pkgName,
                newVers,
            )
            return
        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("UPDATE packages SET version = ? WHERE name = ?", (newVers, pkgName))
        cur.execute("DELETE FROM scripts WHERE package = ?", (pkgName,))
        if scripts is not None:
            for scriptType in scripts.keys():
                cur.execute("INSERT INTO scripts(package, type, script) VALUES(?, ?, ?)",
                            (pkgName, scriptType, scripts[scriptType]))

        self._closedb()

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
            log.warn("Package %s is not in database", pkgName)
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
            log.warn("Package %s is not in database", pkgName)
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
            log.warn(
                "Package %s is not in database, cannot remove scripts",
                pkgName,
            )
            return False

        cur = self._connectdb(cursor = True)
        cur.execute("DELETE FROM scripts WHERE package = ?", (pkgName, ))
        self._closedb()
        return True

    # This removes the contents of the given packages from both the filesystem
    # and the database.  It leaves the package itself in the database.
    def RemovePackageContents(self, pkgName, failDirectoryRemoval = False):
        if self.FindPackage(pkgName) is None:
            log.warn("Package %s is not in database", pkgName)
            return False

        if self.RemovePackageFiles(pkgName) == False:
            return False
        if self.RemovePackageDirectories(pkgName, failDirectoryRemoval) == False:
            return False
        if self.RemovePackageScripts(pkgName) == False:
            return False

        return True

    # Note that this just affects the database, it doesn't run any script.
    # That makes it the opposite of RemovePackageContents().
    def RemovePackage(self, pkgName):
        if self.FindPackage(pkgName) is not None:
            flist = self.FindFilesForPackage(pkgName)
            if len(flist) != 0:
                log.error(
                    "Can't remove package %s, it has %d files still",
                    pkgName,
                    len(flist),
                )
                raise Exception("Cannot remove package %s if it still has files" % pkgName)
            dlist = self.FindScriptForPackage(pkgName)
            if dlist is not None and len(dlist) != 0:
                log.error(
                    "Cannot remove package %s, it still has scripts",
                    pkgName,
                )
                raise Exception("Cannot remove package %s as it still has scripts" % pkgName)

        self._connectdb()
        cur = self.__conn.cursor()
        cur.execute("DELETE FROM packages WHERE name = ?", (pkgName, ))
        self._closedb()
        return

class Configuration(object):
    _root = ""
    _config_path = "/data/update.conf"
    _trains = None
    _temp = "/tmp"
    _system_pool_link = "/var/db/system"
    _package_dir = None

    def __init__(self, root = None, file = None):
        if root is not None: self._root = root
        if file is not None: self._config_path = file
        self.LoadConfigurationFile(self._config_path)
        # Set _temp to the system pool, if it exists.
        if os.path.islink(self._system_pool_link):
            self._temp = os.readlink(self._system_pool_link)

    # Load the list of currently-watched trains.
    # The file is a JSON file.
    # This sets self._trains as a dictionary of
    # Train objects (key being the train name).
    def LoadTrainsConfig(self):
        import json
        if self._temp is None:
            if not os.path.islink(self._system_pool_link):
                log.error("No system pool, cannot load trains configuration")
            else:
                self._temp = os.readlink(self._system_pool_link)
        self._trains = {}
        if self._temp:
            train_path = self._temp + "/Trains.json"
            try:
                with open(train_path, "r") as f:
                    trains = json.load(f)
                for train_name in trains.keys():
                    temp = Train.Train(train_name)
                    if TRAIN_DESC_KEY in trains[train_name]:
                        temp.SetDescription(trains[train_name][TRAIN_DESC_KEY])
                    if TRAIN_SEQ_KEY in trains[train_name]:
                        temp.SetLastSequence(trains[train_name][TRAIN_SEQ_KEY])
                    if TRAIN_CHECKED_KEY in trains[train_name]:
                        temp.SetLastCheckedTime(trains[train_name][TRAIN_CHECKED_KEY])
                    self._trains[train_name] = temp
            except:
                pass
        sys_mani = self.SystemManifest()
        if sys_mani.Train() not in self._trains:
            temp = Train.Train(sys_mani.Train(), "Installed OS", sys_mani.Sequence())
            self._trains[temp.Name()] = temp
        return

    # Save the list of currently-watched trains.
    def SaveTrainsConfig(self):
        import json
        sys_mani = self.SystemManifest()
        current_train = sys_mani.Train()
        if self._trains is None: self._trains = {}
        if current_train not in self._trains:
            self._trains[current_train] = Train.Train(current_train, "Installed OS", sys_mani.Sequence())
        if self._temp is None:
            if not os.path.islink(self._system_pool_link):
                log.error("No system pool, cannot load trains configuration")
            else:
                self._temp = os.readlink(self._system_pool_link)
        if self._temp:
            obj = {}
            for train_name in self._trains.keys():
                train = self._trains[train_name]
                temp = {}
                if train.Description():
                    temp[TRAIN_DESC_KEY] = train.Description()
                if train.LastSequence():
                    temp[TRAIN_SEQ_KEY] = train.LastSequence()
                if train.LastCheckedTime():
                    temp[TRAIN_CHECKED_KEY] = train.LastCheckedTime()
                obj[train_name] = temp
            train_path = self._temp + "/Trains.json"
            try:
                with open(train_path, "w") as f:
                    json.dump(obj, f, sort_keys=True,
                              indent=4, separators=(',', ': '))
            except OSError as e:
                log.error("Could not write out trains:  %s" % str(e))
        return

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
        raise Exception("This is obsolete")
        cfp = ConfigParser.SafeConfigParser()
        if self._trains is not None:
            for train in self._trains:
                cfp.add_section(train.Name())
                if train.LastSequence() is not None:
                    cfp.set(train.Name(), TRAIN_SEQ_KEY, train.LastSequence())
                if train.Description() is not None:
                    cfp.set(train.Name(), TRAIN_DESC_KEY, train.Description())
                if train.LastCheckedTime() is not None:
                    cfp.set(train.Name(), TRAIN_CHECKED_KEY, train.LastCheckedTime())
        if path is None:
            filename = self._root + self._config_path
        else:
            filename = path
        with open(filename, "w") as f:
            cfp.write(f)
        return

    def PackageDB(self, create = True):
        return PackageDB(self._root, create)

    def LoadConfigurationFile(self, path):
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
                # Nothing to do for now.  Maybe later
                pass
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

        return

    def SetPackageDir(self, loc):
        self._package_dir = loc
        return

    def AddSearchLocation(self, loc, insert = False):
        raise Exception("Deprecated method")
        if self._search is None:  self._search = []
        if insert is True:
            self._search.insert(0, loc)
        else:
            self._search.append(loc)
        return

    def SetSearchLocations(self, list):
        raise Exception("Deprecated method")
        self._search = list
        return
    
    def SearchLocations(self):
        return SEARCH_LOCATIONS

    def AddTrain(self, train):
        self._trains.append(train)
        return

    def CurrentTrain(self):
        """
        Returns the name of the train of the current
        system.  It may return None, but that's for edge cases
        generally related to installation and build environments.
        """
        sys_mani = self.SystemManifest()
        if sys_mani:
           return sys_mani.Train()
        return None

    def AvailableTrains(self):
        """
        Returns the set of available trains from
        the upgrade server.  The return value is
        a dictionary, keyed by the train name, and
        value being the description.
        The list of trains is on the upgrade server,
        with the name "trains.txt".  Or whatever
        I decide it should be called.
        """
        rv = {}
        sys_mani = self.SystemManifest()
        if sys_mani is None:
            current_version = "unknown"
        else:
            current_version = str(sys_mani.Sequence())

        fileref = TryGetNetworkFile(TRAIN_FILE,
                                    self._temp,
                                    current_version,
                                    )

        if fileref is None:
            return None

        for line in fileref:
            import re
            line = line.rstrip()
            # Ignore comments
            if line.startswith("#"):
                continue
            # Input is <name><white_space><description>
            m = re.search("(\S+)\s+(.*)$", line)
            if m.lastindex == None:
                log.debug("Input line `%s' is unparsable" % line)
                continue
            rv[m.group(1)] = m.group(2)

        return rv if len(rv) > 0 else None

    def WatchedTrains(self):
        if self._trains is None:
            self._trains = self.LoadTrainsConfig()
        return self._trains

    def WatchTrain(self, train, watch = True):
        """
        Add a train to the local set to be watched.
        A watched train is checked for updates.
        If the train is already watched, this does nothing.
        train is a Train object.
        If stop is True, then this is used to stop watching
        this particular train.
        """
        if self._trains is None:
            self._trains = {}
        if watch:
            if train.Name() not in self._trains:
                self._trains[train.Name()] = train
        else:
            if train.Name() in self._trains:
                self._trains.pop(train.Name())
        return

    def SetTrains(self, tlist):
        self._trains = tlist
        return

    def TemporaryDirectory(self):
        return self._temp

    def SetTemporaryDirectory(self, path):
        self._temp = path
        return

    def CreateTemporaryFile(self):
        return tempfile.TemporaryFile(dir = self._temp)

    def PackagePath(self, pkg):
        if self._package_dir:
            return "%s/%s" % (self._package_dir, pkg.FileName())
        else:
            return "%s/Packages/%s" % (UPDATE_SERVER, pkg.FileName())

    def PackageUpdatePath(self, pkg, old_version):
        # Do we need this?  If we're given a package directory,
        # then we won't have updates.
        if self._package_dir:
            return "%s/%s" % (self._package_dir, pkg.FileName(old_version))
        else:
            return "%s/Packages/%s" % (UPDATE_SERVER, pkg.FileName(old_version))

    def SearchForFile(self, path, handler=None):
        # Iterate through the search locations,
        # looking for $loc/$path.
        # If we find the file, we return a file-like
        # object for it.
        sys_mani = self.SystemManifest()
        if sys_mani is None:
            current_version = "unknown"
        else:
            current_version = str(sys_mani.Sequence())

        # Minor hack to minimize some code duplication
        first_search = []
        if path.startswith("Packages/") and self._package_dir is not None:
            first_search = [self._package_dir]

        for location in first_search + self.SearchLocations():
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
                file_ref = TryGetNetworkFile(
                    full_pathname,
                    self._temp,
                    current_version,
                    handler=handler,
                )
            if file_ref is not None:
                yield file_ref
        return
            
    def GetManifest(self, train = None, sequence = None, handler = None):
        """
        GetManifest:  fetch, over the network, the requested
        manifest file.  If train isn't specified, it'll use
        the current system; if sequence isn't specified, it'll
        use LATEST.
        Returns either a manifest object, or None.
        """
        # Get the specified manifeset.
        # If train is None, then we use the current train;
        # if sequence is None, then we get LATEST.
        sys_mani = self.SystemManifest()
        if sys_mani is None:
            raise Exceptions.ConfigurationInvalidException
        current_version = str(sys_mani.Sequence())
        if train is None:
            train = sys_mani.Train()
        if sequence is None:
            ManifestFile = "/%s/LATEST" % train
        else:
            # This needs to change for TrueNAS, doesn't it?
            ManifestFile = "/%s/%s-%s" % (Avatar(), train, sequence)

        file_ref = TryGetNetworkFile(UPDATE_SERVER + ManifestFile,
                                     self._temp,
                                     current_version,
                                     handler=handler,
                                 )
        return file_ref

    def FindLatestManifest(self, train = None):
        # Gets <UPDATE_SERVER>/<train>/LATEST
        # Returns a manifest, or None.
        rv = None
        current_version = None
        temp_mani = self.SystemManifest()
        if temp_mani:
            current_version = temp_mani.Sequence()

        if train is None:
            if temp_mani is None:
                # I give up
                raise Exceptions.ConfigurationInvalidException
            if temp_mani.NewTrain():
                # If we're redirected to a new train, use that.
                train = temp_mani.NewTrain()
            else:
                train = temp_mani.Train()

        file = TryGetNetworkFile("%s/%s/LATEST" % (UPDATE_SERVER, train),
                                 self._temp,
                                 current_version,
                                 )
        if file is None:
            log.debug("Could not get latest manifest file for train %s" % train)
        else:
            rv = Manifest.Manifest(self)
            rv.LoadFile(file)
        return rv

    def FindPackageFile(self, package, upgrade_from=None, handler=None):
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
        # First thing:  if we were given a package path, we use that,
        # and that only, and delta packages don't matter.
        if self._package_dir:
            try:
                file = open(self.PackagePath(package))
            except:
                return None
            else:
                if package.Checksum():
                    h = ChecksumFile(file)
                    if h != package.Checksum():
                        return None
                return file

        # If we got here, then we are using the network to get the
        # requested package.  In that case, if possible, we want to
        # try to get a delta package, both to lower network bandwidth,
        # and to improve speed.  And writes to the filesystem.
        # So first we see if we can upgrade.

        # If upgrade_from was explicitly given, we'll use that.
        # Otherwise, we check the packagedb.
        # If we don't have a packagedb on the system,
        # that's not fatal -- it just means we can't do an upgrade.
        curVers = None
        if upgrade_from is None:
            pkgInfo = None
            pkgdb = None
            try:
                pkgdb = self.PackageDB(create = False)
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
            # o is eiter curVers, or a version found in
            # the Package object.
            # Figure out the name.
            upgrade_name = package.FileName(curVers)
            file = TryGetNetworkFile(
                self.PackageUpdatePath(package, curVers),
                handler = handler,
                )
            if h is None:
                # No checksum, so just accept the file
                return file
            else:
                hash = ChecksumFile(file)
                if hash == h:
                    return file
        # All that, and now we do much of it again with the full version
        file = TryGetNetworkFile(
            self.PackagePath(package),
            handler = handler,
            )
        if package.Checksum() is None:
            # No checksum, so we just go wit hthe match
            return file
        else:
            hash = ChecksumFile(file)
            if hash == package.Checksum():
                return file
            else:
                # No match
                return None
        raise Exception("This should not be reached")


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
