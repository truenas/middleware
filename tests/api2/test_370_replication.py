#!/usr/bin/env python3
import os
import random
import string
import sys
import textwrap
import pytest
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

from middlewared.test.integration.utils import call

BASE_REPLICATION = {
    "direction": "PUSH",
    "transport": "LOCAL",
    "source_datasets": ["data"],
    "target_dataset": "data",
    "recursive": False,
    "auto": False,
    "retention_policy": "NONE",
}


@pytest.fixture(scope="module")
def credentials():
    return {}


@pytest.fixture(scope="module")
def periodic_snapshot_tasks():
    return {}


def test_00_bootstrap(request, credentials, periodic_snapshot_tasks):
    depends(request, ["pool_04"], scope="session")
    for plugin in ["replication", "pool/snapshottask"]:
        for i in GET(f"/{plugin}/").json():
            assert DELETE(f"/{plugin}/id/{i['id']}").status_code == 200
    for i in GET("/keychaincredential/").json():
        DELETE(f"/keychaincredential/id/{i['id']}")
    for i in GET("/keychaincredential/").json():
        assert DELETE(f"/keychaincredential/id/{i['id']}").status_code == 200

    result = POST("/keychaincredential/", {
        "name": "SSH Key Pair",
        "type": "SSH_KEY_PAIR",
        "attributes": {
            "private_key": textwrap.dedent("""\
                -----BEGIN RSA PRIVATE KEY-----
                MIIEowIBAAKCAQEA6+D7AWdNnM8T5f2P1j5VIwVABjugtL252iEhhGWTNaR2duCK
                kuZmG3+o55b0vo2mUpjWt+CKsLkVL/e/JgZqzlHYm+MhRs4q7zODo/IEtx/uAVKM
                zqWS0Zs9NRdU1UnhsETjrhhQhNFwx7MUYlB2s8+mAduLbeqRuVIKsXzg5Rz+m3VL
                Wl4R82A10oZl0UPyIcEHAtHMgMVyGzQcNUsxsp/oN40nnkXiXHaXtSMxjEtOPLno
                t21bJ0ZV8RFmXtJqHXgyTTM5maJM3JwqhMHD2tcHodqCcnxvuuWv31pAB+HKQ8IM
                dORYnhZqqs/Bt80gRLQuJBpNeX2/cKPDDMCRnQIDAQABAoIBAQCil6+N9R5rw9Ys
                iA85GDhpbnoGkd2iGNHeiU3oTHgf1uEN6pO61PR3ahUMpmLIYy3N66q+jxoq3Tm8
                meL6HBxNYd+U/Qh4HS89OV45iV80t97ArJ2A6GL+9ypGyXFhoI7giWwEGqCOHSzH
                iyq25k4cfjspNqOyval7fBEA7Vq8smAMDJQE7WIJWzqrTbVAmVf9ho4r5dYxYBNW
                fXWo84DU8K+p0mE0BTokqqMWhKiA5JJG7OZB/iyeW2BWFOdASXvQmh1hRwMzpU4q
                BcZ7cJHz248SNSGMe5R3w7SmLO7PRr1/QkktJNdFmT7o/RGmQh8+KHql6r/vIzMM
                ci60OAxlAoGBAPYsZJZF3HK70fK3kARSzOD1LEVBDTCLnpVVzMSp6thG8cQqfCI5
                pCfT/NcUsCAP6J+yl6dqdtonXISmGolI1s1KCBihs5D4jEdjbg9KbKh68AsHXaD3
                v5L3POJ9hQnI6zJdvCfxniHdUArfyYhqsp1bnCn+85g4ed7BzDqMX2IDAoGBAPVL
                Y45rALw7lsjxJndyFdffJtyAeuwxgJNwWGuY21xhwqPbuwsgLHsGerHNKB5QAJT8
                JOlrcrfC13s6Tt4wmIy/o2h1p9tMaitmVR6pJzEfHyJhSRTbeFybQ9yqlKHuk2tI
                jcUZV/59cyRrjhPKWoVym3Fh/P7D1t1kfdTvBrvfAoGAUH0rVkb5UTo/5xBFsmQw
                QM1o8CvY2CqOa11mWlcERjrMCcuqUrZuCeeyH9DP1WveL3kBROf2fFWqVmTJAGIk
                eXLfOs6EG75of17vOWioJl4r5i8+WccniDH2YkeQHCbpX8puHtFNVt05spSBHG1m
                gTTW1pRZqUet8TuEPxBuj2kCgYAVjCrRruqgnmdvfWeQpI/wp6SlSBAEQZD24q6R
                vRq/8cKEXGAA6TGfGQGcLtZwWzzB2ahwbMTmCZKeO5AECqbL7mWvXm6BYCQPbeza
                Raews/grL/qYf3MCR41djAqEcw22Jeh2QPSu4VxE/cG8UVFEWb335tCvnIp6ZkJ7
                ewfPZwKBgEnc8HH1aq8IJ6vRBePNu6M9ON6PB9qW+ZHHcy47bcGogvYRQk1Ng77G
                LdZpyjWzzmb0Z4kjEYcrlGdbNQf9iaT0r+SJPzwBDG15+fRqK7EJI00UhjB0T67M
                otrkElxOBGqHSOl0jfUBrpSkSHiy0kDc3/cTAWKn0gowaznSlR9N
                -----END RSA PRIVATE KEY-----
            """)
        },
    })
    assert result.status_code == 200, result.text

    result = POST("/keychaincredential/", {
        "name": "SSH Credentials",
        "type": "SSH_CREDENTIALS",
        "attributes": {
            "host": "localhost",
            "private_key": result.json()["id"],
            "remote_host_key": "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBB5fBj8hpYu+"
                               "ts0pvDbjKOGwxRaSHqJMjo2MxkNkgn2VfG7tHq/KWmoXh/PdRu3h/b7mLrAJ1k7ZDJE1+A1MHXc=",
        },
    })
    assert result.status_code == 200, result.text
    credentials.update(**result.json())

    for k, v in {
        "data-recursive": {
            "dataset": "tank/data",
            "recursive": True,
            "lifetime_value": 1,
            "lifetime_unit": "WEEK",
            "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
            "schedule": {},
        },
        "data-work-nonrecursive": {
            "dataset": "tank/data/work",
            "recursive": False,
            "lifetime_value": 1,
            "lifetime_unit": "WEEK",
            "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
            "schedule": {},
        },

        "exclude": {
            "dataset": "tank/exclude",
            "recursive": True,
            "exclude": ["tank/exclude/work/garbage"],
            "lifetime_value": 1,
            "lifetime_unit": "WEEK",
            "naming_schema": "snap-%Y%m%d-%H%M-1w",
            "schedule": {},
        },
    }.items():
        POST("/pool/dataset/", {"name": v["dataset"]})

        result = POST("/pool/snapshottask/", v)
        assert result.status_code == 200, result.text

        periodic_snapshot_tasks[k] = result.json()


@pytest.mark.parametrize("req,error", [
    # Push + naming-schema
    (dict(naming_schema=["snap-%Y%m%d-%H%M-1m"]), "naming_schema"),

    # Auto with both periodic snapshot task and schedule
    (dict(periodic_snapshot_tasks=["data-recursive"], schedule={"minute": "*/2"}, auto=True), None),
    # Auto with periodic snapshot task
    (dict(periodic_snapshot_tasks=["data-recursive"], auto=True), None),
    # Auto with schedule
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-2m"], schedule={"minute": "*/2"}, auto=True), None),
    # Auto without periodic snapshot task or schedule
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-2m"], auto=True), "auto"),

    # Pull + periodic snapshot tasks
    (dict(direction="PULL", periodic_snapshot_tasks=["data-recursive"]), "periodic_snapshot_tasks"),
    # Pull with naming schema
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"]), None),
    # Pull + also_include_naming_schema
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"], also_include_naming_schema=["snap-%Y%m%d-%H%M-2m"]),
     "also_include_naming_schema"),
    # Pull + hold_pending_snapshots
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"], hold_pending_snapshots=True),
     "hold_pending_snapshots"),

    # SSH+Netcat
    (dict(periodic_snapshot_tasks=["data-recursive"],
          transport="SSH+NETCAT", ssh_credentials=True, netcat_active_side="LOCAL", netcat_active_side_port_min=1024,
          netcat_active_side_port_max=50000),
     None),
    # Bad netcat_active_side_port_max
    (dict(transport="SSH+NETCAT", ssh_credentials=True, netcat_active_side="LOCAL", netcat_active_side_port_min=60000,
          netcat_active_side_port_max=50000),
     "netcat_active_side_port_max"),
    # SSH+Netcat + compression
    (dict(transport="SSH+NETCAT", compression="LZ4"), "compression"),
    # SSH+Netcat + speed limit
    (dict(transport="SSH+NETCAT", speed_limit=1024), "speed_limit"),

    # Does not exclude garbage
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=True), "exclude"),
    # Does not exclude garbage
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=True,
          exclude=["tank/exclude/work/garbage"]),
     None),
    # May not exclude if not recursive
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=False), None),
    # Can't replicate excluded dataset
    (dict(source_datasets=["tank/exclude/work/garbage"], periodic_snapshot_tasks=["exclude"]),
     "source_datasets.0"),

    # Non-recursive exclude
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=False,
          exclude=["tank/exclude/work/garbage"]),
     "exclude"),

    # Unrelated exclude
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=True,
          exclude=["tank/data"]),
     "exclude.0"),

    # Does not require unrelated exclude
    (dict(source_datasets=["tank/exclude/work/important"], periodic_snapshot_tasks=["exclude"], recursive=True),
     None),

    # Custom retention policy
    (dict(periodic_snapshot_tasks=["data-recursive"],
          retention_policy="CUSTOM", lifetime_value=2, lifetime_unit="WEEK"), None),

    # Complex custom retention policy
    (dict(periodic_snapshot_tasks=["data-recursive"],
          retention_policy="CUSTOM", lifetime_value=2, lifetime_unit="WEEK", lifetimes=[
              dict(schedule={"hour": "0"}, lifetime_value=30, lifetime_unit="DAY"),
              dict(schedule={"hour": "0", "dow": "1"}, lifetime_value=1, lifetime_unit="YEAR"),
          ]), None),

    # name_regex
    (dict(name_regex="manual-.+"), None),
    (dict(direction="PULL", name_regex="manual-.+"), None),
    (dict(name_regex="manual-.+",
          retention_policy="CUSTOM", lifetime_value=2, lifetime_unit="WEEK"), "retention_policy"),

    # replicate
    (dict(source_datasets=["tank/data", "tank/data/work"], periodic_snapshot_tasks=["data-recursive"], replicate=True,
          recursive=True, properties=True),
     "source_datasets.1"),
    (dict(source_datasets=["tank/data"], periodic_snapshot_tasks=["data-recursive", "data-work-nonrecursive"],
          replicate=True, recursive=True, properties=True),
     "periodic_snapshot_tasks.1"),
])
def test_create_replication(request, credentials, periodic_snapshot_tasks, req, error):
    depends(request, ["pool_04"], scope="session")
    if "ssh_credentials" in req:
        req["ssh_credentials"] = credentials["id"]

    if "periodic_snapshot_tasks" in req:
        req["periodic_snapshot_tasks"] = [periodic_snapshot_tasks[k]["id"] for k in req["periodic_snapshot_tasks"]]

    name = "".join(random.choice(string.ascii_letters) for _ in range(64))
    result = POST("/replication/", dict(BASE_REPLICATION, name=name, **req))

    if error:
        assert result.status_code == 422, result.text
        assert f"replication_create.{error}" in result.json(), result.text
    else:
        assert result.status_code == 200, result.text

        task_id = result.json()["id"]

        result = POST(f"/replication/id/{task_id}/restore/", {
            "name": f"restore {name}",
            "target_dataset": "data/restore",
        })
        assert result.status_code == 200, result.text

        call("replication.delete", result.json()["id"])

        call("replication.delete", task_id)
