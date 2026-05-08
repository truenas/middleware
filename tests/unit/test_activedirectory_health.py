import logging

import pytest
import wbclient

from unittest.mock import MagicMock, patch

from middlewared.plugins.directoryservices_ import activedirectory_health_mixin as ad_health
from middlewared.plugins.directoryservices_.activedirectory_health_mixin import (
    ADHealthMixin,
    _AUTH_NTSTATUS_SUGGEST_BAD_SECRET,
)
from middlewared.utils.directoryservices import krb5
from middlewared.utils.directoryservices.health import ADHealthError, ADHealthCheckFailReason
from middlewared.utils.directoryservices.krb5_error import KRB5Error, KRB5ErrCode


# CLDAP-style domain_info dict. The IP here is intentionally NOT the SAF-pinned IP — that's
# precisely the case the SAF preference fix is supposed to defend against (RDNS / cache
# drift switching us to a different DC than the one we joined to).
LIBADS_DOMAIN_INFO = {
    'ldap_server': '10.0.0.99',
    'ldap_server_name': 'dc-other.ad.example.com',
    'realm': 'AD.EXAMPLE.COM',
    'kdc_server': '10.0.0.99',
    'server_time_offset': 5,
    'workgroup': 'AD',
}

SAF_PINNED_IP = '10.0.0.42'
SAF_PINNED_HOST = 'dc-joined.ad.example.com'

SMB_CONFIG = {'workgroup': 'AD', 'netbiosname': 'TRUENAS'}
DS_CONFIG = {
    'kerberos_realm': 'AD.EXAMPLE.COM',
    'configuration': {'domain': 'AD.EXAMPLE.COM'},
    'enable': True,
    'service_type': 'ACTIVEDIRECTORY',
}


class _ADHealthHarness(ADHealthMixin):
    """
    Minimal subclass that gives ADHealthMixin enough context to run without spinning up
    the real Service framework. Tests inject a Mock middleware and replace the password
    validation helper so we can assert on the KDC argument it received.
    """
    def __init__(self):
        self.middleware = MagicMock()
        self.logger = logging.getLogger('test_activedirectory_health')


@pytest.fixture
def saf_cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr(krb5, 'SAF_CACHE_FILE', str(tmp_path / 'saf_cache'))
    return tmp_path / 'saf_cache'


@pytest.fixture
def harness(saf_cache_file):
    h = _ADHealthHarness()

    # Map middleware.call_sync(name, *args) to canned return values for the calls
    # _health_check_ad makes. Anything not specified raises so a missing mock doesn't
    # pass silently.
    def call_sync(name, *args, **kwargs):
        match name:
            case 'directoryservices.config':
                return DS_CONFIG
            case 'smb.config':
                return SMB_CONFIG
            case 'directoryservices.secrets.get_machine_secret':
                return b'cGFzc3dvcmQ='  # base64('password')
            case 'kerberos.keytab.query':
                return {'name': 'AD_MACHINE_ACCOUNT'}
            case 'service.started':
                return True
            case _:
                raise AssertionError(f'unexpected middleware call: {name}')

    h.middleware.call_sync.side_effect = call_sync
    return h


def _make_wbc_error(wbc_error_code=None, ntstatus='NT_STATUS_ACCESS_DENIED', message=None):
    """
    Build a wbclient.WBCError shaped like the real C extension produces. The
    message format mirrors py_wbclient.c:540 (and _set_exc_from_wbcerrno around
    line 70 prepending wbcErrorString) so the production allowlist's substring
    check sees the same shape it sees in production.
    """
    if wbc_error_code is None:
        wbc_error_code = wbclient.WBC_ERR_AUTH_ERROR
    if message is None:
        if wbc_error_code == wbclient.WBC_ERR_AUTH_ERROR:
            message = (
                f'WBC_ERR_AUTH_ERROR: wbcCheckTrustCredentials(AD): '
                f'error code was {ntstatus} (0xc0000022)'
            )
        else:
            message = 'WBC_ERR_FOO: wbcPingDc2 failed'

    err = wbclient.WBCError(wbc_error_code, message, 'tests/synthetic')
    err.error_code = wbc_error_code
    return err


def _wbclient_with_failing_ping(wbc_error_code=None, ntstatus='NT_STATUS_ACCESS_DENIED', message=None):
    """
    Build a WBClient mock whose ping_dc() raises a wbclient.WBCError -- driving
    _health_check_ad into the refinement branch where _test_machine_account_password
    runs. Defaults to AUTH_ERROR + NT_STATUS_ACCESS_DENIED so the refinement is
    triggered.
    """
    instance = MagicMock()
    instance.ping_dc.side_effect = _make_wbc_error(wbc_error_code, ntstatus, message)
    cls = MagicMock(return_value=instance)
    return cls


def _wbclient_healthy():
    """ WBClient mock whose ping_dc() succeeds. """
    instance = MagicMock()
    instance.ping_dc.return_value = None
    cls = MagicMock(return_value=instance)
    return cls


# ---- Happy path: password test is NOT run on healthy systems ------------------------------

def test__health_check_ad_does_not_run_password_test_when_ping_dc_succeeds(harness):
    """
    The password test writes a temporary krb5.conf and triggers a regenerate of the
    system one — that's churn we don't want on every periodic health check. Verify
    that on a healthy system (ping_dc succeeds) we never call _test_machine_account_password.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_healthy(),
         ):
        harness._health_check_ad()

    assert not test_pw.called, (
        'Healthy ping_dc must not trigger the password-validity test. The test is a '
        'refinement that should only run when ping_dc has already failed; running it '
        'on every periodic check writes a temporary krb5.conf and regenerates the '
        'system one, which is unnecessary churn.'
    )


# ---- Refinement path: password test runs after ping_dc fails ------------------------------

def test__health_check_ad_runs_password_test_after_ping_dc_fails(harness):
    """
    When ping_dc fails the health check should refine the diagnosis by validating the
    machine-account password against the DC. The customer's symptom -- "Stored machine
    account secret is invalid" -- is a more actionable diagnosis than the generic
    "AD_NETLOGON_FAILURE" when the underlying issue is a credential mismatch.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(),
         ):
        with pytest.raises(ADHealthError):
            harness._health_check_ad()

    assert test_pw.called
    kdc_arg, _password = test_pw.call_args.args
    assert kdc_arg == SAF_PINNED_IP, (
        f'Refinement password test passed {kdc_arg!r} as the KDC; should have preferred '
        f'the SAF cache pin ({SAF_PINNED_IP!r}) over libads-discovered '
        f'{LIBADS_DOMAIN_INFO["kdc_server"]!r}.'
    )


def test__health_check_ad_does_not_use_saf_hostname_for_kdc_arg(harness):
    """
    krb5.conf's kdc= and the kdc argument to _test_machine_account_password must be an
    address. If the SAF cache only holds a hostname (legacy IPA entry, partial set), we
    fall through to libads' value rather than passing a hostname into the krb5 override.
    Drive the refinement path via a failing ping_dc to exercise the SAF-resolution code.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST)  # host only, no ip

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(),
         ):
        with pytest.raises(ADHealthError):
            harness._health_check_ad()

    kdc_arg, _password = test_pw.call_args.args
    assert kdc_arg == LIBADS_DOMAIN_INFO['kdc_server'], (
        f'When SAF entry has no ip, refinement test must not pass the hostname '
        f'(got {kdc_arg!r}); it should fall back to libads kdc_server.'
    )


def test__health_check_ad_falls_back_to_libads_when_saf_empty(harness):
    """
    With no SAF cache present, the refinement test uses libads' KDC pick.
    """
    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(),
         ):
        with pytest.raises(ADHealthError):
            harness._health_check_ad()

    kdc_arg, _password = test_pw.call_args.args
    assert kdc_arg == LIBADS_DOMAIN_INFO['kdc_server']


def test__health_check_ad_password_preauth_failed_pins_diagnosis_to_secret_invalid(harness):
    """
    When ping_dc fails AND the refinement password test fails with KRB5KDC_ERR_PREAUTH_FAILED,
    the user-facing fault must be AD_SECRET_INVALID rather than AD_NETLOGON_FAILURE. The
    remediation is different (re-join vs check the DC / network) and the password fault is
    the more specific signal.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    def password_test_boom(*_args, **_kwargs):
        raise KRB5Error(
            gss_major=458752,
            gss_minor=2529638936,  # lower 8 bits == KRB5KDC_ERR_PREAUTH_FAILED (24)
            errmsg='Preauthentication failed',
        )

    with patch.object(
            _ADHealthHarness, '_test_machine_account_password', side_effect=password_test_boom
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(),
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    assert excinfo.value.reason is ADHealthCheckFailReason.AD_SECRET_INVALID


def test__health_check_ad_password_passes_falls_through_to_netlogon_failure(harness):
    """
    If ping_dc fails with an NTSTATUS that triggers refinement (e.g. ACCESS_DENIED)
    but the refinement password test SUCCEEDS, the underlying problem isn't a
    credential mismatch -- it's something else (transient DC state, schannel
    desync). Don't overwrite the netlogon diagnosis with a misleading "secret
    invalid" one; preserve the original netlogon error string instead.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password', return_value=None) as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(ntstatus='NT_STATUS_ACCESS_DENIED'),
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    # The refinement actually ran (the WBCError was AUTH/ACCESS_DENIED) but
    # passed, so the final diagnosis stays at AD_NETLOGON_FAILURE.
    assert test_pw.called
    assert excinfo.value.reason is ADHealthCheckFailReason.AD_NETLOGON_FAILURE
    # And the netlogon error string from ping_dc should be preserved.
    assert 'NT_STATUS_ACCESS_DENIED' in excinfo.value.errmsg


def test__health_check_ad_password_test_other_krb5_error_falls_through(harness):
    """
    If the refinement password test raises a non-PREAUTH KRB5Error (e.g. clock skew,
    ticket expired), don't pin the diagnosis to AD_SECRET_INVALID -- only PREAUTH_FAILED
    is unambiguous evidence of a credential mismatch. Other errors fall through to
    AD_NETLOGON_FAILURE.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    def password_test_skew(*_args, **_kwargs):
        raise KRB5Error(
            gss_major=458752,
            gss_minor=2529639061,  # KRB5KRB_AP_ERR_SKEW (37)
            errmsg='Clock skew too great',
        )

    with patch.object(
            _ADHealthHarness, '_test_machine_account_password', side_effect=password_test_skew
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(),
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    assert excinfo.value.reason is ADHealthCheckFailReason.AD_NETLOGON_FAILURE


# ---- Error-filter gating: refinement skipped for non-secret winbind errors ---------------

@pytest.mark.parametrize('wbc_error_code', [
    wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE,
    wbclient.WBC_ERR_DOMAIN_NOT_FOUND,
    wbclient.WBC_ERR_UNKNOWN_FAILURE,
    wbclient.WBC_ERR_NSS_ERROR,
])
def test__health_check_ad_non_auth_wbcerror_skips_password_test(harness, wbc_error_code):
    """
    Only WBC_ERR_AUTH_ERROR can plausibly indicate a bad secrets.tdb (non-AUTH WBC
    codes carry no NTSTATUS and originate from infrastructure paths -- daemon down,
    domain lookup, NSS plumbing). Running the expensive password test for these
    just churns /etc/krb5.conf with no diagnostic value, so the refinement must
    not run.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(wbc_error_code=wbc_error_code),
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    assert not test_pw.called, (
        f'Non-AUTH WBCError ({wbc_error_code}) must not trigger the password test'
    )
    assert excinfo.value.reason is ADHealthCheckFailReason.AD_NETLOGON_FAILURE


@pytest.mark.parametrize('ntstatus', [
    'NT_STATUS_IO_TIMEOUT',
    'NT_STATUS_NETWORK_ACCESS_DENIED',
    'NT_STATUS_NO_LOGON_SERVERS',
    'NT_STATUS_DOWNGRADE_DETECTED',
])
def test__health_check_ad_auth_error_with_non_secret_ntstatus_skips_password_test(harness, ntstatus):
    """
    WBC_ERR_AUTH_ERROR can wrap a wide range of NTSTATUS values. Network/transport
    failures (IO_TIMEOUT, NETWORK_ACCESS_DENIED, NO_LOGON_SERVERS) and crypto
    negotiation failures (DOWNGRADE_DETECTED) reproduce identically under a
    refinement kinit, so the password test adds nothing -- gate it to the
    secret-related NTSTATUS allowlist only.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(ntstatus=ntstatus),
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    assert not test_pw.called, (
        f'AUTH_ERROR with non-secret NTSTATUS ({ntstatus}) must not trigger the password test'
    )
    assert excinfo.value.reason is ADHealthCheckFailReason.AD_NETLOGON_FAILURE
    assert ntstatus in excinfo.value.errmsg


@pytest.mark.parametrize('ntstatus', sorted(_AUTH_NTSTATUS_SUGGEST_BAD_SECRET))
def test__health_check_ad_auth_error_with_secret_ntstatus_runs_password_test(harness, ntstatus):
    """
    Every NTSTATUS in the secret-related allowlist must trigger the refinement
    password test. If samba ever stops surfacing one of these strings the
    corresponding case here will fail, telling us the allowlist needs revision.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(ntstatus=ntstatus),
         ):
        with pytest.raises(ADHealthError):
            harness._health_check_ad()

    assert test_pw.called, (
        f'Allowlisted NTSTATUS ({ntstatus}) must trigger the refinement password test'
    )


def test__health_check_ad_unexpected_non_wbcerror_does_not_crash(harness):
    """
    libwbclient is expected to always raise WBCError, but a packaging mismatch
    or corrupted handle could surface something else. The defensive outer catch
    must still produce a structured ADHealthError for the alert framework --
    and must NOT run the expensive refinement because the message format is
    untrusted.
    """
    instance = MagicMock()
    instance.ping_dc.side_effect = RuntimeError('libwbclient.so broken')
    wbclient_mock = MagicMock(return_value=instance)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=wbclient_mock,
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    assert not test_pw.called
    assert excinfo.value.reason is ADHealthCheckFailReason.AD_NETLOGON_FAILURE
    assert 'libwbclient.so broken' in excinfo.value.errmsg


def test__health_check_ad_secret_ntstatus_without_domain_info_skips_password_test(harness):
    """
    Even on an otherwise-qualifying AUTH error, refinement must be skipped when
    get_domain_info() failed -- without it there is no KDC to point the test at.
    The health check should still report AD_NETLOGON_FAILURE rather than crash
    trying to dereference None.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    with patch.object(_ADHealthHarness, '_test_machine_account_password') as test_pw, \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             side_effect=RuntimeError('CLDAP probe failed'),
         ), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.WBClient',
             new=_wbclient_with_failing_ping(ntstatus='NT_STATUS_ACCESS_DENIED'),
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._health_check_ad()

    assert not test_pw.called
    assert excinfo.value.reason is ADHealthCheckFailReason.AD_NETLOGON_FAILURE


# ---- _recover_secrets path keeps the password test as a primary check ---------------------

def test__recover_secrets_kdc_preauth_failed_arm_is_reachable(harness):
    """
    Regression for the typo at activedirectory_health_mixin.py:147 where the arm matched
    KRB5_PREAUTH_FAILED (209, lib-side) instead of KRB5KDC_ERR_PREAUTH_FAILED (24, the
    KDC-returned code). _recover_secrets keeps the password test as a primary check
    (it's how we verify the restored secrets actually match AD), so this code path
    still matters.
    """
    krb5.kdc_saf_cache_set(host=SAF_PINNED_HOST, ip=SAF_PINNED_IP)

    harness.middleware.call_sync.side_effect = lambda name, *_a, **_kw: {
        'directoryservices.config': DS_CONFIG,
        'smb.config': SMB_CONFIG,
        'directoryservices.secrets.restore': True,
        'directoryservices.secrets.get_machine_secret': b'cGFzc3dvcmQ=',
    }[name]

    def boom(*_args, **_kwargs):
        raise KRB5Error(
            gss_major=458752,
            gss_minor=2529638936,
            errmsg='Preauthentication failed',
        )

    with patch.object(_ADHealthHarness, '_test_machine_account_password', side_effect=boom), \
         patch(
             'middlewared.plugins.directoryservices_.activedirectory_health_mixin.get_domain_info',
             return_value=LIBADS_DOMAIN_INFO,
         ):
        with pytest.raises(ADHealthError) as excinfo:
            harness._recover_secrets()

    # The credential-mismatch arm contains this distinctive substring; the generic
    # catchall would just say 'Failed to validate stored credential: ...'. Asserting on
    # the arm-specific text means the typo can't silently regress.
    assert 'computer account credentials are not valid' in excinfo.value.errmsg
    assert excinfo.value.reason is ADHealthCheckFailReason.AD_SECRET_INVALID
    # And confirm the krb5_code we're matching is what we think it is.
    err = KRB5Error(gss_major=458752, gss_minor=2529638936, errmsg='')
    assert err.krb5_code is KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED


# ---- _test_machine_account_password cleanup (#6) ------------------------------------------

def _temp_kerberos_harness(monkeypatch, tmp_path):
    """
    Build a harness whose middleware replies to all the calls _test_machine_account_password
    actually makes. Captures the etc.generate('kerberos') call so tests can assert on
    cleanup behaviour.
    """
    h = _ADHealthHarness()
    krb5_conf_path = tmp_path / 'krb5.conf'
    monkeypatch.setattr(
        'middlewared.utils.directoryservices.krb5_conf.KRB5_CONFIG_PATH',
        str(krb5_conf_path),
        raising=False,
    )

    calls = {'etc_generate_calls': []}

    def call_sync(name, *args, **kwargs):
        if name == 'directoryservices.config':
            return DS_CONFIG
        if name == 'smb.config':
            return SMB_CONFIG
        if name == 'kerberos.kdestroy':
            return None
        if name == 'etc.generate':
            calls['etc_generate_calls'].append(args)
            return None
        raise AssertionError(f'unexpected middleware call: {name}')

    h.middleware.call_sync.side_effect = call_sync
    return h, calls, krb5_conf_path


def test__test_machine_account_password_regenerates_krb5_conf_on_kinit_failure(
    monkeypatch, tmp_path
):
    """
    When kinit_with_cred raises KRB5Error (e.g. PREAUTH_FAILED), the system krb5.conf
    must still be regenerated -- otherwise the minimal temp config persists and pollutes
    every subsequent kerberos op until something else triggers a regenerate.
    """
    h, calls, _ = _temp_kerberos_harness(monkeypatch, tmp_path)

    def boom(*_a, **_kw):
        raise KRB5Error(
            gss_major=458752, gss_minor=2529638936, errmsg='Preauthentication failed'
        )

    with patch.object(ad_health, 'kinit_with_cred', side_effect=boom):
        with pytest.raises(KRB5Error):
            h._test_machine_account_password('10.0.0.1', b'cGFzc3dvcmQ=')

    assert ('kerberos',) in calls['etc_generate_calls'], (
        "etc.generate('kerberos') must be called even when kinit raises -- otherwise "
        "the temporary minimal krb5.conf is left in place as the system config."
    )


def test__test_machine_account_password_temp_config_disables_rdns_and_canonicalize(
    monkeypatch, tmp_path
):
    """
    The temporary krb5.conf written for the test must include the AD-specific defaults
    (rdns=false, dns_canonicalize_hostname=false) introduced by NAS-138687. Otherwise
    the test runs under different rules than normal AD operations and may produce
    inconsistent results.
    """
    h, _, _ = _temp_kerberos_harness(monkeypatch, tmp_path)

    captured = {}

    class _FakeKrb5Conf:
        def __init__(self):
            self.libdefaults = {}

        def add_libdefaults(self, libdefs, aux=None):
            self.libdefaults.update(libdefs)
            captured.update(libdefs)

        def add_realms(self, realms):
            pass

        def write(self):
            pass

    with patch.object(ad_health, 'KRB5Conf', _FakeKrb5Conf), \
         patch.object(ad_health, 'kinit_with_cred', return_value=None):
        h._test_machine_account_password('10.0.0.1', b'cGFzc3dvcmQ=')

    assert captured.get('rdns') == 'false', (
        'temp krb5.conf must set rdns=false to mirror NAS-138687'
    )
    assert captured.get('dns_canonicalize_hostname') == 'false', (
        'temp krb5.conf must set dns_canonicalize_hostname=false to mirror NAS-138687'
    )
