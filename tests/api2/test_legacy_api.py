import pytest

from middlewared.test.integration.utils import client, session, url


def get_api_versions():
    with session() as s:
        return s.get(f"{url()}/api/versions").json()


@pytest.fixture(scope="module", params=get_api_versions(), ids=lambda v: f"legacy_api_client={v}")
def legacy_api_client(request):
    with client(version=request.param) as c:
        yield c


def get_methods(name: str | None = None):
    with client() as c:
        methods = c.call("core.get_methods")

    if name:
        return filter(lambda m: m.endswith(f".{name}"), methods)

    return methods


@pytest.fixture(scope="module", params=get_methods("query"), ids=lambda m: f"query_method={m}")
def query_method(request):
    yield request.param


@pytest.fixture(scope="module", params=get_methods("config"), ids=lambda m: f"config_method={m}")
def config_method(request):
    yield request.param


def test_query_method(legacy_api_client, query_method):
    version = legacy_api_client._ws.url.split("/")[-1].lstrip("v")
    # Methods that do not exist in the previous API versions
    if version in {"25.04.0", "25.04.1"} and query_method in {
        "vm.query",
        "vm.device.query",
        "zfs.resource.query"
    }:
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
        "zfs.resource.query"
    }:
        return

    legacy_api_client.call(query_method)


def test_config_method(legacy_api_client, config_method):
    version = legacy_api_client._ws.url.split("/")[-1].lstrip("v")
    if config_method == "app.config":
        # Not a ConfigService config method. Requires an argument.
        return

    # Methods that do not exist in 25.04
    if (
        version in {"25.04.0", "25.04.1", "25.04.2"}
        and config_method in {
            "audit.config",
            "auth.twofactor.config",
            "directoryservices.config",
            "kerberos.config",
            "kmip.config",
            "mail.config",
            "network.configuration.config",
            "nvmet.global.config",
            "replication.config.config",
            "ssh.config",
            "support.config",
            "system.advanced.config",
            "system.general.config",
            "systemdataset.config",
            "truecommand.config",
            "update.config",
            "ups.config",
        }
    ):
        return

    legacy_api_client.call(config_method)
