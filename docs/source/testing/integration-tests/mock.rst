Mocking Middleware Methods In Integration Tests
===============================================

Integration tests should be executed as closely to the real-world deployment conditions as possible. However, it's not
always feasible to simulate all existing hardware configurations on testing VMs. For example, we won't be able to test
that CPU temperature graphs are working because the VM does not expose CPU temperature sensors to the guest. However,
we can mock the middleware method that provides CPU temperatures to make it return fake values and this way we should
get non-empty CPU temperature graphs even on a VM.

Using middleware method mock is similar to using standard `unittest.mock` package:

.. code-block:: python

    from middlewared.test.integration.utils import mock

    def test_cpu_temperatures():
        with mock("reporting.cpu_temperatures", return_value={"0": 55, "1": 50}):
            assert len(call("reporting.cpu_temperatures")) > 0

More sophisticated mock methods can be provided by passing python code string:

.. code-block:: python

    def test_nfs_client_count():
        with mock("nfs.client_count", """
            i = 1
            def mock(self):
                global i
                try:
                    return i
                finally:
                    i *= 2
        """):
            assert call("nfs.client_count") == 1
            assert call("nfs.client_count") == 2
            assert call("nfs.client_count") == 4

Mock function can be `async` and call other middleware methods:

.. code-block:: python

    def test_pool_dataset_query():
    with mock("pool.dataset.query", """
        async def mock(self):
            return [
                {"id": pool["name"], "type": "FILESYSTEM"}
                for pool in await self.middleware.call("pool.query")
            ]
    """):
        assert call("pool.dataset.query") == [{"id": "tank", "type": "FILESYSTEM"}]

Jobs can be mocked as well:

.. code-block:: python

    def test_sync_catalogs():
        with mock("catalog.sync_all", """
            async def mock(self, job):
                job.set_progress(100, "Done")
                return [{"name": "main"}]
        """):
            assert call("catalog.sync_all", job=True) == [{"name": "main"}]

.. automodule:: middlewared.test.integration.utils.mock
   :members:
