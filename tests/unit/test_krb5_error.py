import pickle

import pytest

from middlewared.utils.directoryservices.krb5_error import KRB5ErrCode, KRB5Error

GSS_S_NO_CRED = 458752


@pytest.mark.parametrize(
    "minor,expected",
    [
        (2529638936, KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED),
        (2529638980, KRB5ErrCode.KRB5KDC_ERR_WRONG_REALM),
        (2529639132, KRB5ErrCode.KRB5_REALM_CANT_RESOLVE),
        (2529638965, None),  # KRB5PLACEHOLD_53
        (122, None),  # EDQUOT
        (2, None),  # ENOENT
        (39756033, None),  # KG_KEYTAB_NOMATCH from the GSSAPI krb5 mech table
    ],
)
def test__krb5_error_code(minor, expected):
    assert KRB5Error(GSS_S_NO_CRED, minor, "error").krb5_code is expected


def test__krb5_error_str():
    assert str(KRB5Error(GSS_S_NO_CRED, 2529638936, "Preauthentication failed")) == (
        "[KRB5KDC_ERR_PREAUTH_FAILED] Preauthentication failed"
    )
    assert str(KRB5Error(GSS_S_NO_CRED, 122, "Disk quota exceeded")) == "Disk quota exceeded"


def test__krb5_error_pickle():
    err = pickle.loads(pickle.dumps(KRB5Error(GSS_S_NO_CRED, 122, "Disk quota exceeded")))
    assert err.krb5_code is None
    assert err.gss_minor_code == 122
