#!/usr/bin/env python
"""
Simple script for pruning old builds.

Garrett Cooper, February 2012
"""

import optparse
import os
import sys
import time


# Seconds in a day.
DAY = 24 * 3600


def rm_old_files(rootdir, excludes=None, includes=None,
                 expire_time=(30 * DAY)):
    """Nuke everything under '''rootdir''' that doesn't match
       '''exclude''' that's older than '''expire_time'''.
    """

    if excludes is None:
        excludes = []

    if includes is None:
        includes = []

    # TODO: add in basic filter logic so wanted files that are
    # older than a specific date aren't nuked (e.g. README ;)..).

    #def is_wanted(path):
    #    not (exclude) or

    os.chdir(rootdir)

    expiration_date = time.time() - expire_time

    for path in \
        filter(lambda e: os.stat(e).st_ctime < expiration_date,
               os.listdir('.')):
        sys.stdout.write('Removing "%s/%s"\n' % (rootdir, path, ))
        if os.path.isdir(path):
            for root, __, files, in os.walk(path, topdown=False):
                for f in files:
                    os.unlink(os.path.join(root, f))
            os.rmdir(path)
        else:
            os.unlink(path)


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

    parser.add_option('-X', '--exclude', dest='exclude',
                      type='str',
                      action='append',
                      help='Globs of files to exclude',
                      )

    args, dirs = parser.parse_args()
    if not dirs:
        parser.error('you must specify one or more directories')

    for buildroot in dirs:
        rm_old_files(buildroot, expire_time=(args.expire_date * DAY))


if __name__ == '__main__':
    main(sys.argv[1:])
