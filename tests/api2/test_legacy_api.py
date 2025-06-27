def test_query_method(legacy_api_client, query_method):
    version = legacy_api_client._ws.url.split("/")[-1].lstrip("v")
    # Methods that do not exist in the previous API versions
    if version in {"25.04.0", "25.04.1"} and query_method in {"vm.query", "vm.device.query"}:
        return

    if version in {"25.04.0", "25.04.1", "25.04.2"} and query_method in {
        "audit.query",
        "certificate.query",
        "cloudsync.query",
        "disk.query",
        "dns.query",
        "interface.query",
        "ipmi.lan.query",
        "jbof.query",
        "kerberos.keytab.query",
        "kerberos.realm.query",
        "nvmet.host.query",
        "nvmet.host_subsys.query",
        "nvmet.namespace.query",
        "nvmet.port.query",
        "nvmet.port_subsys.query",
        "nvmet.subsys.query",
        "pool.query",
        "pool.dataset.query",
        "pool.snapshot.query",
        "privilege.query",
        "replication.query",
        "rsynctask.query",
        "service.query",
        "sharing.smb.query",
        "tunable.query",
        "vmware.query",
    }:
        return

    legacy_api_client.call(query_method)
