import os
import pytest
import shutil
import stat

from middlewared.utils.io import atomic_replace, atomic_write


TEST_DIR = 'test-atomic-replace'
TEST_UID = 8675309
TEST_GID = 8675310


@pytest.fixture(scope='module')
def test_directory(request):
    """Create a test directory for atomic_replace tests."""
    os.mkdir(TEST_DIR)

    try:
        yield os.path.realpath(TEST_DIR)
    finally:
        shutil.rmtree(TEST_DIR)


def test__atomic_replace_creates_new_file(test_directory):
    """Test that atomic_replace creates a new file when target doesn't exist."""
    target = os.path.join(test_directory, 'new_file.txt')
    data = b"Hello, World!"

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data
    )

    assert os.path.exists(target)
    with open(target, 'rb') as f:
        assert f.read() == data

    os.unlink(target)


def test__atomic_replace_replaces_existing_file(test_directory):
    """Test that atomic_replace replaces an existing file's contents."""
    target = os.path.join(test_directory, 'existing_file.txt')

    # Create initial file
    with open(target, 'wb') as f:
        f.write(b"Original content")

    # Replace with new content
    new_data = b"New content"
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=new_data
    )

    with open(target, 'rb') as f:
        assert f.read() == new_data

    os.unlink(target)


def test__atomic_replace_sets_permissions(test_directory):
    """Test that atomic_replace sets file permissions correctly."""
    target = os.path.join(test_directory, 'perms_file.txt')
    data = b"Permission test"
    perms = 0o644

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data,
        perms=perms
    )

    file_stat = os.stat(target)
    assert stat.S_IMODE(file_stat.st_mode) == perms

    os.unlink(target)


def test__atomic_replace_sets_ownership(test_directory):
    """Test that atomic_replace sets file ownership correctly."""
    target = os.path.join(test_directory, 'owner_file.txt')
    data = b"Ownership test"
    uid = os.getuid()  # Current user
    gid = os.getgid()  # Current group

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data,
        uid=uid,
        gid=gid
    )

    file_stat = os.stat(target)
    assert file_stat.st_uid == uid
    assert file_stat.st_gid == gid

    os.unlink(target)


def test__atomic_replace_handles_empty_data(test_directory):
    """Test that atomic_replace handles empty data correctly."""
    target = os.path.join(test_directory, 'empty_file.txt')
    data = b""

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data
    )

    assert os.path.exists(target)
    assert os.path.getsize(target) == 0

    os.unlink(target)


def test__atomic_replace_handles_large_data(test_directory):
    """Test that atomic_replace handles large data correctly."""
    target = os.path.join(test_directory, 'large_file.txt')
    # Create 1MB of data
    data = b"A" * (1024 * 1024)

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data
    )

    assert os.path.getsize(target) == len(data)
    with open(target, 'rb') as f:
        assert f.read() == data

    os.unlink(target)


def test__atomic_replace_preserves_data_on_replace(test_directory):
    """Test that atomic_replace preserves old data until replacement is complete."""
    target = os.path.join(test_directory, 'preserve_file.txt')
    original_data = b"Original data that should not be lost"

    # Create initial file
    with open(target, 'wb') as f:
        f.write(original_data)

    # Verify original data exists
    with open(target, 'rb') as f:
        assert f.read() == original_data

    # Replace with new content
    new_data = b"New data after atomic replace"
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=new_data
    )

    # Verify new data
    with open(target, 'rb') as f:
        content = f.read()
        assert content == new_data
        assert content != original_data

    os.unlink(target)


def test__atomic_replace_handles_binary_data(test_directory):
    """Test that atomic_replace correctly handles binary data with null bytes."""
    target = os.path.join(test_directory, 'binary_file.bin')
    data = bytes([0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD, 0x00, 0x00])

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data
    )

    with open(target, 'rb') as f:
        assert f.read() == data

    os.unlink(target)


def test__atomic_replace_fails_with_nonexistent_temp_path(test_directory):
    """Test that atomic_replace fails when temp_path doesn't exist."""
    target = os.path.join(test_directory, 'will_fail.txt')
    nonexistent_temp = os.path.join(test_directory, 'nonexistent_dir')
    data = b"This should fail"

    with pytest.raises((OSError, FileNotFoundError)):
        atomic_replace(
            temp_path=nonexistent_temp,
            target_file=target,
            data=data
        )


def test__atomic_replace_multiple_operations(test_directory):
    """Test multiple atomic_replace operations on the same file."""
    target = os.path.join(test_directory, 'multi_op_file.txt')

    # First write
    data1 = b"First content"
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data1
    )
    with open(target, 'rb') as f:
        assert f.read() == data1

    # Second write
    data2 = b"Second content"
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data2
    )
    with open(target, 'rb') as f:
        assert f.read() == data2

    # Third write with different permissions
    data3 = b"Third content"
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data3,
        perms=0o600
    )
    with open(target, 'rb') as f:
        assert f.read() == data3

    file_stat = os.stat(target)
    assert stat.S_IMODE(file_stat.st_mode) == 0o600

    os.unlink(target)


# Tests for atomic_write context manager


def test__atomic_write_creates_new_file_text_mode(test_directory):
    """Test that atomic_write creates a new file in text mode."""
    target = os.path.join(test_directory, 'new_text_file.txt')
    content = "Hello, World!"

    with atomic_write(target) as f:
        f.write(content)

    assert os.path.exists(target)
    with open(target, 'r') as f:
        assert f.read() == content

    os.unlink(target)


def test__atomic_write_creates_new_file_binary_mode(test_directory):
    """Test that atomic_write creates a new file in binary mode."""
    target = os.path.join(test_directory, 'new_binary_file.bin')
    data = b"Binary data"

    with atomic_write(target, "wb") as f:
        f.write(data)

    assert os.path.exists(target)
    with open(target, 'rb') as f:
        assert f.read() == data

    os.unlink(target)


def test__atomic_write_replaces_existing_file(test_directory):
    """Test that atomic_write replaces an existing file's contents."""
    target = os.path.join(test_directory, 'existing_text_file.txt')

    # Create initial file
    with open(target, 'w') as f:
        f.write("Original content")

    # Replace with new content
    new_content = "New content"
    with atomic_write(target) as f:
        f.write(new_content)

    with open(target, 'r') as f:
        assert f.read() == new_content

    os.unlink(target)


def test__atomic_write_sets_permissions(test_directory):
    """Test that atomic_write sets file permissions correctly."""
    target = os.path.join(test_directory, 'perms_text_file.txt')
    content = "Permission test"
    perms = 0o644

    with atomic_write(target, perms=perms) as f:
        f.write(content)

    file_stat = os.stat(target)
    assert stat.S_IMODE(file_stat.st_mode) == perms

    os.unlink(target)


def test__atomic_write_sets_ownership(test_directory):
    """Test that atomic_write sets file ownership correctly."""
    target = os.path.join(test_directory, 'owner_text_file.txt')
    content = "Ownership test"
    uid = os.getuid()  # Current user
    gid = os.getgid()  # Current group

    with atomic_write(target, uid=uid, gid=gid) as f:
        f.write(content)

    file_stat = os.stat(target)
    assert file_stat.st_uid == uid
    assert file_stat.st_gid == gid

    os.unlink(target)


def test__atomic_write_handles_empty_content(test_directory):
    """Test that atomic_write handles empty content correctly."""
    target = os.path.join(test_directory, 'empty_text_file.txt')

    with atomic_write(target) as f:
        f.write("")

    assert os.path.exists(target)
    assert os.path.getsize(target) == 0

    os.unlink(target)


def test__atomic_write_handles_large_content(test_directory):
    """Test that atomic_write handles large content correctly."""
    target = os.path.join(test_directory, 'large_text_file.txt')
    # Create 1MB of text data
    content = "A" * (1024 * 1024)

    with atomic_write(target) as f:
        f.write(content)

    assert os.path.getsize(target) == len(content)
    with open(target, 'r') as f:
        assert f.read() == content

    os.unlink(target)


def test__atomic_write_handles_binary_data_with_null_bytes(test_directory):
    """Test that atomic_write correctly handles binary data with null bytes."""
    target = os.path.join(test_directory, 'binary_with_nulls.bin')
    data = bytes([0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD, 0x00, 0x00])

    with atomic_write(target, "wb") as f:
        f.write(data)

    with open(target, 'rb') as f:
        assert f.read() == data

    os.unlink(target)


def test__atomic_write_validates_mode(test_directory):
    """Test that atomic_write only accepts 'w' or 'wb' modes."""
    target = os.path.join(test_directory, 'mode_test.txt')

    # These should fail
    invalid_modes = ['r', 'rb', 'a', 'ab', 'r+', 'w+', 'x', 'wt']
    for mode in invalid_modes:
        with pytest.raises(ValueError, match='invalid mode'):
            with atomic_write(target, mode) as f:
                f.write("test")


def test__atomic_write_uses_default_tmppath(test_directory):
    """Test that atomic_write defaults tmppath to dirname(target)."""
    target = os.path.join(test_directory, 'default_tmppath.txt')
    content = "Testing default tmppath"

    # Don't specify tmppath - it should use test_directory
    with atomic_write(target) as f:
        f.write(content)

    assert os.path.exists(target)
    with open(target, 'r') as f:
        assert f.read() == content

    os.unlink(target)


def test__atomic_write_uses_explicit_tmppath(test_directory):
    """Test that atomic_write respects explicit tmppath parameter."""
    target = os.path.join(test_directory, 'explicit_tmppath.txt')
    content = "Testing explicit tmppath"

    with atomic_write(target, tmppath=test_directory) as f:
        f.write(content)

    assert os.path.exists(target)
    with open(target, 'r') as f:
        assert f.read() == content

    os.unlink(target)


def test__atomic_write_does_not_replace_on_exception(test_directory):
    """Test that atomic_write does not replace file if exception occurs."""
    target = os.path.join(test_directory, 'exception_test.txt')
    original_content = "Original content"

    # Create initial file
    with open(target, 'w') as f:
        f.write(original_content)

    # Try to write but raise exception
    with pytest.raises(ValueError):
        with atomic_write(target) as f:
            f.write("This should not be written")
            raise ValueError("Intentional error")

    # Original content should be preserved
    with open(target, 'r') as f:
        assert f.read() == original_content

    os.unlink(target)


def test__atomic_write_multiple_writes_in_context(test_directory):
    """Test that atomic_write handles multiple write calls in one context."""
    target = os.path.join(test_directory, 'multi_write.txt')

    with atomic_write(target) as f:
        f.write("First line\n")
        f.write("Second line\n")
        f.write("Third line\n")

    with open(target, 'r') as f:
        content = f.read()
        assert content == "First line\nSecond line\nThird line\n"

    os.unlink(target)


def test__atomic_write_binary_mode_rejects_string(test_directory):
    """Test that binary mode rejects string data."""
    target = os.path.join(test_directory, 'binary_string_test.bin')

    with pytest.raises(TypeError):
        with atomic_write(target, "wb") as f:
            f.write("This is a string, not bytes")

    # File should not exist if write failed
    if os.path.exists(target):
        os.unlink(target)


def test__atomic_write_text_mode_accepts_string(test_directory):
    """Test that text mode accepts string data."""
    target = os.path.join(test_directory, 'text_string_test.txt')
    content = "This is a string"

    with atomic_write(target, "w") as f:
        f.write(content)

    with open(target, 'r') as f:
        assert f.read() == content

    os.unlink(target)


def test__atomic_write_preserves_data_until_complete(test_directory):
    """Test that atomic_write preserves old data until replacement is complete."""
    target = os.path.join(test_directory, 'preserve_test.txt')
    original_content = "Original data that should not be lost"

    # Create initial file
    with open(target, 'w') as f:
        f.write(original_content)

    # Verify original data exists
    with open(target, 'r') as f:
        assert f.read() == original_content

    # Replace with new content
    new_content = "New data after atomic write"
    with atomic_write(target) as f:
        f.write(new_content)

    # Verify new data
    with open(target, 'r') as f:
        content = f.read()
        assert content == new_content
        assert content != original_content

    os.unlink(target)


def test__atomic_write_multiple_operations(test_directory):
    """Test multiple atomic_write operations on the same file."""
    target = os.path.join(test_directory, 'multi_op_text_file.txt')

    # First write
    content1 = "First content"
    with atomic_write(target) as f:
        f.write(content1)
    with open(target, 'r') as f:
        assert f.read() == content1

    # Second write
    content2 = "Second content"
    with atomic_write(target) as f:
        f.write(content2)
    with open(target, 'r') as f:
        assert f.read() == content2

    # Third write with different permissions
    content3 = "Third content"
    with atomic_write(target, perms=0o600) as f:
        f.write(content3)
    with open(target, 'r') as f:
        assert f.read() == content3

    file_stat = os.stat(target)
    assert stat.S_IMODE(file_stat.st_mode) == 0o600

    os.unlink(target)


# Tests for -1 uid/gid preservation feature


def test__atomic_replace_preserves_uid_when_minus_one(test_directory):
    """Test that atomic_replace preserves existing uid when uid=-1."""
    target = os.path.join(test_directory, 'preserve_uid_file.txt')

    # Create initial file with specific ownership
    initial_data = b"Initial content"

    with open(target, 'wb') as f:
        f.write(initial_data)
    os.chown(target, TEST_UID, TEST_GID)

    # Replace file with uid=-1 to preserve existing uid, but change gid
    new_data = b"New content"
    new_gid = 1000

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=new_data,
        uid=-1,  # Should preserve existing uid
        gid=new_gid
    )

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID  # Should be preserved
    assert file_stat.st_gid == new_gid  # Should be changed

    with open(target, 'rb') as f:
        assert f.read() == new_data

    os.unlink(target)


def test__atomic_replace_preserves_gid_when_minus_one(test_directory):
    """Test that atomic_replace preserves existing gid when gid=-1."""
    target = os.path.join(test_directory, 'preserve_gid_file.txt')

    # Create initial file with specific ownership
    initial_data = b"Initial content"

    with open(target, 'wb') as f:
        f.write(initial_data)
    os.chown(target, TEST_UID, TEST_GID)

    # Replace file with gid=-1 to preserve existing gid, but change uid
    new_data = b"New content"
    new_uid = 1000

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=new_data,
        uid=new_uid,
        gid=-1  # Should preserve existing gid
    )

    file_stat = os.stat(target)
    assert file_stat.st_uid == new_uid  # Should be changed
    assert file_stat.st_gid == TEST_GID  # Should be preserved

    with open(target, 'rb') as f:
        assert f.read() == new_data

    os.unlink(target)


def test__atomic_replace_preserves_both_uid_gid_when_minus_one(test_directory):
    """Test that atomic_replace preserves both uid and gid when both are -1."""
    target = os.path.join(test_directory, 'preserve_both_file.txt')

    # Create initial file with specific ownership
    initial_data = b"Initial content"

    with open(target, 'wb') as f:
        f.write(initial_data)
    os.chown(target, TEST_UID, TEST_GID)

    # Replace file with both uid=-1 and gid=-1
    new_data = b"New content preserving ownership"

    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=new_data,
        uid=-1,  # Should preserve existing uid
        gid=-1   # Should preserve existing gid
    )

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID  # Should be preserved
    assert file_stat.st_gid == TEST_GID  # Should be preserved

    with open(target, 'rb') as f:
        assert f.read() == new_data

    os.unlink(target)


def test__atomic_replace_defaults_to_zero_when_minus_one_no_file(test_directory):
    """Test that atomic_replace defaults to 0 when uid/gid=-1 and file doesn't exist."""
    target = os.path.join(test_directory, 'new_file_minus_one.txt')
    data = b"New file with -1 ownership"

    # File doesn't exist, so -1 should default to 0
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=data,
        uid=-1,
        gid=-1
    )

    assert os.path.exists(target)
    file_stat = os.stat(target)
    # When file doesn't exist, -1 should default to 0
    assert file_stat.st_uid == 0
    assert file_stat.st_gid == 0

    os.unlink(target)


def test__atomic_replace_preserves_ownership_across_multiple_updates(test_directory):
    """Test that ownership preservation works across multiple updates."""
    target = os.path.join(test_directory, 'multi_update_preserve.txt')

    # Create initial file
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=b"First version",
        uid=TEST_UID,
        gid=TEST_GID
    )

    # Update 1: Preserve both
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=b"Second version",
        uid=-1,
        gid=-1
    )

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == TEST_GID

    # Update 2: Preserve both again
    atomic_replace(
        temp_path=test_directory,
        target_file=target,
        data=b"Third version",
        uid=-1,
        gid=-1
    )

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == TEST_GID

    os.unlink(target)


def test__atomic_write_preserves_uid_when_minus_one(test_directory):
    """Test that atomic_write preserves existing uid when uid=-1."""
    target = os.path.join(test_directory, 'preserve_uid_write.txt')

    # Create initial file
    with open(target, 'w') as f:
        f.write("Initial content")
    os.chown(target, TEST_UID, TEST_GID)

    # Replace with uid=-1
    new_gid = 1000
    with atomic_write(target, uid=-1, gid=new_gid) as f:
        f.write("New content")

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == new_gid

    os.unlink(target)


def test__atomic_write_preserves_gid_when_minus_one(test_directory):
    """Test that atomic_write preserves existing gid when gid=-1."""
    target = os.path.join(test_directory, 'preserve_gid_write.txt')

    # Create initial file
    with open(target, 'w') as f:
        f.write("Initial content")
    os.chown(target, TEST_UID, TEST_GID)

    # Replace with gid=-1
    new_uid = 1000
    with atomic_write(target, uid=new_uid, gid=-1) as f:
        f.write("New content")

    file_stat = os.stat(target)
    assert file_stat.st_uid == new_uid
    assert file_stat.st_gid == TEST_GID

    os.unlink(target)


def test__atomic_write_preserves_both_uid_gid_when_minus_one(test_directory):
    """Test that atomic_write preserves both uid and gid when both are -1."""
    target = os.path.join(test_directory, 'preserve_both_write.txt')

    # Create initial file
    with open(target, 'w') as f:
        f.write("Initial content")
    os.chown(target, TEST_UID, TEST_GID)

    # Replace with both -1
    with atomic_write(target, uid=-1, gid=-1) as f:
        f.write("New content")

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == TEST_GID

    os.unlink(target)


def test__atomic_write_defaults_to_zero_when_minus_one_no_file(test_directory):
    """Test that atomic_write defaults to 0 when uid/gid=-1 and file doesn't exist."""
    target = os.path.join(test_directory, 'new_write_minus_one.txt')

    # File doesn't exist, so -1 should default to 0
    with atomic_write(target, uid=-1, gid=-1) as f:
        f.write("New file content")

    assert os.path.exists(target)
    file_stat = os.stat(target)
    assert file_stat.st_uid == 0
    assert file_stat.st_gid == 0

    os.unlink(target)


def test__atomic_write_preserves_ownership_across_multiple_updates(test_directory):
    """Test that atomic_write ownership preservation works across multiple updates."""
    target = os.path.join(test_directory, 'multi_write_preserve.txt')

    # Create initial file
    with atomic_write(target, uid=TEST_UID, gid=TEST_GID) as f:
        f.write("First version")

    # Update 1: Preserve both
    with atomic_write(target, uid=-1, gid=-1) as f:
        f.write("Second version")

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == TEST_GID

    # Update 2: Preserve both again
    with atomic_write(target, uid=-1, gid=-1) as f:
        f.write("Third version")

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == TEST_GID

    os.unlink(target)


def test__atomic_write_binary_preserves_ownership_when_minus_one(test_directory):
    """Test that atomic_write in binary mode preserves ownership when uid/gid=-1."""
    target = os.path.join(test_directory, 'preserve_binary_write.bin')

    # Create initial file
    with open(target, 'wb') as f:
        f.write(b"Initial binary content")
    os.chown(target, TEST_UID, TEST_GID)

    # Replace with both -1 in binary mode
    with atomic_write(target, "wb", uid=-1, gid=-1) as f:
        f.write(b"New binary content")

    file_stat = os.stat(target)
    assert file_stat.st_uid == TEST_UID
    assert file_stat.st_gid == TEST_GID

    with open(target, 'rb') as f:
        assert f.read() == b"New binary content"

    os.unlink(target)
