#!/usr/bin/env python
"""
Provide a 'graph' of all of the packages/ports.

Copyright (c) 2011-2012 iXsystems, Inc., All rights reserved.

XXX: this is a prototype script -- it will change.

Garrett Cooper, December 2011
"""

import argparse
import os
import pipes
import shlex
import subprocess
import sys

def warnx(fmt, args):
    sys.stderr.write(fmt % (args, ) + '\n')

PACKAGE_CACHE = []

class Package:

    # A dependency cache.
    __depends = None

    def __init__(self, pkg_origin, opts=None, portsdir='/usr/ports'):

        if opts is None:
            opts = []

        self.opts = []
        # XXX: clean up unnecessary loop with map + lambdas.
        for opt in opts:
            if opt.find('=') == -1:
                opt = '%s=y' % (opt, )
            self.opts.append(opt)

        self.pkg_origin = pkg_origin
        self.portsdir = os.path.abspath(portsdir) + '/'
        if not os.path.exists(os.path.join(portsdir, pkg_origin)):
            raise ValueError('Could not find path for package: %s'
                             % (pkg_origin, ))

    def __str__(self):
        if not instanceof(other, Package):
            raise ValueError('Bad object for comparison provided')
        return self.pkg_origin

    def __eq__(self, other):
        if not instanceof(other, Package):
            raise ValueError('Bad object for comparison provided')
        return str(self) == str(other)

    def __ne__(self, other):
        if not instanceof(other, Package):
            raise ValueError('Bad object for comparison provided')
        return str(self) != str(other)

    def __gt__(self, other):
        if not instanceof(other, Package):
            raise ValueError('Bad object for comparison provided')
        return True

    def get_dependencies(self):

        if self.__depends:
            # Cache dependencies.
            return self.__depends

        opts_str = ' '.join(map(pipes.quote, self.opts))
        cmd = 'make describe %s BATCH=y PORTSDIR="%s"' % \
              (' '.join(map(pipes.quote, self.opts), ), self.portsdir)

        pipe = subprocess.Popen(shlex.split(cmd),
                                cwd=os.path.join(self.portsdir,
                                                 self.pkg_origin),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = pipe.communicate()
        if pipe.returncode:
            warnx('Could not determine dependencies for port (the error '
                  'message received was: %s)', err)

        # RUN_DEPENDS
        depends = out.split('|')[11].split()

        # XXX: why doesn't .replace(self.portsdir, '') work here?
        self.__depends = map(lambda x: x[len(self.portsdir)+1:], depends)

        return self.__depends

print ' '.join(Package(sys.argv[1], opts=sys.argv[2:]).get_dependencies())

#def main(argv):
#
#    parser = argparse.ArgumentParser()
#
#if __name__ == '__main__':
#    main(sys.argv)
