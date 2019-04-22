from datetime import datetime

import pytest

from middlewared.alert.source.ssh_login_failures import get_login_failures


@pytest.mark.parametrize("now,messages,failures", [
    (datetime(year=2017, month=8, day=31), [
        b'Aug 30 invalid login\n',  # 2017
        b'Aug 31 invalid login\n',  # 2017
    ], [
        b'Aug 30 invalid login\n',
    ]),

    (datetime(year=2017, month=8, day=31), [
        b'Aug 30 invalid login\n',  # 2016
        b'Oct 18 invalid login\n',  # 2016
        b'Aug 31 invalid login\n',  # 2017
    ], []),

    (datetime(year=2017, month=8, day=31), [
        b'Aug 30 invalid login\n',  # 2015
        b'Oct 18 invalid login\n',  # 2015
        b'Aug 31 invalid login\n',  # 2016
        b'Aug 30 bad login\n',  # 2017
    ], [
        b'Aug 30 bad login\n',
    ]),

    (datetime(year=2017, month=8, day=31), [
        b'Aug 30 invalid login\n',  # 2017
        b'Aug 31 invalid login\n',  # 2017
        b'\n',  # Random empty line at the end of file
    ], [
        b'Aug 30 invalid login\n',
    ]),
])
def test__get_login_failures(now, messages, failures):
    assert get_login_failures(now, messages) == failures
