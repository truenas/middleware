"""The S3 service's global configuration, the files it renders and the
verb each change costs. The daemon takes most changes on a reload and
silently refuses or half applies the rest, so the tests watch the
service's pid: a reload keeps it, a restart replaces it."""

import contextlib
from configparser import RawConfigParser

import pytest
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, ssh

SERVICE = "truenas_s3"
BUCKETS_CONF = "/etc/truenas_s3/buckets.conf"
POLICIES_CONF = "/etc/truenas_s3/policies.conf"
CREDENTIALS_CONF = "/etc/truenas_s3/credentials.conf"
DROPIN = "/etc/systemd/system/truenas_s3.service.d/override.conf"


def parse(path):
    parser = RawConfigParser(interpolation=None)
    parser.read_string(ssh(f"cat {path}"))
    return {section: dict(parser[section]) for section in parser.sections()}


def service():
    return call("service.query", [["service", "=", SERVICE]], {"get": True})


def audit_licensed():
    return call("system.license") is not None


@contextlib.contextmanager
def running_service():
    assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
    try:
        yield
    finally:
        call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


@contextlib.contextmanager
def config(**changes):
    old = call("s3.config")
    call("s3.update", changes)
    try:
        yield
    finally:
        call("s3.update", {k: old[k] for k in changes})


def test_defaults():
    cfg = call("s3.config")
    assert cfg["bindip"] == []
    assert cfg["port"] == 9000
    assert cfg["servers"] == 1
    assert cfg["certificate"] is None
    assert cfg["region"] == ""
    assert cfg["log_level"] == "NOTICE"
    assert cfg["default_audit"] == []
    assert cfg["default_audit_overflow"] == "DROP"
    assert cfg["global_grants"] == []
    assert "host_id" not in cfg and "owner_id_seed" not in cfg


def test_bindip_choices_and_validation():
    # the choices are the static addresses (the VIPs on HA); a box on DHCP
    # has none, and an address outside them is refused either way
    choices = call("s3.bindip_choices")
    assert isinstance(choices, dict)

    with pytest.raises(ValidationErrors) as ve:
        call("s3.update", {"bindip": ["203.0.113.7"]})
    assert "valid ip address" in ve.value.errors[0].errmsg

    with pytest.raises(ValidationErrors) as ve:
        call("s3.update", {"bindip": ["203.0.113.7", "203.0.113.8"]})
    assert "at most one" in ve.value.errors[0].errmsg


def test_servers_is_bounded_by_the_daemon_and_the_cpus():
    for bad in (0, 9):
        with pytest.raises(ValidationErrors):
            call("s3.update", {"servers": bad})
    cpus = int(ssh("nproc"))
    if cpus < 8:
        with pytest.raises(ValidationErrors) as ve:
            call("s3.update", {"servers": cpus + 1})
        assert f"at most {cpus}" in ve.value.errors[0].errmsg


def test_port_conflict_is_refused():
    with pytest.raises(ValidationErrors) as ve:
        call("s3.update", {"port": 22})
    assert "used by" in ve.value.errors[0].errmsg


def test_rendered_files_on_start():
    """Starting the service renders every file the daemon reads, with the
    identities generated once and the credentials file root-only."""
    with running_service():
        assert service()["state"] == "RUNNING"

        server = parse(BUCKETS_CONF)["server"]
        assert len(server["host_id"]) == 36
        assert len(server["owner_id_seed"]) == 56
        assert server["log_level"] == "notice"
        assert "region" not in server
        assert "tls_cert" not in server

        assert ssh(f"stat -c '%a %U' {CREDENTIALS_CONF}").strip() == "600 root"
        assert parse(POLICIES_CONF) == {}
        assert (
            ssh(f"cat {DROPIN}")
            == "[Service]\nExecStart=\nExecStart=/usr/bin/s3d 0.0.0.0:9000\n"
        )
        assert "@include common-account" in ssh("cat /etc/pam.d/truenas-s3")
        assert ":9000" in ssh("ss -Hltn sport = :9000")

        # the identities never move
        call("s3.update", {"log_level": "INFO"})
        assert parse(BUCKETS_CONF)["server"]["host_id"] == server["host_id"]
        assert parse(BUCKETS_CONF)["server"]["owner_id_seed"] == server["owner_id_seed"]
        call("s3.update", {"log_level": "NOTICE"})


def test_reload_keeps_the_process_and_restart_replaces_it():
    with running_service():
        pid = service()["pids"]
        assert pid

        with config(log_level="DEBUG"):
            assert parse(BUCKETS_CONF)["server"]["log_level"] == "debug"
            assert service()["pids"] == pid, "a log level change is a reload"

        with config(port=9001):
            assert ssh(f"cat {DROPIN}").endswith("s3d 0.0.0.0:9001\n")
            assert service()["pids"] != pid, "a listen address change is a restart"
            assert ":9001" in ssh("ss -Hltn sport = :9001")

        with config(region="us-east-1"):
            assert parse(BUCKETS_CONF)["server"]["region"] == "us-east-1"
            assert service()["state"] == "RUNNING"

        if int(ssh("nproc")) >= 2:
            pid = service()["pids"]
            with config(servers=2):
                assert parse(BUCKETS_CONF)["server"]["servers"] == "2"
                assert service()["pids"] != pid, "a thread count change is a restart"
                # every ring binds the address itself, under SO_REUSEPORT
                assert len(ssh("ss -Hltn sport = :9000").splitlines()) == 2


def test_global_grants_render_as_wildcard_rows():
    with user(
        {
            "username": "s3globaluser",
            "full_name": "global",
            "group_create": True,
            "password": "test1234",
        }
    ) as u:
        with config(
            global_grants=[
                {"principal_type": "USER", "xid": u["uid"], "access": "DENY"}
            ]
        ):
            cfg = call("s3.config")
            assert cfg["global_grants"] == [
                {
                    "principal_type": "USER",
                    "xid": u["uid"],
                    "access": "DENY",
                    "name": "s3globaluser",
                }
            ]
            call("etc.generate", "truenas_s3")
            assert parse(POLICIES_CONF) == {
                'grant user "s3globaluser" "*"': {
                    "xid": str(u["uid"]),
                    "access": "deny",
                },
            }

        for bad, message in (
            (
                [{"principal_type": "EVERYONE", "xid": 5, "access": "READONLY"}],
                "not allowed",
            ),
            ([{"principal_type": "USER", "access": "READONLY"}], "required"),
            (
                [{"principal_type": "USER", "xid": 4294967000, "access": "READONLY"}],
                "No user",
            ),
            (
                [
                    {"principal_type": "USER", "xid": u["uid"], "access": "READONLY"},
                    {"principal_type": "USER", "xid": u["uid"], "access": "DENY"},
                ],
                "only be granted once",
            ),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("s3.update", {"global_grants": bad})
            assert message in ve.value.errors[0].errmsg


def test_audit_follows_the_license():
    if audit_licensed():
        with config(
            default_audit=["GetObject", "PutObject"],
            default_audit_overflow="BACKPRESSURE",
        ):
            call("etc.generate", "truenas_s3")
            server = parse(BUCKETS_CONF)["server"]
            assert server["default_audit"] == "GetObject,PutObject"
            assert server["default_audit_overflow"] == "backpressure"
    else:
        with pytest.raises(ValidationErrors) as ve:
            call("s3.update", {"default_audit": "ALL"})
        assert "Enterprise license" in ve.value.errors[0].errmsg
        call("etc.generate", "truenas_s3")
        assert "default_audit" not in parse(BUCKETS_CONF)["server"]
