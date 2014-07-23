import os, sys
import json
import hashlib

import Configuration
import Exceptions
import Package

SYSTEM_MANIFEST_FILE = "/etc/manifest"
BACKUP_MANIFEST_FILE = "/conf/base/etc/manifest"

SEQUENCE_KEY = "Sequence"
PACKAGES_KEY = "Packages"
SIGNATURE_KEY = "Signature"
NOTES_KEY = "Notes"
TRAIN_KEY = "Train"
VERSION_KEY = "Version"

class ChecksumFailException(Exception):
    pass

def MakeString(obj):
    retval = json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': '), cls = ManifestEncoder)
    return retval

def CompareManifests(m1, m2):
    """
    Compare two manifests.  The return value is an
    array of tuples; each tuple is (package, op, old).
    op is "delete", "upgrade", or "install"; for "upgrade",
    the third element of the tuple will be the old version.
    Deleted packages will always be first.
    It assumes m1 is the older, and m2 is the newer.
    """
    old_packages = m1.Packages()
    new_packages = m2.Packages()
    old_list = {}

    retval = []

    for P in old_packages:
        old_list[P.Name()] = P

    for P in new_packages:
        if P.Name() in old_list:
            # Either it's the same version, or a new version
            if old_list[P.Name()].Version() != P.Version():
                retval.append((P, "upgrade", old_list[P.Name()]))
            old_list.pop(P.Name())
        else:
            retval.append((P, "install", None))

    for P in old_list:
        retval.insert(0, (P, "delete", None))
    
    return retval
                    
class ManifestEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Package.Package):
            return obj.dict()
        elif isinstance(obj, Manifest):
            return obj.dict()
        else:
            return json.JSONEncoder.default(self, obj)

class Manifest(object):
    _config = None
    _root = None
    _sequence = None
    _notes = None
    _train = None
    _packages = None
    _signature = None
    _version = None
    _dirty = False
    

    def __init__(self, configuration = None):
        if configuration is None:
            self._config = Configuration.Configuration()
        return

    def dict(self):
        retval = {}
        if self._sequence is not None: retval[SEQUENCE_KEY] = int(self._sequence)
        if self._packages is not None: retval[PACKAGES_KEY] = self._packages
        if self._signature is not None: retval[SIGNATURE_KEY] = self._signature
        if self._notes is not None: retval[NOTES_KEY] = self._notes
        if self._train is not None: retval[TRAIN_KEY] = self._train
        if self._version is not None: retval[VERSION_KEY] = self._version
        return retval

    def String(self):
        retval = MakeString(self.dict())
        return retval

    def MarkDirty(self, b):
        self._dirty = b
        if b is True: self._signature = None
        return

    def LoadFile(self, file):
        # Load a manifest from a file-like object.
        # It's loaded as a json file, and then parsed
        tdict = json.load(file)
        # Now go through the keys
        self._sequence = None
        self._notes = None
        self._train = None
        self._packages = None
        self._signature = None
        self._version = None

        for key in tdict.keys():
            if key == SEQUENCE_KEY:
                self.SetSequence(int(tdict[key]))
            elif key == PACKAGES_KEY:
                for p in tdict[key]:
                    pkg = Package.Package(p[Package.NAME_KEY], p[Package.VERSION_KEY], p[Package.CHECKSUM_KEY])
                    if Package.UPGRADES_KEY in p:
                        for upd in p[Package.UPGRADES_KEY]:
                            pkg.AddUpdate(upd[Package.VERSION_KEY], upd[Package.CHECKSUM_KEY])
                    self.AddPackage(pkg)
            elif key == SIGNATURE_KEY:
                self.SetSignature(tdict[key])
            elif key == NOTES_KEY:
                self.SetNotes(tdict[key])
            elif key == TRAIN_KEY:
                self.SetTrain(tdict[key])
            elif key == VERSION_KEY:
                self.SetVersion(tdict[key])
            else:
                raise ManifestInvalidException
        self.Validate()
        self.MarkDirty(True)
        return

    def LoadPath(self, path):
        # Load a manifest from a path.
        with open(path, "r") as f:
            self.LoadFile(f)
        return

    def StorePath(self, path):
        with open(path, "w") as f:
            f.write(self.String())
        self.MarkDirty(False)
        return

    def Validate(self):
        # A manifest needs to have a sequence number, train,
        # and some number of packages.  If there is a signature,
        # it needs to match the computed signature.
        if self._sequence is None:
            raise ManifestInvalidException
        if self._sequence != int(self._sequence):
            raise ManifestInvalidException
        if self._train is None:
            raise ManifestInvalidException
        if self._packages is None or len(self._packages) == 0:
            raise ManifestInvalidException
        if self._signature is not None:
            temp = self.dict()
            if SIGNATURE_KEY in temp:  temp.pop(SIGNATURE_KEY)
            tstr = MakeString(temp)
            # This needs to do something real with signatures
            thash = hashlib.sha256(tstr).hexdigest()
            if thash != self._signature:
                raise ChecksumFailException
        return True

    def Sequence(self):
        return self._sequence

    def SetSequence(self, seq):
        self._sequence = int(seq)
        self.MarkDirty(True)
        return

    def Notes(self):
        return self._notes

    def SetNotes(self, notes):
        self._notes = notes
        self.MarkDirty(True)
        return

    def Train(self):
        if self._train is None:  raise ManifestInvalidException
        return self._train

    def SetTrain(self, train):
        self._train = train
        self.MarkDirty(True)
        return

    def Packages(self):
        return self._packages

    def AddPackage(self, pkg):
        if self._packages is None: self._packages = []
        self._packages.append(pkg)
        self.MarkDirty(True)
        return

    def AddPackages(self, list):
        if self._packages is None: self._packages = []
        self._packages.append(list)
        self.MarkDirty(True)
        return

    def VerifySignature(self):
        return False

    def Signature(self):
        return self._signature

    def SetSignature(self, hash = None):
        if hash is None:
            temp = self.dict()
            if SIGNATURE_KEY in temp: temp.pop(SIGNATURE_KEY)
            tstr = MakeString(temp)
            thash = hashlib.sha256(tstr).hexdigest()
            self._signature = thash
        else:
            self._signature = hash
        return

    def Version(self):
        return self._version

    def SetVersion(self, version):
        self._version = version
        self.MarkDirty(True)
        return
