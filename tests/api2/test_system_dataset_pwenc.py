# Why SSH: the API hides the datasets under .system and has no call that tests a raw key file. So the tests of
# the index dataset read it, set it and test its key with zfs over SSH. SSH also writes the test secret file.
"""
Tests of the system dataset that the pwenc secret encrypts. TrueSearch keeps its indexes on it. The boot pool cannot
hold an encrypted dataset, so these tests use the pool of the test run. The system dataset is on that pool.
"""

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

PWENC_SECRET = "/data/pwenc_secret"
PWENC_KEY_LOCATION = f"file://{PWENC_SECRET}"
PASSPHRASE = "pwenc-test-passphrase"
# The index dataset has a legacy mountpoint, so nothing mounts it at its creation.
PROPS = {"mountpoint": "legacy"}
# The encryption, keyformat, keylocation and keystatus of a dataset that the pwenc secret of the system encrypts.
PWENC_ENCRYPTED = ["aes-256-gcm", "raw", PWENC_KEY_LOCATION, "available"]


def properties(name, *names):
    """The raw values of the properties `names` of the dataset `name`."""
    [found] = call("zfs.resource.query", {"paths": [name], "properties": list(names)})
    return [found["properties"][n]["raw"] for n in names]


def setup(name, encryption):
    return call("systemdataset.setup_encrypted_dataset", name, PROPS, encryption)


def unload_key(name):
    call("zfs.resource.unload_key", name)


def index_dataset():
    config = call("systemdataset.config")
    return config, f"{config['pool']}/.system/truesearchd"


def index_properties(*names):
    return ssh(f"zfs get -H -o value {','.join(names)} {index_dataset()[1]}").split()


def opens_index(key_location):
    """Whether the key at `key_location` opens the index dataset. ZFS only checks the key."""
    command = f"zfs load-key -n -L {key_location} {index_dataset()[1]}"
    return ssh(command, check=False, complete_response=True)["result"]


@pytest.fixture
def parent():
    """A dataset that holds the datasets of one test. They are deleted with it."""
    with dataset("pwenc_test") as name:
        yield name


@pytest.fixture
def pwenc_dataset(parent):
    """A dataset that the system dataset setup made. The pwenc secret of the system is its key."""
    name = f"{parent}/pwenc"
    assert setup(name, None) is True
    return name


@pytest.fixture
def secret():
    """The pwenc secret of another system, as a configuration upload gives it: 32 random bytes."""
    path = "/var/tmp/pwenc_test_secret"
    ssh(f"head -c 32 /dev/urandom > {path}")
    try:
        yield path
    finally:
        ssh(f"rm -f {path}")


def test_a_missing_dataset_is_made_with_the_pwenc_secret_as_its_key(pwenc_dataset):
    assert properties(pwenc_dataset, "encryption", "keyformat", "keylocation", "keystatus", "encryptionroot") == [
        *PWENC_ENCRYPTED,
        pwenc_dataset,
    ]


def test_a_loaded_key_is_left_alone(pwenc_dataset):
    assert setup(pwenc_dataset, "aes-256-gcm") is False
    assert properties(pwenc_dataset, "keystatus") == ["available"]


def test_the_key_is_loaded_from_the_pwenc_secret(pwenc_dataset):
    unload_key(pwenc_dataset)
    assert setup(pwenc_dataset, "aes-256-gcm") is False
    assert properties(pwenc_dataset, "keystatus") == ["available"]


def test_a_dataset_that_the_pwenc_secret_does_not_unlock_is_refused(pwenc_dataset):
    # Another key encrypts the dataset, as on a pool that a new installation imports.
    call("zfs.resource.encryption.change_key", {"path": pwenc_dataset, "generate_key": True}, job=True)
    unload_key(pwenc_dataset)
    with pytest.raises(CallError, match="does not unlock"):
        setup(pwenc_dataset, "aes-256-gcm")
    assert properties(pwenc_dataset, "keystatus") == ["unavailable"]


def test_a_pool_unlock_leaves_the_index_dataset_to_the_system_dataset(parent, pwenc_dataset):
    # The pool unlock at boot and at failover, its summary, and the pool import take the locked encryption roots from
    # encryption_roots. Only the system dataset setup can load the key of the index dataset.
    other = f"{parent}/other"
    call(
        "pool.dataset.create",
        {
            "name": other,
            "encryption": True,
            "inherit_encryption": False,
            "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        },
    )
    call("pool.dataset.lock", other, job=True)
    unload_key(pwenc_dataset)
    assert list(call("zfs.resource.encryption.encryption_roots", parent, "locked")) == [other]


def test_a_configuration_upload_wraps_the_key_of_the_index_dataset_with_the_new_secret(secret):
    assert not opens_index(f"file://{secret}")
    call("systemdataset.rekey_encrypted_datasets", secret)
    try:
        assert index_properties("keylocation", "keystatus") == [PWENC_KEY_LOCATION, "available"]
        assert opens_index(f"file://{secret}")
        assert not opens_index(PWENC_KEY_LOCATION)
    finally:
        call("systemdataset.rekey_encrypted_datasets", PWENC_SECRET)

    assert opens_index(PWENC_KEY_LOCATION)


def test_the_system_dataset_setup_sets_the_properties_of_the_index_dataset_again():
    config, index = index_dataset()
    ssh(f"zfs set atime=on {index}")
    assert index in [ds["name"] for ds in call("systemdataset.setup_datasets", config["pool"], config["uuid"])]
    assert index_properties("atime") == ["off"]
