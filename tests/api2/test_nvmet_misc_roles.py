import pytest

from middlewared.test.integration.assets.roles import common_checks


# Handle public APIs not covered by test_nvmet_crud_roles.py

@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_NVME_TARGET_READ"])
def test_read_role_can_read(unprivileged_user_fixture, role):
    # Global
    common_checks(unprivileged_user_fixture, "nvmet.global.config", role, True,
                  valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "nvmet.global.sessions", role, True,
                  valid_role_exception=False)

    # Host
    common_checks(unprivileged_user_fixture, "nvmet.host.dhchap_dhgroup_choices", role, True,
                  valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "nvmet.host.dhchap_hash_choices", role, True,
                  valid_role_exception=False)

    # Port
    common_checks(unprivileged_user_fixture, "nvmet.port.transport_address_choices", role, True,
                  valid_role_exception=False, method_args=['TCP'])


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_NVME_TARGET_READ"])
def test_read_role_cant_write(unprivileged_user_fixture, role):
    # Global
    common_checks(unprivileged_user_fixture, "nvmet.global.update", role, False, method_args={})

    # Host
    common_checks(unprivileged_user_fixture, "nvmet.host.generate_key", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_NVME_TARGET_WRITE"])
def test_write_role_can_write(unprivileged_user_fixture, role):
    # Global
    common_checks(unprivileged_user_fixture, "nvmet.global.update", role, True, method_args={})

    # Host
    common_checks(unprivileged_user_fixture, "nvmet.host.generate_key", role, True,
                  valid_role_exception=False)
