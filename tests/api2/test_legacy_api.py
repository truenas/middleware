def test_query_method(legacy_api_client, query_method):
    version = legacy_api_client._ws.url.split("/")[-1].lstrip("v")
    # Methods that do not exist in the previous API versions
    if version in {"25.04.0", "25.04.1"} and query_method in {"vm.query", "vm.device.query"}:
        return

    legacy_api_client.call(query_method)
