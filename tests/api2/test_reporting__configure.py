import pytest

from middlewared.test.integration.utils import call, ssh


@pytest.fixture(autouse=True, scope="module")
def stop_collectd_rrdcached():
    ssh("systemctl stop collectd")
    ssh("systemctl stop rrdcached")
    yield
    ssh("systemctl start rrdcached")
    ssh("systemctl start collectd")


def rrd_mount():
    systemdatasetconfig = call("systemdataset.config")
    return f'{systemdatasetconfig["path"]}/rrd-{systemdatasetconfig["uuid"]}'


def setup_stage0():
    # Ensures `/var/db/collectd/rrd` is a proper system dataset link
    ssh(f"rm -rf {rrd_mount()}/*")
    ssh("rm -rf /var/db/collectd")
    ssh("mkdir /var/db/collectd")
    ssh(f"ln -s {rrd_mount()} /var/db/collectd/rrd")


def assert_reporting_setup():
    assert call("reporting.setup")

    assert ssh("[ -L /var/db/collectd/rrd ] && echo OK").strip() == "OK"
    assert ssh("readlink /var/db/collectd/rrd").strip() == rrd_mount()

    hostname = call("reporting.hostname")
    assert set(ssh("ls -1 /var/db/collectd/rrd/").split()) - {"journal"} == {"localhost", hostname}
    assert ssh("[ -d /var/db/collectd/rrd/localhost ] && echo OK").strip() == "OK"
    assert ssh(f"[ -L /var/db/collectd/rrd/{hostname} ] && echo OK").strip() == "OK"
    assert ssh(f"readlink /var/db/collectd/rrd/{hostname}").strip() == "/var/db/collectd/rrd/localhost"


def test__sets_up_from_scratch():
    ssh(f"rm -rf {rrd_mount()}/*")
    ssh("rm -rf /var/db/collectd")

    assert_reporting_setup()


def test__sets_up_from_invalid_link():
    ssh(f"rm -rf {rrd_mount()}/*")
    ssh("rm -rf /var/db/collectd")
    ssh("mkdir /var/db/collectd")
    ssh("ln -s /mnt /var/db/collectd/rrd")

    assert_reporting_setup()


def test__sets_up_with_already_existing_directory():
    ssh(f"rm -rf {rrd_mount()}/*")
    ssh("rm -rf /var/db/collectd")
    ssh("mkdir -p /var/db/collectd/rrd/some-data")

    assert_reporting_setup()


def test__sets_up_when_stage0_already_set_up():
    setup_stage0()

    assert_reporting_setup()


def test__sets_up_removes_localhost_symlink():
    setup_stage0()
    ssh("ln -s /mnt /var/db/collectd/rrd/localhost")

    assert_reporting_setup()


def test__sets_up_removes_invalid_directory():
    setup_stage0()
    ssh("mkdir -p /var/db/collectd/rrd/invalidhostname.invaliddomain/data")

    assert_reporting_setup()


def test__sets_up_removes_invalid_symlink():
    setup_stage0()
    ssh("ln -s /mnt /var/db/collectd/rrd/invalidhostname.invaliddomain")

    assert_reporting_setup()


def test__sets_up_keeps_existing_data():
    setup_stage0()
    ssh("mkdir -p /var/db/collectd/rrd/journal")
    ssh("sh -c 'echo 1 > /var/db/collectd/rrd/journal/file'")
    ssh("mkdir -p /var/db/collectd/rrd/localhost")
    ssh("sh -c 'echo 1 > /var/db/collectd/rrd/localhost/file'")

    assert_reporting_setup()

    assert ssh("cat /var/db/collectd/rrd/journal/file") == "1\n"
    assert ssh("cat /var/db/collectd/rrd/localhost/file") == "1\n"
