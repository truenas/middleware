#!/usr/bin/env python
import sys
import os

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(HERE, ".."))


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fireflyUI.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
