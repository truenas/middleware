import os, sys
import json
import hashlib
import logging

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
# TIMESTAMP_KEY:	An integer, being the unix time of the build.
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
TIMESTAMP_KEY = "BuildTime"
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

def DiffManifests(m1, m2):
    """
    Compare two manifests.  The return value is a dictionary,
    with at least the following keys/values as possible:
    Packages -- an array of tuples (pkg, op, old)
    Sequence -- a tuple of (old, new)
    Train -- a tuple of (old, new)
    Reboot -- a boolean indicating whether a reboot is necessary.
    (N.B.  This may be speculative; it's going to assume that any
    updates listed in the packages are available, when they may not
    be.)
    If a key is not present, then there are no differences for that
    value.
    """
    return_diffs = {}

    def DiffPackages(old_packages, new_packages):
        retval = []
        old_list = {}
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

        for P in old_list.itervalues():
            retval.insert(0, (P, "delete", None))
    
        return retval

    # First thing, let's compare the packages
    # This will go into the Packages key, if it's non-empty.
    package_diffs = DiffPackages(m1.Packages(), m2.Packages())
    if len(package_diffs) > 0:
        return_diffs["Packages"] = package_diffs
        # Now let's see if we need to do a reboot
        reboot_required = False
        for pkg, op, old in package_diffs:
            if op == "delete":
                # XXX You know, I hadn't thought this one out.
                # Is there a case where a removal requires a reboot?
                continue
            elif op == "install":
                if pkg.RequiresReboot() == True:
                    reboot_required = True
            elif op == "upgrade":
                # This is a bit trickier.  We want to see
                # if there is an upgrade for old
                upd = pkg.Update(old.Version())
                if upd:
                    if upd.RequiresReboot() == True:
                        reboot_required = True
                else:
                    if pkg.RequiresReboot() == True:
                        reboot_required = True
        return_diffs["Reboot"] = reboot_required
        
    # Next, let's look at the train
    # XXX If NewTrain is set, should we use that?
    if m1.Train() != m2.Train():
        return_diffs["Train"] = (m1.Train(), m2.Train())

    # Sequence
    if m1.Sequence() != m2.Sequence():
        return_diffs["Sequence"] = (m1.Sequence(), m2.Sequence())
        
    return return_diffs

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
    diffs = DiffManifests(m1, m2)
    if "Packages" in diffs:
        return diffs["Packages"]
    return []
                    
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

    _notes = None
    _train = None
    _packages = None
    _signature = None
    _version = None
    _scheme = SCHEME_V1
    _notice = None
    _switch = None
    _timestamp = None
    _requireSignature = False

    def __init__(self, configuration = None, require_signature = False):
        if configuration is None:
            self._config = Configuration.Configuration()
        else:
            self._config = configuration
        self._requireSignature = require_signature
        self._dict = {}
        return

    def dict(self):
        return self._dict

    def String(self):
        retval = MakeString(self.dict())
        return retval

    def LoadFile(self, file):
        # Load a manifest from a file-like object.
        # It's loaded as a json file, and then parsed
        self._dict = json.load(file)

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
        from . import SIGNATURE_FAILURE
        if SEQUENCE_KEY not in self._dict:
            raise Exceptions.ManifestInvalidException("Sequence is not set")
        if TRAIN_KEY not in self._dict:
            raise Exceptions.ManifestInvalidException("Train is not set")
        if PACKAGES_KEY not in self._dict \
           or len(self._dict[PACKAGES_KEY]) == 0:
            raise Exceptions.ManifestInvalidException("No packages")
        if self._config and self._config.UpdateServerSigned() == False:
            log.debug("Update server %s [%s] does not sign, so not checking" %
                      (self._config.UpdateServerName(),
                       self._config.UpdateServerURL()))
            return True
        if SIGNATURE_KEY not in self._dict:
            # If we don't have a signature, but one is required,
            # raise an exception
            if self._requireSignature and SIGNATURE_FAILURE:
                log.debug("No signature in manifest")
        else:
            if self._requireSignature:
                if not self.VerifySignature():
                    if self._requireSignature and SIGNATURE_FAILURE:
                        raise Exceptions.ManifestInvalidSignature("Signature verification failed")
                    if not self._requireSignature:
                        log.debug("Ignoring invalid signature due to manifest option")
                    elif not SIGNATURE_FAILURE:
                        log.debug("Ignoring invalid signature due to global configuration")
        return True

    def Notice(self):
        if NOTICE_KEY not in self._dict:
            if (SWITCH_KEY in self._dict):
                # If there's no notice, but there is a train-switch directive,
                # then make up a notice about it.
                return "This train (%s) should no longer be used; please switch to train %s instead" % (self.Train(), self.NewTrain())
            else:
                return None
        else:
            return self._dict[NOTICE_KEY]

    def SetNotice(self, n):
        self._dict[NOTICE_KEY] = n
        return

    def Scheme(self):
        if SCHEME_KEY in self._dict:
            return self._dict[SCHEME_KEY]
        else:
            return None

    def SetScheme(self, s):
        self._dict[SCHEME_KEY] = s
        return

    def Sequence(self):
        return self._dict[SEQUENCE_KEY]

    def SetSequence(self, seq):
        self._dict[SEQUENCE_KEY] = seq
        return

    def SetNote(self, name, location):
        if NOTES_KEY not in self._dict:
            self._dict[NOTES_KEY] = {}
        if location.startswith(self._config.UpdateServerURL()):
            location = location[len(location):]
        self._dict[NOTES_KEY][name] = location

    def Notes(self):
        if NOTES_KEY in self._dict:
            rv = {}
            for name in self._dict[NOTES_KEY].keys():
                loc = self._dict[NOTES_KEY][name]
                if not loc.startswith(self._config.UpdateServerURL()):
                    loc = "%s/%s/Notes/%s" % (self._config.UpdateServerURL(), self.Train(), loc)
                rv[name] = loc
            return rv
        return None

    def SetNotes(self, notes):
        self._notes = {}
        for name in notes.keys():
            loc = notes[name]
            if loc.startswith(self._config.UpdateServerURL()):
                loc = loc[len(self._config.UpdateServerURL()):]
            self._notes[name] = os.path.basename(loc)
        return

    def Note(self, name):
        if NOTES_KEY not in self._dict:
            return None
        notes = self._dict[NOTES_KEY]
        if name not in notes:
            return None
        loc = notes[name]
        if not loc.startswith(self._config.UpdateServerURL()):
            loc = self._config.UpdateServerURL + loc
        return loc

    def Train(self):
        if TRAIN_KEY not in self._dict:
            raise Exceptions.ManifestInvalidException("Invalid train")
        return self._dict[TRAIN_KEY]

    def SetTrain(self, train):
        self._dict[TRAIN_KEY] = train
        return

    def Packages(self):
        pkgs = []
        for p in self._dict[PACKAGES_KEY]:
            pkg = Package.Package(p)
            pkgs.append(pkg)
        return pkgs

    def AddPackage(self, pkg):
        if PACKAGES_KEY not in self._dict:
            self._dict[PACKAGES_KEY] = []
        self._dict[PACKAGES_KEY].append(pkg.dict())
        return

    def AddPackages(self, list):
        if PACKAGES_KEY not in self._dict:
            self._dict[PACKAGES_KEY] = []
        for p in list:
            self.AddPackage(p)
        return

    def SetPackages(self, list):
        self._dict[PACKAGES_KEY] = []
        self.AddPackages(list)
        return

    def VerifySignature(self):
        from . import IX_ROOT_CA_FILE, UPDATE_CERT_FILE, VERIFIER_HELPER, IX_CRL
        from . import SIGNATURE_FAILURE
        if self.Signature() is None:
            return not SIGNATURE_FAILURE
        # Probably need a way to ignore the signature
        else:
            import subprocess
            import tempfile

            if not os.path.isfile(IX_ROOT_CA_FILE) or \
               not os.path.isfile(UPDATE_CERT_FILE) or \
               not os.path.isfile(VERIFIER_HELPER):
                log.debug("VerifySignature:  Cannot find a required file")
                return False

            # Now need to get the CRL
            crl_file = tempfile.NamedTemporaryFile(suffix=".pem")
            if crl_file is None:
                log.debug("Could not create CRL, ignoring for now")
            else:
                if not self._config.TryGetNetworkFile(url = IX_CRL,
                                                  pathname = crl_file.name,
                                                  reason = "FetchCRL"):
                    log.error("Could not get CRL file %s" % IX_CRL)
                    crl_file.close()
                    crl_file = None

            tdata = None
            verify_cmd = [VERIFIER_HELPER,
                          "-K", UPDATE_CERT_FILE,
                          "-C", IX_ROOT_CA_FILE,
                          "-S", self.Signature()]
            if crl_file:
                verify_cmd.extend(["-R", crl_file.name])
            else:
                log.debug("Could not get CRL %s, so we'll just continue" % IX_CRL)

            log.debug("Verify command = %s" % verify_cmd)

            temp = self.dict().copy()
            if SIGNATURE_KEY in temp:  temp.pop(SIGNATURE_KEY)
            canonical = MakeString(temp)
            if len(canonical) < 10 * 1024:
                # I think we can have 10k arguments in freebsd
                verify_cmd.append(canonical)
            else:
                tdata = tempfile.NamedTemporaryFile()
                tdata.write(canonical)
                verify_cmd.extend(["-D", tdata.name])
            
            rv = False
            try:
                subprocess.check_call(verify_cmd)
                log.debug("Signature check succeeded")
                rv = True
            except subprocess.CalledProcessError as e:
                rv = False
                log.error("Signature check failed, exit value %d" % e.returncode)

            if tdata:
                tdata.close()
                os.remove(tdata.name)

            return rv
        return False

    def Signature(self):
        if SIGNATURE_KEY in self._dict:
            return self._dict[SIGNATURE_KEY]

    def SetSignature(self, signed_hash):
        self._dict[SIGNATURE_KEY] = signed_hash
        return

    def SignWithKey(self, key_data):
        if key_data is None:
            # We'll cheat, and say this means "get rid of the signature"
            if SIGNATURE_KEY in self._dict:
                self._dict.pop(SIGNATURE_KEY)
        else:
            import OpenSSL.crypto as Crypto
            from base64 import b64encode as base64

            # If it's a PKey, we don't need to load it
            if isinstance(key_data, Crypto.PKey):
                key = key_data
            else:
                # Load the key.  This is most likely to fail.
                key = Crypto.load_privatekey(Crypto.FILETYPE_PEM, key_data)

            # Generate a canonical representation of the manifest
            temp = self.dict()
            if SIGNATURE_KEY in temp: temp.pop(SIGNATURE_KEY)
            tstr = MakeString(temp)

            # Sign it.
            signed_value = base64(Crypto.sign(key, tstr, "sha256"))

            # And now set the signature
            self._dict[SIGNATURE_KEY] = signed_value
        return

    def Version(self):
        if VERSION_KEY in self._dict:
            return self._dict[VERSION_KEY]
        else:
            return None

    def SetVersion(self, version):
        self._dict[VERSION_KEY] = version
        return

    def SetTimeStamp(self, ts):
        self._dict[TIMESTAMP_KEY] = ts

    def TimeStamp(self):
        if TIMESTAMP_KEY in self._dict:
            return self._dict[TIMESTAMP_KEY]
            return 0

    def NewTrain(self):
        if SWITCH_KEY in self._dict:
            return self._dict[SWITCH_KEY]
        else:
            return None

