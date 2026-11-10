"""
Tests of the system dataset that is encrypted with the pwenc secret. TrueSearch keeps its indexes on it.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import middlewared.plugins.sysdataset as sysdataset_plugin
from middlewared.plugins.sysdataset import SystemDatasetService
from middlewared.plugins.system_dataset import encryption
from middlewared.plugins.system_dataset.hierarchy import get_system_dataset_spec
from middlewared.plugins.zfs import encryption_info
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import CallError

INDEX_DATASET = "tank/.system/truesearchd"
KEY_LOCATION = "file:///data/pwenc_secret"
PROPS = {"atime": "off", "mountpoint": "legacy"}


def test_only_the_index_dataset_is_encrypted_with_the_pwenc_secret():
    spec = get_system_dataset_spec("tank", "uuid")
    assert [ds["name"] for ds in spec if ds.get("pwenc_encrypted")] == [INDEX_DATASET]


def test_a_pool_unlock_leaves_the_index_dataset_to_the_system_dataset(monkeypatch):
    # The pool unlock at boot and at failover, its summary, and the pool import take the locked encryption roots from
    # encryption_roots. Only the system dataset setup can load the key of the index dataset.
    def locked_root(name, keyformat, keylocation):
        return {
            "name": name,
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {"raw": "legacy"},
                "encryption": {"raw": "aes-256-gcm"},
                "encryptionroot": {"value": name},
                "keyformat": {"raw": keyformat},
                "keystatus": {"raw": "unavailable"},
                "keylocation": {"raw": keylocation},
            },
        }

    rows = [locked_root("tank/secret", "hex", "prompt"), locked_root(INDEX_DATASET, "raw", KEY_LOCATION)]
    monkeypatch.setattr(encryption_info._query, "list_impl", lambda context, tls, query: rows)
    monkeypatch.setattr(encryption_info, "stored_keys", lambda context, filters: {"tank/secret": "ab" * 32})
    assert list(encryption_info.encryption_roots(None, None, "tank", "locked")) == ["tank/secret"]


@pytest.fixture
def zfs(monkeypatch):
    """
    Stand-ins for the ZFS calls of setup_pwenc_dataset. Set `loaded` if the key of the dataset is loaded. Set
    `unlocks` if the pwenc secret unlocks the dataset.
    """
    state = SimpleNamespace(loaded=False, unlocks=True, created=[], loaded_from=[])
    crypto = Mock()
    crypto.info.side_effect = lambda: SimpleNamespace(key_is_loaded=state.loaded)
    monkeypatch.setattr(encryption, "open_resource", lambda tls, name: SimpleNamespace(crypto=lambda: crypto))
    monkeypatch.setattr(encryption, "check_key", lambda tls, name, key_location: state.unlocks)
    monkeypatch.setattr(
        encryption,
        "load_key",
        lambda tls, name, key_location: state.loaded_from.append(key_location),
    )
    monkeypatch.setattr(
        encryption,
        "create_leaf",
        lambda tls, name, type_, props, user_props, crypto: state.created.append((name, type_, props, crypto)),
    )
    state.tls = SimpleNamespace(lzh=Mock(resource_cryptography_config=Mock(return_value="raw key")))
    state.setup = lambda value: encryption.setup_pwenc_dataset(state.tls, INDEX_DATASET, PROPS, value)
    return state


def test_a_missing_dataset_is_made_with_the_pwenc_secret_as_its_key(zfs):
    assert zfs.setup(None) is True
    zfs.tls.lzh.resource_cryptography_config.assert_called_once_with(keyformat="raw", keylocation=KEY_LOCATION)
    assert zfs.created == [(INDEX_DATASET, "FILESYSTEM", PROPS, "raw key")]


def test_a_dataset_that_is_not_encrypted_is_refused(zfs):
    with pytest.raises(CallError, match="is not encrypted. Destroy it"):
        zfs.setup("off")
    assert zfs.created == []


def test_a_loaded_key_is_left_alone(zfs):
    zfs.loaded = True
    assert zfs.setup("aes-256-gcm") is False
    assert (zfs.loaded_from, zfs.created) == ([], [])


def test_the_key_is_loaded_from_the_pwenc_secret(zfs):
    assert zfs.setup("aes-256-gcm") is False
    assert zfs.loaded_from == [KEY_LOCATION]
    assert zfs.created == []


def test_a_dataset_that_the_pwenc_secret_does_not_unlock_is_refused(zfs):
    # The pwenc secret changed without a configuration upload, for example on a new installation that imports the
    # pool.
    zfs.unlocks = False
    with pytest.raises(CallError, match="does not unlock"):
        zfs.setup("aes-256-gcm")
    assert (zfs.loaded_from, zfs.created) == ([], [])


def test_a_rekey_wraps_the_key_with_the_new_secret_and_keeps_the_key_location(monkeypatch):
    calls = []
    monkeypatch.setattr(encryption, "change_key", lambda tls, name, properties: calls.append((name, properties)))
    monkeypatch.setattr(
        encryption,
        "open_resource",
        lambda tls, name: SimpleNamespace(set_properties=lambda properties: calls.append((name, properties))),
    )
    encryption.rekey_pwenc_dataset(None, INDEX_DATASET, "/data/pwenc_secret_uploaded")
    assert calls == [
        (INDEX_DATASET, {"keyformat": "raw", "keylocation": "file:///data/pwenc_secret_uploaded"}),
        (INDEX_DATASET, {"keylocation": KEY_LOCATION}),
    ]


@pytest.mark.parametrize(
    "uploaded,rekeyed",
    [
        (b"a" * 32, False),
        (b"b" * 32, True),
        # A configuration reset uploads no secret.
        (None, False),
    ],
)
def test_a_configuration_upload_with_another_secret_rekeys_the_index_dataset(monkeypatch, tmp_path, uploaded, rekeyed):
    secret = tmp_path / "pwenc_secret"
    secret.write_bytes(b"a" * 32)
    upload = tmp_path / "pwenc_secret_uploaded"
    if uploaded is not None:
        upload.write_bytes(uploaded)
    monkeypatch.setattr(sysdataset_plugin, "PWENC_FILE_SECRET", str(secret))
    monkeypatch.setattr(sysdataset_plugin, "PWENC_UPLOADED", str(upload))
    m = Middleware()
    m["systemdataset.rekey_encrypted_datasets"] = Mock()
    sysdataset_plugin.on_config_upload(m, "/data/uploaded.db")
    calls = m["systemdataset.rekey_encrypted_datasets"].call_args_list
    assert [c.args for c in calls] == ([(str(upload),)] if rekeyed else [])


def index_dataset_row(keystatus="available"):
    """The encryption properties of the index dataset, as zfs.resource.list_impl gives them."""
    return {
        "name": INDEX_DATASET,
        "properties": {
            "encryption": {"raw": "aes-256-gcm"},
            "keyformat": {"raw": "raw"},
            "keylocation": {"raw": KEY_LOCATION},
            "keystatus": {"raw": keystatus},
        },
    }


@pytest.mark.parametrize(
    "pool,imported,found,rekeyed",
    [
        ("tank", ["boot-pool", "tank"], [index_dataset_row()], [INDEX_DATASET]),
        # The standby controller has not imported the pool.
        ("tank", ["boot-pool"], [index_dataset_row()], []),
        # The datasets on the boot pool are not encrypted.
        ("boot-pool", ["boot-pool"], [], []),
        # A dataset that does not exist is made with the new secret at the next boot.
        ("tank", ["boot-pool", "tank"], [], []),
        # A locked dataset cannot be wrapped again. It can be encrypted with the new secret already.
        ("tank", ["boot-pool", "tank"], [index_dataset_row("unavailable")], []),
    ],
)
def test_a_rekey_wraps_only_a_loaded_key_on_the_node_with_the_pool(monkeypatch, pool, imported, found, rekeyed):
    m = Middleware()
    m["systemdataset.config"] = Mock(return_value={"pool": pool, "uuid": "uuid"})
    m.services.boot.pool_name = Mock(return_value="boot-pool")
    m.services.zfs.resource.list_impl = Mock(return_value=found)
    monkeypatch.setattr(
        sysdataset_plugin, "query_imported_fast_impl", lambda: {name: {"name": name} for name in imported}
    )
    done = []
    monkeypatch.setattr(sysdataset_plugin, "rekey_pwenc_dataset", lambda tls, name, secret_path: done.append(name))
    SystemDatasetService(m).rekey_encrypted_datasets(None, "/data/pwenc_secret_uploaded")
    assert done == rekeyed
    queried = [c.args[0].paths for c in m.services.zfs.resource.list_impl.call_args_list]
    assert queried == ([[INDEX_DATASET]] if pool == "tank" and "tank" in imported else [])


def test_a_release_stops_a_daemon_that_runs_alone_and_starts_it_after_a_failure(monkeypatch):
    m = Middleware()
    # The truesearch service is stopped, because one daemon is down. The other daemon still holds the index files.
    m.services.service.started = Mock(return_value=False)
    m.services.service.control = Mock()
    m.services.truesearch.alive = Mock(return_value=True)
    m.services.truesearch.configure = Mock()
    monkeypatch.setattr(sysdataset_plugin, "close_sysdataset_tdb_handles", lambda: None)
    with pytest.raises(OSError):
        with SystemDatasetService(m).release_system_dataset():
            raise OSError("the swap failed")

    assert ("STOP", "truesearch") in [c.args for c in m.services.service.control.call_args_list]
    m.services.truesearch.configure.assert_called_once_with()


def sysdataset(pool="tank", passphrase=False, existing=None, setup=None):
    """
    A system dataset service with stand-ins for its ZFS calls. `existing` holds the properties of the datasets that
    exist, by name. `setup` stands in for setup_encrypted_dataset.
    """
    m = Middleware()
    m.services.boot.pool_name = AsyncMock(return_value="boot-pool")
    root = {
        "encryption": {"raw": "aes-256-gcm" if passphrase else "off"},
        "keyformat": {"raw": "passphrase"},
        "keylocation": {"raw": "prompt"},
        "keystatus": {"raw": "available"},
    }

    def list_impl(query):
        if query.paths == [pool]:
            return [{"name": pool, "properties": root}]
        return [
            {"name": name, "properties": properties}
            for name, properties in (existing or {}).items()
            if name in query.paths
        ]

    m.services.zfs.resource.list_impl = AsyncMock(side_effect=list_impl)
    m.services.zfs.resource.create_impl = AsyncMock()
    m.services.zfs.resource.set_impl = AsyncMock()
    m["systemdataset.setup_encrypted_dataset"] = setup or AsyncMock(return_value=True)
    return m, SystemDatasetService(m)


def created(m):
    return {call.args[0].path: call.args[0] for call in m.services.zfs.resource.create_impl.call_args_list}


@pytest.mark.asyncio
async def test_the_index_dataset_is_set_up_with_its_key_on_a_data_pool():
    m, svc = sysdataset()
    spec = await svc.setup_datasets("tank", "uuid")
    setup = m["systemdataset.setup_encrypted_dataset"]
    setup.assert_awaited_once()
    assert setup.await_args.args[0] == INDEX_DATASET
    assert setup.await_args.args[2] is None
    assert INDEX_DATASET not in created(m)
    assert INDEX_DATASET in [ds["name"] for ds in spec]


@pytest.mark.asyncio
async def test_a_passphrase_pool_does_not_turn_off_the_encryption_of_the_index_dataset():
    m, svc = sysdataset(passphrase=True)
    await svc.setup_datasets("tank", "uuid")
    assert "encryption" not in m["systemdataset.setup_encrypted_dataset"].await_args.args[1]
    assert created(m)["tank/.system"].properties.encryption == "off"


@pytest.mark.asyncio
async def test_the_index_dataset_is_not_encrypted_on_the_boot_pool():
    m, svc = sysdataset(pool="boot-pool")
    await svc.setup_datasets("boot-pool", "uuid")
    m["systemdataset.setup_encrypted_dataset"].assert_not_awaited()
    assert "boot-pool/.system/truesearchd" in created(m)


@pytest.mark.asyncio
async def test_an_index_dataset_that_cannot_be_set_up_is_left_out():
    m, svc = sysdataset(setup=AsyncMock(side_effect=CallError(f"The pwenc secret does not unlock {INDEX_DATASET}.")))
    names = [ds["name"] for ds in await svc.setup_datasets("tank", "uuid")]
    # It is not mounted, so truesearchd and truesearch-indexer do not start.
    assert INDEX_DATASET not in names
    assert "tank/.system" in names


@pytest.mark.asyncio
async def test_the_properties_of_an_existing_index_dataset_are_updated():
    spec = next(ds for ds in get_system_dataset_spec("tank", "uuid") if ds["name"] == INDEX_DATASET)
    properties = {str(name): {"raw": value} for name, value in spec["props"].items()}
    properties |= {"atime": {"raw": "on"}, "encryption": {"raw": "aes-256-gcm"}}
    m, svc = sysdataset(existing={INDEX_DATASET: properties}, setup=AsyncMock(return_value=False))
    await svc.setup_datasets("tank", "uuid")
    assert m["systemdataset.setup_encrypted_dataset"].await_args.args[2] == "aes-256-gcm"
    [update] = [
        call.args[0] for call in m.services.zfs.resource.set_impl.call_args_list if call.args[0].path == INDEX_DATASET
    ]
    assert update.properties.atime == "off"
