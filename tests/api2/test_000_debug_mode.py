import os
import sys
sys.path.append(os.getcwd())
from functions import POST
from auto_config import ha, debug_mode


def test_set_debug_mode():
    results = POST("/core/set_debug_mode/", debug_mode, controller_a=ha)
    assert results.status_code == 200, results
