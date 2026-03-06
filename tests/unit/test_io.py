import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.utils.io import safe_open


def test_safe_open_read(tmp_path):
    f = tmp_path / 'test.txt'
    f.write_text('hello')
    with safe_open(str(f)) as fh:
        assert fh.read() == 'hello'


def test_safe_open_write(tmp_path):
    f = tmp_path / 'test.txt'
    with safe_open(str(f), 'w') as fh:
        fh.write('world')
        fh.flush()
    assert f.read_text() == 'world'


def test_safe_open_append(tmp_path):
    f = tmp_path / 'test.txt'
    f.write_text('hello')
    with safe_open(str(f), 'a') as fh:
        fh.write(' world')
        fh.flush()
    assert f.read_text() == 'hello world'


def test_safe_open_creates_file(tmp_path):
    f = tmp_path / 'new.txt'
    assert not f.exists()
    with safe_open(str(f), 'w') as fh:
        fh.write('created')
        fh.flush()
    assert f.read_text() == 'created'


def test_safe_open_symlink_raises(tmp_path):
    target = tmp_path / 'target.txt'
    target.write_text('secret')
    link = tmp_path / 'link.txt'
    link.symlink_to(target)

    with pytest.raises(CallError) as exc_info:
        with safe_open(str(link)) as fh:
            fh.read()

    assert exc_info.value.errno == errno.ELOOP


def test_safe_open_symlink_in_path_raises(tmp_path):
    real_dir = tmp_path / 'real'
    real_dir.mkdir()
    (real_dir / 'file.txt').write_text('data')

    link_dir = tmp_path / 'link_dir'
    link_dir.symlink_to(real_dir)

    with pytest.raises(CallError) as exc_info:
        with safe_open(str(link_dir / 'file.txt')) as fh:
            fh.read()

    assert exc_info.value.errno == errno.ELOOP


def test_safe_open_encoding(tmp_path):
    f = tmp_path / 'test.txt'
    f.write_bytes('héllo'.encode('utf-8'))
    with safe_open(str(f), encoding='utf-8') as fh:
        assert fh.read() == 'héllo'


def test_safe_open_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        with safe_open(str(tmp_path / 'nonexistent.txt')) as fh:
            fh.read()
