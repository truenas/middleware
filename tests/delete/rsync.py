#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE


class rsync_test(unittest.TestCase):

    def test_01_Delete_rsync_resource(self):
        assert DELETE("/services/rsyncmod/1/") == 204

if __name__ == "__main__":
    unittest.main(verbosity=2)
