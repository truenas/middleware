from middlewared.utils.auth import OTPW_MANAGER, OTPWResponseCode


def test__auth_success():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp.code is OTPWResponseCode.SUCCESS
    assert resp.data['password_set_override'] is False


def test__auth_used():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1000, passwd).code
    assert resp is OTPWResponseCode.SUCCESS

    resp = OTPW_MANAGER.authenticate(1000, passwd).code
    assert resp is OTPWResponseCode.ALREADY_USED


def test__auth_nokey():
    resp = OTPW_MANAGER.authenticate(1000, '80000_canary').code
    assert resp is OTPWResponseCode.NO_KEY


def test__auth_bad_passkey():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1000, passwd + 'bad').code
    assert resp is OTPWResponseCode.BAD_PASSKEY

    # This shouldn't prevent using correct passkey
    resp = OTPW_MANAGER.authenticate(1000, passwd).code
    assert resp is OTPWResponseCode.SUCCESS


def test__auth_wrong_user():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    resp = OTPW_MANAGER.authenticate(1001, passwd).code
    assert resp is OTPWResponseCode.WRONG_USER

    # This shouldn't prevent correct user
    resp = OTPW_MANAGER.authenticate(1000, passwd).code
    assert resp is OTPWResponseCode.SUCCESS


def test__auth_expired():
    passwd = OTPW_MANAGER.generate_for_uid(1000)
    idx, plaintext = passwd.split('_')

    OTPW_MANAGER.otpasswd[idx].expires = 1

    resp = OTPW_MANAGER.authenticate(1000, passwd).code
    assert resp is OTPWResponseCode.EXPIRED


def test__auth_flag():
    passwd = OTPW_MANAGER.generate_for_uid(1000, True)
    resp = OTPW_MANAGER.authenticate(1000, passwd)
    assert resp.code is OTPWResponseCode.SUCCESS
    assert resp.data['password_set_override'] is True
