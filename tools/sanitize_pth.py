#!/usr/bin/env python
"""
  Description: A script / importable module that sanitizes .pth files to
  ensure all entries are correct.

  Copyright (c) 2009-2012, Garrett Cooper
  All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the Garrett Cooper nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY Garrett Cooper ''AS IS'' AND ANY
  EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
  DISCLAIMED. IN NO EVENT SHALL Garrett Cooper BE LIABLE FOR ANY
  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
  THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

  Other errata --

  There are some gaps which have yet to addressed with the some popular Python
  packaging tools (setuptools / easy_install primarily), such that data which
  was recorded to .pth files isn't guaranteed to be correct in all cases after
  a package has been installed ot a site directory. One shortcoming with
  easy_install that it frequently omits packages installed concurrently as
  the authors didn't design it in an MP-safe manner, such that it properly
  locks easy-install.pth when installing multiple packages.

  Until all issues have been addressed with packaging (and
  features / functionality is the point where the jury is still largely out
  in the Python community due to differences in opinion -_-...), popular tools
  have been fully fixed, and the .pth file data never becomes stale, this
  script will continue to be useful in fixing .pth files...

  Design notes:

  This script is designed to work as-is with 2.4+ ~ 3.x with as much core
  functionality as possible. As such, I use generic version agnostic syntax
  and idioms, which is why...

  1. I don't use print (well, not in production -- just the commented out
     debug messages..). Why?
     -- 2.x with `print()' syntax is aesthetically unappealing (tries to
        print tuples).
     -- 3.x doesn't like `print >> stream' syntax.
  2. I don't catch specific exceptions and store as vars.
     -- 2.x's syntax is ""except `type_tuple', var"", whereas 3.x's syntax
        is: ""except `type_tuple' as var"".
  3. I don't use fancy 2.5+ available modules, 3rd party modules, decorators,
     etc. I mean, c'mon... this is only for parsing text files and doing path
     related os operations..

"""

import copy, glob, os, re, sys

def sanitize_pth(path, pth_basename, glob_expr, pth_match_expr, backup=False,
    fix=False):
    """ Sanitize a .pth file, which exists in `path' and has the name
    `pth_basename'. Compared the contained data against the globbed
    files / directories in the expression: `path'/`glob_expr'.

    This function returns True if the file has changed, and False if
    unchanged, or tosses a relevant Exception.

    - If backup is True, backup the previous file (good to do if you're
    not sure about the results and want to test / revert after the fact).
    Only applies if fix is True.
    - If fix is True, go ahead and fix the file instead of just faking the
    fix.

    Notes:
    - I use assertions heavily so prepare to catch AssertExceptions if you need
    to...
    """

    # Don't assume that the path that's passed in is absolute.
    path = os.path.abspath(path)

    pth_f = os.path.join(path, str(pth_basename))

    # Get the absolute path for the user-specified glob expression.
    globbed_paths = [p.replace(path, '.') \
                        for p in glob.glob(os.path.join(path, glob_expr))]

    assert 0 < len(globbed_paths), "Didn't find any globbed packages"

    # Read in the .pth file.
    with open(pth_f, 'r') as pth_fd:
        pth_lines = [line.rstrip() for line in pth_fd]

    # print "\nOld lines:\n", "\n".join(pth_lines)

    #
    # The purpose of this function is to:
    #
    # 1. Keep non-existent matched expression lines intact (non-file.
    # 2. Add all globbed entries that weren't already in the .pth file.
    # 3. Remove all entries that don't exist in the filesystem at their
    # designated spots.
    #

    globbed_entries = filter(pth_match_expr.search, pth_lines)

    #
    # I refuse to make stupid guesses about files without valid entries.
    # Guessing based on malformed data, exceptions to the rule, and using some
    # projects' status quo's, not the python status quo is how some software
    # projects in Python get into ratholes (*cough* SetupTools *cough*)...
    # 
    # Make the system work without hacking the sh*t outta it -- not the other
    # way around... simplicity is key.
    #
    assert len(globbed_entries), ("Couldn't find a valid globbed entry "
                                   "in %s" % pth_f)

    last_valid_entry = pth_lines.index(globbed_entries[-1])

    globbed_entries_set = set(globbed_entries)
    globbed_paths_set = set(globbed_paths)

    #
    # Given the requirements noted above, we can think of the data being in
    # four distinct sets:
    #
    # - Set A consists is of original .pth file data.
    # - Set B consists of non-existent package entries in the .pth file.
    # - Set C consists of package files / directories which aren't recorded
    #   in the .pth file.
    # - Set D is the package on disk data.
    #
    # Python allows us to demonstrate this relationship by using the set data
    # structure =].
    #
    # Unfortunately Python set ordering is tricky and nondeterministic, so I
    # have to provide breadcrumbs back to entries of interest so we where to
    # add more entries...
    #
    # Sorry, but if what I just said above the sounded like an adult in a
    # Charlie Brown cartoon, please take it on faith that what I'm doing below
    # is correct :) (until proven otherwise).
    #

    # Criteria 2: Set ( C - B )
    entries_to_add = list(globbed_paths_set - globbed_entries_set)
    # Criteria 3: Set ( B & (B - C) )
    entries_to_dump = list(globbed_entries_set &
                            (globbed_entries_set - globbed_paths_set))

    #print "\nGlobbed entries:\n", '\n'.join(list(globbed_entries_set))
    #print "\nGlobbed paths:\n", '\n'.join(list(globbed_paths_set))
    #print "\nEntries to dump:\n", '\n'.join(entries_to_dump)

    # Need to deepcopy because lists / dicts use references under the covers.
    old_pth_lines = copy.deepcopy(pth_lines)

    #
    # Insert the entire list _at_ the last globbed entry's index.
    # This is essentially the same as a `fluid' extend method.
    # See:
    # 
    #
    # This must be done before any list manipulation's are performed below or
    # we could go outta bounds...
    #
    pth_lines[last_valid_entry:last_valid_entry] = entries_to_add

    for entry in entries_to_dump:
        # Trim the fat... I didn't do this with a set object because some data
        # gets sort of lost in translation on 2.4.x
        # (see: ).
        pth_lines.remove(entry)

    #print "Old lines:\n", '\n'.join(old_pth_lines), "\nNew lines:\n",
    #print '\n'.join(pth_lines)

    if fix:
        # Fix the file.

        if backup:
            # Back, back, back it up!
            os.rename(pth_f, pth_f + '~')

        with open(pth_f, 'w') as pth_fd:
            pth_fd.write('\n'.join(pth_lines))

        # Spare the rod, spoil the child..

    # If something changed, there will be a disjoint set =].
    return bool(set(pth_lines) ^ set(old_pth_lines))

def main():
    """ The main fn. """

    import getopt

    # Remove app name
    argv = sys.argv[1:]
    # Backup the file before writing?
    backup = False
    # Fix the file?
    fix = False
    glob_expr = '*.egg'
    pth_file_basename = 'easy-install.pth'
    #
    # easy-install.pth looks like something similar to the following:
    #
    # import sys; sys.__plen = len(sys.path)
    #./multiprocessing-2.6.1.1-py2.5-linux-i686.egg
    # import sys; new=sys.path[sys.__plen:]; del sys.path[sys.__plen:]; \
    # p=getattr(sys,'__egginsert',0); sys.path[p:p]=new; \
    # sys.__egginsert = p+len(new)
    #
    # But someone can comment out entries to skip sourcing directories --
    # so let's skip evaluating those items.
    # 
    pth_line_re = re.compile('^([^#].+\.egg[\\\/]?)$')

    def usage():
        """ Print out a usage message and exit. """
        sys.exit("usage: %s -bfv [-g site-pkg-glob] [-p pth_file] "
                 "-r [pth_line_regexp][path_0] ... [path_n]\n" %
                 os.path.basename(__file__))

    if len(sys.argv) == 0:
        usage()

    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'bfg:p:v',
            [ 'backup', 'fix', 'glob', 'pth-file' ])
    except:
        usage()

    for opt, arg in opts:
        if opt == '-b':
            backup = True
        elif opt == '-f':
            fix = True
        elif opt == '-g':

            try:
                glob.glob(arg)
                # glob.glob allows for zero-length string arguments. This is
                # invalid for searching in my book...
                assert (len(arg) != 0)
            except:
                sys.stderr.write('Bad glob expression: %s' % str(arg))
                sys.exit(2)
            glob_expr = arg

        elif opt == '-p':
            pth_file_basename = arg
        elif opt == '-r':
            try:
                pth_line_re = re.compile(arg)
                # re.compile allows for zero-length string arguments. This is
                # invalid for searching in my book...
                assert (len(arg) != 0)
            except:
                sys.stderr.write('Bad regular expression: %s' % str(arg))
                sys.exit(2)

        else:
            assert False, "Unhandled option: %s" % opt

    paths = []

    if len(argv) != 0:
        paths = argv
    else:
        exc_are_critical = False
        # User didn't specify a specific path; let's search through sys.path
        # instead (painful and will print out more messages about not finding
        # .pth files, but whatever..).
        paths = list(set(sys.path))

    for path in paths:
        try:

            sys.stderr.write("%s: - " % os.path.join(path, pth_file_basename))

            if (sanitize_pth(path, pth_file_basename, glob_expr, pth_line_re,
                                backup=backup, fix=fix)):
                # The contents differed.
                if fix:
                    sys.stderr.write("fixed")
                else:
                    sys.stderr.write("would fix")

            else:
                sys.stderr.write("no change")

        except (AssertionError, IOError):
            sys.stderr.write("skipped")

        sys.stderr.write("\n")

if __name__ == "__main__":
    main()
