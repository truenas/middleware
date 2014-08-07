#!/usr/local/bin/python -R
            
import os
import sys
import time
import getopt
import hashlib
            
sys.path.append("/usr/local/lib")
                
import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
from freenasOS.Configuration import ChecksumFile
import freenasOS.Package as Package
        
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
    print >> sys.stderr, "Usage: %s [-P package_directory] [-C configuration_file] [-o output_file] [-N <release_notes_file>] [-R release_name] -T <train_name> -S <manifest_version> pkg=version[:upgrade_from[,...]]  [...]" % sys.argv[0]
    print >> sys.stderr, "\tMultiple -P options allowed; multiple pkg arguments allowed"
    sys.exit(1)

if __name__ == "__main__":
    package_dir = None
    searchdirs = []
    notesfile = None
    releasename = None
    trainname = None
    sequencenum = 0
    pkgs = []
    outfile = None
    config_file = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "P:C:N:R:T:S:o:qvd")
    except getopt.GetoptError as err:
        print str(err)
        usage()
                
    for o, a in opts:
        if o == "-P":
            package_dir = a
        elif o == '-C':
            config_file = a
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
    
    if sequencenum == 0:
        # Use time
        sequencenum = int(time.time())
        
    if (trainname is None) or len(pkgs) == 0:
        usage()
    
    # We need a configuration to do searching
    conf = Configuration.Configuration(file = config_file, nopkgdb = True)
    mani = Manifest.Manifest(conf)
    mani.SetTrain(trainname)
    mani.SetSequence(sequencenum)
    if releasename is not None: mani.SetVersion(releasename)
    if notesfile is not None:
        notes = []
        with open(notesfile, "r") as f:
            for line in f:
                notes.append(line)
        mani.SetNotes(notes)
            

    # Small hack to make the package_dir option
    # make sense.
    if package_dir is not None:
        if package_dir.endswith("Packages"):
            package_dir = package_dir[:-len("Packages")]
        elif package_dir.endswith("Packages/"):
            package_dir = package_dir[:-len("Packages/")]

        conf.SetPackageDir(package_dir)
        
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
        pkg = Package.Package(name, version, None)
        pkgname = pkg.FileName()
        print "Package file name is %s" % pkgname
        pkgfile = conf.FindPackageFile(pkg)
        hash = None
        if pkgfile is not None:
            hash = ChecksumFile(pkgfile)
            pkgfile.seek(0, os.SEEK_END)
            size = pkgfile.tell()
            pkg.SetSize(size)
            pkgfile.seek(0)
        else:
            print >> sys.stderr, "Can't find file for %s" % name

        pkg.SetChecksum(hash)
        for U in upgrades:
            upgrade_file_name = pkg.FileName(U)
            print "Delta package name is %s" % upgrade_file_name
            upgrade_file = conf.FindPackageFile(pkg, U)
            if upgrade_file is None:
                print >> sys.stderr, "Could not find upgrade file %s" % upgrade_file_name
            else:
                hash = ChecksumFile(upgrade_file)
                upgrade_file.seek(0, os.SEEK_END)
                size = upgrade_file.tell()
                upgrade_file.seek(0)
                # See above for looking for upgrades.
                pkg.AddUpdate(U, hash, size if size != 0 else None)

        mani.AddPackage(pkg)
        
    # Don't set the signature
    mani.Validate()

    if outfile is None:
        outfile = sys.stdout
    else:
        outfile = open(outfile, "w")
            
    
    print >>outfile, mani.String()
