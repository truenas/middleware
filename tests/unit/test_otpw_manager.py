from middlewared.utils.auth import OTPW_MANAGER, OTPWResponse


def test__auth_success():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp is OTPWResponse.SUCCESS


def test__auth_used():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp is OTPWResponse.SUCCESS

    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp is OTPWResponse.ALREADY_USED


def test__auth_nokey():
    resp = OTPW_MANAGER.authenticate(1000, '80000_canary')
    assert resp is OTPWResponse.NO_KEY


def test__auth_bad_passkey():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1000, passwd + 'bad')
    assert resp is OTPWResponse.BAD_PASSKEY

    # This shouldn't prevent using correct passkey
    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp is OTPWResponse.SUCCESS


def test__auth_wrong_user():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1001, passwd)
    assert resp is OTPWResponse.WRONG_USER

    # This shouldn't prevent correct user
    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp is OTPWResponse.SUCCESS


def test__auth_expired():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    idx, plaintext = passwd.split('_')

    OTPW_MANAGER.otpasswd[idx].expires = 1

    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp is OTPWResponse.EXPIRED
