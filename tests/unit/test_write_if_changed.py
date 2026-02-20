import os
import pytest
import shutil

from middlewared.utils.io import (
     FileChanges,
     ID_MAX,
     UnexpectedFileChange,
     write_if_changed
)


ETC_DIR = 'test-etc'


@pytest.fixture(scope='module')
def create_etc_dir(request):
    os.mkdir(ETC_DIR)

    try:
        yield os.path.realpath(ETC_DIR)
    finally:
        shutil.rmtree(ETC_DIR)


def test__write_file_content_basic(create_etc_dir):
    target = os.path.join(create_etc_dir, 'testfile1')
    changes = write_if_changed(target, "canary")
    assert changes == FileChanges.CONTENTS

    changes = write_if_changed(target, b"canary2")
    assert changes == FileChanges.CONTENTS

    # basic smoketest that we're actually writing contents
    with open(target, 'r') as f:
        assert f.read() == 'canary2'

    os.unlink(target)


def test__write_file_perms(create_etc_dir):
    target = os.path.join(create_etc_dir, 'testfile3')

    # file doesn't exist and so we only expect contents change
    changes = write_if_changed(target, "canary", perms=0o777)
    assert changes == FileChanges.CONTENTS

    # changing content and perms
    changes = write_if_changed(target, b"canary2", perms=0o755)
    assert changes == FileChanges.CONTENTS | FileChanges.PERMS

    # changing only perms
    changes = write_if_changed(target, b"canary2", perms=0o700)
    assert changes == FileChanges.PERMS

    # changing nothing
    changes = write_if_changed(target, b"canary2", perms=0o700)
    assert changes == 0

    assert os.stat(target).st_mode & 0o777 == 0o700
    os.unlink(target)


def test__write_file_uid(create_etc_dir):
    target = os.path.join(create_etc_dir, 'testfile4')

    # file doesn't exist and so we only expect contents change
    changes = write_if_changed(target, "canary", uid=1000)
    assert changes == FileChanges.CONTENTS

    # changing content and uid
    changes = write_if_changed(target, b"canary2", uid=1001)
    assert changes == FileChanges.CONTENTS | FileChanges.UID

    # changing uid only
    changes = write_if_changed(target, b"canary2", uid=1002)
    assert changes == FileChanges.UID

    # changing nothing
    changes = write_if_changed(target, b"canary2", uid=1002)
    assert changes == 0

    assert os.stat(target).st_uid  == 1002
    os.unlink(target)


def test__write_file_gid(create_etc_dir):
    target = os.path.join(create_etc_dir, 'testfile5')

    # file doesn't exist and so we only expect contents change
    changes = write_if_changed(target, "canary", gid=1000)
    assert changes == FileChanges.CONTENTS

    # changing content and gid
    changes = write_if_changed(target, b"canary2", gid=1001)
    assert changes == FileChanges.CONTENTS | FileChanges.GID

    # changing gid only
    changes = write_if_changed(target, b"canary2", gid=1002)
    assert changes == FileChanges.GID

    # changing nothing
    changes = write_if_changed(target, b"canary2", gid=1002)
    assert changes == 0

    assert os.stat(target).st_gid  == 1002
    os.unlink(target)


def test__write_file_exceptions(create_etc_dir):
    target = os.path.join(create_etc_dir, 'testfile6')

    changes = write_if_changed(target, "canary")
    assert changes == FileChanges.CONTENTS

    with pytest.raises(UnexpectedFileChange) as exc:
        changes = write_if_changed(target, "canary", uid=1000, gid=1001, perms=0o700, raise_error=True)

    assert exc.value.changes == FileChanges.UID | FileChanges.GID | FileChanges.PERMS
    assert exc.value.path == target

    # Make sure changes were still written
    st = os.stat(target)
    assert st.st_uid == 1000
    assert st.st_gid == 1001
    assert st.st_mode & 0o700 == 0o700
    os.unlink(target)


@pytest.mark.parametrize("params,expected_text", [
    ({'uid': -1}, f'uid must be between 0 and {ID_MAX}'),
    ({'gid': -1}, f'gid must be between 0 and {ID_MAX}'),
    ({'uid': 'bob'}, 'uid must be an integer'),
    ({'gid': 'bob'}, 'gid must be an integer'),
    ({'perms': 'bob'}, 'perms must be an integer'),
    ({'perms': 0o4777}, '2559: invalid mode. Supported bits are RWX for UGO.'),
])
def test__write_file_value_errors(create_etc_dir, params, expected_text):
    target = os.path.join(create_etc_dir, 'testfile7')

    with pytest.raises(ValueError) as exc:
        write_if_changed(target, "canary", **params)

    assert expected_text in str(exc.value)


def test__write_file_path_relative_value_error(create_etc_dir):
    with pytest.raises(ValueError) as exc:
        write_if_changed('testfile8', "canary")

    assert 'path must be absolute' in str(exc.value)

@pytest.mark.parametrize("mask,expected_dump", [
    (FileChanges.CONTENTS, ['CONTENTS']),
    (FileChanges.UID, ['UID']),
    (FileChanges.GID, ['GID']),
    (FileChanges.PERMS, ['PERMS']),
    (FileChanges.CONTENTS | FileChanges.UID | FileChanges.GID | FileChanges.PERMS, [
        'CONTENTS', 'UID', 'GID', 'PERMS'
    ])
])
def test__write_file_dump_changes(mask, expected_dump):
    assert FileChanges.dump(mask) == expected_dump



def test__write_file_dump_changes_validation():
    with pytest.raises(ValueError) as exc:
        FileChanges.dump(16)

    assert 'unsupported flags in mask' in str(exc.value)
