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
import ConfigParser

CAT_KEY = "category"
TYPE_KEY = "type"
TYPE_FILE = ["file", "link", "hlink"]
TYPE_DIR = ["dir"]

debug = 0
verbose = False

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
        # Symlinks have their leading / (if any) removed
        link_target = os.readlink(full_path)
        if link_target[0] == "/":
            return hashlib.sha256(link_target[1:]).hexdigest()
        else:
            return hashlib.sha256(link_target).hexdigest()
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
    print >> sys.stderr, "\t-p\tCategories/Packages to include (e.g., base, dev, kernel, crypto:ALL)"
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

def TemplateFiles(path):
    """
    Load a ConfigParser file as a configuration file.
    Look for a section labeled "Files", "exclude" and
    "include" otions.  Return both in a dictionary; the
    value is an array of files to include or exclude.
    (The files may be paths, or shell-style globs.)
    """

    rv = {}
    includes = []
    excludes = []
    if os.path.exists(path) == False:
        return None
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
        return None

    if cfp.has_option("Files", "exclude"):
        opt = cfp.get("Files", "exclude")
        for f in opt.split():
            excludes.append(f)

    if cfp.has_option("Files", "include"):
        opt = cfp.get("Files", "include")
        for f in opt.split():
            includes.append(f)

    rv["include"] = includes
    rv["exclude"] = excludes
    return rv

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
    
def CategoryIsWanted(file_categories, desired_categories):
    """
    Return a boolean indicating whether the file (based
    on file_categories) is desired (based on desired_categories).
    Both file_categories and desired_categories are arrays of
    strings; the strings look like "name" or "name:subname".
    Alternately, "ALL" means everything (including subcategories),
    and "name:ALL" means all name:subname (including "name").
    e.g.:  CategoryIsWanted("base:doc", ["base", "kernel"]) would
    return False, while CategoryIsWanted("base:doc", ["base", "base:doc"])
    would return True
    """
    # First, go through the categories for the file
    for file_entry in file_categories:
        if ":" in file_entry:
            (cat, subcat) = file_entry.split(":")
        else:
            cat = file_entry
            subcat = None
        # Next, go through the desired categories
        for desired_entry in desired_categories:
            if ":" in desired_entry:
                (desired_cat, desired_subcat) = desired_entry.split(":")
            else:
                desired_cat = desired_entry
                desired_subcat = None

            # If desired_cat is "ALL" and desired_subcat is None or ALL then we want it regardless
            if desired_cat == "ALL":
                if desired_subcat == "ALL" or desired_subcat is None:
                    return True
                if subcat is desired_subcat:
                    return True

            if cat == desired_cat:
                # If it's the same category, check the subcategory
                if subcat == desired_subcat:
                    return True
                if desired_subcat == "ALL":
                    return True
    return False

def FilterFunc(path, include_list, exclude_list):
    """
    Return a boolean indicating whether the path in question
    should be filtered out.  This is a bit tricky, unfortunately,
    but we'll start out simple.
    Returns True if it should be filtered out, False if not.
    There are four cases to worry about:
    1.  No include_list or exclude_list
    2.  include_list but no exclude_list
    3.  exclude_list but no include_list
    4.  Both include_list and exclude_list
    For (1), return value is always False (never filter out).
    For (2), return value is False if it is in the list, True otherwise.
    For (3), return value is True if it is in the list, False otherwise.
    For (4), return value is True if it is in the exclude list,
    False if it is in the include list, False if it is in neither.
    """
    # Set the default return value based on include and exclude lists.
    if include_list is None and exclude_list is None:
        retval = False
    elif include_list is not None and exclude_list is None:
        retval = True
    elif include_list is None and exclude_list is not None:
        retval = False
    else:
        retval = False

    def matches(path, pattern):
        import fnmatch

        prefix = ""
        if path.startswith("./"):
            prefix = "."
        if pattern.startswith("/"):
            tmp = prefix + pattern
        else:
            tmp = pattern
        # First, check to see if the name simply matches
        if path == tmp:
            if debug: print >> sys.stderr, "Match: %s" % path
            return True
        # Next, check to see if elem is a subset of it
        if path.startswith(tmp) and \
           path[len(tmp)] == "/":
            if debug: print >> sys.stderr, "Match %s as child of %s" % (path, tmp)
            return True
        # Now to start using globbing.
        # fnmatch is awful, but let's try just that
        # (It's awful because it doesn't handle path boundaries.
        # Thus, "/usr/*.cfg" matches both "/usr/foo.cfg" and
        # "/usr/local/etc/django.cfg".)
        if fnmatch.fnmatch(path, elem):
            if debug: print >> sys.stderr, "Match: %s as glob match for %s" % (path, tmp)
            return True
        return False

    # Include takes precedence over exclude, so we handle
    # the exclude list first
    if exclude_list is not None:
        for elem in exclude_list:
            if matches(path, elem) == True:
                retval = True
                break
    if include_list is not None:
        for elem in include_list:
            if matches(path, elem) == True:
                retval = False

    return retval

def main():
    categories = []
    verbose = False
    debug = False
    name = "base-os"
    version = "unknown"
    uncat = False
    list_cats = False
    pkg_dirs = []
    pkg_files = []
    output_file = None
    uniq_cats = {}
    root_path = None
    metalog = None
    use_json = True
    template_file = None
    include_list = None
    exclude_list = None

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
        elif o == "-o":
            output_file = a
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
        tdict = LoadTemplate(template_file)
        if tdict is not None:
            for k in tdict.keys():
                manifest[k] = tdict[k]
        filters = TemplateFiles(template_file)
        if filters is not None:
            if debug > 1:  print >> sys.stderr, "Filter list = %s" % filters
            if len(filters["include"]) > 0:
                include_list = filters["include"]
            if len(filters["exclude"]) > 0:
                exclude_list = filters["exclude"]

    # Now we set any defaults that are left
    for key in default_manifest_keys.keys():
        if key not in manifest:
            manifest[key] = default_manifest_keys[key]

    # And a couple of special case ones (unless "-l" was given)
    if not list_cats:
        if "name" not in manifest:
            print >> sys.stderr, "Package does not have a name.  Not acceptable"
            sys.exit(1)
        if "version" not in manifest:
            print >> sys.stderr, "Package %s does not have a version.  Not acceptable!" % manifest["name"]
            sys.exit(1)

        if "origin" not in manifest:
            manifest["origin"] = "system/" + manifest["name"]

        if output_file is None:
            output_file = "%s-%s.tgz" % (manifest["name"], manifest["version"])

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
        if FilterFunc(fname, include_list, exclude_list) is True:
            continue
        wantit = False
        parms = system[fname]
#        print "parms = %s" % parms
        if CAT_KEY in parms:
            wantit = CategoryIsWanted(parms[CAT_KEY], categories)
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

    # Collect the main keys first
    manifest["files"] = {}
    for (fname, hash) in pkg_files:
        manifest["files"][fname] = hash
    manifest["directories"] = {}
    for dname in pkg_dirs:
        # Wow, this is a hack, I didn't think about it.
        manifest["directories"][dname] = "n"
    manifest_string = json.dumps(manifest, sort_keys=True, indent=4, separators=(',', ': '))

    tf = tarfile.open(output_file, mode = "w:gz", format = tarfile.PAX_FORMAT)
    if tf is None:
        print >> sys.stderr, "Cannot create tar file %s" % output_file
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

    
