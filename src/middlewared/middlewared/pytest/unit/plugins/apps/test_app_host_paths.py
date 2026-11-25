from unittest.mock import patch

import pytest

from middlewared.api.current import AppEntry
from middlewared.api.v28_0_0.app import AppActiveWorkloads, AppVolumes
from middlewared.plugins.apps.ix_apps.host_paths import compose_bind_sources, get_host_paths
from middlewared.plugins.apps.ix_apps.path import get_app_volume_path

COMPOSE = {
    "services": {
        "web": {
            "image": "nginx",
            "volumes": [
                "/mnt/tank/web:/data",
                "/mnt/tank/web:/data-again:ro",
                "named:/named",
                {"type": "bind", "source": "/mnt/tank/long", "target": "/long"},
                {"type": "volume", "source": "named", "target": "/named-long"},
                {"type": "tmpfs", "target": "/tmp"},
            ],
        },
        "worker": {"image": "busybox"},
    },
    "volumes": {
        "named": None,
        "bound": {"driver": "local", "driver_opts": {"type": "none", "o": "bind", "device": "/mnt/tank/bound"}},
        "nfs": {"driver_opts": {"type": "nfs", "o": "addr=10.0.0.1,rw", "device": ":/export"}},
        "cifs": {"driver_opts": {"type": "cifs", "o": "username=u,password=p", "device": "//server/share"}},
    },
}


def test_compose_bind_sources():
    assert list(compose_bind_sources(COMPOSE)) == [
        "/mnt/tank/web",
        "/mnt/tank/web",
        "/mnt/tank/long",
        "/mnt/tank/bound",
    ]


def test_compose_bind_sources_without_volumes():
    assert list(compose_bind_sources({"services": {"web": {"image": "nginx"}}})) == []


def volume(source):
    return AppVolumes(source=source, destination="/data", mode="rw", type="bind")


def app_entry(version, sources):
    return AppEntry.model_construct(
        name="plex",
        version=version,
        active_workloads=AppActiveWorkloads.model_construct(volumes=[volume(source) for source in sources]),
    )


def test_get_host_paths_of_a_running_app():
    app = app_entry(
        None,
        [
            "/mnt/tank/media",
            "/mnt/tank/media/../photos",
            "/mnt/tank/media",
            f"{get_app_volume_path('plex')}/config",
            "/mnt/.ix-apps/docker/volumes/abc/_data",
            "/etc/localtime",
            "/mnt/.ix-apps-lookalike/data",
        ],
    )

    assert get_host_paths(app) == ["/mnt/tank/media", "/mnt/tank/media/../photos", "/mnt/.ix-apps-lookalike/data"]


def test_get_host_paths_of_a_stopped_app():
    with patch(
        "middlewared.plugins.apps.ix_apps.host_paths.get_rendered_template_config_of_app", return_value=COMPOSE
    ) as rendered:
        assert get_host_paths(app_entry("1.0.0", [])) == ["/mnt/tank/web", "/mnt/tank/long", "/mnt/tank/bound"]

    rendered.assert_called_once_with("plex", "1.0.0")


def test_get_host_paths_declared_and_held():
    with patch("middlewared.plugins.apps.ix_apps.host_paths.get_rendered_template_config_of_app", return_value=COMPOSE):
        assert get_host_paths(app_entry("1.0.0", ["/mnt/tank/web", "/mnt/tank/held"])) == [
            "/mnt/tank/web",
            "/mnt/tank/held",
            "/mnt/tank/long",
            "/mnt/tank/bound",
        ]


def test_get_host_paths_without_rendered_templates():
    with patch(
        "middlewared.plugins.apps.ix_apps.host_paths.get_rendered_template_config_of_app", side_effect=FileNotFoundError
    ):
        assert get_host_paths(app_entry("1.0.0", ["/mnt/tank/held"])) == ["/mnt/tank/held"]


@pytest.mark.parametrize("version", [None, "1.0.0"])
def test_get_host_paths_of_an_app_without_mounts(version):
    with patch("middlewared.plugins.apps.ix_apps.host_paths.get_rendered_template_config_of_app", return_value={}):
        assert get_host_paths(app_entry(version, [])) == []
