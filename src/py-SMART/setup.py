# Copyright (C) 2014 Marc Herndon
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License,
# version 2, as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.
#
################################################################
from distutils.core import setup
import os
import re


def read_file(path):
    with open(os.path.join(os.path.dirname(__file__), path)) as fp:
        return fp.read()


def _get_version_match(content):
    # Search for lines of the form: # __version__ = 'ver'
    regex = r"^__version__ = ['\"]([^'\"]*)['\"]"
    version_match = re.search(regex, content, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string in '__init__.py'.")


def get_version(path):
    return _get_version_match(read_file(path))

setup(
    name='pySMART',
    version=get_version(os.path.join('pySMART', '__init__.py')),
    author='Marc Herndon',
    author_email='Herndon.MarcT@gmail.com',
    packages=['pySMART'],
    url='none',
    license='GNU LGPLv2.1.html',
    description='Wrapper for smartctl (smartmontools)',
    long_description=open('README.txt').read(),
)
