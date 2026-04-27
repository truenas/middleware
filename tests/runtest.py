#!/usr/bin/env python3
import os
import sys

from middlewared.test.integration.runner.run import run

workdir = os.getcwd()
sys.path.append(workdir)

run(workdir)
