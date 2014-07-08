#!/usr/local/bin/python -R

import os
import sys
import getopt
import hashlib

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration

debug = 0
quiet = False
verbose = 0

#
# Create a manifest.  This needs to be given a set of packages,
# a train name, and a sequence number.  If package_directory is
# given, it will search there for the package files.
#
# TBD:  Sequence number should be automatically generated.
#

def usage():
    print >> sys.stderr, "Usage: %s [-P package_directory] [-N <release_notes_file>] [-R release_name] -T <train_name> -S <manifest_version> pkg=version[:upgrade_from[,...]]  [...]" % sys.argv[0]
    print >> sys.stderr, "\tMultiple -P options allowed; multiple pkg arguments allowed"
    sys.exit(1)

if __name__ == "__main__":
    searchdirs = []
    notesfile = None
    releasename = None
    trainname = None
    sequencenum = 0
    pkgs = []
    outfile = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "P:N:R:T:S:o:qvd")
    except getopt.GetoptError as err:
        print str(err)
        usage()

    for o, a in opts:
        if o == "-P":
            searchdirs.append(a)
        elif o == "-N":
            notesfile = a
        elif o == "-R":
            releasename = a
        elif o == "-T":
            trainname = a
        elif o == "-S":
            sequencenum = int(a)
        elif o == "-q":
            quiet = True
        elif o == "-v":
            verbose += 1
        elif o == "-d":
            debug += 1
        elif o == "-o":
            outfile = a
        else:
            usage()

    pkgs = args

    if (trainname is None) or (sequencenum == 0) or len(pkgs) == 0:
        usage()

    mani = Manifest.ixManifest()
    mani.SetTrain(trainname)
    mani.SetSequence(sequencenum)
    gconfig = Configuration.Configuration()
    if releasename is not None: mani.SetVersion(releasename)
    if notesfile is not None:
        notes = []
        with open(notesfile, "r") as f:
            for line in f:
                notes.append(line)
        mani.SetNotes(notes)

    for loc in searchdirs:
        gconfig.AddSearch(loc)

    for P in pkgs:
        # Need to parse the name, which is pkg=version[:upgrade,upgrade,upgrade]
        upgrades = []
        if ":" in P:
            (P, tmp) = P.split(":")
            if "," in tmp:
                upgrades = tmp.split(",")
            else:
                upgrades.append(tmp)
        if "=" not in P:
            usage()
        (name, version) = P.split("=")
        pkgname = Manifest.FormatName(name, version)
        print "Package file name is %s" % pkgname
        pkgfile = gconfig.FindPackage(pkgname)
        hash = None
        if pkgfile is not None:
            hash = hashlib.sha256(pkgfile.read()).hexdigest()
        else:
            print >> sys.stderr, "Can't find file for %s" % pkgfile

        pkg = Manifest.ixPackage(name, version, hash)
        for U in upgrades:
            print "Upgrade package name is %s" % Manifest.FormatName(name, version, U)
            # See above for looking for upgrades.
            pkg.AddUpgrade(U, "unknown")
        mani.AddPackage(pkg)

    if outfile is None:
        outfile = sys.stdout
    else:
        outfile = open(outfile, "w")

    print >>outfile, mani.json_string()
    print hashlib.sha256(mani.json_string()).hexdigest()
