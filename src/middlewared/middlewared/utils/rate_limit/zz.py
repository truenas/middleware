import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from time import monotonic
from cache import RateLimitCache

# Mock configurations and global cache
class RateLimitConfig:
    separator = ":"
    max_period = 60  # 1 minute
    max_calls = 5
    sleep_start = 0.1
    sleep_end = 0.5
    max_cache_entries = 100

RL_CACHE = {}

class TCPIPOrigin:
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port

def is_ha_connection(ip, port):
    return False

class RateLimitObject:
    def __init__(self, num_times_called, last_reset):
        self.num_times_called = num_times_called
        self.last_reset = last_reset

# The RateLimit class (as provided)

# Unit test class
class TestRateLimit(unittest.TestCase):
    def setUp(self):
        self.rate_limiter = RateLimitCache
        self.method_name = "test_method"
        self.ip = "192.168.1.1"
        self.origin = TCPIPOrigin(self.ip, 12345)
        RL_CACHE.clear()

    def test_cache_key(self):
        key = self.rate_limiter.cache_key(self.method_name, self.ip)
        self.assertEqual(key, f"{self.method_name}:{self.ip}")

    @patch("time.monotonic", return_value=100.0)
    def test_rate_limit_not_exceeded_first_call(self, mock_monotonic):
        RL_CACHE[f"{self.method_name}:{self.ip}"] = RateLimitObject(0, 90.0)
        exceeded = self.rate_limiter.rate_limit_exceeded(self.method_name, self.ip)
        self.assertFalse(exceeded)
        self.assertEqual(RL_CACHE[f"{self.method_name}:{self.ip}"].num_times_called, 1)

    @patch("time.monotonic", return_value=200.0)
    def test_rate_limit_reset(self, mock_monotonic):
        RL_CACHE[f"{self.method_name}:{self.ip}"] = RateLimitObject(RateLimitConfig.max_calls, 100.0)
        exceeded = self.rate_limiter.rate_limit_exceeded(self.method_name, self.ip)
        self.assertFalse(exceeded)
        self.assertEqual(RL_CACHE[f"{self.method_name}:{self.ip}"].num_times_called, 1)
        self.assertEqual(RL_CACHE[f"{self.method_name}:{self.ip}"].last_reset, 200.0)

    @patch("time.monotonic", return_value=100.0)
    def test_rate_limit_exceeded(self, mock_monotonic):
        RL_CACHE[f"{self.method_name}:{self.ip}"] = RateLimitObject(RateLimitConfig.max_calls, 90.0)
        exceeded = self.rate_limiter.rate_limit_exceeded(self.method_name, self.ip)
        self.assertTrue(exceeded)

    @patch("time.monotonic", return_value=100.0)
    async def test_add_entry_to_cache(self, mock_monotonic):
        ip = await self.rate_limiter.add(self.method_name, self.origin)
        self.assertIsNotNone(ip)
        self.assertIn(f"{self.method_name}:{self.ip}", RL_CACHE)
        self.assertEqual(RL_CACHE[f"{self.method_name}:{self.ip}"].num_times_called, 0)

    async def test_add_invalid_origin(self):
        origin = TCPIPOrigin(None, 12345)
        ip = await self.rate_limiter.add(self.method_name, origin)
        self.assertIsNone(ip)

    async def test_pop_entry_from_cache(self):
        await self.rate_limiter.add(self.method_name, self.origin)
        await self.rate_limiter.pop(self.method_name, self.ip)
        self.assertNotIn(f"{self.method_name}:{self.ip}", RL_CACHE)

    async def test_clear_cache(self):
        await self.rate_limiter.add(self.method_name, self.origin)
        await self.rate_limiter.clear()
        self.assertEqual(len(RL_CACHE), 0)

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("random.uniform", return_value=0.3)
    async def test_random_sleep(self, mock_uniform, mock_sleep):
        await self.rate_limiter.random_sleep()
        mock_sleep.assert_called_with(0.3)

    def test_max_entries_reached(self):
        for i in range(RateLimitConfig.max_cache_entries):
            RL_CACHE[f"method{i}:{self.ip}"] = RateLimitObject(0, monotonic())
        self.assertTrue(self.rate_limiter.max_entries_reached)

        RL_CACHE.pop(f"method0:{self.ip}")
        self.assertFalse(self.rate_limiter.max_entries_reached)

if __name__ == "__main__":
    unittest.main()
