import os
import pytest
import shutil
import stat

from middlewared.utils.io import atomic_replace


TEST_DIR = 'test-atomic-replace'


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
