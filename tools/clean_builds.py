#!/usr/bin/env python
"""
Simple script for pruning old builds.

Garrett Cooper, February 2012
"""

import fnmatch
import optparse
import os
import sys
import time


# Seconds in a day.
DAY = 24 * 3600


def rm_old_files(rootdir, excludes=None, includes=None,
                 expire_time=(30 * DAY), fake=False):
    """Nuke everything under '''rootdir''' that doesn't match
       '''exclude''' that's older than '''expire_time'''.
    """

    if excludes is None:
        excludes = []

    if includes is None:
        includes = []

    os.chdir(rootdir)

    expiration_date = time.time() - expire_time

    def nuke(path):
        if filter(lambda e: fnmatch.fnmatchcase(path, e), excludes):
            return False
        if os.stat(path).st_ctime < expiration_date:
            return True
        return False

    def nukeit(function, path):
        if nuke(path):
            if fake:
                sys.stdout.write('%s("%s")\n' % (function.__name__, path))
            else:
                function(path)

    for path in filter(lambda e: nuke(e), os.listdir('.')):
        sys.stdout.write('Removing "%s/%s"\n' % (rootdir, path, ))
        if os.path.isdir(path):
            for root, __, files, in os.walk(path, topdown=False):
                for f in files:
                    nukeit(os.unlink, os.path.join(root, f))
            nukeit(os.rmdir, path)
        else:
            nukeit(os.unlink, path)


def main(argv):
    """main"""

    parser = optparse.OptionParser()

    parser.add_option('-e', '--expire-date', dest='expire_date',
                      type='int',
                      default=30,
                      help='number of days before builds expire',
                      )

    parser.add_option('-i', '--include', dest='include',
                      type='str',
                      action='append',
                      help='Globs of files to include',
                      )

    parser.add_option('-n', '--no-exec', dest='fake',
                      action='store_true',
                      help='Do not remove files',
                      )

    parser.add_option('-X', '--exclude', dest='exclude',
                      type='str',
                      action='append',
                      help='Globs of files to exclude',
                      )

    args, dirs = parser.parse_args()
    if not dirs:
        parser.error('you must specify one or more directories')

    for buildroot in dirs:
        rm_old_files(buildroot,
                     expire_time=(args.expire_date * DAY),
                     excludes=args.exclude,
                     fake=args.fake,
                     includes=args.include,
                     )


if __name__ == '__main__':
    main(sys.argv[1:])
