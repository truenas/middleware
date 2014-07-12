#!/usr/bin/python -R

import os
import sys
import json
import re
import hashlib
import getopt
import shlex
import urllib2
import tempfile

sys.path.append("/usr/local/lib")

import freenasOS.Exceptions
import freenasOS.Configuration

"""
Class and methods to handle a FreeNAS manifest file.
A manifest file consists of a signature line (optional);
the rest of the file is JSON, with the following keys:

Sequence -- an integer, identifying the manifest sequence number (required);
Train -- a string, indicating which train this is for (release, nightly, etc.) (optional);
Version -- a string, indicating the version for the release (optional);
Notes -- Any release notes to be displayed (optional);
Packages -- an array of packages (required)

Packages have the following contents:

name -- the name of the package (required)
version -- The version of this package (required)
checksum -- Checksum for this package (required)
upgrades -- an array of <old_version, checksum> pairs (optional)

Packages are listed in the order they are to be installed.

"""

#
# Compare two manifest objects, in particular the packages.
# Returns an array of tuples; each entry is (package, action, old_version).
# "action" is going to be "delete", "upgrade", or "install".  old_version
# will only be set for "upgrade".
# The sequence number of the manifests is used to determine
# "old" vs "new".
# Packages to be deleted are listed first; after that, they are listed
# in the order they appear in the new manifest.

def CompareManifests(m1, m2):
    if m1.Sequence() < m2.Sequence():
        old = m1
        new = m2
    elif m1.Sequence() > m2.Sequence():
        old = m2
        new = m1
    elif m1.Sequence() == m2.Sequence():
        return None
    retval = []
    old_packages = old.Packages()
    new_packages = new.Packages()
    old_list = {}

    for P in old_packages:
        old_list[P.Name()] = P

    for P in new_packages:
        if P.Name() in old_list:
            if old_list[P.Name()].Version() != P.Version():
                retval.append((P, "upgrade", old_list[P.Name()]))
            old_list.pop(P.Name(), None)
        else:
            retval.append((P, "install", None))

    for P in old_list:
        retval.insert(0, (old_list[P], "delete", None))

    return retval

def FormatName(pkg, version, upgrade = None):
    if upgrade is None:
        return "%s-%s" % (pkg, version)
    else:
        return "%s-%s-%s" % (pkg, upgrade, version)

class Package(object):
    __name = None
    __version = None
    __checksum = None
    __upgrades = None

    def __init__(self, name, version, hash):
        self.__name = name
        self.__version = version
        self.__checksum = hash
        freenasOS.Configuration.Configuration()

    def dict(self):
        r = {}
        r["Name"] = self.__name
        r["Version"] = self.__version
        r["Checksum"] = self.__checksum
        u = []
        if self.__upgrades:
            for X in self.__upgrades:
                u.append(X)
            if len(u) > 0:
                r["Upgrades"] = u
        return r
            
    def __repr__(self):
        return "{ Name : \"%s\", Version : \"%s\", Checksum : \"%s\" }" % (self.__name, self.__version, self.__checksum)

    def __str__(self):
        return "<%s-%s>" % (self.__name, self.__version)

    def Name(self):
        return self.__name

    def Version(self):
        return self.__version

    def Checksum(self):
        return self.__checksum

    def Upgrades(self):
        return self.__upgrades

    def AddUpgrade(self, ver, hash):
        if self.__upgrades is None:
            self.__upgrades = []

        self.__upgrades.append({"Version" : ver, "Checksum" : hash})

class Manifest(object):
    __sequence = 0
    __version = None
    __train = None
    __notes = None
    __packages = None
    __signature = None

    def __init__(self):
        return

    def dict(self, file = None):
        h = {}
        if self.__sequence:
            h["Sequence"] = int(self.__sequence)
        if self.__train:
            h["Train"] = self.__train
        if self.__version:
            h["Version"] = self.__version
        if self.__notes:
            h["Notes"] = self.__notes
        if self.__packages:
            a = []
            for P in self.__packages:
                a.append(P.dict())
            h["Packages"] = a
        if file is not None:
            self.load_path(file)
        return h

    def load_file(self, file):
        """
        Given a file, load a JSON from it, and convert it
        into an Manifest.
        The first line may be "SIGNATURE=", which case it's
        a hash.
        """
        file.seek(0)
        sig_line = None
        json_str = ""
        line = file.readline()
        if line.startswith("SIGNATURE="):
            print "Has a hash"
            self.__signature = line.rstrip()
        else:
            json_str += line
        for line in file:
            json_str += line
        file_hash = hashlib.sha256(json_str).hexdigest()
        # Would need to now use this to verify a signature
        if file_hash == "":
            raise ManifestSignatureError

        # Now process and start converting things
        j = json.loads(json_str)
        for K in j:
            if K == "Sequence":
                self.SetSequence(j[K])
            elif K == "Train":
                self.SetTrain(j[K])
            elif K == "Version":
                self.SetVersion(j[K])
            elif K == "Notes":
                self.SetNotes(j[K])
            elif K == "Packages":
                for P in j[K]:
                    p = Package(P["Name"], P["Version"], P["Checksum"])
                    if "Upgrades" in P:
                        for U in P["Upgrades"]:
                            p.AddUpgrade(U["Version"], U["Checksum"])
                    self.AddPackage(p)
        return

    def load_path(self, path):
        """
        Like load_file, but opens the path.
        """
        try:
            with open(path, "r") as f:
                self.load_file(f)
        except Exception as e:
            print >> sys.stderr, "Got an error trying to load manifest from path %s: %s" % (path, str(e))
            pass
        return

    def json_string(self):
        h = self.dict()
        if h is None:
            raise ManifestConversionError
        return json.dumps(h, sort_keys=True, indent=4, separators=(',', ': '))

    def store(self, path):
        json_str = self.json_string()
        if json_str is None:
            raise ManifestConversionError

        with open(path, "w") as f:
            if self.__signature is not None:
                f.write("%s\n" % self.__signature)
            f.write(json_str)
            f.write("\n")
        return

    def Signature(self):
        return self.__signature

    def Sequence(self):
        return self.__sequence

    def SetSequence(self, seq):
        self.__sequence = int(seq)
        return

    def Train(self):
        return self.__train

    def SetTrain(self, train):
        self.__train = train
        return

    def Version(self):
        return self.__version

    def SetVersion(self, version):
        self.__version = version
        return

    def Notes(self):
        return self.__notes

    def SetNotes(self, note):
        self.__notes = note
        return

    def Packages(self):
        return self.__packages

    def AddPackage(self, pkg):
        if self.__packages is None:
            self.__packages = []
        self.__packages.append(pkg)
        return

    def FindPackage(self, pkgname):
        if self.__packages is None:
            return None
        for p in self.__packages:
            if p.Name() == pkgname:
                return p
        return None

if __name__ == "__main__":
    man = Manifest()
    if man is None:
        print >> sys.stderr, "Cannot create manifest object"
        sys.exit(1)
    if len(sys.argv) == 3:
        man1 = Manifest()
        man2 = Manifest()
        man1.load_path(sys.argv[1])
        man2.load_path(sys.argv[2])
        print "%s sequence = %d, %s sequence = %d" % (sys.argv[1], man1.Sequence(), sys.argv[2], man2.Sequence())
        pkg_list = CompareManifests(man1, man2)
        for A in pkg_list:
            (p, a, o) = A
            if a == "delete":
                print "Delete %s-%s" % (p.Name(), p.Version())
            elif a == "upgrade":
                print "Upgrade %s from %s to %s" % (p.Name(), o.Version(), p.Version())
            elif a == "install":
                print "Install %s-%s" % (p.Name(), p.Version())
            else:
                print "Unknown action `%s'" % a
        sys.exit(0)
    if len(sys.argv) > 1:
        for m in sys.argv[1:]:
            man = Manifest()
            man.load_path(m)
            print "%s" % man.dict()
    else:
        man.SetSequence(1)
        man.SetTrain("FreeNAS-Stable")
        man.SetVersion("FreeNAS-9.2.2")
        p = Package("base-os", "1.0", "abcd")
        p.AddUpgrade("0.9", "ffff")
        p.AddUpgrade("0.8", "aaaa")
        man.AddPackage(p)
        man.AddPackage(Package("samba", "4.0", "1234"))
        man.store("/tmp/man.json")
        print "%s" % man.dict()

    baseos = man.FindPackage("base-os")
    print baseos

