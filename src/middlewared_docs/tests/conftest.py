# -*- coding=utf-8 -*-
import os
import sys

# Make the package modules (changelog.py, ...) importable without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
