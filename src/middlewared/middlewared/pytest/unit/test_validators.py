import os
import shutil
import pytest

from middlewared.schema import Dict, Int, Str
from middlewared.service_exception import ValidationErrors
from middlewared.validators import check_path_resides_within_volume_sync, validate_schema, Range, Email


@pytest.mark.parametrize("schema,data,result", [
    ([Str("text")], {"text": "XXX"}, {"text": "XXX"}),
    ([Str("text", default="XXX")], {}, {"text": "XXX"}),
    ([Str("text", required=True)], {}, {"text"}),
    ([Int("number")], {"number": "1"}, {"number": 1}),
    ([Int("number")], {"number": "XXX"}, {"number"}),
    ([Int("number", validators=[Range(min_=2)])], {"number": 1}, {"number"}),
    ([Dict("image", Str("repository", required=True))], {}, {"image.repository"}),
])
def test__validate_schema(schema, data, result):
    verrors = validate_schema(schema, data)
    if isinstance(result, set):
        assert result == {e.attribute for e in verrors.errors}
    else:
        assert data == result


@pytest.mark.parametrize("email,should_raise", [
    ("2@2@me.com", False),
    ("2&2@me.com", False),
    ("2@\uD800\uD800ñoñó郵件ñoñó郵件.商務", False),
    (f'{"2" * 250}@me.com', True),
    ("@me.com", True),
    ("2@", True),
    ("@", True),
    ("", True),
])
def test__email_schema(email, should_raise):
    if not should_raise:
        Email()(email)
    else:
        with pytest.raises(ValueError):
            Email()(email)


@pytest.fixture(scope="function")
def setup_mnt(tmpdir):
    os.makedirs('/mnt/pool/foo')
    os.mkdir('/mnt/foo')
    try:
        os.symlink(tmpdir, '/mnt/pool/symlink')
        os.symlink('/mnt/foo', '/mnt/pool/symlink2')
        yield
    finally:
        shutil.rmtree('/mnt/pool')


@pytest.mark.parametrize("path,should_raise", [
    ('/tmp', True),
    ('EXTERNAL://smb_server.local/SHARE', True),
    ('/mnt/does_not_exist', True),
    ('/mnt/foo', True),
    ('/mnt/pool/foo', False),
    ('/mnt/pool', False),
    ('/mnt/pool/..', True),
    ('/mnt/pool/symlink', True),
    ('/mnt/pool/symlink2', True)
])
def test___check_path_resides_within_volume(setup_mnt, path, should_raise):
    volumes = ['pool']
    verr = ValidationErrors()
    check_path_resides_within_volume_sync(verr, "test.path", path, volumes)
    if should_raise:
        with pytest.raises(ValidationErrors):
            verr.check()
    else:
        verr.check()
