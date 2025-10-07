import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import client, session, url


def get_api_versions():
    with session() as s:
        return s.get(f"{url()}/api/versions").json()


@pytest.fixture(scope="module", params=get_api_versions(), ids=lambda v: f"legacy_api_client={v}")
def legacy_api_client(request):
    with client(version=request.param) as c:
        yield c, c._ws.url.split("/")[-1].lstrip("v")


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


@pytest.fixture(scope="module")
def misc_methods() -> list[tuple[tuple, str]]:
    """Add methods to this list to test calling them through previous API versions.

    `((method_name, method_args...), earliest_version_to_test)`

    Remove methods from this list if they are removed from the current API version.    

    """
    return [
        (("fcport.status",), "25.04.0"),
    ]


def test_query_method(legacy_api_client, query_method):
    client, version = legacy_api_client
    # Methods that do not exist in the previous API versions
    if version in {"25.04.0", "25.04.1"} and query_method in {
        "vm.query",
        "vm.device.query",
        "zfs.resource.query"
    }:
        return

    if version in {"25.04.0", "25.04.1", "25.04.2", "25.10.0"} and query_method in {
        "audit.query",
        "certificate.query",
        "cloudsync.query",
        "container.query",
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

    client.call(query_method)


def test_config_method(legacy_api_client, config_method):
    client, version = legacy_api_client
    if config_method == "app.config":
        # Not a ConfigService config method. Requires an argument.
        return

    if (
        # Methods that do not exist in 25.04
        version in {"25.04.0", "25.04.1", "25.04.2"}
        and config_method in {
            "audit.config",
            "auth.twofactor.config",
            "directoryservices.config",
            "kerberos.config",
            "kmip.config",
            "lxc.config",
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

    if (
        # Methods that do not exist in 25.10
        version in {"25.10.0"}
        and config_method in {
            "lxc.config",
        }
    ):
        return

    client.call(config_method)


def test_misc_methods(legacy_api_client, misc_methods):
    """General test for calling any other methods using previous API versions."""
    client, version = legacy_api_client
    exceptions = []
    for args, vers in misc_methods:
        if version >= vers:
            try:
                client.call(*args)
            except Exception as exc:
                exceptions.append(CallError(f"method call: {args}, version: {vers}, error: {str(exc)}"))
    if exceptions:
        raise ExceptionGroup("One or more methods failed backwards compatibility", exceptions)
