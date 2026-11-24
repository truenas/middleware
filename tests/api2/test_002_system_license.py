from middlewared.test.integration.utils import ha_test
from middlewared.test.integration.utils.server_setup import apply_and_verify_license


@ha_test
def test_apply_and_verify_license():
    apply_and_verify_license()
