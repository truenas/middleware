import pytest
import codecs

from middlewared.utils.smb import SMBUnixCharset


@pytest.mark.parametrize('charset', [charset for charset in SMBUnixCharset])
def test__charset_exists(charset):
    codecs.lookup(charset)
