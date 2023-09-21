__all__ = ["fail"]

failed = [None]


def fail(reason):
    """
    Prematurely abort the whole test suite execution, failing the test where this function is called
    (as opposed to just using `pytest.exit` which will not fail the test, and, if no previous tests failed, junit
    Jenkins plugin will display the test suite as green)
    """
    failed[0] = reason
    assert False, reason
