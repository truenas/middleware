import os, sys
import json
import hashlib
import logging

from . import Avatar, UPDATE_SERVER
import Configuration
import Exceptions
import Package

log = logging.getLogger('freenasOS.Manifest')

SYSTEM_MANIFEST_FILE = "/data/manifest"

# The keys are as follows:
# SEQUENCE_KEY:  A string, uniquely identifying this manifest.
# PACKAGES_KEY:  An array of dictionaries.  They are installed in this order.
# SIGNATURE_KEY:  A string for the signed value of the manifest.  Not yet implemented.
# NOTES_KEY:  An array of name, URL pairs.  Typical names are "README" and "Release Notes".
# TRAIN_KEY:  A string identifying the train for this maifest.
# VERSION_KEY:  A string, the friendly name for this particular release.  Does not need to be unqiue.
# SCHEME_KEY:  A string, identifying the layout version.  Only one value for now.
# NOTICE_KEY:  A string, identifying a message to be displayed before installing this manifest.
# 	This is mainly intended to be used to indicate a particular train is ended.
#	A notice is something more important than a release note, and is included in
#	the manifest, rather than relying on a URL.
# SWITCH_KEY:  A string, identifying the train that should be used instead.
# 	This will cause Configuraiton.FindLatestManifest() to use that value instead, so
#	it should only be used when a particular train is end-of-life'd.

SEQUENCE_KEY = "Sequence"
PACKAGES_KEY = "Packages"
SIGNATURE_KEY = "Signature"
NOTES_KEY = "Notes"
TRAIN_KEY = "Train"
VERSION_KEY = "Version"
SCHEME_KEY = "Scheme"
NOTICE_KEY = "Notice"
SWITCH_KEY = "NewTrainName"

# SCHEME_V1 is the first scheme for packaging and manifests.
# Manifest is at <location>/FreeNAS/<train_name>/LATEST,
# packages are at <location>/Packages

SCHEME_V1 = "version1"

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
    This only compares packages; it does not compare
    sequence, train names, notices, etc.
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
    _scheme = SCHEME_V1
    _notice = None
    _switch = None

    def __init__(self, configuration = None):
        if configuration is None:
            self._config = Configuration.Configuration()
        return

    def dict(self):
        retval = {}
        if self._sequence is not None: retval[SEQUENCE_KEY] = self._sequence
        if self._packages is not None: retval[PACKAGES_KEY] = self._packages
        if self._signature is not None: retval[SIGNATURE_KEY] = self._signature
        if self._notes is not None: retval[NOTES_KEY] = self._notes
        if self._train is not None: retval[TRAIN_KEY] = self._train
        if self._version is not None: retval[VERSION_KEY] = self._version
        if self._notice is not None:  retval[NOTICE_KEY] = self._notice
        if self._switch is not None:  retval[SWITCH_KEY] = self._switch
        retval[SCHEME_KEY] = self._scheme
        return retval

    def String(self):
        retval = MakeString(self.dict())
        return retval

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
        self._notice = None
        self._switch = None

        for key in tdict.keys():
            if key == SEQUENCE_KEY:
                self.SetSequence(tdict[key])
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
            elif key == SCHEME_KEY:
                self.SetScheme(tdict[key])
            elif key == NOTICE_KEY:
                self.SetNotice(tdict[key])
            elif key == SWITCH_KEY:
                # Deliberately not a method to set this one
                self._switch = tdict[key]
            else:
                log.debug("Unknown key %s" % key)
        self.Validate()
        return

    def LoadPath(self, path):
        # Load a manifest from a path.
        with open(path, "r") as f:
            self.LoadFile(f)
        return

    def StoreFile(self, f):
        f.write(self.String())

    def StorePath(self, path):
        with open(path, "w") as f:
            self.StoreFile(f)
        return

    def Save(self, root):
        # Need to write out the manifest
        if root is None:
            root = self._root

        if root is None:
            prefix = ""
        else:
            prefix = root
        self.StorePath(prefix + SYSTEM_MANIFEST_FILE)

    def Validate(self):
        # A manifest needs to have a sequence number, train,
        # and some number of packages.  If there is a signature,
        # it needs to match the computed signature.
        if self._sequence is None:
            raise Exceptions.ManifestInvalidException("Sequence is not set")
        if self._train is None:
            raise Exceptions.ManifestInvalidException("Train is not set")
        if self._packages is None or len(self._packages) == 0:
            raise Exceptions.ManifestInvalidException("No packages")
        if self._signature is not None:
            temp = self.dict()
            if SIGNATURE_KEY in temp:  temp.pop(SIGNATURE_KEY)
            tstr = MakeString(temp)
            # This needs to do something real with signatures
            thash = hashlib.sha256(tstr).hexdigest()
            if thash != self._signature:
                raise ChecksumFailException
        return True

    def Notice(self):
        if not self._notice and self._switch:
            # If there's no notice, but there is a train-switch directive,
            # then make up a notice about it.
            return "This train (%s) should no longer be used; please switch to train %s instead" % (self.Train(), self.NewTrain())
        return self._notice

    def SetNotice(self, n):
        self._notice = n
        return

    def Scheme(self):
        return self._scheme

    def SetScheme(self, s):
        self._scheme = s
        return

    def Sequence(self):
        return self._sequence

    def SetSequence(self, seq):
        self._sequence = seq
        return

    def SetNote(self, name, location):
        if self._notes is None:
            self._notes = {}
        if location.startswith(UPDATE_SERVER):
            location = location[len(location):]
        self._notes[name] = location

    def Notes(self):
        if self._notes:
            rv = {}
            for name in self._notes.keys():
                loc = self._notes[name]
                if not loc.startswith(UPDATE_SERVER):
                    loc = "%s/%s/Notes/%s" % (UPDATE_SERVER, self.Train(), loc)
                rv[name] = loc
            return rv
        return None

    def SetNotes(self, notes):
        self._notes = {}
        for name in notes.keys():
            loc = notes[name]
            if loc.startswith(UPDATE_SERVER):
                loc = loc[len(UPDATE_SERVER):]
            self._notes[name] = os.path.basename(loc)
        return

    def Note(self, name):
        if self._notes is None or name not in self._Notes:
            return None
        loc = self._notes[name]
        if not loc.startswith(UPDATE_SERVER):
            loc = UPDATE_SERVER + loc
        return loc

    def Train(self):
        if self._train is None:
            raise Exceptions.ManifestInvalidException("Invalid train")
        return self._train

    def SetTrain(self, train):
        self._train = train
        return

    def Packages(self):
        return self._packages

    def AddPackage(self, pkg):
        if self._packages is None: self._packages = []
        self._packages.append(pkg)
        return

    def AddPackages(self, list):
        if self._packages is None: self._packages = []
        self._packages.append(list)
        return

    def SetPackages(self, list):
        self._packages = list
        return

    def VerifySignature(self):
        return False

    def Signature(self):
        return self._signature

    def SetSignature(self, signed_hash):
        self._signature = signed_hash
        return

    def SignWithKey(self, key_data):
        if key is None:
            # We'll cheat, and say this means "get rid of the signature"
            self._signature = None
        else:
            import OpenSSL.crypto as Crypto
            from base64 import b64encode as base64

            # Load the key.  This is most likely to fail.
            key = Crypto.load_privatekey(Crypto.FILETYPE_PEM, key_data)

            # Generate a canonical representation of the manifest
            temp = self.dict()
            if SIGNATURE_KEY in temp: temp.pop(SIGNATURE_KEY)
            tstr = MakeString(temp)

            # Sign it.
            signed_value = base64(Crypto.sign(key, tstr, "sha256"))

            # And now set the signature
            self._signature = signed_value
        return

    def Version(self):
        return self._version

    def SetVersion(self, version):
        self._version = version
        return

    def NewTrain(self):
        return self._switch

