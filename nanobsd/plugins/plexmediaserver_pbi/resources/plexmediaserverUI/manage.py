#!/usr/bin/env python

import os
import sys
import platform

arch = platform.machine()
python_major = sys.version_info.major
python_minor = sys.version_info.minor
python = "python%d.%d" % (python_major, python_minor)

PLEXMEDIASERVER_PATH = "/usr/pbi/plexmediaserver-%s" % arch
PLEXMEDIASERVER_UI = os.path.join(PLEXMEDIASERVER_PATH, "plexmediaserverUI")
PYTHON_SITE_PACKAGES = os.path.join(PLEXMEDIASERVER_PATH,
    "lib/%s/site-packages" % python)

sys.path.append(PYTHON_SITE_PACKAGES)
sys.path.append(PLEXMEDIASERVER_PATH)
sys.path.append(PLEXMEDIASERVER_UI)

os.environ["DJANGO_SETTINGS_MODULE"] = "plexmediaserverUI.settings"

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
