import itertools
import pytest

from middlewared.test.integration.assets.roles import common_checks

CRUD_APIS = ["host", "port", "subsys", "host_subsys", "port_subsys", "namespace"]


@pytest.mark.parametrize(
    "api, role",
    itertools.product(CRUD_APIS, ["SHARING_READ", "SHARING_NVME_TARGET_READ"])
)
def test_read_role_can_read(unprivileged_user_fixture, api, role):
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.query", role, True, valid_role_exception=False)


@pytest.mark.parametrize(
    "api, role",
    itertools.product(CRUD_APIS, ["SHARING_READ", "SHARING_NVME_TARGET_READ"])
)
def test_read_role_cant_write(unprivileged_user_fixture, api, role):
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.create", role, False)
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.update", role, False)
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.delete", role, False)


@pytest.mark.parametrize(
    "api, role",
    itertools.product(CRUD_APIS, ["SHARING_WRITE", "SHARING_NVME_TARGET_WRITE"])
)
def test_write_role_can_write(unprivileged_user_fixture, api, role):
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.create", role, True)
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.update", role, True)
    common_checks(unprivileged_user_fixture, f"nvmet.{api}.delete", role, True)


@pytest.mark.parametrize(
    "role",
    ["SHARING_WRITE", "SHARING_NVME_TARGET_WRITE"]
)
def test_write_role_can_change_service_state(unprivileged_user_fixture, role):
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["START", "nvmet"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["RESTART", "nvmet"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["RELOAD", "nvmet"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["STOP", "nvmet"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
