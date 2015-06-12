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
"""
This module contains generic utilities and configuration information for use
by the other submodules of the `pySMART` package.
"""
# Python built-ins
import ctypes
import os
import platform
from subprocess import Popen, PIPE
import warnings

# Configuration definitions
_min_smartctl_ver = {
    'Windows': {
        'maj': 6,
        'min': 1
        },
    'Linux': {
        'maj': 5,
        'min': 42
        },
    'FreeBSD': {
        'maj': 6,
        'min': 1
        }
    }
"""
(dict of dict of int): Outer dict contains operating system names as keys.
Inner dict has keys 'maj' and 'min' with int values representing the minimum
required major and minor versions, respectively.
"""

OS = platform.system()
"""**(str):** The operating system's name, generally 'Linux' or 'Windows'"""

_req_ma, _req_mi = _min_smartctl_ver[OS]['maj'], _min_smartctl_ver[OS]['min']
"""Major and minor version requirements, parsed from the version string."""

smartctl_type = {
    'ata': 'ata',
    'csmi': 'ata',
    'sas': 'scsi',
    'sat': 'sat',
    'sata': 'ata',
    'scsi': 'scsi',
    'atacam': 'atacam'
}
"""
**(dict of str):** Contains actual interface types (ie: sas, csmi) as keys and
the corresponding smartctl interface type (ie: scsi, ata) as values.
"""


# Helper functions
def admin():
    """Determine whether this scrpt is running with administrative privilege.

    ### Returns:
    * **(bool):** True if running as an administrator, False otherwise.
    """
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    return is_admin


def pd_to_sd(pd):
    """
    Converts a device name from Windows' physical device ID (ie: pd0) to
    Linux's sda notation. Handles up to 'pd675' = 'sdzz'.

    ###Args:
    * **pd (int):** Physical device ID number.

    ##Returns:
    * **(str):** Linux-style 'sd_' device name.
    """
    try:
        pd = int(pd)
    except ValueError:
        return None
    pd2sd = {}
    # Tried to build a list comprehension but Py2.6 on Linux gave syntax error
    for i in range(26):
        pd2sd[i] = chr(ord('a') + i)
    if pd > 26:
        first = (pd // 26) - 1
        second = pd % 26
        return 'sd' + pd2sd[first] + pd2sd[second]
    else:
        return 'sd' + pd2sd[pd]


def rescan_device_busses():
    """Force a rescan of internal storage busses under Windows"""
    cmd = Popen('echo "rescan" | diskpart', shell=True,
                stdout=PIPE, stderr=PIPE)
    _stdout, _stderr = cmd.communicate()


def _warning_on_one_line(message, category, filename, lineno, file=None,
                         line=None):
    """Formats warning messages to appear on one line."""
    return '%s:%s: %s: %s\n' % (filename, lineno, category.__name__, message)
warnings.formatwarning = _warning_on_one_line


def path_append():
    """Appneds the path to smartctl (OS Specific)"""
    if OS == 'FreeBSD':
        os.environ["PATH"] += '/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:' +\
                              '/usr/local/sbin:/usr/local/bin:/root/bin'


path_append()
# Verify smartctl is on the system path and meets the minimum required version
cmd = Popen('smartctl --version', shell=True, stdout=PIPE, stderr=PIPE)
_stdout, _stderr = cmd.communicate()
if _stdout == '':
    raise Exception(
        "Required package 'smartmontools' is not installed, or 'smartctl'\n"
        "component is not on the system path. Please install and try again."
        "The current env path is: {0}".format(os.environ["PATH"]))
else:
    for line in _stdout.split('\n'):
        if 'release' in line:
            _ma, _mi = line.strip().split(' ')[2].split('.')
            if (int(_ma) < _req_ma or
                    (int(_ma) == _req_ma and int(_mi) < _req_mi)):
                raise Exception(
                    "Installed version of smartctl [{0}.{1}] is below the "
                    "minimum requirement of [{2}.{3}]. Please upgrade and "
                    "try again.".format(_ma, _mi, _req_ma, _req_mi))

# Check for admin rights
if not admin():
    warnings.warn(
        "_NOT_ADMIN_: smartctl is intended to be run as administrator/root "
        "and may not detect all device types, or may parse device information "
        "incorrectly, if run without these permissions.")

__all__ = ['admin', 'OS', 'pd_to_sd', 'rescan_device_busses', 'smartctl_type',
           'path_append']
