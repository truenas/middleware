#+
# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
from collections import OrderedDict

IEC_MAP = OrderedDict((
    ('PiB', 1125899906842624.0),
    ('TiB', 1099511627776.0),
    ('GiB', 1073741824.0),
    ('MiB', 1048576.0),
    ('KiB', 1024.0),
    ('B', 1),
))


SI_MAP = OrderedDict((
    ('PB', 1000000000000000.0),
    ('TB', 1000000000000.0),
    ('GB', 1000000000.0),
    ('MB', 1000000.0),
    ('kB', 1000.0),
    ('B', 1),
))


def __humanize_number_common(number, maptbl):
    number = int(number)
    for suffix, factor in maptbl.items():
        if number > factor:
            return ('%.1f %s' % (number / factor, suffix))
    return number


# The hard drive industry is using SI (10^n) rather than 2^n
def humanize_number_si(number):
    return (__humanize_number_common(int(number), SI_MAP))


def humanize_size(number):
    return (__humanize_number_common(int(number), IEC_MAP))
