# Copyright 2012 iXsystems, Inc.
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
import glob
import os
import re

import polib

LOCALE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "locale",
    )
)

RE_SIMPLE = re.compile(r'\B%[sfd]\b')
RE_FORMAT = re.compile(r'\B%\(\w+\)s\b')


def pocompile(src, dest):

    po = polib.pofile(src)
    for entry in po:
        translated = entry.msgstr.encode('ascii', 'ignore').decode('ascii')
        if not translated:
            continue

        if '%' not in entry.msgid:
            continue

        # Make sure the format is the same in the translated str
        if entry.msgid.count('%') != entry.msgstr.count('%'):
            if 'fuzzy' not in entry.flags:
                entry.flags.append('fuzzy')
            continue

        for fmt in RE_FORMAT.findall(entry.msgid):
            if fmt not in translated:
                if 'fuzzy' not in entry.flags:
                    entry.flags.append('fuzzy')
                break

        tmp = entry.msgid
        for fmt in RE_SIMPLE.findall(tmp):
            if fmt not in translated:
                if 'fuzzy' not in entry.flags:
                    entry.flags.append('fuzzy')
                break
            else:
                tmp = tmp.replace(fmt, '', 1)

    po.save_as_mofile(dest)


def main():

    for popath in glob.glob("%s/*/LC_MESSAGES/*.po" % LOCALE_DIR):
        mopath = popath.rsplit(".", 1)[0] + ".mo"
        pocompile(popath, mopath)


if __name__ == "__main__":
    main()
