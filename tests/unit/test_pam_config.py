import os
import pytest

from middlewared.utils import pam


def test_pam_control():
    # First check with a generic PAMResponse and PAMAction
    p = pam.PAMControl(pam.PAMResponse.SUCCESS, pam.PAMAction.OK)
    assert p.as_conf() == 'success=ok'

    # Next check that specifying an integer jump also works
    p = pam.PAMControl(pam.PAMResponse.SUCCESS, 2)
    assert p.as_conf() == 'success=2'


@pytest.mark.parametrize('svc,control,module,module_args,expected', [
    (
        pam.PAMService.SESSION,
        pam.PAMSimpleControl.REQUIRED,
        pam.PAMModule.SSS,
        ('test1', 'test2'),
        'session\trequired\tpam_sss.so\ttest1 test2'
    ),
    (
        pam.PAMService.AUTH,
        (
            pam.PAMControl(
                pam.PAMResponse.SUCCESS,
                1
            ),
            pam.PAMControl(
                pam.PAMResponse.NEW_AUTHTOK_REQD,
                pam.PAMAction.OK
            )
        ),
        pam.PAMModule.WINBIND,
        None,
        'auth\t[success=1 new_authtok_reqd=ok]\tpam_winbind.so'
    ),
])
def test_pam_line(svc, control, module, module_args, expected):
    p = pam.PAMLine(svc, control, module, module_args)
    assert p.as_conf() == expected


@pytest.mark.parametrize('pam_module', pam.PAMModule)
def test_map_module_exists(pam_module):
    if pam_module == 'pam_truenas.so':
        libpath = '/usr/lib/security'
    else:
        libpath = '/usr/lib/x86_64-linux-gnu/security'

    assert os.path.exists(os.path.join(libpath, pam_module))
