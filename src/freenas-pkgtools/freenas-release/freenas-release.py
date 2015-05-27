#!/usr/bin/env python
import os
import sys
import getopt
import stat
import fcntl

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Package as Package
import freenasOS.PackageFile as PackageFile

"""
The purpose of this is to take the output of a build,
and put it into a repoistory, or at least a hierarchy
that can be pushed out to a real server, through rsync,
scp, replication, whatever.

This also will keep track of the releases.

We start with the contents of objs/os-base/amd64/_.packages
from a build.  This will have a file called FreeNAS-MANIFEST
(actually a symlink), and a directory calld Packages.

We load the manifest, verify the checksums for the packages,
and then copy the packages into the destination location,
using the current scheme (which is, at this moment,
$ROOT/FreeNAS/Packages -- but this may change due to clumsiness).

At that point, we could write out the manifest.  Or we could
look at previous releases for that train, and see what possible
delta packags we can make.
"""

debug = 0
verbose = 1
debugsql = False

# A brief note here:
# The database_version should change only when absolutely
# necessary -- new tables that can happily be empty should
# have the same version number.  But if new semantics are needed,
# or tables are removed or repurosed, then the database version
# should change.
database_version = 1

class DatabaseException(Exception):
    pass

class DatabaseIncompatibleVersionException(DatabaseException):
    pass

def DebugSQL(sql, parms):
    if debugsql:
        print >> sys.stderr, "sql = %s, parms = %s" % (sql, parms)
        
CONFIG_KEYFILE_KEY = "keyfile"
CONFIG_DBPATH_KEY = "db"
CONFIG_ARCHIVE_KEY = "archive"

CONFIG_FILE_DEFAULT = "/usr/local/etc/freenas-release-default.conf"
CONFIG_FILE_SYSTEM = "/usr/local/etc/freenas-release.conf"
CONFIG_FILE_USER = os.path.expanduser("~/.freenas-release.conf")

def SetConfiguration(path, project, arg_dict = {}):
    """
    Set configuration files for the configuration file at
    path.  If path doesn't exist, it will attempt to create
    it; if it does exist, it loads it up first, and then
    replaces as needed.
    Values are taken from kwargs, which should be the keys
    from above.
    If project does not exist as a section in the file, then
    it is created; it may be an empty section.
    """
    import ConfigParser

    # Just a raw config parser so we do no interpolation.
    cfp = ConfigParser.RawConfigParser()
    try:
        fp = open(path, "r")
    except:
        pass
    else:
        try:
            cfp.readfp(fp)
            fp.close()
        except BaseException as e:
            print >> sys.stderr, "Could not load config file %s: %s" % (path, str(e))
            return False

    # Now see if the section exists
    if cfp.has_section(project) == False:
        cfp.add_section(project)

    # Now go through arg_dict
    for key, value in arg_dict.iteritems():
        cfp.set(project, key, value)
        if value == "":
            cfp.remove_option(project, key)
            
    # Now save the object
    try:
        fp = open(path, "w")
    except BaseException as e:
        print >> sys.stderr, "Could not open config file %s for writing: %s" % (path, str(e))
        return False
    else:
        cfp.write(fp)

    return True
        
def GetConfiguration(path, project):
    """
    Load the configuration file at path, and
    return a dictionary with the setings for project.
    If path does not exist, or project does not exist in
    it, return None
    For now, we use ConfigParser.  May go to JSON after
    some experience with it.
    The contents of the configuration file will be parsed
    for environment variables and ~expansion.
    This uses the default config file.
    """
    import ConfigParser
    # This file is only used in this one function.
    
    retval = None

    cfp = ConfigParser.SafeConfigParser()
    # Read in the default config file, the system one, and the one given.
    # It's possible that the latter two will be the same, but that's okay.
    cfp.read([CONFIG_FILE_DEFAULT, CONFIG_FILE_SYSTEM, path])

    # Okay, got a file.  Now let's look for project.
    if cfp.has_section(project):
        # We may want to figure out how to have some default
        # values.
        # We do want to stash the project name in the environment space
        old_env = None
        if "PROJECT" in os.environ:
            old_env = os.environ["PROJECT"]
        os.environ["PROJECT"] = project
        # Okay, let's load the values from it
        # Most of the values are just strings, but
        # there are some known-type values, so we'll
        # look for those specially.  (Okay, none come
        # to mind just yet.)
        retval = {}
        for option in cfp.options(project):
            tstr = cfp.get(project, option)
            retval[option] = os.path.expanduser(os.path.expandvars(tstr))
        # And that's it
        # So now undo th eenvironment change
        if old_env:
            os.environ["PROJECT"] = old_env
        else:
            os.environ.pop("PROJECT")
            
    return retval

# Obtain a lock for an archive.
# This should be done before creating any files,
# such as manifests or package files.
# To unlock, simply close the returned object.
# Pass in wait = True to have it try to get
# a lock, otherwise it will return None if it
# can't get the lock.
is_locked = False
def LockArchive(archive, reason, wait = False):
    global is_locked
    
    class Locker(object):
        def __init__(self, wait = False):
            import fcntl
            # Do thrown an exception if we can't get the lock
            self._lock_file = open(os.path.join(archive, ".lock"), "wb+")
            flags = fcntl.LOCK_EX
            if not wait:
                flags |= fcntl.LOCK_NB
            try:
                fcntl.lockf(self._lock_file, flags, 0, 0)
            except (IOError, Exception) as e:
                print >> sys.stderr, "Unable to obtain lock for archive %s: %s" % (archive, str(e))
                return None
        def close(self):
            global is_locked
            if self._lock_file:
                self._lock_file.close()
                is_locked = False
            else:
                raise Exception("Lock isn't locked!")
                
    print >> sys.stderr, "LockArchive(%s, %s): %s" % (archive, wait, reason)
    if is_locked:
        print >> sys.stderr, "Recursive lock!??!?!"
        raise Exception("Recursive lock?!?!?!")
    lock_file = Locker(wait = wait)
    is_locked = True
    return lock_file

class ReleaseDB(object):
    """
    A class for manipulating the release database.
    A release consists of a train, sequence number, optional friendly name,
    optional release notes (preferrably URLs), and a set of packages.
    The sequence number is unique.
    """
    global debug, verbose

    def __init__(self, use_transactions = False, initialize = False):
        self._connection = None
        self._use_transactions = use_transactions

    def commit(self):
        pass

    def abort(self):
        pass

    def close(self, commit = True):
        if commit:
            self.commit()
        self._connection = None

    def AddRelease(self, manifest):
        pass

    def PackageForSequence(self, sequence, name = None):
        """
        Return the package for the given sequence.  If
        name is None, it will return all packages for the
        sequence as an array; otherwise, it returns a single
        object.  The return objects are freenasOS.Package
        (responding to Name() and Version() methods).
        """
        return None

    def TrainForSequence(self, sequence):
        """
        Return the train (as a string) for a given sequence.
        """
        return None

    def RecentPackageVersionsForTrain(self, pkg, train, count = 5):
        """
        Return the <count> most recent packages for the given train.
        If count is 0, return them all.
        """
        sql = """
        SELECT Packages.PkgVersion AS PkgVersion
        FROM Packages
        JOIN Manifests
        JOIN Sequences
        JOIN Trains
        WHERE Packages.PkgName = ?
        AND Trains.TrainName = ?
        AND Sequences.Train = Trains.indx
        AND Manifests.Sequence = Sequences.indx
        AND Manifests.Pkg = Packages.indx
        GROUP BY PkgVersion
        """
    def RecentSequencesForTrain(self, train, count = 5, oldest_first = False):
        """
        Return the last <count> sequences for the given train.
        If count is 0, it returns them all.  Returns an
        empty array if no match.
        """
        if debug:  print >> sys.stderr, "ReleaseDB::RecentSequencesForTrain(%s, %d)" % (train, count)
        return []

    def AddPakageUpdate(self, Pkg, OldPkg, DeltaChecksum = None):
        """
        Add an update, with optional checksum, for Pkg.
        """
        pass

    def PackageUpdate(self, Pkg, OldPkg):
        """
        Get the update for oldpkg -> pkg, if any.
        Returns None if there is not one in the database, otherwise
        returns a dictionary.
        """
        pass
    
    def UpdatesForPackage(self, Pkg, count = 5):
        """
        Return an array of updates for the given package.
        If count is 0, it returns all known updates.
        The return objects are tuples of (version, checksum, reboot-required).
        checksum may be None.
        """
        return []

    def Trains(self):
        """
        Return a list of trains.  This an array of strings.
        Order of the list is undefined.
        """
        return []

    def NotesForSequence(self, sequence):
        return {}

    def NoticeForSequence(self, sequence):
        return None

class SQLiteReleaseDB(object):
    """
    SQLite subclass for ReleaseDB
    """
    global debug, verbose

    def __init__(self, initialize = False, dbfile = None):
        global debug
        import sqlite3
        if dbfile is None:
            raise Exception("dbfile must be specified")
        self._dbfile = dbfile
        if initialize:
            try:
                os.remove(self._dbfile)
            except:
                pass
        else:
            # If it doesn't exist, we act as if we've been asked to initialize
            if not os.path.exists(self._dbfile):
                initialize = True
                
        self._connection = sqlite3.connect(self._dbfile, isolation_level = None)
        if self._connection is None:
            raise Exception("Could not connect to sqlie db file %s" % dbfile)

        self._connection.text_factory = str
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()
        self._cursor.execute("PRAGMA foreign_keys = ON")

        if not initialize:
            # Check the version number
            try:
                self._cursor.execute("SELECT Version FROM Version")
            except sqlite3.OperationalError:
                version = None
            else:
                rows = self._cursor.fetchone()
                version = rows["Version"]
            if version != database_version:
                raise DatabaseIncompatibleVersionException("Database version incompatible; may need a rebuild")
        else:
            self._cursor.execute("CREATE TABLE Version(dumb_text TEXT PRIMARY KEY, Version INTEGER NOT NULL)")
            self._cursor.execute("INSERT INTO Version(dumb_text, Version) VALUES(?, ?)", ("version", database_version))
            self._connection.commit()
            self._cursor = self._connection.cursor()
            
        # The Packages table consists of the package names, package version, optional checksum.
        # The indx value is used to determine which versions are newer, and also as a foreign
        # key to create the Releases table below.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Packages(PkgName TEXT NOT NULL, PkgVersion TEXT NOT NULL, RequiresReboot INTEGER DEFAULT 1, Checksum TEXT, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT pkg_constraint UNIQUE (PkgName, PkgVersion) ON CONFLICT IGNORE)")

        # The Trains table consists solely of the train name, and an indx value to determine which ones
        # are newer.  (I don't think that's used for anything, however.)
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Trains(TrainName TEXT NOT NULL UNIQUE ON CONFLICT IGNORE, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT)")

        # The Sequences table consists of sequences, a reference to a train name,
        # and an indx value to determine which ones are newer.  Sequence is used as a foreign key
        # in several other tables.
        self._cursor.execute("""
        CREATE TABLE IF NOT EXISTS Sequences(Sequence TEXT NOT NULL UNIQUE,
        Train NOT NULL,
        indx INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        CONSTRAINT sequence_constraint FOREIGN KEY(Train) REFERENCES Trains(indx))
        """)

        # The ReleaseNotes table consists of notes, and which sequences use them.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS ReleaseNotes(NoteName TEXT NOT NULL, NoteFile TEXT NOT NULL, Sequence NOT NULL, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT relnote_constraint UNIQUE(NoteName, Sequence), CONSTRAINT relnote_sequence_constraint FOREIGN KEY(Sequence) REFERENCES Sequences(indx))")


        # The ReleaseNames table consists of release names, and which sequences use them.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS ReleaseNames(Name TEXT NOT NULL, Sequence NOT NULL UNIQUE, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT relname_constrant FOREIGN KEY(Sequence) REFERENCES Sequences(indx))")

        # A table for notices.  Notices are like notes, except there is
        # only one, and it is kept in the manifest, not downloaded
        # separately.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Notices(Notice TEXT NOT NULL, Sequence NOT NULL UNIQUE, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT notices_constraint FOREIGN KEY(Sequence) REFERENCES Sequences(indx))")
 
        # The Manifests table.
        # A manifest consists of a reference to an entry in Sequences for the sequence number,
        # and a package reference.  A manifest file is built by selecting the packages for
        # the given sequence, in order.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Manifests(Sequence NOT NULL, Pkg NOT NULL, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT releases_seq_constraint FOREIGN KEY(Sequence) REFERENCES Sequences(indx), CONSTRAINT releases_pkg_constraint FOREIGN KEY(Pkg) REFERENCES Packages(indx))")

        # A table for keeping track of delta packages.
        # We ignore duplicates, but this could be a problem
        # if the checksum is different.  So revisit this.
        self._cursor.execute("""
        CREATE TABLE IF NOT EXISTS PackageUpdates(Pkg NOT NULL,
        	PkgBase NOT NULL,
		RequiresReboot INTEGER DEFAULT 1,
		Checksum TEXT,
		indx INTEGER PRIMARY KEY ASC AUTOINCREMENT,
		CONSTRAINT pkg_update_key FOREIGN KEY (Pkg) REFERENCES Packages(indx),
		CONSTRAINT pkg_update_base_key FOREIGN KEY (PkgBase) REFERENCES Packages(indx),
		CONSTRAINT pkg_update_constraint UNIQUE (Pkg, PkgBase) ON CONFLICT IGNORE)
        """)

        # A table for keeping track of delta-update scripts.
        self._cursor.execute("""
        CREATE TABLE IF NOT EXISTS PackageDeltaScripts(Pkg NOT NULL,
		ScriptName TEXT,
		Checksum TEXT,
		indx INTEGER PRIMARY KEY ASC AUTOINCREMENT,
	        CONSTRAINT package_delta_scripts_key FOREIGN KEY (Pkg) REFERENCES Packages(indx),
		CONSTRAINT package_delta_scripts_contraint UNIQUE (Pkg, ScriptName) ON CONFLICT IGNORE)
        """)

        # A table for keeping track of which services are to be restarted on update
        # ServiceRestart maps to a boolean.
        self._cursor.execute("""
        CREATE TABLE IF NOT EXISTS PackageServiceRestart(Pkg NOT NULL,
        	ServiceName TEXT NOT NULL,
        	ServiceRestart INTEGER NOT NULL,
		indx INTEGER PRIMARY KEY ASC AUTOINCREMENT,
		CONSTRAINT package_servicerestart_key FOREIGN KEY (Pkg) REFERENCES Packages(indx))
        """)
        
        self.commit()

    def commit(self):
        if self._cursor:
            self._connection.commit()
            self._cursor = self._connection.cursor()
        else:
            print >> sys.stderr, "Commit attempted with no cursor"
            
    def cursor(self):
        if self._cursor is None:
            print >> sys.stderr, "Cursor was none, so getting a new one"
            self._cursor = self._connection.cursor()
        return self._cursor

    def close(self, commit = True):
        if commit:
            print >> sys.stderr, "Committing the transaciton"
            self.commit()
        if self._connection:
            self._cursor = None
            self._connection.close()
            self._connection = None

    def ManifestDeleteSequence(self, sequence):
        """
        Remove the given sequence from the Manifests table.
        """
        # First the manifests table
        sql = """
        DELETE FROM Manifests
        WHERE sequence IN
        (SELECT indx
         FROM Sequences
         WHERE Sequences.sequence = ?)
        ;
        """
        parms = (sequence,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        sql = """
        SELECT * from Manifests WHERE sequence IN
        (SELECT indx FROM Sequences WHERE Sequences.sequence = ?);
        """
        self.cursor().execute(sql, parms)
        for m in self.cursor().fetchall():
            print >> sys.stderr, "m = %s" % m
            raise Exception("Damnit")
        
        return

    def DeleteSequence(self, sequence):
        """
        Remove the given sequence form the Sequences table.
        """
        sql = """
        DELETE FROM Sequences
        WHERE Sequence = ?
        ;
        """
        parms = (sequence, )
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        sql = "SELECT Sequence FROM Sequences WHERE Sequence = ?"
        self.cursor().execute(sql, parms)
        for m in self.cursor().fetchall():
            print >> sys.stderr, "This shouldn't happen:  %s" % str(m)
            raise Exception("This should not have happened")
        
        return
    
    def NoticesDeleteSequence(self, sequence):
        sql = """
        DELETE FROM Notices WHERE Sequence IN
        (SELECT indx FROM Sequences WHERE Sequence = ?)
        ;
        """
        parms = (sequence, )
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        return
    
    def AddRelease(self, manifest):
        #    def AddRelease(self, sequence, train, packages, name = None, notes = None, notice = None):

        """
        Add the release into the database.  This inserts values into
        the Releases, Packages, Trains, and ReleaseNotes tables, as appropriate.
        """

        # First, make sure the train name is in the database
        # The "ON CONFLICT IGNORE" ensures it won't cause a problem if it's already in there.
        self.cursor().execute("INSERT INTO Trains(TrainName) VALUES(?)", (manifest.Train(),))

        # Next, insert the sequence into the database, referring the train name
        sql = """
        INSERT INTO Sequences(Sequence, Train)
        SELECT ?, Trains.indx
        FROM Trains
        WHERE Trains.TrainName = ?
        """
        parms = (manifest.Sequence(), manifest.Train())
        DebugSQL(sql, parms)

        self.cursor().execute(sql, parms)

        if manifest.Notes():
            for note in manifest.Notes().keys():
                sql = """
                INSERT INTO ReleaseNotes(NoteName, NoteFile, Sequence)
                SELECT ?, ?, Sequences.indx
                FROM Sequences
                WHERE Sequences.Sequence = ?
                """
                parms = (note, manifest.Notes()[note], manifest.Sequence())
                DebugSQL(sql, parms)
                self.cursor().execute(sql, parms)

        if manifest.Notice():
            sql = """
            INSERT INTO Notices(Notice, Sequence)
            SELECT ?, Sequences.indx
            FROM Sequences
            WHERE Sequences.Sequence = ?
            """
            parms = (manifest.Notice(), manifest.Sequence())
            DebugSQL(sql, parms)
            self.cursor().execute(sql, parms)

        # Next, the packages.
        for pkg in manifest.Packages():
            # The package was added to the database during processing
            sql = """
            INSERT INTO Manifests(Sequence, Pkg)
            SELECT Sequences.indx, Packages.indx
            FROM Sequences JOIN Packages
            WHERE Sequences.Sequence = ?
            AND (Packages.PkgName = ? AND Packages.PkgVersion = ?)
            """
            parms = (manifest.Sequence(), pkg.Name(), pkg.Version())
            DebugSQL(sql, parms)
                
            self.cursor().execute(sql, parms)
            
        # I haven't implemented this at all
        # if manifest.Name():
        #self.cursor().execute("""
        #INSERT INTO ReleaseNames(Name, Sequence)
        #SELECT ?, Sequences.indx
        #FROM Sequences
        #WHERE Sequences.Sequence = ?
        #""", (name, sequence))

        self.commit()

    def SequencesForPackage(self, pkg):
        """
        For a given package (name and version), return a list
        (if any) of sequences that use it.
        """
        sql = """
        SELECT Sequences.Sequence AS Sequence
        FROM Sequences
        JOIN Manifests
        JOIN Packages
        WHERE Packages.PkgName = ? AND Packages.PkgVersion = ?
        AND Manifests.Pkg = Packages.indx
        AND Manifests.Sequence = Sequences.indx
        """
        parms = (pkg.Name(), pkg.Version())
        DebugSQL(sql, parms)

        self.cursor().execute(sql, parms)
        rv = []
        sequences = self.cursor().fetchall()
        for seq in sequences:
            rv.append(seq["Sequence"])

        if len(rv) == 0:
            return None
        return rv
    
    def PackageForSequence(self, sequence, name = None):
        """
        For a given sequence, return the package for it.
        If name is None, then return all the packages for
        that sequence.

        """

        sql = """
        SELECT PkgName, PkgVersion, RequiresReboot, Checksum
        FROM Manifests
        JOIN Packages
        JOIN Sequences
        WHERE Sequences.Sequence = ?
        AND Manifests.Sequence = Sequences.indx
        AND Manifests.Pkg = Packages.indx
        %s
        ORDER BY Manifests.indx ASC
        """ % ("AND Packages.PkgName = ?" if name else "")

        if name:
            parms = (sequence, name)
        else:
            parms = (sequence,)

        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        packages = self.cursor().fetchall()
        rv = []
        for pkg in packages:
            if debug:  print >> sys.stderr, "Found package %s-%s" % (pkg['PkgName'], pkg['PkgVersion'])
            p = Package.Package(pkg["PkgName"], pkg["PkgVersion"], pkg["Checksum"])
            p.SetRequiresReboot(bool(pkg["RequiresReboot"]))
            rv.append(p)
        if rv and name:
            if len(rv) > 1:
                raise Exception("Too many results for package %s:  expected 1, got %d" % (name, len(rv)))
            return rv[0]
        if len(rv) == 0:
            return None
        return rv

    def TrainForSequence(self, sequence):
        """
        Return the name of the train for the given sequence.
        """
        sql = """
        SELECT Trains.TrainName AS Train
        FROM Trains
        JOIN Sequences
        WHERE Sequences.Sequence = ?
        AND Sequences.Train = Trains.indx
        """
        parms = (sequence,)

        self.cursor().execute(sql, parms)
        seq = self.cursor().fetchone()
        if seq is None:
            return None
        return seq["Train"]

    def RecentPackageVersionsForTrain(self, pkg, train, count = 5):
        """
        Return the <count> most recent packages for the given train.
        If count is 0, return them all.
        """
        sql = """
        SELECT Packages.PkgVersion AS PkgVersion,
        Packages.Checksum as Checksum,
        Packages.RequiresReboot as RequiresReboot
        FROM Packages
        JOIN Manifests
        JOIN Sequences
        JOIN Trains
        WHERE Packages.PkgName = ?
        AND Trains.TrainName = ?
        AND Sequences.Train = Trains.indx
        AND Manifests.Sequence = Sequences.indx
        AND Manifests.Pkg = Packages.indx
        GROUP BY PkgVersion
        ORDER BY Manifests.indx DESC
        """
        parms = (pkg.Name(), train)
        if count:
            sql += "LIMIT ?"
            parms += (count,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        rv = []
        for entry in self.cursor():
            if debug: print >> sys.stderr, "\t%s" % entry['PkgVersion']
            p = Package.Package(pkg.Name(), entry['PkgVersion'], entry['Checksum'])
            p.SetRequiresReboot(bool(entry['RequiresReboot']))
            rv.append(p)
        return rv
    
    def RecentSequencesForTrain(self, train, count = 5, oldest_first = False):
        """
        Get the most recent (ordered by indx desc, limit count)
        sequences for the given train.  If train is None, then
        it gets all the sequences.
        """
        if debug or verbose:
            print >> sys.stderr, "SQLiteReleaseDB::RecentSequencesForTrain(%s, %d, %s)" % (train, count, oldest_first)
        sql = """
        SELECT Sequences.Sequence AS Sequence
        FROM Sequences
        """
        if train:
            sql += """
        JOIN Trains
        WHERE Trains.TrainName = ?
        AND Sequences.Train = Trains.indx
            """
            parms = (train,)
        else:
            parms = ()
        sql += "ORDER BY Sequences.indx %s " % ("ASC" if oldest_first else "DESC")
        if count:
            sql += "LIMIT ?"
            parms += (count,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        rv = []
        for entry in self.cursor():
            if debug:  print >> sys.stderr, "\t%s" % entry['Sequence']
            rv.append( entry['Sequence'] )

        return rv

    def AddPackage(self, Pkg):
        sql = """
        INSERT INTO Packages(PkgName, PkgVersion, RequiresReboot, Checksum)
        VALUES(?, ?, ?, ?)
        """
        parms = (Pkg.Name(), Pkg.Version(), Pkg.RequiresReboot(), Pkg.Checksum())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
    
    def FindPackage(self, Pkg):
        sql = """
        SELECT PkgName, PkgVersion, RequiresReboot, Checksum
        FROM Packages
        WHERE PkgName = ? AND PkgVersion = ?
        """
        parms = (Pkg.Name(), Pkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        row = self.cursor().fetchone()
        if row is None:
            return None
        retval = Package.Package(row["PkgName"], row["PkgVersion"], row["Checksum"])
        retval.SetRequiresReboot(row["RequiresReboot"])
        return retval
        
    def PackageUpdatesDeleteUpdate(self, Pkg, base):
        sql = """
        DELETE
        FROM PackageUpdates
        WHERE
        PackageUpdates.Pkg IN (SELECT Packages.indx FROM Packages WHERE Packages.PkgName = ? AND Packages.PkgVersion = ?)
        AND
        PackageUpdates.PkgBase IN (SELECT Packages.indx FROM Packages WHERE Packages.PkgName = ? AND Packages.PkgVersion = ?)
        ;
        """
        parms = (Pkg.Name(), Pkg.Version(), Pkg.Name(), base)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        
    def PackageUpdatesDeletePkg(self, Pkg):
        sql = """
        DELETE
        FROM PackageUpdates
        WHERE PackageUpdates.Pkg IN
        (SELECT Packages.indx FROM Packages WHERE Packages.PkgName = ? AND Packages.PkgVersion = ?)
        ;
        """
        parms = (Pkg.Name(), Pkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        
    def AddPackageUpdate(self, Pkg, OldVersion, DeltaChecksum = None, RequiresReboot = True):
        import pdb
        global debug

        if debug or verbose:  print >> sys.stderr, "SQLiteReleaseDB:AddPackageUpdate(%s, %s, %s, %s, %s)" % (Pkg.Name(), Pkg.Version(), OldVersion, DeltaChecksum, RequiresReboot)

        sql = """
        INSERT INTO PackageUpdates(Pkg, PkgBase, RequiresReboot, Checksum)
        SELECT New.indx, Old.indx, ?, ?
        FROM Packages as New
        JOIN Packages as Old
        WHERE New.PkgName = ? AND New.PkgName = Old.PkgName
        AND New.PkgVersion = ?
        AND Old.PkgVersion = ?
        """
        parms = (int(RequiresReboot), DeltaChecksum, Pkg.Name(), Pkg.Version(), OldVersion)
        DebugSQL(sql, parms)

        self.cursor().execute(sql, parms)
        self.commit()
        if debug:
            x = self.UpdatesForPackage(Pkg, 1)
            print >> sys.stderr, "x = %s" % x

    def PackageUpdate(self, Pkg, OldPkg):
        """
        Return the update from OldPkg->Pkg, if any.
        This is in the database because it allows us to
        keep track of the RequiresReboot for an update, and
        the checksum for the delta package.  (We could recompute
        the checksum during processing, but it'd add time.  And
        we could figure out if a reboot was required by looking
        at the 
        """
        sql = """
        SELECT Updates.RequiresReboot as RequiresReboot, Updates.Checksum as Checksum
        FROM PackageUpdates as Updates
        JOIN Packages as New
        JOIN Packages as Old
        WHERE New.PkgName = ? AND New.PkgName = Old.PkgName
        AND New.PkgVersion = ?
        AND Old.PkgVersion = ?
        AND Updates.Pkg = New.indx
        AND Updates.PkgBase = Old.indx
        """
        parms = (Pkg.Name(), Pkg.Version(), OldPkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        rv = None
        rows = self.cursor().fetchone()
        if rows:
            if debug or verbose: print >> sys.stderr, "rows[RequiresReboot] = %s, rows[Checksum] = %s" % (bool(rows['RequiresReboot']), rows['Checksum'])
            rv = {
                Package.REBOOT_KEY : bool(rows["RequiresReboot"]),
                Package.CHECKSUM_KEY : rows["Checksum"]
                }
        return rv
        
    def UpdatesFromPackage(self, Pkg, count = 5):
        # Return an array of package updates from Pkg.
        # That is, entries in the PackageUpdates table
        # where Pkg is the PkgBase version.
        # For now, this simply returns an array of the
        # versions that are updated to, or None if there
        # aren't any
        sql = """
        SELECT Packages.PkgVersion as PkgNewVersion
        FROM PackageUpdates
        JOIN Packages
        WHERE PackageUpdates.PkgBase = Packages.indx
        AND Packages.PkgName = ?
        AND Packages.PkgVersion = ?
        ORDER BY PackageUpdates.indx DESC
        """
        parms = (Pkg.Name(), Pkg.Version())
        if count:
            sql += "LIMIT ?"
            parms += (count,)
        DebugSQL(sql, parms)

        self.cursor().execute(sql, parms)
        rv = []
        rows = self.cursor().fetchall()
        for pkgRow in rows:
            rv.append(pkgRow["PkgNewVersion"])
        if len(rv) == 0:
            return None
        return rv
    
    def UpdatesForPackage(self, Pkg, count = 5):
        # Return an array of package updates for Pkg.
        # That is, entries in the Updates table where
        # Pkg is the new version, it returns the PkgBase,
        # RequiresReboot, and Checksum fields.
        sql = """
        SELECT Packages.PkgVersion AS PkgOldVersion,
        	PackageUpdates.Checksum AS Checksum,
		PackageUpdates.RequiresReboot AS RequiresReboot
        FROM PackageUpdates
        JOIN Packages
        JOIN Packages as New
        WHERE PackageUpdates.PkgBase = Packages.indx
        AND New.PkgName = ?
        AND New.PkgVersion = ?
        AND PackageUpdates.Pkg = New.indx
        And Packages.PkgName = New.PkgName
        ORDER By PackageUpdates.indx DESC
        """
        parms = (Pkg.Name(), Pkg.Version())
        
        if count:
            sql += "LIMIT ?"
            parms += (count,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        rows = self.cursor().fetchall()
        rv = []
        for pkgRow in rows:
            if debug:  print >> sys.stderr, "Found Update %s for package %s-%s" % (pkgRow["PkgOldVersion"], Pkg.Name(), Pkg.Version())
            p = ( pkgRow['PkgOldVersion'] ,  pkgRow['Checksum'], bool(pkgRow['RequiresReboot']) )
            rv.append(p)
        return rv

    def Trains(self):
        rv = []
        cur = self.cursor()
        cur.execute("SELECT DISTINCT TrainName FROM TRAINS")
        trains = cur.fetchall()
        for t in trains:
            rv.append(t["TrainName"])

        return rv

    def NotesForSequence(self, sequence):
        sql = """
        SELECT ReleaseNotes.NoteName AS Name,
        	ReleaseNotes.NoteFile AS File
        FROM ReleaseNotes
        JOIN Sequences
        WHERE ReleaseNotes.Sequence = Sequences.indx
        AND Sequences.Sequence = ?
        """
        parms = (sequence,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql,parms)
        rv = {}
        for row in self.cursor().fetchall():
            n = row["Name"]
            f = row["File"]
            rv[n] = f
        return rv

    def NotesDeleteNoteFile(self, note_file):
        sql = """
        DELETE FROM ReleaseNotes WHERE NoteFile = ?
        ;
        """
        parms = (note_file,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)

    def NotesDeleteNoteSequence(self, sequence):
        sql = """
        DELETE FROM ReleaseNotes WHERE Sequence IN
        (SELECT indx FROM Sequences WHERE Sequence = ?)
        ;
        """
        parms = (sequence,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        
    def NoticeForSequence(self, sequence):
        sql = """
        SELECT Notice
        FROM Notices
        JOIN Sequences
        WHERE Notices.Sequence = Sequences.indx
        AND Sequences.Sequence = ?
        """
        parms = (sequence,)
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        notice = self.cursor().fetchone()
        return notice["Notice"]

    def AddPackageScript(self, pkg, name, script):
        import hashlib
        sql = """
        INSERT INTO PackageDeltaScripts(Pkg, ScriptName, Checksum)
        SELECT Packages.indx, ?, ?
        FROM Packages 
        WHERE Packages.PkgName = ? AND Packages.PkgVersion = ?
        """
        if script == "reboot":
            parms = (name, "-", pkg.Name(), pkg.Version())
        else:
            parms = (name, hashlib.sha256(script).hexdigest(), pkg.Name(), pkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        self.commit()

    def ScriptsDeleteForPackage(self, pkg, name = None):
        """
        Remove the given update script for the given package;
        if name is None, then remove them all.  This is only
        database entry, remember; the file needs to be handled
        separately.
        """
        sql = """
        DELETE FROM PackageDeltaScripts WHERE
        """
        parms = ()
        if name:
            sql += "name = ? AND"
            parms += (name,)
        sql += """
        indx IN (SELECT indx FROM Packages WHERE PkgName = ? AND PkgVersion = ?)
        ;
        """
        parms += (pkg.Name(), pkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        return
    
    def ServiceRestartDeleteForPackage(self, pkg, name = None):
        sql = """
        DELETE FROM PackageServiceRestart
        WHERE
        Pkg IN (SELECT indx FROM Packages WHERE PkgName = ? AND PkgVersion = ?)
        """
        parms = (pkg.Name(), pkg.Version())
        if name:
            sql += "AND ServiceName = ?"
            parms += (name, )
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        
    def AddServiceForPackageUpdate(self, pkg, name, restart):
        sql = """
        INSERT INTO PackageServiceRestart(Pkg, ServiceName, ServiceRestart)
        SELECT Packages.indx, ?, ?
        FROM Packages
        WHERE Packages.PkgName = ? AND Packages.PkgVersion = ?
        """
        parms = (name, int(restart), pkg.Name(), pkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        return
    
    def ServicesForPackageUpdate(self, pkg):
        """
        Return a dictionary of services to be restarted for
        a package update.
        """
        sql = """
        SELECT ServiceName as Name, ServiceRestart as Restart
        FROM PackageServiceRestart
        JOIN Packages
        WHERE
        Packages.PkgName = ?
        AND Packages.PkgVersion = ?
        AND PackageServiceRestart.Pkg = Packages.indx
        """
        parms = (pkg.Name(), pkg.Version())
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        retval = {}
        for svc in self.cursor().fetchall():
            retval[svc["Name"]] = bool(svc["Restart"])

        return retval
    
    def ScriptForPackage(self, pkg, name = None):
        """
        Get the update scripts for a particular package version.
        This resturns a dictionary, keyed by the name, with the
        value being (checksum, script).
        If name is None, it'll get all scripts for the package,
        otherwise it'll get only the specified script.
        It returns an empty dictionary if none are found.
        If any of the scripts require a reboot, the hash will be '-',
        and the method returns None.
        """
        sql = """
        SELECT Script.ScriptName AS Name, Script.Checksum AS Hash
        FROM PackageDeltaScripts AS Script
        JOIN Packages
        WHERE Script.Pkg = Packages.indx
        AND Packages.PkgName = ?
        AND Packages.PkgVersion = ?
        """
        parms = (pkg.Name(), pkg.Version())
        if name:
            sql += "AND Script.ScriptName = ?"
            parms += (name,)
        rv = {}
        DebugSQL(sql, parms)
        self.cursor().execute(sql, parms)
        scripts = self.cursor().fetchall()
        for s in scripts:
            if debug or verbose:
                print >> sys.stderr, "Found script %s for package %s-%s" % (s["Name"], pkg.Name(), pkg.Version())
            n = s["Name"]
            h = s["Hash"]
            if s == "reboot" or h == "-":
                return { "reboot" : "reboot" }
            rv[n] = h
        if len(rv) == 0:
            return None
        return rv
    
def ChecksumFile(path):
    import hashlib
    global debug, verbose

    if debug: print >> sys.stderr, "ChecksumFile(%s)" % path
    kBufSize = 4 * 1024 * 1024
    sum = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            buf = f.read(kBufSize)
            if buf:
                sum.update(buf)
            else:
                break

    if debug:  print >> sys.stderr, "sum.hexdigest = %s" % sum.hexdigest()
    return sum.hexdigest()

def usage():
    print >> sys.stderr, """Usage: %s [--config config_file] [--database|-D db] [--debug|-d] [--verbose|-v] [--archive|--destination|-a archive_directory] <cmd> [args]
    Command is:
	add	Add the build-output directories (args) to the archive and database
	check	Check the archive for self-consistency.
    	rebuild	Rebuild the databse (--copy <new_dest> and --verify options)
	dump	Print out the sequences in order (--train=<train> to limit to a specific train)
    	extract	Extract a particular release from the archive
	project	Settings for a project (run as root for system-wide, as user for user-specific).
    	delete	Delete a sequence or package.
    	rollback	Delete the most recent sequence for a train.
	prune	Delete oldest sequences.
""" % sys.argv[0]
    sys.exit(1)

def UpgradeScriptsForPackage(archive, db, pkg, sequences = None):
    """
    Return the update scripts for the given packages, for the
    given sequences.

    Returns None if a reboot is required for any of the updates.
    Otherwise, it returns a dictionary, where the key is the name
    of the script, and the value is the concatenated value of all
    of the versions (in sequential order) from the sequences.
    If there are no delta scripts, it will return an empty dictionary,
    in which case the defaults for the package should be used by
    the caller.
    """
    import hashlib
    rv = {}

    if sequences is None:
        # Just get the scripts for this version
        pkg_list = (pkg,)
    else:
        for sequence in sequences:
            pkg_list += (db.PackageForSequence(sequence, pkg.Name()),)
            
    for current_pkg in pkg_list:
        # Let's see if there is are any update scripts
        pkg_scripts = db.ScriptForPackage(current_pkg)
        if pkg_scripts is None:
            if current_pkg.RequiresReboot() == True:
                # That means a reboot was required
                print >> sys.stderr, "Package %s-%s requires a reboot" % (current_pkg.Name(), current_pkg.Version())
                return None
        elif "reboot" in pkg_scripts:
            # Force a reboot
            return None
        else:
            for script_name in pkg_scripts:
                if script_name not in rv:
                    rv[script_name] = ""
                script_path = os.path.join(archive, "Packages", pkg.Name(), current_pkg.Version(), script_name)
                try:
                    script_content = open(script_path).read()
                except:
                    print >> sys.stderr, "Cannot open expected script %s" % script_path
                    print >> sys.stderr, "Returning None, indicating a reboot will be required"
                    return None
                # Should check the checksum, I suppose
                if pkg_scripts[script_name] != hashlib.sha256(script_content).hexdigest():
                    print >> sys.stderr, "*** %s script for %s-%s does not match checksum!" % (script_name, current_pkg.Name(), current_pkg.Version())
                rv[script_name] += script_content
    return rv

def AddPackageUpdateScript(db, archive, pkg, name, script, lock = True):
    """
    Add the given script to both the database and the archive.
    The script goes in <archive>/Packages/<pkg.name>/<pkg.version>/<name>
    """
    print >> sys.stderr, "AddPackageUpdateScript(db, %s, %s-%s, %s, %s, lock = %s)" % (archive, pkg.Name(), pkg.Version(), name, script, lock)
    script_dir = os.path.join(archive, "Packages", pkg.Name(), pkg.Version())
    script_path = os.path.join(script_dir, name)
    if lock:
        a_lock = LockArchive(archive, "Add Package Update Script", wait = True)
    else:
        a_lock = None
    try:
        os.makedirs(script_dir)
    except:
        pass
    try:
        open(script_path, "wx").write(script)
        try:
            db.AddPackageScript(pkg, name, script)
        except:
            print >> sys.stderr, "Unable to add script %s to db for %s-%s" % (name, pkg.Name(), pkg.Version())
            try:
                os.remove(script_path)
                os.rmdir(script_dir)
            except:
                pass
    except:
        print >> sys.stderr, "Could not create %s script for %s-%s" % (name, pkg.Name(), pkg.Version())
        print >> sys.stderr, "Path was %s, exception = %s" % (script_path, str(sys.exc_info()))
        pass
    if a_lock:
        a_lock.close()

def AddPackage(pkg, db = None,
               source = None,
               archive = None,
               train = None,
               scripts = None,
               fail_on_error = True,
               restart_services = {}):
    """
    THE ARCHIVE MUST BE LOCKED BY THE CALLER.

    Add the given package to the database.
    If source is set, it will compute the checksum for the file;
    if archive is also set, it will copy the file to the archive.
    If source is None but archive is set, then it will verify
    the checksums in the pkg object (including delta packages).
    (This is confusing enough to describe that perhaps it should use
    other arguments to indicate the various states.)

    Adding a package is somewhat intensive:  in addition to copying
    the file (which could be large), it also wants to create delta
    packages.  To create delta packages, it needs to know the train
    name -- so if that's not set, it can't create delta packages.
    (It can still try to verify them, however, or add them to the
    database.)
    When creating a delta package, if there are no differences, it
    will change the package to the previous version for the train.

    Returns the new pkg object (which may be the same as in the invocation).
    """

    def MergeServiceList(list1, list2):
        """
        Merge the cleverly-named list2 set of services
        into list1.  Both are expected to be dictionaries.
        True means to restart it; False means not to.  True
        trumps False.
        Returns a new dictionary.
        """

        if list1 is None and list2 is None:
            return None
        if list1 is None:
            retval = {}
        else:
            retval = list1.copy()

        if list2 is None:
            return retval
        
        for (svc, val) in list2.iteritems():
            if not svc in retval:
                retval[svc] = val
            else:
                # It's in the first list, so we have
                # to check the values
                if retval[svc] != val:
                    if val:
                        retval[svc] = val
                    # Do nothing if it's false
        return retval
    
    def PackageFromDB(package):
        """
        Given the package, we want to get all the information for it from
        the databae (and filesystem, if it exists).  This returns the
        Package object, with all its checksums.
        If archive is defined, then it will also attempt to get the
        file sizes.
        """
        retval = db.FindPackage(package)
        if retval is None:
            # This package isn't in the database
            return None
        # Set count to one more than usual
        previous_versions = db.RecentPackageVersionsForTrain(package, train, count = 6)
        if previous_versions:
            if previous_versions[0].Version() == package.Version():
                # This means that the package is already in the database.
                # So let's shift everything over
                retval = previous_versions[0]
                previous_versions = previous_versions[1:6]
            else:
                previous_versions = previous_versions[0:5]
        if archive:
            # If we've got an archive, we can set filesize and verify checksum
            pkgfile = os.path.join(archive, "Packages", retval.FileName())
            if os.path.exists(pkgfile):
                if retval.Checksum() != ChecksumFile(pkgfile):
                    print >> sys.stderr, "Archive and database for %s-%s disagree about checksum" % (retval.Name(), retval.Version())
                    raise Exception("How can this be?!?!")
                retval.SetSize(os.stat(pkgfile).st_size)
            else:
                raise Exception("We should not be here")
            # Should also get the list of services from the package file.
            package_services = PackageFile.GetPackageServices(path = pkgfile)

            if package_services:
                if "Restart" in package_services:
                    pkg_restart_list = package_services["Restart"]
                    tlist = []
                    for svc in pkg_restart_list.keys():
                        tlist.append(svc)
                    if tlist:
                        pkg.SetRestartServices(tlist)
                    
        # Now we want to get the updates from previous_versions to this version
        updates = db.UpdatesForPackage(retval)
        print >> sys.stderr, "\tFound updates %s" % updates
        for update in updates:
            (base, hash, rr) = update
            print >> sys.stderr, "\tAdding update from %s" % base
            if archive:
                delta_path = os.path.join(archive, "Packages", retval.FileName(base))
                size = os.stat(delta_path).st_size
            else:
                size = None
            upd = retval.AddUpdate(base,
                                   hash,
                                   size = size,
                                   RequiresReboot = rr)
            # Get any service restarts for this update
            svcs = db.ServicesForPackageUpdate(Package.Package(retval.Name(), base))
            if len(svcs) > 0:
                upd.SetRestartServices(svcs)
                
        return retval
    
    print >> sys.stderr, "AddPackage(%s-%s, db = %s, source = %s, archive = %s, train = %s, scripts = %s, fail_on_error = %s, restart_services = %s)" % (pkg.Name(), pkg.Version(), db, source, archive, train, scripts, fail_on_error, restart_services)
    
    add_pkg_to_db = True
    
    if source:
        pkg_file = os.path.join(source, pkg.FileName())

        checksum = ChecksumFile(pkg_file)
        if pkg.Checksum() != checksum:
            if pkg.Checksum():
                msg = "Package %s-%s checksum doesn't match source file" % (pkg.Name(), pkg.Version())
                print >> sys.stderr, msg
                if fail_on_error:
                    raise Exception(msg)
            pkg.SetChecksum(checksum)

        if archive:
            pkg_dest_file = os.path.join(archive, "Packages", pkg.FileName())
            if os.path.exists(pkg_dest_file):
                # If the package file already exists, then it's already been
                # added to the database.  We can't use the given one, because both it and
                # all the updates have been created already.  So we need to
                # get everything -- package information, delta scripts, updates --
                # from the database.
                print >> sys.stderr, "Package file for %s-%s already exists, so doing wackiness" % (pkg.Name(), pkg.Version())
                add_pkg_to_db = False
                checksum = ChecksumFile(pkg_dest_file)
                if pkg.Checksum() != checksum:
                    msg = "Package %s-%s checksum does not match archive version" % (pkg.Name(), pkg.Version())
                    print >> sys.stderr, msg
                    if fail_on_error:
                        raise Exception(msg)

                # This gets the previous version.
                # I think.
                pkg = PackageFromDB(pkg)
                if scripts:
                    print >> sys.stderr, "******* Package %s-%s already exists, can't specify delta scripts! ********" % (pkg.Name(), pkg.Version())
                    print >> sys.stderr, "\tTHEY WILL BE IGNORED"
                    
            else:
                # Copy pkg_file to pkg_dest_file
                # Also get previous version for pkg for train from database.
                # Create a delta package file.
                # If the diffs are empty, then remove the delta package file.
                # Remove the package file.
                # Set package to the previous version.
                # Either:
                # a) Get the updates for this version, or
                # b) Get the previous versions for this train and then get
                # the updates for those, if any.  Create delta packages as
                # necessary?
                with open(pkg_file, "rb") as src:
                    with open(pkg_dest_file, "wxb") as dst:
                        kBufSize = 1024 * 1024
                        while True:
                            buffer = src.read(kBufSize)
                            if buffer:
                                dst.write(buffer)
                            else:
                                break
                # Now get the previous versions of this package for this train
                previous_versions = db.RecentPackageVersionsForTrain(pkg, train)

                # Find out if there are any services listed for this package.
                package_services = PackageFile.GetPackageServices(path = pkg_file)
                print >> sys.stderr, "\t**** package_services = %s" % package_services
                
                pkg_svc_list = None
                pkg_restart_list = None
                service_list = None
                if package_services:
                    # If the package doesn't have any services to restart,
                    # we don't have to worry about it.
                    # This is a dictionary, with two keys:
                    # Services
                    try:
                        pkg_svc_list = package_services["Services"]
                    except:
                        pkg_svc_list = []
                    # and Restart
                    try:
                        pkg_restart_list = package_services["Restart"]
                    except:
                        pkg_restart_list = {}
                        
                    # We want to remove anything from restart_services that
                    # isn't listed in pkg_svc_list
                    if restart_services:
                        restart_services = restart_services.copy()
                        for svc in restart_services.keys():
                            print >> sys.stderr, "\t%s" % svc
                            if not svc in pkg_svc_list:
                                restart_services.pop(svc)
                        # And now let's get rid of anything that simply
                        # duplicates the defaults
                        if pkg_restart_list and restart_services:
                            for svc in restart_services.keys():
                                if svc in pkg_restart_list and \
                                   pkg_restart_list[svc] == restart_services[svc]:
                                    restart_services.pop(svc)
                                    
                            # Just in case this ends up being the same
                            if restart_services == pkg_restart_list:
                                restart_services = None
                else:
                    restart_services = None

                # We use this to add to the database, later on.
                if restart_services:
                    service_list = restart_services.copy()
                print >> sys.stderr, "After rpuning: restart_services = %s" % restart_services
                
                # Note that we are doing this before adding the new package to
                # the database, although that's not strictly necessary.  (But
                # not doing so means we don't have to remove it later if
                # we downgrade.)
                for v in previous_versions:
                    print >> sys.stderr, "\t%s" % v.Version()
                
                if previous_versions:
                    most_recent_pkg = previous_versions[0]
                    if most_recent_pkg.Version() == pkg.Version():
                        print >> sys.stderr, "Most recent version is the same as version being added?!?!"
                        raise Exception("That's not right")
                    
                    # This gets us the most recent version of the package
                    # for this train.  Since we created the package file, we
                    # don't have to look for a delta package file.
                    previous_pkgfile = os.path.join(archive, "Packages", most_recent_pkg.FileName())
                    if os.path.exists(previous_pkgfile):
                        delta_pkgfile = os.path.join(archive, "Packages", pkg.FileName(most_recent_pkg.Version()))
                        print >> sys.stderr, "Attempting to create delta package %s version %s -> %s" % (pkg.Name(), most_recent_pkg.Version(), pkg.Version())
                        diffs = PackageFile.DiffPackageFiles(previous_pkgfile, pkg_dest_file, delta_pkgfile, scripts = scripts)
                        if diffs is None:
                            print >> sys.stderr, "No differences between new package %s-%s and %s-%s" % (pkg.Name(), pkg.Version(), most_recent_pkg.Name(), most_recent_pkg.Version())
                            print >> sys.stderr, "Downgrading to previous package version"
                            # Need to downgrade, and also find updates.
                            os.remove(pkg_dest_file)
                            pkg = PackageFromDB(most_recent_pkg)
                            # The package is (obviously) already in the database
                            add_pkg_to_db = False
                        else:
                            # Add the update to the pkg
                            delta_checksum = ChecksumFile(delta_pkgfile)
                            # If there is a delta script, then we set rr to false
                            # We also don't need to reboot if a restart service
                            # is specified.
                            # Specifically for that:  if the package has any
                            # services to restart, even after modification by
                            # the options for this particular update, then we
                            # don't reboot.
                            # Note that pkg_restart_list is kept pristine, because
                            # it's the default set of restarts for the packge, which
                            # we need if there is no entry for the package.
                            print >> sys.stderr, "########### pkg_restart_list = %s, restart_services = %s" % (pkg_restart_list, restart_services)
                                
                            rr = None
                            if scripts:
                                if "reboot" in scripts:
                                    rr = True
                                else:
                                    rr = False
                            # When we look at the service restart list,
                            # a reboot is not required if ... what?
                            if restart_services and "reboot" in restart_services:
                                if restart_services["reboot"]:
                                    rr = True
                                else:
                                    rr = False
                                
                            upd = pkg.AddUpdate(most_recent_pkg.Version(),
                                                delta_checksum,
                                                size = os.lstat(delta_pkgfile).st_size,
                                                RequiresReboot = rr)
                            
                            print >> sys.stderr, "\t*** restart_services = %s" % restart_services
                            print >> sys.stderr, "\t\tpkg_restart_list = %s" % pkg_restart_list
                            upd.SetRestartServices(restart_services)
                            # Need to repeat for all the previous versions.
                            # But first we start with this, the most recent version
                            if restart_services:
                                tmp_restart_list = db.ServicesForPackageUpdate(most_recent_pkg)
                                restart_services = MergeServiceList(restart_services, tmp_restart_list)
                            if restart_services == pkg_restart_list:
                                restart_services = None
                            # Except that if diffs is none in those cases, we still
                            # need to create a delta package, even if it's empty.
                            if scripts:
                                delta_scripts = scripts.copy()
                            else:
                                delta_scripts = {}
                            # Now we need to get any update scripts for this, the most recent version
                            update_scripts = UpgradeScriptsForPackage(archive, db, most_recent_pkg)
                            print >> sys.stderr, "*** update_scripts = %s" % update_scripts
                            if update_scripts is None:
                                if not restart_services:
                                    delta_scripts["reboot"] = "reboot"
                            else:
                                for script in update_scripts:
                                    if script in delta_scripts:
                                        if script.startswith("pre-"):
                                            delta_scripts[script] = update_scripts[script] + delta_scripts[script]
                                        else:
                                            delta_scripts[script] += update_scripts[script]
                                    else:
                                        delta_scripts[script] = update_scripts[script]
                            
                            # Note that we go through this most-recent to oldest
                            # This is important for the delta script creation
                            for older_pkg in previous_versions[1:]:
                                # Need to get the service restart list for this update,
                                # then merge it into a list to be used when updating from
                                # this version to the current version.
                                # If there were no specified service restarts for this
                                # version, then we use the default for the package.  And
                                # remember:  restart always trumps not restarting.
                                # If the package requires a reboot, and any intervening
                                # version requires a reboot (no delta script, and no
                                # service restart list for that version), then the update
                                # requires a reboot.
                                print >> sys.stderr, "\tOlder version %s, restart_servces = %s" % (older_pkg.Version(), restart_services)
                                if restart_services:
                                    tmp_restart_list = db.ServicesForPackageUpdate(older_pkg)
                                else:
                                    tmp_restart_list = {}
                                print >> sys.stderr, "\tRestart list for pkg %s-%s = %s, pkg_restart_list = %s" % (older_pkg.Name(), older_pkg.Version(), tmp_restart_list, pkg_restart_list)
                                if tmp_restart_list:
                                    restart_services = MergeServiceList(restart_services, tmp_restart_list)
                                else:
                                    restart_services = None

                                update_scripts = UpgradeScriptsForPackage(archive, db, older_pkg)
                                # If the update's service restart list is the same as the package default,
                                # then don't include it at all.
                                if restart_services == pkg_restart_list:
                                    restart_services = None
                                print >> sys.stderr, "\tUpdate scripts for pkg %s-%s = %s" % (older_pkg.Name(), older_pkg.Version(), update_scripts)
                                if update_scripts is None:
                                    # That means a reboot is required
                                    # If the package default is to reboot, we have to reboot.
                                    if not restart_services and pkg.RequiresReboot():
                                        delta_scripts["reboot"] = "reboot"
                                else:
                                    for script in update_scripts:
                                        if script in delta_scripts:
                                            if script.startswith("pre-"):
                                                delta_scripts[script] = update_scripts[script] + delta_scripts[script]
                                            else:
                                                delta_scripts[script] += update_scripts[script]
                                        else:
                                            delta_scripts[script] = update_scripts[script]
                                if "reboot" in delta_scripts:
                                    delta_scripts = { "reboot" : "reboot" }
                                print >> sys.stderr, "\tdelta_scripts = %s" % delta_scripts
                                # Now we've got the update scripts from older_pkg to the current version.
                                # So let's create a delta package file
                                previous_pkgfile = os.path.join(archive, "Packages", older_pkg.FileName())
                                if os.path.exists(previous_pkgfile):
                                    delta_pkgfile = os.path.join(archive, "Packages", pkg.FileName(older_pkg.Version()))
                                    print >> sys.stderr, "Creating (forced) delta package file version %s -> %s" % (older_pkg.Version(), pkg.Version())
                                    PackageFile.DiffPackageFiles(previous_pkgfile,
                                                                 pkg_dest_file,
                                                                 delta_pkgfile,
                                                                 scripts = None if "reboot" in delta_scripts else delta_scripts,
                                                                 force_output = True)
                                    if (not delta_scripts) and (not restart_services):
                                        # Use the package default
                                        rr = None
                                    elif (delta_scripts and "reboot" in delta_scripts):
                                        rr = True
                                    elif (restart_services and "reboot" in restart_services):
                                        rr = restart_services["reboot"]
                                    elif delta_scripts or restart_services:
                                        rr = False
                                    else:
                                        raise Exception("I do not understand boolean logic")
                                        rr = False
                                    # If the package requires a reboot, and there is no
                                    # service restart list for this update, then we have
                                    # to reboot.
                                    print >> sys.stderr, "Package %s, second update:  RequiresReboot = %s, rr = %s, tmp_restart_list = %s" % (pkg.Name(), older_pkg.RequiresReboot(), rr, tmp_restart_list)
                                    upd = pkg.AddUpdate(older_pkg.Version(),
                                                        ChecksumFile(delta_pkgfile),
                                                        size = os.lstat(delta_pkgfile).st_size,
                                                        RequiresReboot = rr)
                                    if restart_services:
                                        upd.SetRestartServices(restart_services)
                                    print >> sys.stderr, "\t#### second one:  restart_services = %s" % restart_services
                                else:
                                    print >> sys.stderr, "Secondary Previous package file %s doesn't exist" % previous_pkgfile
                    else:
                        print >> sys.stderr, "Initial previous package file %s doesn't exist" % previous_pkgfile
                else:
                    print >> sys.stderr, "No previous versions for package %s-%s" % (pkg.Name(), pkg.Version())
        else:
            # No archive, so can't save
            # But we can compare the checksum to the real file
            # The checksum has already been computed above,
            # so all that's left to do is look at the updates,
            # if any.
            for upd in pkg.Updates():
                delta_file = os.path.join(source, pkg.FileName(upd.Version()))
                if os.path.exists(delta_file):
                    if upd.Checksum():
                        update_cksum = ChecksumFile(delta_file)
                        if upd.Checksum() != update_cksum:
                            print >> sys.stderr, "Delta package %s checksum does not match package" % pkg.FileName(upd.Version())
                            if fail_on_error:
                                raise Exception("Delta packgage checksum mismatch")
    elif archive:
        # We got here by having source = None, so we may be
        # rebuilding the database.  We expect that the input
        # package has all the updates as required (for a rebuild,
        # that would come from the manifest file).
        if restart_services:
            service_list = restart_services
        else:
            service_list = None
            
        # So first let's see if the package is already in the database.
        if db.FindPackage(pkg):
            if debug or verbose:  print >> sys.stderr, "\tPackage is already in database"
            add_pkg_to_db = False
        else:
            # Okay, it's not in the database, so we'll want to
            # add it.  Let's check on the status of delta scripts.
            if scripts is None:
                scripts = {}
                # Let's look in the archive for scripts.
                script_dir = os.path.join(archive, "Packages", pkg.Name(), pkg.Version())
                if os.path.exists(script_dir):
                    for script_name in os.listdir(script_dir):
                        if script_name == "Services":
                            continue
                        scripts[script_name] = open(os.path.join(script_dir, script_name), "r").read()
                if len(scripts) == 0:
                    scripts = None
                if scripts and "reboot" in scripts:
                    scripts = { "reboot" : "reboot" }
                if scripts:
                    print >> sys.stderr, "Delta scripts: %s" % scripts
    else:
        raise Exception("No source or archive, don't know what to do")
    
    # Should the package be added to the database _here_?
    # All the updates would be added here as well, of so.
    # Let's add the package to the database
    if restart_services and not add_pkg_to_db:
        print >> sys.stderr, "Restart services = %s, but not adding package %s-%s to database.  Problem?" % \
            (restart_services, pkg.Name(), pkg.Version())
    if add_pkg_to_db:
        if debug or verbose:  print >> sys.stderr, "\tAdding to database"
        db.AddPackage(pkg)
        # RequiresReboot defaults to the package default
        rr = pkg.RequiresReboot()
        if service_list:
            import json
            svclist_dir = os.path.join(archive, "Packages", pkg.Name(), pkg.Version());
            try:
                os.makedirs(svclist_dir)
            except:
                pass
            svc_list_file_name = os.path.join(svclist_dir, "Services")
            try:
                svc_list_file = open(svc_list_file_name, "wx")
                json.dump(service_list, svc_list_file)
                svc_list_file.close()
                print >> sys.stderr, "Wrote service list to %s" % svc_list_file_name
            except BaseException as e:
                print >> sys.stderr, "Could NOT write service list to %s: %s" % (svc_list_file_name, str(e))
                svc_list_file = None
            for svc, val in service_list.iteritems():
                print >> sys.stderr, "Adding service %s -> %s for %s-%s" % (svc, val, pkg.Name(), pkg.Version())
                db.AddServiceForPackageUpdate(pkg, svc, val)
        if scripts:
            if "reboot" in scripts:
                # Force a reboot for this update
                rr = True
                AddPackageUpdateScript(db, archive, pkg, "reboot", "reboot", lock = False)
            else:
                rr = False
                for script in scripts:
                    AddPackageUpdateScript(db, archive, pkg, script, scripts[script], lock = False)
        # Now add the updates to the database as well
        for update in pkg.Updates():
            o_vers = update.Version()
            o_cksum = update.Checksum()
            if update.RequiresReboot() is None:
                o_reboot = pkg.RequiresReboot()
            else:
                o_reboot = update.RequiresReboot()
            print >> sys.stderr, "\tAdding update to database %s -> %s" % (o_vers, pkg.Version())
            db.AddPackageUpdate(pkg, o_vers, DeltaChecksum = o_cksum, RequiresReboot = o_reboot)
            
    return pkg

def ProcessRelease(source, archive,
                   db = None,
                   sign = False,
                   project = "FreeNAS",
                   key_data = None,
                   changelog = None):
    """
    Process a directory containing the output from a freenas build.
    We're looking for source/${project}-MANIFEST, which will tell us
    what the contents are.
    """
    global debug, verbose

    force_reboot = None
    
    if debug:  print >> sys.stderr, "Processelease(%s, %s, %s, %s)" % (source, archive, db, sign)

    if db is None:
        raise Exception("Invalid db")

    pkg_source_dir = "%s/Packages" % source
    pkg_dest_dir = "%s/Packages" % archive

    if not os.path.isdir(pkg_source_dir):
        raise Exception("Source package directory %s is not a directory!" % pkg_source_dir)
    if not os.path.isdir(pkg_dest_dir):
        os.makedirs(pkg_dest_dir)

    manifest = Manifest.Manifest()
    if manifest is None:
        raise Exception("Could not create a manifest object")
    manifest.LoadPath(source + "/%s-MANIFEST" % project)

    # Let's look for any of the known notes
    notes = {}
    for note_name in ["ReleaseNotes", "ChangeLog", "NOTICE"]:
        try:
            with open("%s/%s" % (source, note_name), "r") as f:
                notes[note_name] = f.read()
        except:
            pass
    
    try:
        service_file = open(os.path.join(source, "RESTART"), "r")
        service_list = service_file.read().strip()
        services = {}
        for svc in service_list.split():
            svc = svc.strip()
            val = True
            if "=" in svc:
                (svc, val) = svc.split("=")
                if val in ("no", "NO", "No", "False", "FALSE", "0"):
                    val = False
                else:
                    val = True
            services[svc] = val
    except BaseException as e:
        # Any errors -- usually going to be ENOENT -- means we
        # have no services to list
        services = {}
    print >> sys.stderr, "******************* services = %s" % services
    
    try:
        reboot_str = open(os.path.join(source, "FORCEREBOOT"), "r").read().strip()
        if reboot_str in ("YES", "yes", "Yes", "True", "TRUE"):
            force_reboot = True
        elif reboot_str in ("NO", "no", "No", "False", "FALSE"):
            force_reboot = False
    except:
        pass
    
    # Everything goes into the archive, and
    # most is relative to the name of the train.
    try:
        os.makedirs("%s/%s" % (archive, manifest.Train()))
    except:
        pass
    # First, let's try creating the manifest file.
    # If there's a duplicate, let's change the sequence by adding a digit.
    # Then loop until we're done
    suffix = None
    name = manifest.Sequence()
    lock = LockArchive(archive, "Creating manifest file", wait = True)
    while True:
        if suffix is not None:
            name = "%s-%d" % (manifest.Sequence(), suffix)
            print >> sys.stderr, "Due to conflict, trying sequence %s" % name
        new_mani_path = "%s/%s/%s-%s" % (archive, manifest.Train(), project, name)
        try:
            mani_file = open(new_mani_path, "wxb", 0622)
            break
        except (IOError, OSError) as e:
            import errno
            if e.errno == errno.EEXIST:
                # Should we instead compare the manifests, and
                temp_mani = Manifest.Manifest()
                temp_mani.LoadPath(new_mani_path)
                if len(Manifest.CompareManifests(manifest, temp_mani)) == 0:
                    print >> sys.stderr, "New manifest seems to be the same as the old one, doing nothing"
                    lock.close()
                    return
                if suffix is None:
                    suffix = 1
                else:
                    suffix += 1
                continue
            else:
                print >> sys.stderr, "Cannot create manifest file %s: %s" % (name, str(e))
                raise e
        except Exception as e:
                raise e
    lock.close()
    manifest.SetSequence(name)

    # Okay, let's see if this train has any prior entries in the database
    previous_sequences = db.RecentSequencesForTrain(manifest.Train())

    pkg_list = []
    delta_scripts = {}
    for pkg in manifest.Packages():
        lock = LockArchive(archive, "Processing package %s-%s" % (pkg.Name(), pkg.Version()), wait = True)
        print >> sys.stderr, "Package %s, version %s, filename %s" % (pkg.Name(), pkg.Version(), pkg.FileName())
        # Some setup for the AddPackage function
        script_path = os.path.join(pkg_source_dir, pkg.Name())
        scripts = {}
        if os.path.isdir(script_path):
            for script_name in os.listdir(script_path):
                scripts[script_name] = open(os.path.join(script_path, script_name), "r").read()
        if len(scripts) == 0:
            scripts = None
        pkg = AddPackage(pkg, db,
                         source = pkg_source_dir,
                         archive = archive,
                         train = manifest.Train(),
                         scripts = scripts,
                         fail_on_error = False,
                         restart_services = services,
                         )

        # Unlock the archive now
        lock.close()
        pkg_list.append(pkg)
        
    # Now let's go over the possible notes.
    # Right now, we only support three:
    # ReleaseNotes, ChangeLog, and NOTICE.
    # NOTICE goes into the manifest to display
    # when loaded; ReleaseNotes and ChangeLog
    # go into the archive under <train>/Notes,
    # with a unique name.  (We'll use mktemp
    # to create it; the name goes into the manifest
    # and is recreated by the library code.)
    if "NOTICE" in notes:
        manifest.SetNotice(notes["NOTICE"])
        notes.pop("NOTICE")
    for note_name in notes.keys():
        import tempfile
        note_dir = "%s/%s/Notes" % (archive, manifest.Train())
        lock = LockArchive(archive, "Creating note file", wait = True)
        try:
            os.makedirs(note_dir)
        except:
            pass
        try:
            # The note goes in:
            # <archive>/<train>/Notes/<name>-<random>.txt
            # The manifest gets a dictionary with
            # <name> : <name>-<random>.txt
            # which the library code will use to
            # fetch over the network.
            note_file = tempfile.NamedTemporaryFile(suffix=".txt",
                                                    dir=note_dir,
                                                    prefix="%s-" % note_name,
                                                    delete = False)
            if debug or verbose:
                print >> sys.stderr, "Created notes file %s for note %s" % (note_file.name, note_name)
            note_file.write(notes[note_name])
            os.chmod(note_file.name, 0664)
            manifest.SetNote(note_name, os.path.basename(note_file.name))
        except OSError as e:
            print >> sys.stderr, "Unable to save note %s in archive: %s" % (note_name, str(e))
        lock.close()
    # And now let's add it to the database
    manifest.SetPackages(pkg_list)
    # If we're given a key file, let's sign it
    if key_data:
        try:
            manifest.SignWithKey(key_data)
        except:
            print >> sys.stderr, "Could not sign manifest, so removing file"
            try:
                os.remove(mani_file.name)
                mani_file.close()
            except:
                pass
            return

    manifest.SetReboot(force_reboot)
        
    lock = LockArchive(archive, "Saving manifest file", wait = True)
    manifest.StorePath(mani_file.name)
    mani_file.close()
    lock.close()
    lock = LockArchive(archive, "Creating LATEST symlink", wait = True)
    MakeLATEST(archive, project, manifest.Train(), manifest.Sequence())
    lock.close()
    
    if changelog:
        changefile = "%s/%s/ChangeLog.txt" % (archive, manifest.Train())
        change_input = None
        if changelog == "-":
            print "Enter changelog, control-d when done"
            change_input = sys.stdin
        else:
            try:
                change_input = open(changelog, "r")
            except:
                print >> sys.stderr, "Unable to open input change log %s" % changelog
        if change_input:
            lock = LockArchive(archive, "Modifying ChangeLog", wait = True)
            try:
                cfile = open(changefile, "ab", 0664)
            except:
                print >> sys.stderr, "Unable to open changelog %s" % changefile
            else:
                cfile.write("### START %s\n" % manifest.Sequence())
                cfile.write(change_input.read())
                cfile.write("\n### END %s\n" % manifest.Sequence())
                cfile.close()
            lock.close()
            
    if db is not None:
        # Why would it ever be none?
        db.AddRelease(manifest)

def Check(archive, db, project = "FreeNAS"):
    """
    Given an archive location -- the target of ProcessRelease -- compare
    the database contents with the filesystem layout.  We're looking for
    missing files/directories, package files with mismatched checksums,
    and orphaned files/directories.
    """
    global verbose, debug
    # First, let's get the list of trains.
    trains = db.Trains()
    # Now let's collect the set of sequences
    # This will be a dictionary, key is train name,
    # value is an array of sequences.  We'll also add
    # "LATEST" to it.
    sequences = {}
    found_notes = {}
    for t in trains:
        s = db.RecentSequencesForTrain(t, 0)
        s.append("LATEST")
        sequences[t] = s
        for note_file in os.listdir(os.path.join(archive, t, "Notes")):
            found_notes[note_file] = True
        
    # First check is we make sure all of the sequence
    # files are there, as expected.  And that nothing
    # unexpected is there.
    # The firsrt step of that is to read the contents
    # of the archive directory.  The only entries in it
    # should be the list of train names, and Packages.
    # Each entry should be a directory.
    expected_contents = { "Packages" : True }
    for t in trains:
        expected_contents[t] = True

    found_contents = {}
    for entry in os.listdir(archive):
        if entry == ".lock":
            # This is the archive lock file
            continue
        if entry == "trains.txt":
            continue
        if not os.path.isdir(archive + "/" + entry):
            print >> sys.stderr, "%s/%s is not a directory" % (archive, entry)
        else:
            found_contents[entry] = True

    if expected_contents != found_contents:
        print >> sys.stderr, "Archive top-level directory does not match expectations"
        for expected in expected_contents.keys():
            if expected in found_contents:
                found_contents.pop(expected)
            else:
                print >> sys.stderr, "Missing Archive top-level entry %s" % expected
        for found in found_contents.keys():
            print >> sys.stderr, "Unexpected archive top-level entry %s" % found

    # Now we want to check that each train has only the sequences
    # expected.  Along the way, we'll also start loading the
    # expected_packages.
    expected_packages = {}
    expected_notes = {}
    sequences_for_packages = {}
    for t in sequences.keys():
        t_dir = "%s/%s" % (archive, t)
        expected_contents = {}
        found_contents = {}

        for entry in os.listdir(t_dir):
            if entry == "Notes":
                # Don't complain about the notes directory
                continue
            if entry == "ChangeLog.txt":
                # Don't complain about the changelog (optional file)
                continue
            found_contents[entry] = True

        if debug:  print >> sys.stderr, "Directory entries for Train %s:  %s" % (t, found_contents.keys())
        # Go thorugh the manifest files for this train.
        # Load each manifest, and get the set of packages from it.
        # Figure out the path for each package, and update, and add
        # those to expected_packages.
        # Also verify that any notes exist in the right location.
        for sequence_file in sequences[t]:
            if sequence_file != "LATEST":
                mani_path = "%s/%s-%s" % (t_dir, project, sequence_file)
                expected_contents["%s-%s" % (project, sequence_file)] = True
            else:
                mani_path = "%s/%s" % (t_dir, sequence_file)
                expected_contents[sequence_file] = True

            if not os.path.isfile(mani_path):
                print >> sys.stderr, "Expected manifest file %s does not exist" % mani_path
                continue
                
            temp_mani = Manifest.Manifest()
            temp_mani.LoadPath(mani_path)

            for pkg in temp_mani.Packages():
                if pkg.FileName() in expected_packages:
                    if expected_packages[pkg.FileName()] != pkg.Checksum():
                        print >> sys.stderr, "Package %s, version %s, already found with different checksum" \
                            % (pkg.Name(), pkg.Version())
                        print >> sys.stderr, "Found again in sequence %s in train %s" % (sequence_file, t)
                        continue
                else:
                    expected_packages[pkg.FileName()] = pkg.Checksum()
                    if debug:  print >> sys.stderr, "%s/%s:  %s: %s" % (t, sequence_file, pkg.FileName(), pkg.Checksum())
                    pathname = os.path.join(archive, "Packages", pkg.FileName())
                    if not os.path.exists(pathname):
                        print >> sys.stderr, "Expected package file %s for %s %s does not exist" % (pathname, pkg.Name(), pkg.Version())
                if pkg.FileName() not in sequences_for_packages:
                    sequences_for_packages[pkg.FileName()] = []
                sequences_for_packages[pkg.FileName()].append(sequence_file)
                # Now check each of the updates for it.
                for upd in pkg.Updates():
                    o_vers = pkg.FileName(upd.Version())
                    o_sum = upd.Checksum()
                    if o_vers in expected_packages:
                        if expected_packages[o_vers] != o_sum:
                            print >> sys.stderr, "Package update %s %s->%s, already found with different checksum" \
                                % (pkg.Name(), upd.Version(), Pkg.Version())
                            print >> sys.stderr, "Found again in sequence %s in train %s" % (sequence_File, t)
                            continue
                    else:
                        expected_packages[o_vers] = o_sum
                        pathname = os.path.join(archive, "Packages", o_vers)
                        if not os.path.exists(pathname):
                            print >> sys.stderr, "Expected package update file %s for %s %s %s does not exist" % (pathname, pkg.Name(), upd.Version(), pkg.Version())
                            
                    if o_vers not in sequences_for_packages:
                        sequences_for_packages[o_vers] = []
                    sequences_for_packages[o_vers].append(sequence_file)
            if sequence_file != "LATEST":
                notes_dict = temp_mani.Notes(raw = True)
                for note in notes_dict:
                    if note == "NOTICE":
                        # Special case, not a file
                        continue
                    note_file = notes_dict[note]
                    if note_file in expected_notes:
                        print >> sys.stderr, "Note file %s already expected, this is confusing" % note_file
                        if debug:
                            print >> sys.stderr, "\tTrain %s, Sequence %s has the duplicate" % (temp_mani.Train(), temp_mani.Sequence())
                    expected_notes[note_file] = True
                    if debug:  print >> sys.stderr, "Found Note %s in Train %s Sequence %s" % (note_file, temp_mani.Train(), temp_mani.Sequence())

        # Now let's check the found_contents and expected_contents dictionaries
        if expected_contents != found_contents:
            print >> sys.stderr, "Sequences for train %s inconsistency found" % t
            if debug:
                print >> sys.stderr, "Expected:  %s" % expected_contents
                print >> sys.stderr, "Found   :  %s" % found_contents
            for seq in expected_contents.keys():
                if seq in found_contents:
                    found_contents.pop(seq)
                else:
                    print >> sys.stderr, "Expected sequence file %s not found in train %s" % (seq, t)
            for found in found_contents.keys():
                print >> sys.stderr, "Unexpected entry in train %s: %s" % (t, found)

    # Now we've got all of the package filenames, so let's start checking
    # the actual packages directory
    p_dir = "%s/Packages" % archive
    found_packages = {}
    for pkgEntry in os.listdir(p_dir):
        full_path = os.path.join(p_dir, pkgEntry)
        if not os.path.isfile(full_path):
            print >> sys.stderr, "Entry in Packages directory, %s, is not a file" % pkgEntry
            continue
        cksum = ChecksumFile(full_path)
        found_packages[pkgEntry] = cksum

    if expected_packages != found_packages:
        print >> sys.stderr, "Packages directory does not match expecations"
        for expected in expected_packages.keys():
            if expected in found_packages:
                if expected_packages[expected] != found_packages[expected]:
                    print >> sys.stderr, "Package %s has a different checksum than expected" % expected
                    if debug or verbose:
                        print >> sys.stderr, "\t%s (expected)\n\t%s (found)" % (expected_packages[expected], found_packages[expected])
                found_packages.pop(expected)
            else:
                # We don't need to print this out, since was printed above
                print >> sys.stderr, "Did not find expected package file %s" % expected
                print >> sys.stderr, "\tUsed in sequences %s" % sequences_for_packages[expected]
        for found in found_packages.keys():
            print >> sys.stderr, "Unexpected package file %s" % found

    # Now let's check the notes
    if found_notes != expected_notes:
        print >> sys.stderr, "Notes inconsistency"
#        if debug or verbose:
#            print >> sys.stderr, "Expected Notes: %s" % expected_notes
#            print >> sys.stderr, "Found Notes: %s" % found_notes
        for n in found_notes.keys():
            if n in expected_notes:
                expected_notes.pop(n)
                found_notes.pop(n)

        if len(found_notes) > 0:
            print "Unexpectedly found notes files:"
            for n in found_notes:  print "\t%s" % n
        if len(expected_notes) > 0:
            print "Missing notes files:"
            for n in expected_notes: print "\t%s" % n
            
def Dump(archive, db, project = "FreeNAS", args = []):
    """
    Dump out, in a somewhat human readable form, the releases.
    This principally dumps the sequences in temporal order.  
    If args has a -T <train> option (as determined by getopt), then
    it will only dump for that train.
    Current format is:
    <train> <sequence> <package> [...]
    """
    train = None
    short_options = "T:"
    long_options = [ "train=" ]
    try:
        opts, arguments = getopt.getopt(args, short_options, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)

    for o, a in opts:
        if o in ("-T", "--train"):
            train = a
        else:
            usage()

    # Now we get all the sequences
    sequences = db.RecentSequencesForTrain(train, count = 0, oldest_first = True)
    for seq in sequences:
        t = db.TrainForSequence(seq)
        # For each sequence, we need to get the package
        pkgs = db.PackageForSequence(seq)
        if pkgs is None:
            print >> sys.stderr, "Sequence %s has no packages?!" % seq
            continue
        output_line = "TRAIN=%s %s " % (t, seq)
        for pkg in pkgs:
            output_line += "%s-%s " % (pkg.Name(), pkg.Version())
        print output_line

    return 0

def Rebuild(archive, dbfile, project = "FreeNAS", key = None, args = []):
    """
    Given an archive, rebuild the database by examining the
    manifests.
    We start by looking for directories in $archive.
    We ignore the directory "Packages" in it.
    For each directory we find, we look for files (and
    exclude LATEST if it is a symlink).
    Then we process each manifest and add its entries to
    the database.
    The manifests are sorted based on their mtime, then
    based on the filename if the mtime is equal.
    """
    found_manifests = []
    pkg_directory = os.path.join(archive, "Packages")
    copy = None
    verify = False
    ifneeded = False
    
    long_options = [ "copy=", "verify", "ifneeded" ]
    try:
        opts, args = getopt.getopt(args, None, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        usage()

    for o, a in opts:
        if o in ("--copy"):
            copy = a
        elif o in ("--verify"):
            verify = True
        elif o in ("--ifneeded"):
            ifneeded = True
        else:
            usage()

    if verify and copy:
        print >> sys.stderr, "Only one of --verify or --copy is allowed"
        usage()

    try:
        db = SQLiteReleaseDB(dbfile = dbfile)
        if ifneeded:
            print >> sys.stderr, "Database rebuild not needed due to compatible versions"
            return
    except DatabaseIncompatibleVersionException:
        db = SQLiteReleaseDB(dbfile = dbfile, initialize = True)
        
    for train_name in os.listdir(archive):
        if train_name == "Packages":
            continue
        if os.path.isdir(os.path.join(archive, train_name)):
            for manifest_file in os.listdir(os.path.join(archive, train_name)):
                if manifest_file == "ChangeLog.txt":
                    continue
                mname = os.path.join(archive, train_name, manifest_file)
                if manifest_file == "LATEST" and os.path.islink(mname):
                    continue
                if os.path.isfile(mname):
                    found_manifests.append(mname)
    def my_sort(left, right):
        if os.stat(left).st_mtime < os.stat(right).st_mtime: return -1
        if os.stat(left).st_mtime > os.stat(right).st_mtime: return 1
        if left < right: return -1
        if left > right: return 1
        return 0
    sorted_manifests = sorted(found_manifests, cmp = my_sort)

    for manifest in sorted_manifests:
        # Process them somehow
        # This seems to duplicate a lot of ProcessRelease
        # so it should be abstracted so both can use it
        if debug or verbose:
            print >> sys.stderr, "Processing %s" % manifest
        m = Manifest.Manifest()
        try:
            m.LoadPath(manifest)
        except BaseException as e:
            print >> sys.stderr, "Got exception %s trying to load %s, skipping" % (str(e), manifest)
            continue
        
        pkg_list = []
        for pkg in m.Packages():
            import json
            # This handles copy and normal rebuild.  To verify, we would
            # need to get the checksums for the package file and any update files.
            if copy:
                svc_list_filename = os.path.join(source, pkg.Name(), pkg.Version(), "Services")
                try:
                    svc_list = json.load(open(svc_list_filename, "r"))
                except:
                    svc_list = {}
                lock = LockArchive(copy, "Copying package file %s-%s" % (pkg.Name(), pkg.Version()), wait = True)
                pkg = AddPackage(pkg, db, source = pkg_directory,
                                 archive = copy,
                                 train = m.Train(),
                                 restart_services = svc_list)
                lock.close()
            else:
                svc_list_filename = os.path.join(pkg_directory, pkg.Name(), pkg.Version(), "Services")
                print >> sys.stderr, "svc_list_filename = %s" % svc_list_filename
                try:
                    svc_list = json.load(open(svc_list_filename, "r"))
                    print >> sys.stderr, "\tsvc_list = %s" % svc_list
                except:
                    svc_list = {}
                pkg = AddPackage(pkg, db, source = None,
                                 archive = archive,
                                 train = m.Train(),
                                 restart_services = svc_list)

            pkg_list.append(pkg)

        m.SetPackages(pkg_list)
        if copy:
            # We need to save the manifest.
            # Since this may change the sequence, we
            # need to do this before updating the database.
            try:
                os.makedirs(os.path.join(copy, m.Train()))
            except:
                # Lazy, let it fail below
                pass
            flock = LockArchive(copy, "Saving Manifest File")
            name = m.Sequence()
            suffix = None
            while True:
                manifest_path = os.path.join(copy, m.Train(), "%s-%s" % (project, name))
                print >> sys.stderr, "%s" % manifest_path
                try:
                    manifest_file = open(manifest_path, "wxb", 0664)
                except OSError as e:
                    # Should compare manifests, perhaps
                    print >> sys.stderr, "Cannot open %s: %s" % (manifest_path, str(e))
                    if suffix is None:
                        suffix = 1
                    else:
                        suffix += 1
                    name = "%s-%d" % (m.Sequence(), suffix)
                    continue
                else:
                    break
            m.SetSequence(name)
            m.StoreFile(manifest_file)
            # And now set the symlink
            latest = os.path.join(copy, m.Train(), "LATEST")
            try:
                os.unlink(latest)
            except:
                pass
            os.symlink("%s-%s" % (project, m.Sequence()), latest)
            flock.close()

        try:
            db.AddRelease(m)
        except BaseException as e:
            print >> sys.stderr, "Processing %s (file %s), got exception %s" % (m.Sequence(), manifest, str(e))
            raise e
            continue
        if debug or verbose:
            print >> sys.stderr, "Done processing %s" % m.Sequence()

    return

def MakeLATEST(archive, project, train, sequence):
    """
    THE ARCHIVE MUST BE LOCKED BY THE CALLER.
    This creates the LATEST symlink; it's a convenience
    function so it can remove the old symlink if needed.
    """
    latest = os.path.join(archive, train, "LATEST")
    try:
        os.unlink(latest)
    except:
        pass
    os.symlink("%s-%s" % (project, sequence), latest)
    return

def RemovePackageUpdate(archive, db, pkg, base, dbonly = False, shlist = None):
    """
    Remove a package update from the database and archive.
    Note that we don't actually keep track of who uses an update, so all this will
    do is make any manifest files very sad.
    """
    try:
        db.PackageUpdatesDeleteUpdate(pkg, base)
    except BaseException as e:
        print >> sys.stderr, "Unable to delete %s %s->%s from db: %s" % (pkg.Name(), base, pkg.Version(), str(e))
        return
    
    if not dbonly:
        update_fname = os.path.join(archive, "Packages", pkg.FileName(base))
        try:
            os.remove(update_fname)
        except BaseException as e:
            print >> sys.stderr, "Could not remove %s due to %s" % (update_fname, str(e))
        if shlist is not None:
            shlist.append("rm -f %s" % update_fname)
            
def RemovePackage(archive, db, pkg, dbonly = False, shlist = None):
    """
    Remove a package from the database, and archive.
    Removing a package requires that nobody else reference the package,
    including updates.
    """
    releases = db.SequencesForPackage(pkg)
    if releases and len(releases):
        if debug or verbose:
            print >> sys.stderr, "Cannot delete package information for %s-%s because other sequences are using it (%s)" % (pkg.Name(), pkg.Version(), releases)
        return
    # Okay, no other sequences reference this package, so
    # we can delete it.  Maybe.  But we also need to delete any
    # update for this package, and any scripts for this package.
    # That's PackageUpdates and PackageDeltaScripts
    # For PackageUpdates, we want to delete any db entry that
    # has it as Pkg, and also any delta package files that
    # have it as the upgrade-to version.
    # *Then* we want to see if any PackageUpdates.PkgBase
    # refer to the package; if not, we can delete all of
    # the PackageUpdates entries that refer to it as PkgBase,
    # and we can also safely delete the package file and any
    # PackageDeltaScripts for the packge.  And then remove the
    # Packages db entries for the package.
    # (We can't remove the db entry for the package if there are
    # any updates that reference it, because we want it to show up
    # for delta package creation.)
    packages_dir = os.path.join(archive, "Packages")
    updates = db.UpdatesForPackage(pkg, count = 0)
    if updates:
        # We're going to delete the delta package files
        # that have this package as the new version
        if debug or verbose:
            print >> sys.stderr, "Deleting packages that update to %s-%s" % (pkg.Name(), pkg.Version())
        for (base, hash, rr) in updates:
            pkg_filename = os.path.join(packages_dir, pkg.FileName(base))
            try:
                if shlist:
                    shlist.append("rm %s" % pkg_filename)
                if not dbonly:
                    os.unlink(pkg_filename)
            except:
                pass
        db.PackageUpdatesDeletePkg(pkg)
                
    # Now we look for updates _from_ this version.
    updates = db.UpdatesFromPackage(pkg)
    if updates:
        print >> sys.stderr, "Doesn't look like we can delete package %s-%s entirely due to updates using it" % (pkg.Name(), pkg.Version())
    else:
        # Nothing to delete from PackageUpdates, so now we want to
        # delete the PackageDeltaScripts for this package.
        scripts = db.ScriptForPackage(pkg)
        # That gets us the names for the scripts; we want to remove them
        # from the filesystem in a bit.
        if len(scripts):
            if debug or verbose:
                print >> sys.stderr, "Deleting delta scripts for %s-%s" % (pkg.Name(), pkg.Version())
            db.ScriptsDeleteForPackage(pkg)
            # Now we remove it from the filesystem
            scripts_dir = os.path.join(archive, "Packages", pkg.Name(), pkg.Version())
            for (script_name, script_hash) in scripts:
                script_filename = os.path.join(scripts_dir, script_name)
                if debug or verbose:
                    print >> sys.stderr, "\tScript %s" % script_filename
                if shlist:
                    shlist.append("rm %s" % script_filename)
                try:
                    if not dbonly:
                        os.unlink(script_filename)
                except:
                    print >> sys.stderr, "Unable to delete delta script %s" % script_filename
                    continue
            # Now try to remove the directory
            if shlist:
                shlist.append("rmdir %s" % scripts_dir)
            try:
                if not dbonly:
                    os.rmdir(scripts_dir)
            except:
                print >> sys.stderr, "Unable to delete delta package script dir %s" % scripts_dir

        # And now we should be able to delete the package file itself
        pkg_filename = os.path.join(packages_dir, pkg.FileName())
        if debug or verbose:
            print >> sys.stderr, "Removing package file %s" % pkg_filename
        if shlist:
            shlist.append("rm %s" % pkg_filename)
        try:
            if not dbonly:
                os.unlink(pkg_filename)
        except:
            pass

#
# Need to figure out where to do this:
# SELECT Pkg.PkgName, Pkg.PkgVersion FROM Packages AS Pkg LEFT JOIN Manifests ON Pkg.indx = Manifests.Pkg WHERE Manifests.Pkg IS NULL;
# That will find any orphaned packages (packages that are in no manifest).
# Need to also ensure there are no updates to or from it, however.
#

def RemoveRelease(archive, db, project, sequence, dbonly = False, shlist = None):
    """
    THE ARCHIVE MUST BE LOCKED BY THE CALLER.
    Remove a given release, given its sequence.
    To remove a sequence, we first need to remove
    1:  ReleaseNotes
    2:  ReleaseNames (or not, not implemented yet apparently)
    3:  Notices
    4:  Manifests
    Before we remove it from Manifests, we want
    to get a list of packages used by this sequence.
    After we remove it from Manifests, we can then
    see if any other releases use those packages;
    any that don't, we can remove the package from
    the database (and the filesystem)
    Before we remove each package, however, we also
    need to see if there are updates for this package,
    so we can remove those (from the database and the
    filesystem).  When we remove each package, we also
    want to remove any script for that package.
    ("package" here refers to a specific version of each
    package, of course.  So foo-1234.)
    """
    train = db.TrainForSequence(sequence)
    if train is None:
        raise Exception("Could not find train for sequence %s" % sequence)
    
    pkgs = db.PackageForSequence(sequence)
    notes = db.NotesForSequence(sequence)
    # At this point, we want to remove the sequence from Manifests.
    if debug or verbose:
        print >> sys.stderr, "Deleting sequence %s from manifest table" % sequence
    db.ManifestDeleteSequence(sequence)
    # Next, let's go through the notes
    for note in notes:
        # note is the name of the note, and notes[note] is the path
        if debug or verbose:
            print >> sys.stderr, "Deleting note %s" % note
        # Well, it turns out the note file has a url in it.  Annoying.  Bug on my part
        # So let's get the filename part of it
        note_path_index = notes[note].find("/Notes/")
        if note_path_index:
            note_file = os.path.join(archive, train, notes[note][note_path_index+1:])
        else:
            note_file = os.path.join(archive, train, notes[note])
        try:
            if shlist is not None:
                shlist.append("rm %s" % note_file)
            if not dbonly:
                os.unlink(note_file)
        except:
            print >> sys.stderr, "Could not remove %s" % note_file
        db.NotesDeleteNoteFile(notes[note])

    if debug or verbose:
        print >> sys.stderr, "Deleting notice for sequence %s" % sequence    
    db.NoticesDeleteSequence(sequence)
    # Now we need to go through the packages
    for pkg in pkgs:
        # For each package, we need to see if this is the
        # only reference to it in Maifests
        # So let's see if any other sequences reference it.
        # Note that we still do, so we have to check for len > 1
        users = db.SequencesForPackage(pkg)
        if users and len(users):
            if len(users) > 1 or not (sequence in users):
                if debug or verbose:
                    print >> sys.stderr, "Cannot delete any package information for %s-%s because other sequences use it (%s)" % (pkg.Name(), pkg.Version(), users)
                continue
        # Okay, no other sequences reference this package, so
        # we can delete it.  Maybe.  But we also need to delete any
        # update for this package, and any scripts for this package.
        # That's PackageUpdates and PackageDeltaScripts
        # For PackageUpdates, we want to delete any db entry that
        # has it as Pkg, and also any delta package files that
        # have it as the upgrade-to version.
        # *Then* we want to see if any PackageUpdates.PkgBase
        # refer to the package; if not, we can delete all of
        # the PackageUpdates entries that refer to it as PkgBase,
        # and we can also safely delete the package file and any
        # PackageDeltaScripts for the packge.  And then remove the
        # Packages db entries for the package.
        # (We can't remove the db entry for the package if there are
        # any updates that reference it, because we want it to show up
        # for delta package creation.)
	packages_dir = os.path.join(archive, "Packages")
        updates = db.UpdatesForPackage(pkg, count = 0)
        if updates:
            # We're going to delete the delta package files
            # that have this package as the new version
            if debug or verbose:
                print >> sys.stderr, "Deleting packages that update to %s-%s" % (pkg.Name(), pkg.Version())
            for (base, hash, rr) in updates:
                pkg_filename = os.path.join(packages_dir, pkg.FileName(base))
                try:
                    if shlist is not None:
                        shlist.append("rm %s" % pkg_filename)
                    if not dbonly:
                        os.unlink(pkg_filename)
                except:
                    pass
            db.PackageUpdatesDeletePkg(pkg)
                
        # Now we look for updates _from_ this version.
        updates = db.UpdatesFromPackage(pkg)
        if updates:
            print >> sys.stderr, "Doesn't look like we can delete package %s-%s entirely" % (pkg.Name(), pkg.Version())
            continue
        # Next, remove any ServiceRestarts for this version of the package
        db.ServiceRestartDeleteForPackage(pkg)
        # Nothing to delete from PackageUpdates, so now we want to
        # delete the PackageDeltaScripts for this package.
        scripts = db.ScriptForPackage(pkg)
        # That gets us the names for the scripts; we want to remove them
        # from the filesystem in a bit.
        if scripts:
            if debug or verbose:
                print >> sys.stderr, "Deleting delta scripts for %s-%s" % (pkg.Name(), pkg.Version())
            db.ScriptsDeleteForPackage(pkg)
            # Now we remove it from the filesystem
            scripts_dir = os.path.join(archive, "Packages", pkg.Name(), pkg.Version())
            for script_name in scripts:
                script_filename = os.path.join(scripts_dir, script_name)
                if debug or verbose:
                    print >> sys.stderr, "\tScript %s" % script_filename
                try:
                    if shlist is not None:
                        shlist.append("rm %s" % script_filename)
                    if not dbonly:
                        os.unlink(script_filename)
                except:
                    print >> sys.stderr, "Unable to delete delta script %s" % script_filename
                    continue
            # Now try to remove the directory
            try:
                if shlist is not None:
                    shlist.append("rmdir %s" % scripts_dir)
                if not dbonly:
                    os.rmdir(scripts_dir)
            except:
                print >> sys.stderr, "Unable to delete delta package script dir %s" % scripts_dir

        # And now we should be able to delete the package file itself
        pkg_filename = os.path.join(packages_dir, pkg.FileName())
        if debug or verbose:
            print >> sys.stderr, "Removing package file %s" % pkg_filename
        try:
            if shlist is not None:
                shlist.append("rm %s" % pkg_filename)
            if not dbonly:
                os.unlink(pkg_filename)
        except:
            pass
    # And that ends the pkg loop
    # So now we delete the manifest file
    manifest_file = os.path.join(archive, train, "%s-%s" % (project, sequence))
    if verbose or debug:
        print >> sys.stderr, "Removing manifest file %s" % manifest_file
    try:
        if shlist is not None:
            shlist.append("rm %s" % manifest_file)
        if not dbonly:
            os.unlink(manifest_file)
    except:
        pass
    if debug or verbose:
        print >> sys.stderr, "Deleting sequence %s from database" % sequence
    db.DeleteSequence(sequence)
    print >> sys.stderr, "shlist = %s" % shlist
    return

def Delete(archive, db, project, args = []):
    """
    Remove the given releases from both the database and filesystem.
    """
    def func_usage():
        print >> sys.stderr, """
Usage: %s [args] delete sequence <sequence> [...] -- delete sequences
        -or-     delete package <pkg> <version> -- delete (if possible) packge version
        -or-     delete package <pkg> <base> <version> -- delete (if possible) package update base -> version
""" % sys.argv[0]
        usage()

    if args[0] == "sequence":
        for sequence in args[1:]:
            msg = "Removing sequence %s" % sequence
            lock = LockArchive(archive, msg, wait = True)
            if debug or verbose:
                print >> sys.stderr, msg
            RemoveRelease(archive, db, project, sequence)
            lock.close()
    elif args[0] == "package":
        if len(args) != 3 and len(args) != 4:
            func_usage()
        pkg_name = args[1]
        if len(args) == 3:
            # Delete a specific package
            pkg_version = args[2]
            pkg_base = None
        elif len(args) == 4:
            pkg_base = args[2]
            pkg_version = args[3]

        pkg = Package.Package(pkg_name, pkg_base)
        if pkg_base is None:
            RemovePackage(archive, db, pkg)
        else:
            RemovePackageUpdate(archive, db, pkg, pkg_base)
    else:
        func_usage()
        
def Prune(archive, db, project, args = []):
    """
    For the given train, prune the oldest releases.
    The train is given on the command line as an argument;
    -K / --keep tells it how many to keep (default is 10).
    """
    def func_usage():
        print >> sys.stderr, "Usage:  %s [args] prune [-K|--keep num] train" % sys.argv[0]
        usage()
        
    keep = 10
    short_options = "-K:"
    long_options = ["--keep="]
    train = None
    try:
        opts, arguments = getopt.getopt(args, short_options, long_options)
    except getopt.GetoptError as err:
        func_usage()

    for o, a in opts:
        if o in ("-K", "--keep"):
            keep = int(a)
        else:
            print >> sys.stderr, "Unknown option %s" % o
            func_usage()

    if len(arguments) != 1:
        func_usage()

    train = arguments[0]

    old_sequences = db.RecentSequencesForTrain(train, count = 0, oldest_first = True)
    if old_sequences is None:
        print >> sys.stderr, "Unknown train %s" % train
        return 1
    if len(old_sequences) <= keep:
        print >> sys.stderr, "Not enough sequences for train %s to prune (%d exist, want to keep %d)" % (train, len(old_sequences), keep)
        return 1

    for sequence in old_sequences[0:-keep]:
        msg = "Removing old sequence %s" % sequence
        lock = LockArchive(archive, msg, wait = True)
        if debug or verbose:
            print >> sys.stderr, msg
        RemoveRelease(archive, db, project, sequence)
        lock.close()
        
def Rollback(archive, db, project = "FreeNAS", args = []):
    """
    For the given train, roll back the most recent update.
    The train must be given as argument.  -C / --count to
    indicate how many to pop; default is 1.
    This will attempt to delete not only the sequence, but
    any packages and updates that were only used by it.
    It must lock the entire archive during the process as
    a result.
    """
    count = 1
    short_options = "C:"
    train = None
    long_options = ["--count=" ]
    try:
        opts, arguments = getopt.getopt(args, short_options, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, "Usage:  %s [args] rollback [-C|--count num] train" % sys.argv[0]
        print >> sys.stderr, str(err)
        usage()

    for o, a in opts:
        if o in ("-C", "--count"):
            count = int(a)
        else:
            print >> sys.stderr, "Unknown option %s" % o
            usage()
            
    if len(arguments) != 1:
        print >> sys.stderr, "rollback must have train name"
        usage()

    train = arguments[0]

    # First, lock the archive
    lock = LockArchive(archive, "Rolling back train %s" % train, wait = True)
    
    # Next, let's get the most recent count+1 sequences for the train
    sequences = db.RecentSequencesForTrain(train, count = count + 1)
    if sequences is None or len(sequences) == 0:
        print >> sys.stderr, "Unable to find sequences for train %s" % train
        lock.close()
        return 1

    # We want to delete all but the last one we got
    if len(sequences) <= count:
        # We're getting rid of all the releases that exist!
        last_sequence = None
        removed_sequences = sequences
    else:
        last_sequence = sequences[-1]
        removed_sequences = sequences[:-1]
        
    for sequence in removed_sequences:
        shlist = []
        RemoveRelease(archive, db, project, sequence, shlist = shlist)
        print >> sys.stderr, shlist
        
    # At this point, we need to either remove or remake the
    # LATEST symlink.
    latest = os.path.join(archive, train, "LATEST")
    try:
        os.path.remove(latest)
    except:
        pass
    if last_sequence:
        MakeLATEST(archive, project, train, last_sequence)
    lock.close()
    
    return

def Project(config_file, args = None):
    """
    Manipulate the configuration file config_file.
    This can be used to create an initial config file,
    or to alter an existing one.
    The usage is:
    project <project_name> <options>
    Op
    """
    def project_usage():
        print >> sys.stderr, """
Usage for project command:
\tproject <project_name> <options>
Options are:
\t--print\tPrint out the settings for the project
\t--archive <archive>\tLocation of archive for project
\t--database|--db <dbfile>\tLocation of database file
\t--key <keyfile>\tLocation of key file (for signing)
\t--delete\tDelete the project.

Use '${PROJECT}' in pathnames to specify the project name;
use an empty string to remove the key from the project settings.
Use no options to simply create a project using the default
values.
"""
        usage()
        
    propt = None
    long_options = ["archive=",
                    "database=",
                    "db=",
                    "key=",
                    "delete",
                    "print",
                    ]
    if len(args) == 0:
        project_usage()
    else:
        project = args[0]
        
    try:
        opts, args = getopt.getopt(args[1:], None, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        project_usage()

    arg_dict = {}
    del_project = None
    
    for o, a in opts:
        if o in ("--archive"):
            arg_dict[CONFIG_ARCHIVE_KEY] = a
        elif o in ("--db", "--database"):
            arg_dict[CONFIG_DBPATH_KEY] = a
        elif o in ("--key"):
            arg_dict[CONFIG_KEYFILE_KEY] = a
        elif o in ("--delete"):
            del_project = project
        elif o in ("--print"):
            propt = True
        else:
            project_usage()

    if del_project and (propt or len(arg_dict) > 0):
        print >> sys.stderr, "Do not set options and then delete the project at the same time"
        project_usage()

    if del_project:
        # Just do the work here
        import ConfigParser
        cfp = ConfigParser.RawConfigParser()
        try:
            fp = open(config_file, "r")
        except BaseException as e:
            print >> sys.stderr, "Cannot delete project %s because can't read config file %s: %s" % (project, config_file, str(e))
            return
        try:
            cfp.readfp(fp)
        except BaseException as e:
            print >> sys.stderr, "Could not delete project %s because could not parse config file %s: %s" % (project, config_file, str(e))
            return

        try:
            cfp.remove_section(project)
        except:
            pass

        try:
            fp = open(config_file, "w")
        except BaseException as e:
            print >> sys.stderr, "Could not delete project %s because could not open config file %s for writing: %s" % (project, config_file, str(e))
            return

        try:
            cfp.write(fp)
        except BaseException as e:
            print >> sys.stderr, "Could not write config file %s: %s" % (config_file, str(e))
            return
    else:
        if arg_dict or not propt:
            rv = SetConfiguration(config_file, project, arg_dict)
            if rv is False:
                print >> sys.stderr, "Unable to alter project %s in config file %s" % (project, config_file)

    if propt:
        # Print out things
        cdict = GetConfiguration(config_file, project)
        if cdict:
            for k, v in cdict.iteritems():
                # Better hope there are no quotes or escaped characters here...
                print "%s=\"%s\"" % (k, v)
    return

def Extract(archive, db, project = "FreeNAS", key = None, args = []):
    """
    This is used to extract a release from the archive.
    That is, for a given sequence, and a target, it will
    create the target directory, ${PROJECT}-MANIFEST,
    Packages directory, and various other files necessary
    (such as ReleaseNotes, ChangeLog (maybe?), upgrade
    scripts, and RESTART service-restart file.
    """
    def Extract_usage():
        print >> sys.stderr, "Usage:  %s extract [--full] [--dest dest] sequence" % sys.argv[0]
        usage()
        
    sequence = None
    dest = None
    full = False

    long_options = ["full",
                    "dest=",
                    ]

    try:
        opts, args = getopt.getopt(args, None, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        Extract_usage()

    for o, a in opts:
        if o in ("--full"):
            full = True
        elif o in ("--dest"):
            dest = a
        else:
            print >> sys.stderr, "Unknown option %s" % o
            Extract_usage()

    if len(args) != 1:
        print >> sys.stderr, "Incorrect number of arguments (%d)" % len(args)
        Extract_usage()

    sequence = args[0]
    

    # This allows "extract FreeNAS-9.3-Nightlies/LATEST" to work.
    if "/" in sequence:
        (train, sequence) = sequence.split("/")
        print >> sys.stderr, "train = %s, sequence = %s" % (train, sequence)
        if train is None or sequence is None:
            print >> sys.stderr, "Don't know how to handle %s" % args[0]
            sys.exit(1)
        manifest_file = os.path.join(archive, train, sequence)
    else:
        train = db.TrainForSequence(sequence)
        if train is None:
            print >> sys.stderr, "Sequence %s does not seem to exist" % sequence
            sys.exit(1)
        manifest_file = os.path.join(archive, train, project + "-" +  sequence)
    
    man = Manifest.Manifest()
    try:
        man.LoadPath(manifest_file)
    except BaseException as e:
        print >> sys.stderr, "Could not load manifest file %s: %s" % (manifest_file, str(e))
        sys.exit(1)

    pkgs = man.Packages()
    pkg_files = []
    update_scripts = {}
    svc_list = {}
    notes_dict = man.Notes(raw = True)
    notice = man.Notice()
    
    if notes_dict:
        for note, loc in notes_dict.iteritems():
            note_file = os.path.join(archive, train, "Notes", loc)
            try:
                notes_dict[note] = open(note_file).read()
            except:
                notes_dict.pop(note)
                
    for pkg in pkgs:
        pkg.SetUpdates(None)
        pkg_files.append(os.path.join(archive, "Packages", pkg.FileName()))
        scripts = db.ScriptForPackage(pkg)
        t = {}
        if scripts:
            for script_name in scripts:
                if script_name == "reboot":
                    t["reboot"] = "reboot"
                else:
                    script_path = os.path.join(archive, "Packages", pkg.Name(), pkg.Version(), script_name)
                    try:
                        script_contents = open(script_path).read()
                        t[script_name] = script_contents
                    except:
                        pass
        if t:
            update_scripts[pkg.Name()] = t
        svc_list_file = os.path.join(archive, "Paackages", pkg.Name(), pkg.Version(), "Services")
        if os.path.exists(svc_list_file):
            try:
                svc_json = json.load(open(svc_list_file))
                for k, v in svc_json.iteritems():
                    svc_list[k] = v
            except:
                pass
            
    man.SetPackages(pkgs)
    man.SetNotes(None)
    man.SetNotice(None)
    man.SignWithKey(key)
    
    if dest is None:
        dest = os.path.join("/tmp", man.Sequence())
        
    try:
        os.makedirs(os.path.join(dest, "Packages"))
    except BaseException as e:
        print >> sys.stderr, "Cannot create destination bundle directory %s" % dest
        sys.exit(1)
        
    for pkg_file in pkg_files:
        import shutil
        try:
            dst_file = os.path.basename(pkg_file)
            dst_file = os.path.join(dest, "Packages", dst_file)
            shutil.copy(pkg_file, dst_file)
        except BaseException as e:
            print >> sys.stderr, "Unable to copy package file %s: %s" % (os.path.basename(pkg_file), str(e))
            sys.exit(1)
            
    if notice:
        try:
            notice_path = os.path.join(dest, "NOTICE")
            open(notice_path, "w").write(notice)
        except BaseException as e:
            print >> sys.stderr, "Unable to write NOTICE file: %s" % str(e)
            sys.exit(1)

    if notes_dict:
        for note, contents in notes_dict.iteritems():
            try:
                note_path = os.path.join(dest, note)
                open(note_path, "w").write(contents)
            except BaseException as e:
                print >> sys.stderr, "Unable to write note file %s: %s" % (note, str(e))
                sys.exit(1)

    if svc_list:
        svcs = []
        for s, v in svc_list.iteritems():
            svcs.append("%s=%s" % s, v)
        try:
            svc_path = os.path.join(dest, "RESTART")
            open(svc_path, "w".write(" ".join(svcs)))
        except BaseException as e:
            print >> sys.stderr, "Unable to write RESTART file: %s" % str(e)
            sys.exit(1)
    
    if update_scripts:
        for pkg_name, d in update_scripts.iteritems():
            try:
                script_path = os.path.join(dest, "Packages", pkg_name)
                os.makedirs(script_path)
            except BaseException as e:
                print >> sys.stderr, "Unable to create script directory for package %s: %s" % (pkg_name, str(e))
                sys.exit(1)
                
            for n, s in d.iteritems():
                try:
                    p = os.path.join(script_path, n)
                    open(p, "w").write(s)
                except BaseException as e:
                    print >> sys.stderr, "Unable to create update script %s for package %s: %s" % (n, pkg_name, str(e))
                    sys.exit(1)
                    
    man.StorePath(os.path.join(dest, "%s-MANIFEST" % project))
    
def main():
    global debug, verbose
    # Variables set via getopt
    # It may be possible to have reasonable defaults for these.
    archive = None
    project_name = "FreeNAS"
    # Work on this
    Database = None
    # Signing support
    key_file = None
    key_data = None
    # Changelog
    changelog = None
    # Configuration file
    # Can be over-ridden
    if os.geteuid() == 0:
        config_file = CONFIG_FILE_SYSTEM
    else:
        config_file = CONFIG_FILE_USER
    # Locabl variables
    db = None

    options = "a:C:D:dK:P:v"
    long_options = ["archive=", "config=", "destination=",
                    "database=",
                    "key=",
                    "project=",
                    "changelog=",
                    "debug", "verbose",
                ]

    try:
        opts, args = getopt.getopt(sys.argv[1:], options, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        usage()

    for o, a in opts:
        if o in ('-a', '--archive', '--destination'):
            archive = a
        elif o in ('--database', '-D'):
            Database = a
        elif o in ('-d', '--debug'):
            debug += 1
        elif o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('-P', '--project'):
            # Not implemented yet, just laying the groundwork
            project_name = a
        elif o in ('-K', '--key'):
            key_file = a
        elif o in ('-C', '--changelog'):
            changelog = a
        elif o in ("--config"):
            config_file = a
        else:
            usage()

    # Now get any config settings
    cs = GetConfiguration(config_file, project_name)
    if cs:
        if CONFIG_ARCHIVE_KEY in cs and archive is None:
            archive = cs[CONFIG_ARCHIVE_KEY]
        if CONFIG_KEYFILE_KEY in cs and key_file is None:
            key_file = cs[CONFIG_KEYFILE_KEY]
        if CONFIG_DBPATH_KEY in cs and Database is None:
            Database = cs[CONFIG_DBPATH_KEY]
            
    if archive is None and args[0] != "project":
        print >> sys.stderr, "For now, archive directory must be specified"
        usage()

    if len(args) == 0:
        print >> sys.stderr, "No command specified"
        usage()

    cmd = args[0]
    args = args[1:]

    if Database and Database.startswith("sqlite:"):
        # Holdover from old implementations.
        Database = Database[len("sqlite:"):]
        
    if Database is not None:
        # rebuild may recreate the database, or it
        # may not depending on options.  So it gets
        # the filename; everything else gets the database
        # itself.
        if cmd != "rebuild":
            try:
                db = SQLiteReleaseDB(dbfile = Database)
            except BaseException as e:
                print >> sys.stderr, "Could not use database %s: %s" % (Database, str(e))
                sys.exit(1)

    if key_file and key_file != "/dev/null" and key_file != "":
        import OpenSSL.crypto as Crypto
        try:
            key_contents = open(key_file).read()
            key_data = Crypto.load_privatekey(Crypto.FILETYPE_PEM, key_contents)
        except:
            print >> sys.stderr, "Cannot open key file %s, aborting" % key_file
            sys.exit(1)

    if cmd == "add":
        if len(args) == 0:
            print >> sys.stderr, "No source directories specified"
            usage()
        for source in args:
            ProcessRelease(source, archive, db, project = project_name, key_data = key_data, changelog = changelog)
    elif cmd == "check":
        Check(archive, db, project = project_name)
    elif cmd == "rebuild":
        st = None
        if os.path.exists(Database):
            st = os.lstat(Database)
        Rebuild(archive, dbfile = Database, project = project_name, key = key_data, args = args)
        if st and os.path.exists(Database):
            # Change ownership/group
            st = os.lstat(Database)
            uid = st.st_uid
            gid = st.st_gid
            mode = st.st_mode
            try:
                os.lchmod(Database, mode)
            except:
                pass
            try:
                os.lchown(Database, uid, gid)
            except:
                pass
    elif cmd == "dump":
        Dump(archive, db, args = args)
    elif cmd == "rollback":
        Rollback(archive, db, project = project_name, args = args)
        db.close()
    elif cmd == "prune":
        Prune(archive, db, project = project_name, args = args)
    elif cmd == "delete":
        Delete(archive, db, project = project_name, args = args)
    elif cmd == "extract":
        Extract(archive, db, project = project_name, key = key_data, args = args)
    elif cmd == "project":
        Project(config_file, args = args)
    else:
        print >> sys.stderr, "Unknown command %s" % cmd
        usage()

if __name__ == "__main__":
    main()
