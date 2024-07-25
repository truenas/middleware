from middlewared.test.integration.utils import mock, call


def test_client_exception():
    with mock("test.test1", """
        def mock(self, *args):
            # endpoint doesn't exist
            broken = self.middleware.call_sync('activedirectory.get_state')
            return "canary"
    """):
        call("test.test1")
