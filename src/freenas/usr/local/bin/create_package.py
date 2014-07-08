#!/usr/local/bin/python -R
# Create a pkgng-like package from a directory.

import os, sys, stat
import json
import tarfile
import getopt
import hashlib
import StringIO

debug = 0
verbose = False
#
# Scan a directory hierarchy, creating a
# "files" and "directories" set of dictionaries.
# Regular files get sha256 checksums.
def ScanTree(root):
    global debug, verbose
    file_list = {}
    directory_list = {}
    for start, dirs, files in os.walk(root):
        prefix = start[len(root):] + "/"
        for d in dirs:
            directory_list[prefix + d] = "y"
        for f in files:
            full_path = start + "/" + f
            if verbose or debug > 0: print >> sys.stderr, "looking at %s" % full_path
            if os.path.islink(full_path):
                buf = os.readlink(full_path)
                if buf.startswith("/"): buf = buf[1:]
                file_list[prefix + f] = hashlib.sha256(buf).hexdigest()
            elif os.path.isfile(full_path):
                with open(full_path) as file:
                    file_list[prefix + f] = hashlib.sha256(file.read()).hexdigest()

    return { "files" : file_list, "directories" : directory_list }

#
# We need to be told a directory,
# package name, version, and output file.
# We'll assume some defaults specific to ix.

def usage():
    print >> sys.stderr, "Usage: %s [-dv] -R <root> -N <name> -V <version> output_file" % sys.argv[0]
    sys.exit(1)

def main():
    global debug, verbose
    manifest = {
        "www" : "http://www.freenas.org",
        "arch" : "freebsd:9:x86:64",
        "maintainer" : "something@freenas.org",
        "comment" : "FreeNAS Package",
        "origin" : "system/os",
        "prefix" : "/",
        "licenselogic" : "single",
        "desc" : "FreeNAS Package",
        }
    root = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dvN:V:R:")
        for o, a in opts:
            if o == "-N":
                manifest["name"] = a
            elif o == "-V":
                manifest["version"] = a
            elif o == "-R":
                root = a
            elif o == "-d":
                debug += 1
            elif o == "-v":
                verbose = True
            else:
                usage()
        if len(args) != 1:
            usage()
        if root is None:
            usage()
        output = args[0]
        if "name" not in manifest:
            usage()
        if "version" not in manifest:
            usage()
    except getopt.GetoptError as err:
        print str(err)
        usage()
    if len(args) != 1:
        usage()
    if root is None:
        usage()
    output = args[0]

    t = ScanTree(root)
    manifest["files"] = t["files"]
    manifest["directories"] = t["directories"]
    manifest_string = json.dumps(manifest, sort_keys=True,
                                 indent=4, separators=(',', ': '))
    print manifest_string

    tf = tarfile.open(output, "w:gz", format = tarfile.PAX_FORMAT)

    # Add the manifest string as "+MANIFEST"
    mani_file_info = tarfile.TarInfo(name = "+MANIFEST")
    mani_file_info.size = len(manifest_string)
    mani_file_info.mode = 0600
    mani_file_info.type = tarfile.REGTYPE
    mani_file = StringIO.StringIO(manifest_string)
    tf.addfile(mani_file_info, mani_file)
    # Now add all of the files
    for file in manifest["files"].keys():
        if verbose or debug > 0:  print >> sys.stderr, "Adding %s to archive" % file
        tf.add(root + file, arcname = file, recursive = False)
    # And now the directories
    for dir in manifest["directories"].keys():
        print >> sys.stderr, "Adding %s to archive" % dir
        tf.add(root + dir, arcname = dir, recursive = False)

    return 0

if __name__ == "__main__":
    sys.exit(main())
