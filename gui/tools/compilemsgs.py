import glob
import os
import re
import sys

import polib

LOCALE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "locale",
        )
    )

RE_FORMAT = re.compile(r'\B%\(\w+\)s\b')


def pocompile(src, dest):

    po = polib.pofile(src)
    for entry in po:
        translated = entry.msgstr.encode('ascii', 'ignore')
        if not translated:
            continue

        if 'python-format' not in entry.flags:
            continue

        for fmt in RE_FORMAT.findall(entry.msgid):
            if fmt not in translated:
                if 'fuzzy' not in entry.flags:
                    entry.flags.append('fuzzy')
                break

    #po.save()
    po.save_as_mofile(dest)


def main():

    for popath in glob.glob("%s/*/LC_MESSAGES/*.po" % LOCALE_DIR):
        mopath = popath.rsplit(".", 1)[0] + ".mo"
        pocompile(popath, mopath)


if __name__ == "__main__":
    main()
