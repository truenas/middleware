"""
Copyright (c) 2012 Garrett Cooper, All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL Garrett Cooper OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.
"""

import os
import sys

from distutils.core import setup
try:
    from Cython.Distutils.extension import Extension
    from Cython.Distutils import build_ext

    has_cython = True

except ImportError:
    from distutils.extension import Extension

    has_cython = False


if has_cython:
    srcs = [
              'src/c_sysctl.pxd',
              'src/sysctl.pyx',
           ]
else:
    # Ensure that if cython is not installed, the generated C files exist so
    # the module can be built.

    srcs = [
              'src/sysctl.c',
           ]

    for src in srcs:
        if not os.path.exists(src):
            sys.exit('C sources do not exist; you must install cython first')


kwargs = {
    'name':         'sysctl',
    'version':      '0.1.0',
    'description':  'Cython module for interfacing with sysctl(3) libcalls via python',
    'author':       'Garrett Cooper',
    'author_email': 'yanegomi@gmail.com',
    'url':          'http://gitorious.org/py-sysctl',
    'license':      'BSD 2-clause',
    'ext_modules': [
                     Extension('sysctl',
                     srcs,
                     include_dirs=[
                         'src',
                     ]),
                   ],
}


if has_cython:
    kwargs['cmdclass'] = {
                          'build_ext': build_ext
                         }


if __name__ == '__main__':
    setup(**kwargs)
