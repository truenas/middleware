import asyncio
from unittest.mock import MagicMock

import pytest

from middlewared.job import Job
from middlewared.service import Service, ServicePartBase, job, private
from middlewared.service_exception import CallError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(**kwargs):
    """Create a minimal Job for testing without a real Middleware instance."""
    mw = MagicMock()
    mw.loop = asyncio.get_event_loop()
    mw.create_task = asyncio.ensure_future
    defaults = {
        'lock': None,
        'lock_queue_size': None,
        'logs': False,
        'pipes': [],
        'check_pipes': False,
        'transient': False,
        'description': None,
        'abortable': False,
        'read_roles': [],
    }
    return Job(
        middleware=mw,
        method_name='test.method',
        serviceobj=MagicMock(),
        method=MagicMock(),
        args=[],
        options=defaults,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 2A: _JobDecorator behaviour
# ---------------------------------------------------------------------------

class TestJobDecoratorOptions:
    def test_sets_options(self):
        """@job sets _job dict with specified options."""
        @job(lock='test_lock', logs=True, abortable=True)
        def method(self, job_arg):
            pass

        assert hasattr(method, '_job')
        assert method._job['lock'] == 'test_lock'
        assert method._job['logs'] is True
        assert method._job['abortable'] is True

    def test_default_options(self):
        """@job with no args uses sensible defaults."""
        @job()
        def method(self, job_arg):
            pass

        assert method._job['lock'] is None
        assert method._job['lock_queue_size'] == 5
        assert method._job['logs'] is False
        assert method._job['pipes'] == []
        assert method._job['check_pipes'] is True
        assert method._job['transient'] is False
        assert method._job['abortable'] is False
        assert method._job['read_roles'] == []

    def test_all_options(self):
        """@job preserves all option types."""
        def desc_fn(args):
            return f'Processing {args[0]}'

        def lock_fn(args):
            return f'lock_{args[0]}'

        @job(
            lock=lock_fn, lock_queue_size=10, logs=True,
            pipes=['input', 'output'], check_pipes=False,
            transient=True, description=desc_fn, abortable=True,
            read_roles=['READONLY_ADMIN'],
        )
        def method(self, job_arg, name):
            pass

        opts = method._job
        assert opts['lock'] is lock_fn
        assert opts['lock_queue_size'] == 10
        assert opts['pipes'] == ['input', 'output']
        assert opts['check_pipes'] is False
        assert opts['transient'] is True
        assert opts['description'] is desc_fn
        assert opts['read_roles'] == ['READONLY_ADMIN']


# ---------------------------------------------------------------------------
# 2B: Decorator stacking
# ---------------------------------------------------------------------------

class TestJobDecoratorStacking:
    def test_job_with_private(self):
        """@job + @private -- both set their attributes."""
        @job()
        @private
        def method(self, job_arg, data):
            return data

        assert hasattr(method, '_job')
        assert hasattr(method, '_private')

    def test_private_with_job(self):
        """@private + @job -- order doesn't matter for attribute setting."""
        @private
        @job()
        def method(self, job_arg, data):
            return data

        assert hasattr(method, '_job')
        assert hasattr(method, '_private')

    def test_preserves_function_identity(self):
        """@job returns the original function (not a wrapper)."""
        def method(self, job_arg):
            return 42

        decorated = job()(method)
        assert decorated is method
        assert decorated(None, None) == 42


# ---------------------------------------------------------------------------
# 2C: Job[T] result behaviour
# ---------------------------------------------------------------------------

class TestJobResult:
    def test_result_initially_none(self):
        j = _make_job()
        assert j.result is None

    def test_set_result_string(self):
        j = _make_job()
        j.set_result('backup-name')
        assert j.result == 'backup-name'

    def test_set_result_dict(self):
        j = _make_job()
        j.set_result({'pool': 'tank', 'status': 'RUNNING'})
        assert j.result == {'pool': 'tank', 'status': 'RUNNING'}

    def test_set_result_none(self):
        j = _make_job()
        j.set_result(None)
        assert j.result is None

    def test_set_result_bool(self):
        j = _make_job()
        j.set_result(True)
        assert j.result is True

    def test_set_result_list(self):
        j = _make_job()
        j.set_result([1, 2, 3])
        assert j.result == [1, 2, 3]


# ---------------------------------------------------------------------------
# 2D: Job.wait() and Job.wait_sync() async behaviour
# ---------------------------------------------------------------------------

class TestJobWait:
    @pytest.mark.asyncio
    async def test_wait_returns_result(self):
        """wait() returns the result after job completion."""
        j = _make_job()
        j.set_result('test-result')
        j._finished.set()
        result = await j.wait()
        assert result == 'test-result'

    @pytest.mark.asyncio
    async def test_wait_raises_on_error(self):
        """wait(raise_error=True) raises CallError when job failed."""
        j = _make_job()
        exc = CallError('Something went wrong')
        j.error = 'Something went wrong'
        j.exc_info = (CallError, exc, None)
        j._finished.set()
        with pytest.raises(CallError, match='Something went wrong'):
            await j.wait(raise_error=True)

    @pytest.mark.asyncio
    async def test_wait_timeout(self):
        """wait() raises TimeoutError when job doesn't complete in time."""
        j = _make_job()
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            await j.wait(timeout=0.01)


# ---------------------------------------------------------------------------
# 2E: Job.wrap() behaviour
# ---------------------------------------------------------------------------

class TestJobWrap:
    @pytest.mark.asyncio
    async def test_wrap_returns_subjob_result(self):
        """wrap() returns the wrapped job's result."""
        parent = _make_job()
        child = _make_job()
        child.set_result('child-result')
        child._finished.set()
        result = await parent.wrap(child)
        assert result == 'child-result'

    @pytest.mark.asyncio
    async def test_wrap_proxies_progress(self):
        """wrap() copies initial progress from subjob to parent."""
        parent = _make_job()
        child = _make_job()
        child.progress = {'percent': 50, 'description': 'halfway', 'extra': None}
        child.set_result(None)
        child._finished.set()
        await parent.wrap(child)
        assert parent.progress['percent'] == 50

    @pytest.mark.asyncio
    async def test_wrap_adds_to_wrapped_list(self):
        """wrap() adds parent to subjob's wrapped list."""
        parent = _make_job()
        child = _make_job()
        child.set_result(None)
        child._finished.set()
        await parent.wrap(child)
        assert parent in child.wrapped


# ---------------------------------------------------------------------------
# 2F: Job.set_progress() behaviour
# ---------------------------------------------------------------------------

class TestJobSetProgress:
    def test_set_progress_percent(self):
        j = _make_job()
        j.set_progress(50)
        assert j.progress['percent'] == 50

    def test_set_progress_description(self):
        j = _make_job()
        j.set_progress(description='Loading data')
        assert j.progress['description'] == 'Loading data'

    def test_set_progress_truncates_to_int(self):
        """Percent is rounded down to int."""
        j = _make_job()
        j.set_progress(73.64)
        assert j.progress['percent'] == 73

    def test_set_progress_extra(self):
        j = _make_job()
        j.set_progress(extra={'speed': '10MB/s'})
        assert j.progress['extra'] == {'speed': '10MB/s'}

    def test_set_progress_all(self):
        j = _make_job()
        j.set_progress(90, 'Almost done', {'remaining': 1})
        assert j.progress['percent'] == 90
        assert j.progress['description'] == 'Almost done'
        assert j.progress['extra'] == {'remaining': 1}


# ---------------------------------------------------------------------------
# 2G: ServicePartBase integration
# ---------------------------------------------------------------------------

class TestJobServicePart:
    def test_job_in_service_part(self):
        """@job works correctly in ServicePartBase + Service class hierarchy."""
        class BackupBase(ServicePartBase):
            @job()
            @private
            def backup(self, job_arg, name):
                pass

        class BackupImpl(Service, BackupBase):
            @private
            def backup(self, job_arg, name):
                return f'backed-up-{name}'

        svc = BackupImpl(None)
        assert svc.backup(None, 'pool1') == 'backed-up-pool1'
        assert hasattr(BackupBase.backup, '_job')

    def test_service_part_preserves_job_options(self):
        """@job options survive through ServicePartBase inheritance."""
        class ProcessBase(ServicePartBase):
            @job(lock='process_lock', abortable=True)
            @private
            def process(self, job_arg, data):
                pass

        assert ProcessBase.process._job['lock'] == 'process_lock'
        assert ProcessBase.process._job['abortable'] is True
