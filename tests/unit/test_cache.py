import pytest
import time
from truenas_api_client import Client, ClientException


def test__volatile_put_and_get():
    """Test basic put and get operations on volatile cache."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', 'test_key', 'test_value', 0, 'VOLATILE')
        result = c.call('cache.get', 'test_key', 'VOLATILE')
        assert result == 'test_value'


def test__volatile_has_key():
    """Test has_key operation on volatile cache."""
    with Client(py_exceptions=True) as c:
        # Key should not exist initially
        assert not c.call('cache.has_key', 'nonexistent_key', 'VOLATILE')

        # Put a key and verify it exists
        c.call('cache.put', 'exists_key', 'some_value', 0, 'VOLATILE')
        assert c.call('cache.has_key', 'exists_key', 'VOLATILE')


def test__volatile_pop():
    """Test pop operation on volatile cache."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', 'pop_key', 'pop_value', 0, 'VOLATILE')

        # Pop should return value and remove key
        result = c.call('cache.pop', 'pop_key', 'VOLATILE')
        assert result == 'pop_value'

        # Key should no longer exist
        assert not c.call('cache.has_key', 'pop_key', 'VOLATILE')

        # Pop on non-existent key should return None
        result = c.call('cache.pop', 'nonexistent_pop_key', 'VOLATILE')
        assert result is None


def test__volatile_timeout():
    """Test timeout functionality on volatile cache."""
    with Client(py_exceptions=True) as c:
        # Put a key with 1 second timeout
        c.call('cache.put', 'timeout_key', 'timeout_value', 1, 'VOLATILE')

        # Should exist immediately
        result = c.call('cache.get', 'timeout_key', 'VOLATILE')
        assert result == 'timeout_value'

        # Wait for timeout
        time.sleep(1.5)

        # Should raise KeyError after timeout
        with pytest.raises(KeyError):
            c.call('cache.get', 'timeout_key', 'VOLATILE')


def test__volatile_complex_data():
    """Test storing complex data structures in volatile cache."""
    with Client(py_exceptions=True) as c:
        complex_data = {
            'nested': {
                'key': 'value',
                'number': 42,
                'list': [1, 2, 3]
            }
        }
        c.call('cache.put', 'complex_key', complex_data, 0, 'VOLATILE')
        result = c.call('cache.get', 'complex_key', 'VOLATILE')
        assert result == complex_data


# Persistent Cache Tests

def test__persistent_put_and_get():
    """Test basic put and get operations on persistent cache."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', 'persistent_key', 'persistent_value', 0, 'PERSISTENT')
        result = c.call('cache.get', 'persistent_key', 'PERSISTENT')
        assert result == 'persistent_value'


def test__persistent_has_key():
    """Test has_key operation on persistent cache."""
    with Client(py_exceptions=True) as c:
        # Key should not exist initially
        assert not c.call('cache.has_key', 'persistent_nonexistent', 'PERSISTENT')

        # Put a key and verify it exists
        c.call('cache.put', 'persistent_exists', 'some_value', 0, 'PERSISTENT')
        assert c.call('cache.has_key', 'persistent_exists', 'PERSISTENT')


def test__persistent_pop():
    """Test pop operation on persistent cache."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', 'persistent_pop', 'pop_value', 0, 'PERSISTENT')

        # Pop should return value and remove key
        result = c.call('cache.pop', 'persistent_pop', 'PERSISTENT')
        assert result == 'pop_value'

        # Key should no longer exist
        assert not c.call('cache.has_key', 'persistent_pop', 'PERSISTENT')

        # Pop on non-existent key should return None
        result = c.call('cache.pop', 'persistent_nonexistent_pop', 'PERSISTENT')
        assert result is None


def test__persistent_timeout():
    """Test timeout functionality on persistent cache."""
    with Client(py_exceptions=True) as c:
        # Put a key with 1 second timeout
        c.call('cache.put', 'persistent_timeout', 'timeout_value', 1, 'PERSISTENT')

        # Should exist immediately
        result = c.call('cache.get', 'persistent_timeout', 'PERSISTENT')
        assert result == 'timeout_value'

        # Wait for timeout
        time.sleep(1.5)

        # Should raise KeyError after timeout
        with pytest.raises(KeyError):
            c.call('cache.get', 'persistent_timeout', 'PERSISTENT')


def test__persistent_complex_data():
    """Test storing complex data structures in persistent cache."""
    with Client(py_exceptions=True) as c:
        complex_data = {
            'nested': {
                'key': 'value',
                'number': 42,
                'list': [1, 2, 3],
                'boolean': True
            }
        }
        c.call('cache.put', 'persistent_complex', complex_data, 0, 'PERSISTENT')
        result = c.call('cache.get', 'persistent_complex', 'PERSISTENT')
        assert result == complex_data


def test__persistent_update_value():
    """Test updating an existing key in persistent cache."""
    with Client(py_exceptions=True) as c:
        # Put initial value
        c.call('cache.put', 'update_key', 'initial_value', 0, 'PERSISTENT')
        assert c.call('cache.get', 'update_key', 'PERSISTENT') == 'initial_value'

        # Update value
        c.call('cache.put', 'update_key', 'updated_value', 0, 'PERSISTENT')
        assert c.call('cache.get', 'update_key', 'PERSISTENT') == 'updated_value'


# Cache Isolation Tests

def test__cache_type_isolation():
    """Test that VOLATILE and PERSISTENT caches maintain separate key spaces."""
    with Client(py_exceptions=True) as c:
        # Put same key in both caches with different values
        c.call('cache.put', 'isolation_key', 'volatile_value', 0, 'VOLATILE')
        c.call('cache.put', 'isolation_key', 'persistent_value', 0, 'PERSISTENT')

        # Verify each cache returns its own value
        assert c.call('cache.get', 'isolation_key', 'VOLATILE') == 'volatile_value'
        assert c.call('cache.get', 'isolation_key', 'PERSISTENT') == 'persistent_value'

        # Pop from volatile should not affect persistent
        c.call('cache.pop', 'isolation_key', 'VOLATILE')
        assert not c.call('cache.has_key', 'isolation_key', 'VOLATILE')
        assert c.call('cache.has_key', 'isolation_key', 'PERSISTENT')


# Edge Cases and Error Conditions

def test__get_nonexistent_key():
    """Test getting a non-existent key raises KeyError."""
    with Client(py_exceptions=True) as c:
        with pytest.raises(KeyError):
            c.call('cache.get', 'definitely_does_not_exist', 'VOLATILE')


def test__get_timeout_nonexistent_key():
    """Test get_timeout on non-existent key raises KeyError."""
    with Client(py_exceptions=True) as c:
        with pytest.raises(KeyError):
            c.call('cache.get_timeout', 'timeout_nonexistent', 'VOLATILE')


def test__empty_string_key():
    """Test using empty string as key."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', '', 'empty_key_value', 0, 'VOLATILE')
        assert c.call('cache.get', '', 'VOLATILE') == 'empty_key_value'


def test__none_value():
    """Test storing None as a value."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', 'none_key', None, 0, 'VOLATILE')
        result = c.call('cache.get', 'none_key', 'VOLATILE')
        assert result is None


def test__zero_timeout_means_no_expiration():
    """Test that timeout=0 means the key never expires."""
    with Client(py_exceptions=True) as c:
        c.call('cache.put', 'no_expire_key', 'forever', 0, 'VOLATILE')
        time.sleep(2)
        result = c.call('cache.get', 'no_expire_key', 'VOLATILE')
        assert result == 'forever'


def test__default_cache_type_is_volatile():
    """Test that cache methods default to VOLATILE when cache_type is not specified."""
    with Client(py_exceptions=True) as c:
        # Put with explicit VOLATILE
        c.call('cache.put', 'default_test', 'value1', 0, 'VOLATILE')

        # Get without specifying cache_type (should default to VOLATILE)
        result = c.call('cache.get', 'default_test')
        assert result == 'value1'
