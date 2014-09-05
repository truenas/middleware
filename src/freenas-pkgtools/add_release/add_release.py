import os
import sys
import getopt

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
verbose = 0


class ReleaseDB(object):
    """
    A class for manipulating the release database.
    A release consists of a train, sequence number, optional friendly name,
    optional release notes (preferrably URLs), and a set of packages.
    The sequence number is unique.
    """
    global debug, verbose

    def __init__(self, use_transactions = False):
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

    def AddRelease(self, sequence, train, packages, name = None, notes = None):
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

    def RecentSequencesForTrain(self, train, count = 5):
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

    def UpdatesForPackage(self, Pkg, count = 5):
        """
        Return an array of updates for the given package.
        If count is 0, it returns all known updates.
        The return objects are tuples of (version, checksum).
        checksum may be None.
        """
        return []

class PyReleaseDB(ReleaseDB):
    """
    Database as a json file.
    __init__ loads the json file and converts it to
    a python object; close writes it out.
    The layout of the object is:
    PACKAGES_KEY:	Dictionary, key is package name.
			Value is an array of tuples.  Item 0 is the version;
    			item 1 is a dictionary, with the keys being:
			CHECKSUM_KEY	-- checksum for this package version
			UPDATES_KEY	-- An array of tuples, item 0 being
					version, and item 1 being a checksum
					(may be None)
    SEQUENCES_KEY:	An array of sequences.  Each element is a tuple,
			with item 0 being the sequence name, and item 1 being
			a dictionary.  The keys are:
			PACKAGES_KEY	-- An array of packages.  Each package
    					is a tuple (PackageName, Package Version)
					that references the PACKAGES_KEY for the
    					db object.
			RELNAME_KEY	-- A string indicating the release name.
			RELNOTES_KEY	-- An array of unknown at this time.
			TRAINS_KEY	-- The name of the train for this sequence.
    TRAINS_KEY:		A dictionary.  Key is the name of the train,
			value is an array of sequences.
    
    """
    global debug, verbose
    PACKAGES_KEY = "kPackages"
    SEQUENCES_KEY = "kSequences"
    RELNAME_KEY = "kReleaseName"
    RELNOTES_KEY = "kReleaseNotes"
    CHECKSUM_KEY = "kChecksum"
    TRAINS_KEY = "kTrains"
    UPDATES_KEY = "kUpdates"

    def __init__(self, use_transactions = False, dbfile = None):
        import json

        super(PyReleaseDB, self).__init__(use_transactions)
        self._dbfile = dbfile
        try:
            with open(self._dbfile, "r") as f:
                self._db = json.load(f)
        except:
            # Just assume an empty database for now
            self._db = {}

    def commit(self):
        # Write the file out
        import json

        if debug: print >> sys.stderr, "PYReleaseDB::commit"
        with open(self._dbfile, "w") as f:
            json.dump(self._db, f, sort_keys=True,
                      indent=4, separators=(',', ': '))

    def close(self):
        # Just write it out.
        self.commit()

    def abort(self):
        # Reload the object
        self._db = {}
        try:
            with open(self._dbfile, "r") as f:
                self._db = json.load(f)
        except:
            pass

    def _sequences(self):
        if self.SEQUENCES_KEY not in self._db:
            self._db[self.SEQUENCES_KEY] = []
        return self._db[self.SEQUENCES_KEY]

    def _packages(self):
        if self.PACKAGES_KEY not in self._db:
            self._db[self.PACKAGES_KEY] = {}
        return self._db[self.PACKAGES_KEY]

    def _trains(self):
        if self.TRAINS_KEY not in self._db:
            self._db[self.TRAINS_KEY] = {}
        return self._db[self.TRAINS_KEY]

    def _find_sequence(self, sequence):
        seqs = self._sequences()
        for s in seqs:
            if s == sequence:
                return s
        return None

    def AddRelease(self, sequence, train, packages, name = None, notes = None):
        # Add the sequence, train, packages, name

        if self._find_sequence(sequence):
            raise Exception("Duplicate sequence %s" % sequence)
        pkg_list = []
        for pkg in packages:
            # See if this package/version is in the db's package list.
            pkgs = self._packages()
            if pkg.Name() not in pkgs:
                pkgs[pkg.Name()] = []
            
            version_array = pkgs[pkg.Name()]
            if pkg.Version() not in version_array:
                version_array.append(
                    (
                        pkg.Version(),
                        {
                            self.CHECKSUM_KEY : pkg.Checksum(),
                            self.UPDATES_KEY : [],
                        }
                        )
                    )
                pkg_list.append((pkg.Name(), pkg.Version()))
        # Now add pkg_list to the list of sequences
        elem = (
            sequence,
            {
                self.PACKAGES_KEY : pkg_list,
                self.RELNAME_KEY : name,
                self.RELNOTES_KEY : [],
                self.TRAINS_KEY : train,
            }
        )
        self._sequences().append(elem)
        if train not in self._trains():
            self._trains()[train] = []
        self._trains()[train].append(sequence)
        self.commit()

    def PackageForSequence(self, sequence, name = None):
        """
        For a given sequence, return the packages for it.
        If name is None, then return all of the packages
        for that sequence.
        The return objects are Package objects
        """
        rv = []
        for seq in self._sequences():
            if seq[0] == sequence:
                break
        for pkg in seq[1][self.PACKAGES_KEY]:
            if name is None or name == pkg[0]:
                (n, v) = pkg
                rv.append(self._find_package(n, v))
                if name: break

        if rv and name:
            return rv[0]
        return rv

    def TrainForSequence(self, sequence):
        """
        Return the name of the train for a given sequence.
        """
        for seq in self._sequences():
            if seq[0] == sequence:
                return seq[1][self.TRAINS_KEY]

    def RecentSequencesForTrain(self, train, count = 5):
        """
        Get the count-most recent sequences for a given train
        """
        if debug:  print >> sys.stderr, "RecentSequencesForTrain(%s, %d)" % (train, count)
        rv = []
        if debug:  print >> sys.stderr, "\ttarins = %s" % self._trains()
        if train in self._trains():
            sequences = self._trains()[train]
            if debug:  print >> sys.stderr, "\tsequences = %s" % sequences
            rev_sequences = sequences[::-1]
            if rev_sequences:
                rv = rev_sequences[0:count]
        if debug: print >> sys.stderr, "\trv = %s" % rv
        return rv

    def AddPackageUpdate(self, Pkg, OldVersion, DeltaChecksum = None):
        """
        Add an update for Pkg.
        """
        pkg_array = self._packages()[Pkg.Name()]
        for p in pkg_array:
            if p[0] == Pkg.Version():
                p_dict = p[1]
                updates = p_dict[self.UPDATES_KEY]
                updates.append((OldVersion, DeltaChecksum))
                self.commit()
                return
        raise Exception("Should not have reached this point")

    def UpdatesForPackage(self, Pkg, count = 5):
        """
        Return an array of updates for the package, most
        recent first
        """
        p_array = self._packages()[Pkg.Name()]
        for p in p_array:
            if p[0] == Pkg.Version():
                rv = []
                for upd in p[1][UPDATES_KEY]:
                    rv.append((upd[0], upd[1]))
                if count == 0:
                    return rv
                else:
                    return rv[0 : count]
        return []

    def _find_package(self, name, version):
        pkg = self._packages()[name]
        for p in pkg:
            if p[0] == version:
                P = Package.Package(name, version, p[1][self.CHECKSUM_KEY])
                for upd in p[1][self.UPDATES_KEY]:
                    P.AddUpdate(upd[0], upd[1])
                return P

class FSReleaseDB(ReleaseDB):
    """
    Filesystem as database.
    This is a dumb idea, it's mainly because it's fairly simple,
    light-weight, and quick.
    Too quick, in fact, since the normal unix file time resolution
    is 1 second, and that makes it not possible to determine order
    properly.
    """

    global debug, verbose

    def SafeMakedir(self, path, mode = 0755):
        """
        Make a directory.  Returns True if it can,
        or if it already exists; False if it can't.
        """
        import errno
        try:
            os.makedirs(path, mode)
        except OSError as e:
            if e.errno == errno.EEXIST:
                return True
            return False
        return True

    def __init__(self, use_transactions = False, dbpath = None):
        super(FSReleaseDB, self).__init__(use_transactions)
        if self.SafeMakedir(dbpath) is False:
            raise Exception("Cannot create database path %s" % dbpath)
        self._dbpath = dbpath
        if not self.SafeMakedir("%s/packages" % dbpath):
            raise Exception("Cannot create database path %s/packages" % dbpath)
        if not self.SafeMakedir("%s/sequences" % dbpath):
            raise Exception("Cannot create database path %s/sequences" % dbpath)

    def AddRelease(self, sequence, train, packages, name = None, notes = None):
        """
        Add the release into the database:
        Create a directory _dbpath/$train (okay if already exists)
        Create a directory _dbpath/$train/$sequence (cannot already exist)
        Soft link _dbpath/$train/$sequence -> _dbpath/sequences/$sequence (cannot already exist)
        Create directories _dbpath/packages/$package_name (okay if already exists)
        Create a file _dbpath/packages/$package_name/$package_version (okay if already exists)
        Write the checksum for the package file into that.
        Soft link _dbpath/pckages/$package_name/$package_version -> _dbpath/$train/$sequence/$package_name
        """

        if debug: print >> sys.stderr, "FSReleaseDB::AddRelease(%s, %s, %s, %s, %s)" % (sequence, train, packages, name, notes)
        if not self.SafeMakedir("%s/%s" % (self._dbpath, train)):
            raise Exception("Cannot create database path %s/%s" % (self._dbpath, train))
        os.makedirs("%s/%s/%s" % (self._dbpath, train, sequence))
        os.symlink("../%s/%s" % (train, sequence),
                   "%s/sequences/%s" % (self._dbpath, sequence))
        for pkg in packages:
            if not self.SafeMakedir("%s/packages/%s" % (self._dbpath, pkg.Name())):
                raise Exception("Cannot create database path %s/packages/%s" % (self._dbpath, pkg.Name()))
            if not os.path.exists("%s/packages/%s/%s" % (self._dbpath, pkg.Name(), pkg.Version())):
                with open("%s/packages/%s/%s" % (self._dbpath, pkg.Name(), pkg.Version()), "w") as f:
                    if pkg.Checksum():
                        f.write(pkg.Checksum())
            os.symlink("../../packages/%s/%s" % (pkg.Name(), pkg.Version()),
                       "%s/%s/%s/%s" % (self._dbpath, train, sequence, pkg.Name()))

    def PackageForSequence(self, sequence, name = None):
        """
        For a given sequence, return the package for it.
        If name is none, return all of the packages for that
        sequence.
        We do this by opening _dbpath/sequences/$sequence,
        and os.listdirs if name is None
        """
        if debug:  print >> sys.stderr, "FSReleaseDB::PackageForSequence(%s, %s)" % (sequence, name)
        sdir = "%s/sequences/%s" % (self._dbpath, sequence)
        if name:
            pkgs = (name,)
        else:
            pkgs = os.listdir(sdir)
        rv = []
        for pkg in pkgs:
            # sdir/pkg is a symlink to the package version.
            # The contents, if any, are a checksum
            if debug:  print >> sys.stderr, "FSReleaseDB::PackageForSequence(%s, %s):  pkg = %s" % (sequence, name, pkg)
            pkgfile = sdir + "/" + pkg
            pkg_version = os.path.basename(os.readlink(pkgfile))
            if debug:  print >> sys.stderr, "\tpkgfile = %s, pkg_version = %s" % (pkgfile, pkg_version)
            with open(pkgfile, "r") as f:
                cksum = f.read()
                if not cksum:
                    cksum = None
            P = Package.Package(pkg, pkg_version, cksum)
            if debug:  print >> sys.stderr, "\tP = %s-%s" % (P.Name(), P.Version())
            rv.append(P)
        if name:
            if len(rv) != 1:
                raise Exception("Too many results:  %s" % rv)
            return rv[0]
        return rv

    def TrainForSequence(self, sequence):
        """
        Return the name of the train for a given sequence.
        This is _dbpath/sequences/$sequence, which
        has ../%s/%s, so we'll break it by "/", and
        use the middle component.
        """
        buf = os.readlink("%s/sequences/%s" % (self._dbpath, sequence))
        comps = buf.split("/")
        return comps[1]

    def RecentSequencesForTrain(self, train, count = 5):
        """
        Get the most recent sequences for the given train.
        """
        import operator
        import errno
        train_path = "%s/%s" % (self._dbpath, train)
        # To sort this, we have to go by ctime.
        sequences = {}
        try:
            for s in os.listdir(train_path):
                sequences[s] = os.lstat("%s/%s" % (train_path, s)).st_ctime
        except OSError as e:
            if e.errno == errno.ENOENT:
                return []
            else:
                raise e
        sorted_sequences = sorted(sequences.iteritems(),
                                  key = operator.itemgetter(1))[::-1]
        rv = []
        for s, t in sorted_sequences:
            rv.append(s)
        return rv

    def AddPackageUpdate(self, Pkg, OldVersion, DeltaChecksum = None):
        """
        Note the existence of a delta update from OldVersion to Pkg.Version.
        With FSReleaseDB, we do this by creating a file
        _dbpath/packages/$package/Updates/$Pkg.Version()/$OldVersion, with the
        contents being DeltaChecksum.
        """
        dirname = "%s/packages/%s/Updates/%s" % (self._dbpath, Pkg.Name(), Pkg.Version())
        if not self.SafeMakedir(dirname):
            raise Exception("Could not create database directory %s" % dirname)
        ufile = "%s/%s" % (dirname, OldVersion)
        if not os.path.exists(ufile):
            with open(ufile, "w") as f:
                if DeltaChecksum:
                    f.write(DeltaChecksum)

    def UpdatesForPackage(self, Pkg, count = 5):
        # Return an array of package update for Pkg.
        import errno
        import operator

        dirname = "%s/packages/%s/Updates/%s" % (self._dbpath, Pkg.Name(), Pkg.Version())
        updates = {}
        try:
            for entry in os.listdir(dirname):
                updates[entry] = os.lstat("%s/%s" % (dirname, entry)).st_ctime
        except OSError as e:
            if e.errno == errno.ENOENT:
                return []
            else:
                raise e
        sorted_updates = sorted(updates.iteritems(),
                                key = operator.itemgetter(1))[::-1]

        rv = []
        for u, t in sorted_updates:
            with open("%s/%s" % (dirname, u), "r") as f:
                cksum = f.read()
                if not cksum:
                    cksum = None
                rv.append((u, cksum))
        if count == 0 or len(rv) == 0:
            return rv
        else:
            return rv[0 : count]

class SQLiteReleaseDB(ReleaseDB):
    """
    SQLite subclass for ReleaseDB
    """
    global debug, verbose

    def __init__(self, use_transactions = False, dbfile = None):
        global debug
        import sqlite3
        if dbfile is None:
            raise Exception("dbfile must be specified")
        super(SQLiteReleaseDB, self).__init__(use_transactions)
        self._dbfile = dbfile
        self._connection = sqlite3.connect(self._dbfile)
        if self._connection is None:
            raise Exception("Could not connect to sqlie db file %s" % dbfile)
        self._connection.text_factory = str
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()
        self._cursor.execute("PRAGMA foreign_keys = ON")

        # The Packages table consists of the package names, package version, optional checksum.
        # The indx value is used to determine which versions are newer, and also as a foreign
        # key to create the Releases table below.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Packages(PkgName TEXT NOT NULL, PkgVersion TEXT NOT NULL, Checksum TEXT, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT pkg_constraint UNIQUE (PkgName, PkgVersion) ON CONFLICT IGNORE)")

        # The Trains table consists solely of the train name, a sequence value,
        # and an indx value to determine which ones are newer.  Sequence is used as a foreign key
        # in several other tables.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Trains(TrainName TEXT NOT NULL, Sequence TEXT NOT NULL UNIQUE, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT)")

        # The ReleaseNotes table consists of notes, and which sequences use them.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS ReleaseNotes(Note TEXT NOT NULL, Sequence TEXT NOT NULL, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT relnote_constraint FOREIGN KEY(Sequence) REFERENCES Trains(Sequence))")

        # The ReleaseNames table consists of release names, and which sequences use them.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS ReleaseNames(Name TEXT NOT NULL, Sequence TEXT NOT NULL UNIQUE, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT relname_constrant FOREIGN KEY(Sequence) REFERENCES Trains(Sequence))")

        # The Releases table.
        # Releases consists of a reference to an entry in Trains for thesequence number,
        # and a package reference.
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Releases(Sequence NOT NULL, Pkg NOT NULL, indx INTEGER PRIMARY KEY ASC AUTOINCREMENT, CONSTRAINT releases_seq_constraint FOREIGN KEY(Sequence) REFERENCES Trains(Sequence), CONSTRAINT releases_pkg_constraint FOREIGN KEY(Pkg) REFERENCES Packages(indx))")

        # A table for keeping track of delta packages.
        # We ignore duplicates, but this could be a problem
        # if the checksum is different.  So revisit this.
        self._cursor.execute("""
        CREATE TABLE IF NOT EXISTS PackageUpdates(Pkg NOT NULL,
        	PkgBase NOT NULL,
		Checksum TEXT,
		indx INTEGER PRIMARY KEY ASC AUTOINCREMENT,
		CONSTRAINT pkg_update_key FOREIGN KEY (Pkg) REFERENCES Packages(indx),
		CONSTRAINT pkg_update_base_key FOREIGN KEY (PkgBase) REFERENCES Packages(indx),
		CONSTRAINT pkg_update_constraint UNIQUE (Pkg, PkgBase) ON CONFLICT IGNORE)
        """)

        self.commit()
        self._in_transaction = False

    def commit(self):
        if self._cursor:
            self._connection.commit()
            self._in_transaction = False
            self._cursor = self._connection.cursor()
            
    def cursor(self):
        if self._cursor is None:
            print >> sys.stderr, "Cursor was none, so getting a new one"
            self._cursor = self._connection.cursor()
        return self._cursor

    def abort(self):
        if self._in_transaction:
            if self._cursor:
                self._cursor.execute("ROLLBACK")
            self._in_transaction = False
        self._cursor = None

    def close(self, commit = True):
        if commit:
            self.commit()
        if self._connection:
            self._cursor = None
            self._connection.close()
            self._connection = None

    def AddRelease(self, sequence, train, packages, name = None, notes = None):
        """
        Add the release into the database.  This inserts values into
        the Releases, Packages, Trains, and ReleaseNotes tables, as appropriate.
        """

        if self._use_transactions:
            self.cursor().execute("BEGIN")
            self._in_transaction = True


        # First get the sequence into the Trains database
        self.cursor().execute("INSERT INTO Trains(TrainName, Sequence) VALUES(?, ?)", (train, sequence))

        # Next, the packages.
        for pkg in packages:
            # First put the package into the database.
            # Note that we created the table with ON CONFLICT IGNORE;
            # without that, we would have to see if the <Name, Version> tuple
            # existed in the database first.
            self.cursor().execute("INSERT INTO Packages(PkgName, PkgVersion, Checksum) VALUES(?, ?, ?)",
                                  (pkg.Name(), pkg.Version(), pkg.Checksum()))

            self.cursor().execute("""
            INSERT INTO Releases(Sequence, Pkg)
            SELECT Trains.Sequence, Packages.indx
            FROM Trains JOIN Packages
            WHERE Trains.Sequence = ?
            AND (Packages.PkgName = ? AND Packages.PkgVersion = ?)
            """, (sequence, pkg.Name(), pkg.Version()))

            
        if notes:
            if isinstance(notes, basestring):
                t_notes = [notes]
            else:
                t_notes = notes
            for n in notes:
                self.cursor().execute("""
                INSERT INTO ReleaseNotes(Sequence, Note)
                SELECT Sequence, ?
                FROM Trains
                WHERE Sequence = ?
                """, (n, sequence))

        if name:
            self.cursor().execute("""
            INSERT INTO ReleaseNames(Name, Sequence)
            SELECT ?, Sequence
            FROM Trains
            WHERE Sequence = ?
            """, (name, sequence))

        self.commit()

    def PackageForSequence(self, sequence, name = None):
        """
        For a given sequence, return the package for it.
        If name is None, then return all the packages for
        that sequence.

        """

        sql = """
        SELECT PkgName, PkgVersion, Checksum
        FROM Releases
        JOIN Packages
        WHERE Releases.Sequence = ?
        AND Releases.Pkg = Packages.indx
        %s
        ORDER BY Packages.indx ASC
        """ % ("AND Packages.PkgName = ?" if name else "")

        if name:
            parms = (sequence, name)
        else:
            parms = (sequence,)

        if debug:  print >> sys.stderr, "sql = `%s', parms = `%s'" % (sql, parms)
        self.cursor().execute(sql, parms)
        packages = self.cursor().fetchall()
        rv = []
        for pkg in packages:
            if debug:  print >> sys.stderr, "Found package %s-%s" % (pkg['PkgName'], pkg['PkgVersion'])
            p = Package.Package(pkg["PkgName"], pkg["PkgVersion"], None)
            rv.append(p)
        if name:
            if len(rv) != 1:
                raise Exception("Too many results: %s" % rv)
            return rv[0]
        return rv

    def TrainForSequence(self, sequence):
        """
        Return the name of the train for the given sequence.
        """
        self.cursor().execute("SELECT Train FROM Releases WHERE Sequence = ? ORDER BY indx", (sequence,))
        seq = self.cursor().fetchone()
        if seq is None:
            return None
        return seq["Train"]

    def RecentSequencesForTrain(self, train, count = 5):
        """
        Get the most recent (ordered by indx desc, limit count)
        sequences for the given train.
        """
        if debug:  print >> sys.stderr, "SQLiteReleaseDB::RecentSequencesForTrain(%s, %d)" % (train, count)
        sql = "SELECT Sequence FROM Trains WHERE TrainName = ? ORDER BY indx DESC LIMIT ?"
        if debug:  print >> sys.stderr, "\tsql = %s" % sql
        self.cursor().execute(sql, (train, count))
        rv = []
        for entry in self.cursor():
            if debug:  print >> sys.stderr, "\t%s" % entry['Sequence']
            rv.append( entry['Sequence'] )

        return rv

    def AddPackageUpdate(self, Pkg, OldVersion, DeltaChecksum = None):
        import pdb
        global debug

        if debug:  print >> sys.stderr, "SQLiteReleaseDB:AddPackageUpdate(%s, %s, %s, %s)" % (Pkg.Name(), Pkg.Version(), OldVersion, DeltaChecksum)

        sql = """
        INSERT INTO PackageUpdates(Pkg, PkgBase, Checksum)
        SELECT New.indx, Old.indx, ?
        FROM Packages as New
        JOIN Packages as Old
        WHERE New.PkgName = ? AND New.PkgName = Old.PkgName
        AND New.PkgVersion = ?
        AND Old.PkgVersion = ?
        """
        parms = (DeltaChecksum, Pkg.Name(), Pkg.Version(), OldVersion)
        if debug:
            print >> sys.stderr, "sql = %s, parms = %s" % (sql, parms)

        self.cursor().execute(sql, parms)
        self.commit()
        if debug:
            x = self.UpdatesForPackage(Pkg, 1)
            print >> sys.stderr, "x = %s" % x

    def UpdatesForPackage(self, Pkg, count = 5):
        # Return an array of package updates for Pkg.
        # That is, entries in the Updates table where
        # Pkg is the new version, it returns the PkgBase
        # and Checksum fields.
        sql = """
        SELECT PackageUpdates.PkgOldVersion AS PkgOldVersion, PackageUpdates.Checksum AS Checksum
        FROM PackageUpdates
        JOIN Packages
        WHERE PackageUpdates.Pkg = Packages.indx
        AND Packages.PkgName = ?
        AND Packages.PkgVersion = ?
        ORDER BY PackageUpdates.indx DESC
        """
        sql = """
        SELECT Packages.PkgVersion AS PkgOldVersion, PackageUpdates.Checksum AS Checksum
        FROM PackageUpdates
        JOIN Packages
        WHERE PackageUpdates.PkgBase = Packages.indx
        AND Packages.PkgName = ?
        AND Packages.PkgVersion = ?
        ORDER By PackageUpdates.indx DESC
        """
        parms = (Pkg.Name(), Pkg.Version())
        
        if count:
            sql += "LIMIT ?"
            parms += (count,)
        if debug:  print >> sys.stderr, "sql = %s, parms = %s" % (sql, parms)
        self.cursor().execute(sql, parms)
        rows = self.cursor().fetchall()
        rv = []
        for pkgRow in rows:
            if debug:  print >> sys.stderr, "Found Update %s for package %s-%s" % (pkgRow["PkgOldVersion"], Pkg.Name(), Pkg.Version())
            p = ( pkgRow['PkgOldVersion'] ,  pkgRow['Checksum'] )
            rv.append(p)
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
    print >> sys.stderr,"Usage: %s [--database|-D db] [--debug|-d] [--verbose|-v] --output|--destination|-o dest_directory input_dir [...]" % sys.argv[0]
    sys.exit(1)

def Process(source, archive, db = None, sign = False):
    """
    Process a directory containing the output from a freenas build.
    We're looking for source/FreeNAS-MANIFEST, which will tell us
    what the contents are.
    """
    global debug, verbose

    if debug:  print >> sys.stderr, "Process(%s, %s, %s, %s)" % (source, archive, db, sign)

    if db is None:
        raise Exception("Invalid db")

    pkg_source_dir = "%s/Packages" % source
    pkg_dest_dir = "%s/Packages" % archive

    if not os.path.isdir(pkg_source_dir):
        raise Exception("Source package directory %s is not a directory!" % pkg_source_dir)
    if not os.path.isdir(pkg_dest_dir):
        raise Exception("Archive package directory %s is not a directory!" % pkg_dest_dir)

    manifest = Manifest.Manifest()
    if manifest is None:
        raise Exception("Could not create a manifest object")
    manifest.LoadPath(source + "/FreeNAS-MANIFEST")

    # Okay, let's see if this train has any prior entries in the database
    previous_sequences = db.RecentSequencesForTrain(manifest.Train())

    pkg_list = []
    for pkg in manifest.Packages():
        if verbose or debug:
            print "Package %s, version %s, filename %s" % (pkg.Name(), pkg.Version(), pkg.FileName())

        pkg_path = "%s/%s" % (pkg_source_dir, pkg.FileName())
        hash = ChecksumFile(pkg_path)
        if debug:  print >> sys.stderr, "%s (computed)\n%s (manifest)" % (hash, pkg.Checksum())
        if hash is None:
            raise Exception("Could not compute hash on package file %s" % pkg_path)
        if hash != pkg.Checksum():
            raise Exception("Computed hash on package %s-%s does not match manifest hash" % (pkg.Name(), pkg.Version()))
        # Okay, the checksums match.
        # Let's see if a package with this version already exists in the destination.
        pkg_dest = "%s/%s" % (pkg_dest_dir, pkg.FileName())
        if os.path.exists(pkg_dest):
            # Okay, let's see if the hash is the same
            hash = ChecksumFile(pkg_dest)
            if hash is None or hash != pkg.Checksum():
                print >> sys.stderr, "A file exists for package %s-%s in the archive, but the checksum doesn't match" % (pkg.Name(), pkg.Version())
                raise Exception("Unsure what to do")
            else:
                if verbose or debug:
                    print >> sys.stderr, "Package %s-%s already exists in the destination, so not copying" % (pkg.Name(), pkg.Version())
        else:
            import shutil
            shutil.copyfile(pkg_path, pkg_dest)
            if verbose or debug:
                print >> sys.stderr, "Package %s-%s copied to archive" % (pkg.Name(), pkg.Version())

        # This is where we'd want to go through old versions and see if we can create any delta pachages
        for older in previous_sequences:
            # Given this sequence, let's look up the package for it
            # Note that for us to have any entries, we must have a valid db.
            old_pkg = db.PackageForSequence(older, pkg.Name())
            if old_pkg:
                if old_pkg.Version() == pkg.Version():
                    # Nothing to do
                    continue
                # We would want to create a delta package
                pkg1 = "%s/Packages/%s" % (archive, old_pkg.FileName())
                pkg2 = "%s/Packages/%s" % (archive, pkg.FileName())
                delta_pkg = "%s/Packages/%s" % (archive, pkg.FileName(old_pkg.Version()))
                # If the delta package exists, let's just trust it,
                # since creating delta packages is very time-consuming.
                if not os.path.exists(delta_pkg):
                    x = PackageFile.DiffPackageFiles(pkg1, pkg2, delta_pkg)
                    if x is None:
                        if debug or verbose:
                            print >> sys.stderr, "%s:  no diffs between versions %s and %s" % (
                                pkg.Name(), old_pkg.Version(), pkg.Version()
                                )
                        # We set the version to the old version, and then remove it.
                        # But other versions might be using it, so we can't do that
                        # just yet.
                        # Note to self:  need garbage collection run over
                        # archive.
                        # XXX - We can look to see if any other releaes are
                        # using this package version, and if not, remove the
                        # file.
                        pkg.SetVersion(old_pkg.Version())
                        pkg.SetChecksum(pkg1)
                    else:
                        print >> sys.stderr, "Created delta package %s" % x
                        cksum = ChecksumFile(x)
                        pkg.AddUpdate(old_pkg.Version(), cksum)
                else:
                    pkg.AddUpdate(old_pkg.Version(), ChecksumFile(delta_pkg))

        pkg_list.append(pkg)

    # And now let's add it to the database
    manifest.SetPackages(pkg_list)
    try:
        os.makedirs("%s/%s" % (archive, manifest.Train()))
    except:
        pass
    manifest.StorePath("%s/%s/FreeNAS-%s" % (archive, manifest.Train(), manifest.Sequence()))
    try:
        os.unlink("%s/%s/LATEST" % (archive, manifest.Train()))
    except:
        pass
    os.symlink("FreeNAS-%s" % manifest.Sequence(), "%s/%s/LATEST" % (archive, manifest.Train()))

    if db is not None:
        db.AddRelease(manifest.Sequence(),
                      manifest.Train(),
                      manifest.Packages())
        for pkg in manifest.Packages():
            # Check for the updates
            for upd in pkg.Updates():
                o_vers = upd[Package.VERSION_KEY]
                o_cksm = upd[Package.CHECKSUM_KEY]
                db.AddPackageUpdate(pkg, o_vers, o_cksm)

def main():
    global debug, verbose
    # Variables set via getopt
    # It may be possible to have reasonable defaults for these.
    OutputDirectory = None
    # Work on this
    Database = None

    # Locabl variables
    db = None

    options = "o:D:dv"
    long_options = ["--output=", "--destination=",
                 "--database=",
                 "--debug", "--verbose",
                    ]

    try:
        opts, args = getopt.getopt(sys.argv[1:], options, long_options)
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        usage()

    for o, a in opts:
        if o in ('-o', '--output', '--destination'):
            OutputDirectory = a
        elif o in ('--database', '-D'):
            Database = a
        elif o in ('-d', '--debug'):
            debug += 1
        elif o in ('-v', '--verbose'):
            verbose += 1
        else:
            usage()

    if OutputDirectory is None:
        print >> sys.stderr, "For now, output directory must be specified"
        usage()

    if len(args) == 0:
        print >> sys.stderr, "No sources specified"
        usage()

    if Database is not None:
        if Database.startswith("sqlite:"):
            db = SQLiteReleaseDB(dbfile = Database[len("sqlite:"):])
        elif Database.startswith("fs:"):
            db = FSReleaseDB(dbpath = Database[len("fs:"):])
        elif Database.startswith("py:"):
            db = PyReleaseDB(dbfile = Database[len("py:"):])

    for source in args:
        Process(source, OutputDirectory, db)
    

if __name__ == "__main__":
    main()
