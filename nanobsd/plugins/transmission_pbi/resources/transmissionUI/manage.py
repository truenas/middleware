#!/usr/bin/env python

import os
import sys
import platform

arch = platform.machine()
python_major = sys.version_info.major
python_minor = sys.version_info.minor
python = "python%d.%d" % (python_major, python_minor)

TRANSMISSION_PATH = "/usr/pbi/transmission-%s" % arch
TRANSMISSION_UI = os.path.join(TRANSMISSION_PATH, "transmissionUI")
PYTHON_SITE_PACKAGES = os.path.join(TRANSMISSION_PATH,
    "lib/%s/site-packages" % python)

sys.path.append(PYTHON_SITE_PACKAGES)
sys.path.append(TRANSMISSION_PATH)
sys.path.append(TRANSMISSION_UI)

os.environ["DJANGO_SETTINGS_MODULE"] = "transmissionUI.settings"

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
