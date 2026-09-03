import pytest

from middlewared.service_exception import ValidationErrors, ValidationError
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, ssh


@pytest.mark.parametrize(
    'key,value,grep_file,sshd_config_cmd,validation_error', [
        ('motd', 'TrueNAS Message Of The Day', '/etc/motd', None, ''),
        ('login_banner', 'TrueNAS Login Banner', '/etc/login_banner', 'grep Banner /etc/ssh/sshd_config', ''),
        ('kernel_extra_options', 'zfs_arc_min=21474836480', None, None, ''),
        ('kernel_extra_options', '', None, None, ''),
        ('kernel_extra_options', 'zfs_arc_min=<21474836480>', None, None, 'Invalid syntax'),
    ],
    ids=[
        'Test MOTD',
        'Test Login Banner',
        'Test Valid Kernel Extra Options 1',
        'Test Valid Kernel Extra Options 2',
        'Test Invalid Kernel Extra Options 1',
    ],
)
def test_(key, value, grep_file, sshd_config_cmd, validation_error):
    if not validation_error:
        call('system.advanced.update', {key: value})
        assert call('system.advanced.config')[key] == value
        if grep_file is not None:
            assert ssh(f'grep "{value}" {grep_file}', complete_response=True)['result']
        if sshd_config_cmd is not None:
            assert ssh(sshd_config_cmd, complete_response=True)['result']
    else:
        with pytest.raises(ValidationErrors) as ve:
            call('system.advanced.update', {key: value})
        assert ve.value.errors == [ValidationError(f"system_advanced_update.{key}", validation_error)]


def test_debugkernel_initrd():
    assert not call("system.advanced.config")["debugkernel"]

    initrds = [initrd for initrd in ssh("ls -1 /boot").split() if "initrd" in initrd]
    assert len(initrds) == 1
    assert "debug" not in initrds[0]

    try:
        call("system.advanced.update", {"debugkernel": True}, timeout=300)

        initrds = [initrd for initrd in ssh("ls -1 /boot").split() if "initrd" in initrd]
        assert len(initrds) == 2
        assert any("debug" in initrd for initrd in initrds)
    finally:
        call("system.advanced.update", {"debugkernel": False})


def test_kernel_extra_options_may_only_be_changed_by_a_full_admin():
    """`kernel_extra_options` reaches the kernel command line, so SYSTEM_ADVANCED_WRITE alone may not touch it
    (NAS-142160)."""
    with unprivileged_user_client(['SYSTEM_ADVANCED_WRITE']) as c:
        with pytest.raises(ValidationErrors) as ve:
            c.call('system.advanced.update', {'kernel_extra_options': 'init=/bin/sh'})

    assert any(error.attribute == 'data.kernel_extra_options' for error in ve.value.errors), ve.value.errors
