import pytest
from functions import failed


@pytest.fixture(autouse=True)
def fail_fixture():
    if failed[0] is not None:
        pytest.exit(failed[0], 1)
