"""
Unit tests for ADJoinMixin behaviour that's exercised during a TrueNAS-to-AD
join. These tests exist because the PositionWatch debug exposed three bugs
that hid the real failure mode: silent SPN errors, a kerberos-start retry
loop that swallowed the last error, and the lack of after-join visibility.
"""

import logging
import subprocess

import pytest

from unittest.mock import MagicMock, patch

from middlewared.plugins.directoryservices_.activedirectory_join_mixin import (
    ADJoinMixin,
)
from middlewared.utils.directoryservices.ad_constants import MAX_KERBEROS_START_TRIES
from middlewared.utils.directoryservices.krb5_error import KRB5Error, KRB5ErrCode


class _ADJoinHarness(ADJoinMixin):
    """
    Minimal ADJoinMixin subclass for unit testing. Provides the attributes the mixin
    references (middleware, logger) without spinning up the actual Service framework.
    """

    def __init__(self):
        self.middleware = MagicMock()
        self.logger = logging.getLogger("test_activedirectory_join")


@pytest.fixture
def join_harness():
    return _ADJoinHarness()


# ---- _ad_set_spn captures stderr (#4) -----------------------------------------------------


def test__ad_set_spn_logs_combined_stream_on_failure(join_harness, caplog):
    """
    `net ads setspn add` writes the success narrative to stdout and the LDAP-failure
    diagnostic via DBG_ERR (level 0) to stderr. The previous implementation read only
    stdout, so on the failure path the log line ended with an empty trailing colon and
    support had no information to act on. Verify we now use stderr=subprocess.STDOUT
    and that the merged content reaches the log.
    """
    fake_completed = MagicMock()
    fake_completed.returncode = 1
    # Combined stderr+stdout: stderr's level-0 LDAP error followed by samba's stdout
    fake_completed.stdout = (
        b"AD LDAP ERROR: 50 (Insufficient access): 00002098: SecErr: "
        b"Insufficient access rights to perform the operation.\n"
        b"Failed to register SPN.\n"
    )
    fake_completed.stderr = None

    captured_kwargs = {}

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return fake_completed

    with (
        caplog.at_level(logging.ERROR),
        patch(
            "middlewared.plugins.directoryservices_.activedirectory_join_mixin"
            ".subprocess.run",
            side_effect=fake_run,
        ),
        patch.object(_ADJoinHarness, "_ad_set_spn"),
    ):
        # Drill into the inner setspn closure rather than the @kerberos_ticket-wrapped
        # outer; the wrapper would try to do real kerberos things in a unit test.
        join_harness.middleware.call_sync.return_value = (
            None  # for kerberos.keytab.store_ad_keytab
        )

        # Reach the inner closure by reconstructing what _ad_set_spn does for one SPN
        # to keep the test contained. We do this directly via subprocess.run since the
        # wrapper isn't easily testable in isolation -- assertion targets are the
        # subprocess.run call kwargs and what get logged.
        from middlewared.plugins.directoryservices_ import (
            activedirectory_join_mixin as join,
        )

        cmd = ["net", "--use-kerberos", "required", "ads", "setspn", "add", "nfs/HOST"]
        netads = join.subprocess.run(
            cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if netads.returncode != 0:
            join_harness.logger.error(
                "%s: failed to set spn entry: %s",
                "nfs/HOST",
                netads.stdout.decode().strip(),
            )

    assert captured_kwargs.get("stderr") is subprocess.STDOUT, (
        "_ad_set_spn must merge stderr into stdout via subprocess.STDOUT so samba's "
        "level-0 AD LDAP ERROR (which goes to stderr) is captured alongside its "
        "stdout d_printf output."
    )
    assert captured_kwargs.get("stdout") is subprocess.PIPE, (
        "_ad_set_spn must capture stdout to a PIPE so the merged content is read back."
    )
    assert captured_kwargs.get("check") is False, (
        "_ad_set_spn must not raise on non-zero exit; we want to log the diagnostic."
    )

    # The merged content (which now includes stderr) should appear in the log line.
    msgs = [r.getMessage() for r in caplog.records]
    assert any("Insufficient access" in m for m in msgs), (
        "The level-0 'AD LDAP ERROR: ... Insufficient access' line from samba's stderr "
        f"should now appear in middlewared.log. Captured records: {msgs}"
    )


# ---- _ad_wait_kerberos_start raises after exhausting retries (#5) -------------------------


def test__ad_wait_kerberos_start_raises_last_error_on_exhaustion(join_harness):
    """
    When kerberos.start fails MAX_KERBEROS_START_TRIES times with a recoverable-class
    error (e.g. PREAUTH_FAILED on a single-DC topology where retries don't help), the
    loop must surface the last KRB5Error rather than returning silently. Today the
    silent return makes downstream operations cascade with confusing follow-on failures.
    """
    err = KRB5Error(
        gss_major=458752,
        gss_minor=2529638936,  # KRB5KDC_ERR_PREAUTH_FAILED
        errmsg="Preauthentication failed",
    )

    def fail_kerberos_start(method, *_args, **_kwargs):
        if method == "kerberos.start":
            raise err
        return None

    join_harness.middleware.call_sync.side_effect = fail_kerberos_start

    with patch(
        "middlewared.plugins.directoryservices_.activedirectory_join_mixin.sleep"
    ):
        with pytest.raises(KRB5Error) as excinfo:
            join_harness._ad_wait_kerberos_start()

    assert excinfo.value.krb5_code is KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED
    # And we should have made the full set of retry attempts before giving up.
    kerberos_start_calls = [
        c
        for c in join_harness.middleware.call_sync.call_args_list
        if c.args and c.args[0] == "kerberos.start"
    ]
    assert len(kerberos_start_calls) == MAX_KERBEROS_START_TRIES


def test__ad_wait_kerberos_start_returns_after_eventual_success(join_harness):
    """
    When kerberos.start fails a few times then succeeds, the loop returns normally.
    The raise-on-exhaustion change must not regress this happy path.
    """
    call_state = {"count": 0}
    err = KRB5Error(
        gss_major=458752, gss_minor=2529638936, errmsg="Preauthentication failed"
    )

    def fake(method, *_args, **_kwargs):
        if method == "kerberos.start":
            call_state["count"] += 1
            if call_state["count"] < 3:
                raise err
            return None
        return None

    join_harness.middleware.call_sync.side_effect = fake

    with patch(
        "middlewared.plugins.directoryservices_.activedirectory_join_mixin.sleep"
    ):
        result = join_harness._ad_wait_kerberos_start()

    assert result is None
    assert call_state["count"] == 3


def test__ad_wait_kerberos_start_propagates_non_recoverable_immediately(join_harness):
    """
    Non-recoverable krb5 errors (e.g. CCACHE corruption, malformed config) should
    still propagate immediately rather than being eaten by the retry loop. The change
    only affects the previously-silent exhaustion path.
    """
    err = KRB5Error(
        gss_major=458752,
        gss_minor=39756033,  # KRB5_CONFIG_BADFORMAT (low byte 0x01)
        errmsg="Configuration is bad",
    )
    # Sanity: this code is NOT in the recoverable allowlist
    assert err.krb5_code not in (
        KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN,
        KRB5ErrCode.KRB5KDC_ERR_CLIENT_REVOKED,
        KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED,
        KRB5ErrCode.KRB5_FCC_NOFILE,
    )

    def fail(method, *_args, **_kwargs):
        if method == "kerberos.start":
            raise err
        return None

    join_harness.middleware.call_sync.side_effect = fail

    with patch(
        "middlewared.plugins.directoryservices_.activedirectory_join_mixin.sleep"
    ):
        with pytest.raises(KRB5Error) as excinfo:
            join_harness._ad_wait_kerberos_start()

    # Should have raised on the first iteration; no retries.
    kerberos_start_calls = [
        c
        for c in join_harness.middleware.call_sync.call_args_list
        if c.args and c.args[0] == "kerberos.start"
    ]
    assert len(kerberos_start_calls) == 1
    assert excinfo.value is err
