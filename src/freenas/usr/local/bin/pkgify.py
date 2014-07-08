#!/usr/local/bin/python
#
# Given a metalog file from a freebsd build system,
# read each line, and create (using the path as key)
# for each.
#
# Valid fields are:
# uname:  name of the owner
# gname:  name of the group
# mode:  mode (as an integer) of the file
# type:  file, dir, link
# link:  if a symlink, this is the source
# hlink:  if a hard link, this is the source
# category:  category (or set of catgories)
#	comma-separated
#	Each category can have a subset, with a ':'
#	e.g., docs,base:dev
#
# Options for this program are:
# -L		List packages/categories in metalog file
# -P <pkglist>	Comma-separated list of categories/packages
# -N name	Name for PKGNG
# -V version	Version for PKGNG
# -A		Include all subsets of a category (default NO)
# -U		Include uncategorized files/directories (default NO)
# -v		Verbose (default NO)
# -d		Debug (default NO)
# Metafile	Metalog from FreeBSD build.
# Root

import os
import sys
import stat
import getopt
import hashlib
import json
import tarfile
import StringIO

CAT_KEY = "category"
TYPE_KEY = "type"
TYPE_FILE = ["file", "link", "hlink"]
TYPE_DIR = ["dir"]

def ParseLine(line, root = None):
    elems = line.split(" ")
    pname = ""
    rd = {}
    for A in elems[1:]:
        (key, value) = A.split("=")
        if key == CAT_KEY:
            if "," in value:
                tarray = value.split(",")
                value = tarray
            else:
                value = [value]
        elif key == "mode":
            value = int(value, 0)
        rd[key] = value
    if TYPE_KEY not in rd:
        raise Exception("Entry has no type key")
    if root is None:
        pname = elems[0]
    else:
# So this gets complicated.
# We need to turn someting like "./usr/share/nls/en_US.US-ASCII/foo" into
# "./usr/share/nls/C/foo", because en_US.US-ASCII is a symlink to "C".
# However, we need to keep "./usr/share/nls/en_US.US-ASCII" as just
# that.
        pname = elems[0]
        dirname = os.path.dirname(pname)
        elemname = os.path.basename(pname)
        realpath = os.path.realpath(root + "/" + dirname)
        if pname.startswith("./"):
            if os.path.relpath(realpath, root) == ".":
                pname = os.path.relpath(realpath, root) + "/" + elemname
            else:
                pname = "./" + os.path.relpath(realpath, root) + "/" + elemname
        elif pname.startswith("/"):
            pname = "/" + os.path.relpath(realpath, root) + "/" + elemname
        else:
            pname = os.path.relpath(realpath, root) + "/" + elemname
        if pname == "./.": pname = "./"
    return (pname, rd)

def ChecksumFile(root, path):
    full_path = root + "/" + path
    if os.path.islink(full_path):
        return "-"
    elif os.path.isfile(full_path):
        with open(full_path, "r") as f:
            retval = hashlib.sha256(f.read()).hexdigest()
        return retval
    else:
        return None

def usage():
    print >> sys.stderr, "Usage: %s [-p pkg[,pkg...]] [-t file] [-N name] [-V version] [-O origin]" \
        "[-M maintainer] [-D description] [-a] [-o dir] [-u] root [metalog]" % sys.argv[0]
    print >> sys.stderr, "\t-t\ttemplate file"
    print >> sys.stderr, "\t-p\tCategories/Packages to include (e.g., base, dev, kernel)"
    print >> sys.stderr, "\t-a\tInclude all sub packages (e.g., base includes base:doc)"
    print >> sys.stderr, "\t-o\tOutput location"
    print >> sys.stderr, "\t-u\tInclude uncategorized entries"
    print >> sys.stderr, "\t-l\tList categories in metafile, and exit."
    print >> sys.stderr, "\t-N name\tPackage name"
    print >> sys.stderr, "\t-V version\tPackage Version"
    print >> sys.stderr, "\t-M maintainer\tPackage maintainer"
    print >> sys.stderr, "\t-C comment\tPackage comment"
    print >> sys.stderr, "\t-D desc\tPackage description"
    print >> sys.stderr, "\t-O origin\tPackage origin (e.g., system/os)"
    sys.exit(1)

def LoadTemplate(m, path):
    """
    Given a path -- which may be a file or a directory -- load manifest fields
    from it.
    If it's a file, then we just treat it as a shlex
    """
    import ConfigParser
    conf = ConfigParser.ConfigParser()
    isdir = False

    scripts = None
    if os.path.isfile(path):
        conf.read(path)
    elif os.path.isdir(path) and os.path.isfile(path + "/settings.cfg"):
        conf.read(path + "/settings.cfg")
        isdir = True
    else:
        print >> sys.stderr, "Cannot handle %s (perhaps it doesn't exist)" % path
        return m

    # Look for "Settings"
    for key, val in conf.items("Settings"):
        # Don't over-ride anything set via CLI options
        if key not in m or m[key] is None:
            m[key] = val

    # Look for scripts
    # Scripts can only be set via template file
    if conf.has_section("Scripts"):
        scripts = {}
        for key, val in conf.items("Scripts"):
            scripts[key] = val
    elif isdir:
        # If the path was a directory, then look for scripts in it
        scriptnames = {
            "pre-upgrade" : "+PRE_UPGRADE",
            "upgrade" : "+UPGRADE",
            "post-upgrade" : "+POST_UPGRADE",
            "pre-install" : "+PRE_INSTALL",
            "install" : "+INSTALL",
            "post-install" : "+POST_INSTALL",
            "pre-deinstall" : "+PRE_DEINSTALL",
            "deinstall" : "+DEINSTALL",
            "post-deinstall" : "+POST_DEINSTALL",
            }
        for key in scriptnames.keys():
            if os.path.isfile(path + "/" + scriptnames[key]):
                with open(path + "/" + scriptnames[key]) as f:
                    scripts[key] = f.read()
    if scripts is not None:
        m["scripts"] = scripts
    return m
    
def main():
    subpackages = False
    categories = []
    verbose = False
    debug = False
    name = "base-os"
    version = "unknown"
    uncat = False
    list_cats = False
    pkg_dirs = []
    pkg_files = []
    output_dir = "."
    uniq_cats = {}
    root_path = None
    metalog = None
    use_json = True
    template_file = None

    manifest = {}
    default_manifest_keys = {
#        "name" : None,
#        "version" : None,
#        "origin" : None,
        "comment" : "FreeNAS package",
        "maintainer" : "dev@freenas.org",
        "prefix" : "/",
        "www" : "http://www.ixsystems.com/",
        "licenselogic" : "single",
        "desc" : "FreeNAS OS Package",
        }
        
        
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ap:o:udvlt:N:V:O:M:C:D:")
    except getopt.GetoptError as err:
        print >>sys.stderr, str(err)
        usage()
        sys.exit(1)

    for (o, a) in opts:
        if o == "-l":
            list_cats = True
        elif o == "-t":
            template_file = a
        elif o == "-a":
            subpackages = True
        elif o == "-o":
            output_dir = a
        elif o == "-p":
            categories.extend(a.split(","))
        elif o == "-M":
            manifest["maintainer"] = a
        elif o == "-D":
            manifest["desc"] = a
        elif o == "-C":
            manifest["comment"] = a
        elif o == "-u":
            uncat = True
        elif o == "-N":
            manifest["name"] = a
        elif o == "-O":
            manifest["origin"] = a
        elif o == "-V":
            manifest["version"] = a
        elif o == "-v":
            verbose = True
        elif o == "-d":
            debug = True
        else:
            usage()

    if template_file is not None:
        manifest = LoadTemplate(manifest, template_file)

    # Now we set any defaults that are left
    for key in default_manifest_keys.keys():
        if key not in manifest:
            manifest[key] = default_manifest_keys[key]

    # And a couple of special case ones
    if "name" not in manifest:
        print >> sys.stderr, "Package does not have a name.  Not acceptable"
        sys.exit(1)
    if "version" not in manifest:
        print >> sys.stderr, "Package %s does not have a version.  Not acceptable!" % manifest["name"]
        sys.exit(1)

    if "origin" not in manifest:
        manifest["origin"] = "system/" + manifest["name"]

        
    # If we have two arguments, check to see which is a directory
    if len(args) > 2 or len(args) == 0:
        usage()
    elif len(args) == 1:
        # Assume this is a root
        if not os.path.isdir(args[0]):
            print >> sys.stderr, "%s is not a directory and needs to be" % args[0]
            usage()
        root_path = args[0]
        metalog = root_path + "/METALOG"
        if not os.path.isfile(metalog):
            print >> sys.stderr, "%s does not have a manifest file" % root_path
            usage
    elif len(args) == 2:
        # Check to see if one is a directory and the other is a file
        if os.path.isfile(args[0]) and os.path.isdir(args[1]):
            metalog = args[0]
            root_path = args[1]
        elif os.path.isfile(args[1]) and os.path.isdir(args[0]):
            metalog = args[1]
            root_path = args[0]
        else:
            usage()

    if root_path is None or metalog is None:
        usage()
    # Turn root_path into the realpath version
    root_path = os.path.realpath(root_path)

    # Assume no options for now; this will change
    system = {}
    with open(metalog, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            (fname, parms) = ParseLine(line.rstrip(), root_path)
            if CAT_KEY in parms:
                for pkg in parms[CAT_KEY]:
                    uniq_cats[pkg] = True

            if fname in system:
                if (CAT_KEY not in parms) and not (debug or uncat): continue
                if verbose or debug: print >> sys.stderr, "Entry `%s' already in system... does that matter?" % fname
                if parms == system[fname]:
                    if verbose or debug: print >> sys.stderr, "\tBut they are the same, so that's okay"
                else:
                    if verbose or debug: print >> sys.stderr, "\tTaking later entry as more valid"
                    del system[fname]
                    system[fname] = parms
            else:
                system[fname] = parms
    if debug: print "Done processing"

    if list_cats:
        print "Categories:"
        for name in sorted(uniq_cats):
            print "\t%s" % name
        return 0

    for fname in system.keys():
        wantit = False
        parms = system[fname]
#        print "parms = %s" % parms
        if CAT_KEY in parms:
            for file_key in parms[CAT_KEY]:
                for requested_key in categories:
                    if ((requested_key == file_key)
                        or
                        (":" in file_key and file_key.startswith(requested_key) and subpackages)):
                        if verbose or debug: print "%s%s" % (fname, "\t#%s, type = %s" % (file_key, parms[TYPE_KEY]) if (debug or verbose) else "")
                        wantit = True
        elif uncat:
            if verbose or debug: print "%s%s" % (fname, "\t# uncategorized, type = %s" % (parms[TYPE_KEY]) if (debug or verbose) else "")
            wantit = True
        if wantit:
            if parms[TYPE_KEY] in TYPE_FILE:
                # Get the hash for the file.  "-" if it's a symlink
                pkg_files.append((fname, ChecksumFile(root_path, fname)))
            elif parms[TYPE_KEY] in TYPE_DIR:
                pkg_dirs.append(fname)
    if verbose or debug: print "%d files\n%d directories" % (len(pkg_files), len(pkg_dirs))
    output_file = "%s/+MANIFEST" % output_dir
    # Collect the main keys first
    manifest["files"] = {}
    for (fname, hash) in pkg_files:
        manifest["files"][fname] = hash
    manifest["directories"] = {}
    for dname in pkg_dirs:
        # Wow, this is a hack, I didn't think about it.
        manifest["directories"][dname] = "n"
    manifest_string = json.dumps(manifest, sort_keys=True, indent=4, separators=(',', ': '))

    # N.B.
    # This should be replaced with tarfile usage.
    with open(output_file, "w") as f:
        f.write(manifest_string)

    tf = tarfile.open(output_dir + ".tgz", mode = "w:gz", format = tarfile.PAX_FORMAT)
    if tf is None:
        print >> sys.stderr, "Cannot create tar file %s" % (output_dir + ".tgz")
        sys.exit(1)

    metaobj = tarfile.TarInfo(name="+MANIFEST")
    metaobj.size = len(manifest_string)
    metaobj.type = tarfile.REGTYPE
    
    tf.addfile(metaobj, StringIO.StringIO(manifest_string))
    ext_flags = {
        "nodump" : stat.UF_NODUMP,
        "sappnd" : stat.SF_APPEND,
        "schg" : stat.SF_IMMUTABLE,
        "sunlnk" : stat.SF_NOUNLINK,
        "uchg" : stat.UF_IMMUTABLE,
        }
    # Now to add the files
    def flags_filter(ti):
        tipath = root_path + "/" + ti.name
        st = os.lstat(tipath)
        if st.st_flags != 0:
            flags = []
            for key in ext_flags.keys():
                if st.st_flags & ext_flags[key]: flags.append(key)
            ti.pax_headers["SCHILY.fflags"] = ",".join(flags)
        return ti

    for (fname, unused) in pkg_files:
        full_path = root_path + "/" + fname
        tf.add(full_path, arcname = fname, recursive = False, filter = flags_filter)

    # Now the directories
    for dname in pkg_dirs:
        full_path = root_path + "/" + dname
        tf.add(full_path, arcname = dname, recursive = False, filter = flags_filter)


    tf.close()
    return 0

if __name__ == "__main__":
    main()

    
