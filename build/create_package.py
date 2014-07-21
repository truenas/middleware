#!/usr/local/bin/python -R
# Create a pkgng-like package from a directory.

import os, sys, stat
import json
import tarfile
import getopt
import hashlib
import StringIO
import ConfigParser

debug = 0
verbose = False
#
# Scan a directory hierarchy, creating a
# "files" and "directories" set of dictionaries.
# Regular files get sha256 checksums.
def ScanTree(root):
    global debug, verbose
    flat_size = 0
    # This is a list of files we've seen, by <st_dev, st_ino> keys.
    seen_files = {}
    file_list = {}
    directory_list = {}
    for start, dirs, files in os.walk(root):
        prefix = start[len(root):] + "/"
        for d in dirs:
            directory_list[prefix + d] = "y"
        for f in files:
            full_path = start + "/" + f
            if verbose or debug > 0: print >> sys.stderr, "looking at %s" % full_path
            st = os.lstat(full_path)
            size = None
            if os.path.islink(full_path):
                buf = os.readlink(full_path)
                size = len(buf)
                if buf.startswith("/"): buf = buf[1:]
                file_list[prefix + f] = hashlib.sha256(buf).hexdigest()
            elif os.path.isfile(full_path):
                size = st.st_size
                with open(full_path) as file:
                    file_list[prefix + f] = hashlib.sha256(file.read()).hexdigest()

            if size is not None and (st.st_dev, st.st_ino) not in seen_files:
                flat_size += size
                seen_files[st.st_dev, st.st_ino] = True

    return { "files" : file_list, "directories" : directory_list, "flatsize" : flat_size }


#
# We need to be told a directory,
# package name, version, and output file.
# We'll assume some defaults specific to ix.

def usage():
    print >> sys.stderr, "Usage: %s [-dv] -R <root> -N <name> -V <version> output_file" % sys.argv[0]
    sys.exit(1)

SCRIPTS = [
	"pre-install",
	"post-install",
	"install",
	"pre-deinstall",
	"post-deinstall",
	"deinstall",
	"pre-upgrade",
	"post-upgrade",
	"upgrade"
]
def LoadTemplate(path):
    """
    Load a ConfigParser file as a template.
    The "Package" section has various defaults for the
    PKGNG-like manifest; other sections have other values
    of interest.
    If path is a directory, then the configuration file
    will be path + "/config".
    For scripts, "file:" indicates a filename to read;
    if path is a directory, it will be relative to that
    directory; otherwise, it will be relative to the directory
    contaning path.  (That is, "/tmp/pkg.cfg" will result in
    "file:+INSTALL" looking for /tmp/+INSTALL.)
    Returns a dictionary, which may be empty.  If path does
    not exist, it raises an exception.
    """
    rv = {}
    if os.path.exists(path) == False:
	raise Exception("%s does not exist" % path)
    if os.path.isdir(path):
	base_dir = path
	cfg_file = path + "/config"
    else:
	base_dir = os.path.dirname(path)
	cfg_file = path

    cfp = ConfigParser.ConfigParser()
    try:
	cfp.read(cfg_file)
    except:
	return rv

    if cfp.has_section("Package"):
	# Get the various manifest 
	for key in ["name", "www", "arch", "maintainer",
		"comment", "origin", "prefix", "licenslogic",
		"licenses", "desc"]:
	    if cfp.has_option("Package", key):
		rv[key] = cfp.get("Package", key)

    if cfp.has_section("Scripts"):
	if "scripts" not in rv:
	    rv["scripts"] = {}
	for opt, val in cfp.items("Scripts"):
	    if val.startswith("file:"):
		# Skip over the file: part
		fname = val[5:]
		if fname.startswith("/") == False:
		    fname = base_dir + "/" + fname
		with open(fname, "r") as f:
		    rv["scripts"][opt] = f.read()
	    else:
		rv["scripts"][opt] = val

    return rv

def main():
    global debug, verbose
    # Some valid, but stupid, defaults.
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
        opts, args = getopt.getopt(sys.argv[1:], "dvN:V:R:T:")
        for o, a in opts:
            if o == "-N":
                manifest["name"] = a
	    elif o == "-T":
		tdict = LoadTemplate(a)
		if tdict is not None:
		    for k in tdict.keys():
			manifest[k] = tdict[k]
            elif o == "-V":
                manifest["version"] = a
            elif o == "-R":
                root = a
            elif o == "-d":
                debug += 1
            elif o == "-v":
                verbose = True
            else:
                print >> sys.stderr, "Unknown options %s" % o
                usage()
    except getopt.GetoptError as err:
        print str(err)
        usage()
    if len(args) > 1:
        print >> sys.stderr, "Too many arguments"
        usage()
    elif len(args) == 0:
        print >> sys.stderr, "Output file must be specified"
        usage()
    else:
        output = args[0]
    if root is None:
        print >> sys.stderr, "Root directory must be specified"
        usage()
    if "name" not in manifest:
        print >> sys.stderr, "Package must have a name"
        usage()
    if "version" not in manifest:
        print >> sys.stderr, "Package must have a version"
        usage()

    if debug > 2: print manifest

    t = ScanTree(root)
    manifest["files"] = t["files"]
    manifest["directories"] = t["directories"]
    manifest["flatsize"] = t["flatsize"]
    manifest_string = json.dumps(manifest, sort_keys=True,
                                 indent=4, separators=(',', ': '))
    if debug > 1: print manifest_string

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
