import base64
import glob
import os
import pytest
import shutil
import tempfile
import truenas_pypwenc

from truenas_api_client import Client
from middlewared.utils.db import FREENAS_DATABASE
from middlewared.utils.pwenc import (
    encrypt,
    decrypt,
    pwenc_rename,
    PWENC_FILE_SECRET,
    PWENC_FILE_SECRET_MODE,
)


@pytest.fixture(scope='module')
def backup_pwenc_and_db():
    """
    Create backups of the pwenc secret file and database at module start,
    and restore them when the module completes.
    """
    pwenc_backup = None
    db_backup = None

    # Create temporary directory for backups
    backup_dir = tempfile.mkdtemp(prefix='pwenc_test_backup_')

    try:
        # Backup pwenc secret if it exists
        if os.path.exists(PWENC_FILE_SECRET):
            pwenc_backup = os.path.join(backup_dir, 'pwenc_secret.backup')
            shutil.copy2(PWENC_FILE_SECRET, pwenc_backup)

        # Backup database if it exists
        if os.path.exists(FREENAS_DATABASE):
            db_backup = os.path.join(backup_dir, 'freenas-v1.db.backup')
            shutil.copy2(FREENAS_DATABASE, db_backup)

        # Clean up any existing pwenc backup files before tests
        for backup_file in glob.glob(f'{PWENC_FILE_SECRET}_old.*'):
            try:
                os.unlink(backup_file)
            except Exception:
                pass

        yield

    finally:
        # Restore pwenc secret
        if pwenc_backup and os.path.exists(pwenc_backup):
            shutil.copy2(pwenc_backup, PWENC_FILE_SECRET)
            os.chmod(PWENC_FILE_SECRET, PWENC_FILE_SECRET_MODE)
            os.chown(PWENC_FILE_SECRET, 0, 0)

        # Restore database
        if db_backup and os.path.exists(db_backup):
            shutil.copy2(db_backup, FREENAS_DATABASE)

        # Clean up backup directory
        shutil.rmtree(backup_dir, ignore_errors=True)

        # Clean up any backup files created during tests
        for backup_file in glob.glob(f'{PWENC_FILE_SECRET}_old.*'):
            try:
                os.unlink(backup_file)
            except Exception:
                pass


def test__pwenc_check(backup_pwenc_and_db):
    """Test that pwenc.check validates the secret correctly"""
    with Client(py_exceptions=True) as c:
        result = c.call('pwenc.check')
        assert isinstance(result, bool)
        assert result is True


@pytest.mark.parametrize('iteration', range(5))
def test__pwenc_check_idempotent(backup_pwenc_and_db, iteration):
    """Test that pwenc.check can be called multiple times"""
    with Client(py_exceptions=True) as c:
        result = c.call('pwenc.check')
        assert result is True


def test__pwenc_generate_secret(backup_pwenc_and_db):
    """Test generating a new pwenc secret"""
    with Client(py_exceptions=True) as c:
        # Verify initial check passes
        assert c.call('pwenc.check') is True

        # Get the initial modification time of the pwenc file
        initial_mtime = os.path.getmtime(PWENC_FILE_SECRET)

        # Generate new secret
        c.call('pwenc.generate_secret')

        # Check should still pass with new secret
        assert c.call('pwenc.check') is True

        # Verify the secret file was modified
        new_mtime = os.path.getmtime(PWENC_FILE_SECRET)
        assert new_mtime > initial_mtime


def test__pwenc_generate_secret_creates_backup(backup_pwenc_and_db):
    """Test that generating a new secret creates a backup of the old secret"""
    with Client(py_exceptions=True) as c:
        # Get list of existing backup files
        existing_backups = glob.glob(f'{PWENC_FILE_SECRET}_old.*')
        initial_backup_count = len(existing_backups)

        # Generate new secret (should create a backup)
        c.call('pwenc.generate_secret')

        # Check that a new backup was created
        new_backups = glob.glob(f'{PWENC_FILE_SECRET}_old.*')
        assert len(new_backups) == initial_backup_count + 1

        # Verify the backup file exists and is readable
        new_backup = [b for b in new_backups if b not in existing_backups][0]
        assert os.path.exists(new_backup)
        assert os.path.getsize(new_backup) == truenas_pypwenc.PWENC_BLOCK_SIZE


@pytest.mark.parametrize('expected_mode,expected_uid,expected_gid', [
    (PWENC_FILE_SECRET_MODE, 0, 0),
])
def test__pwenc_file_permissions(backup_pwenc_and_db, expected_mode, expected_uid, expected_gid):
    """Test that pwenc secret file has correct permissions"""
    stat_info = os.stat(PWENC_FILE_SECRET)

    # Should be 0o600 (read/write for owner only)
    assert stat_info.st_mode & 0o777 == expected_mode

    # Should be owned by root
    assert stat_info.st_uid == expected_uid
    assert stat_info.st_gid == expected_gid


def test__pwenc_file_exists(backup_pwenc_and_db):
    """Test that pwenc secret file exists and is not empty"""
    assert os.path.exists(PWENC_FILE_SECRET)
    assert os.path.isfile(PWENC_FILE_SECRET)

    # File should be exactly PWENC_BLOCK_SIZE bytes
    file_size = os.path.getsize(PWENC_FILE_SECRET)
    assert file_size == truenas_pypwenc.PWENC_BLOCK_SIZE


@pytest.mark.parametrize('cycle', range(3))
def test__pwenc_multiple_generate_cycles(backup_pwenc_and_db, cycle):
    """Test that we can generate new secrets multiple times"""
    with Client(py_exceptions=True) as c:
        # Generate new secret
        c.call('pwenc.generate_secret')

        # Verify check still passes
        assert c.call('pwenc.check') is True

        # Verify file still has correct permissions
        stat_info = os.stat(PWENC_FILE_SECRET)
        assert stat_info.st_mode & 0o777 == PWENC_FILE_SECRET_MODE


def test__pwenc_backup_files_cleanup(backup_pwenc_and_db):
    """Test that old backup files can be identified for cleanup"""
    with Client(py_exceptions=True) as c:
        # Generate a couple of secrets to create backups
        c.call('pwenc.generate_secret')
        c.call('pwenc.generate_secret')

        # Get list of backup files
        backup_files = glob.glob(f'{PWENC_FILE_SECRET}_old.*')

        # Should have at least 2 backup files now
        assert len(backup_files) >= 2

        # All backup files should follow the naming pattern with UUID
        for backup_file in backup_files:
            assert backup_file.startswith(f'{PWENC_FILE_SECRET}_old.')
            # UUID part should exist
            uuid_part = backup_file.split('_old.')[1]
            assert len(uuid_part) > 0

            # Backup files should have correct size
            assert os.path.getsize(backup_file) == truenas_pypwenc.PWENC_BLOCK_SIZE


def test__pwenc_rename_with_tmpdir(backup_pwenc_and_db, tmpdir):
    """Test pwenc_rename functionality using tmpdir"""
    # Create a test file in tmpdir with valid pwenc secret size
    test_secret = os.path.join(tmpdir, 'test_secret.tmp')
    with open(test_secret, 'wb') as f:
        # Write a valid-sized secret (32 bytes)
        f.write(b'X' * truenas_pypwenc.PWENC_BLOCK_SIZE)

    # Get list of existing backups
    existing_backups = glob.glob(f'{PWENC_FILE_SECRET}_old.*')
    initial_count = len(existing_backups)

    # Perform rename
    pwenc_rename(test_secret)

    # Verify backup was created
    new_backups = glob.glob(f'{PWENC_FILE_SECRET}_old.*')
    assert len(new_backups) == initial_count + 1

    # Verify the new secret file has correct permissions
    stat_info = os.stat(PWENC_FILE_SECRET)
    assert stat_info.st_mode & 0o777 == PWENC_FILE_SECRET_MODE
    assert stat_info.st_uid == 0
    assert stat_info.st_gid == 0

    # Verify the source file was moved (no longer exists)
    assert not os.path.exists(test_secret)


@pytest.mark.parametrize('wrong_mode', [0o644, 0o666, 0o755])
def test__pwenc_rename_fixes_permissions(backup_pwenc_and_db, tmpdir, wrong_mode):
    """Test that pwenc_rename corrects file permissions"""
    # Create a test file with wrong permissions
    test_secret = os.path.join(tmpdir, f'test_secret_{wrong_mode}.tmp')
    with open(test_secret, 'wb') as f:
        f.write(b'Y' * truenas_pypwenc.PWENC_BLOCK_SIZE)

    # Set wrong permissions
    os.chmod(test_secret, wrong_mode)

    # Perform rename
    pwenc_rename(test_secret)

    # Verify the new secret file has correct permissions (not the wrong ones)
    stat_info = os.stat(PWENC_FILE_SECRET)
    assert stat_info.st_mode & 0o777 == PWENC_FILE_SECRET_MODE


def test__pwenc_rename_nonexistent_file(backup_pwenc_and_db, tmpdir):
    """Test that pwenc_rename raises error for nonexistent file"""
    nonexistent_path = os.path.join(tmpdir, 'nonexistent.tmp')

    with pytest.raises(FileNotFoundError):
        pwenc_rename(nonexistent_path)


@pytest.mark.parametrize('test_data', [
    'Simple string',
    'String with numbers 12345',
    'Special chars !@#$%^&*()',
    'Unicode 你好 世界',
    'Long' * 100,
    'a',
])
def test__pwenc_encrypt_decrypt(backup_pwenc_and_db, test_data):
    """Test encryption and decryption with various data types"""
    encrypted = encrypt(test_data)
    assert encrypted != test_data
    assert isinstance(encrypted, str)

    decrypted = decrypt(encrypted)
    assert decrypted == test_data


def test__pwenc_decrypt_empty_string(backup_pwenc_and_db):
    """Test that decrypting empty string returns empty string"""
    result = decrypt('')
    assert result == ''


def test__pwenc_decrypt_invalid_data(backup_pwenc_and_db):
    """Test that decrypting invalid data returns empty string by default"""
    result = decrypt('this_is_not_encrypted_data')
    assert result == ''

    # With _raise=True, should raise exception
    with pytest.raises(Exception):
        decrypt('this_is_not_encrypted_data', _raise=True)


def test__pwenc_filesystem_file_receive_blocked(backup_pwenc_and_db):
    """Test that filesystem.file_receive cannot be used to write pwenc secret"""
    # Create test data
    test_data = b'Z' * truenas_pypwenc.PWENC_BLOCK_SIZE
    b64_data = base64.b64encode(test_data).decode()

    with Client(py_exceptions=True) as c:
        # Attempting to use filesystem.file_receive on pwenc secret should fail
        with pytest.raises(Exception) as exc_info:
            c.call('filesystem.file_receive', PWENC_FILE_SECRET, b64_data, {})

        # Verify the error message mentions pwenc.replace
        assert 'pwenc.replace' in str(exc_info.value)
