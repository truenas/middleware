import uuid

import pytest

from middlewared.test.integration.utils import client, mock


@pytest.mark.parametrize("block", [True, False])
def test_block_hooks(block):
    hook_name = str(uuid.uuid4())

    with mock("test.test1", """
        async def mock(self, hook_name, blocked_hooks):
            from pathlib import Path

            sentinel = Path("/tmp/block_hooks_sentinel")
            
            async def hook(middleware):
                sentinel.write_text("")        

            self.middleware.register_hook(hook_name, hook, blockable=True, sync=True)

            sentinel.unlink(missing_ok=True)
            with self.middleware.block_hooks(*blocked_hooks):
                await self.middleware.call_hook(hook_name)
            
            return sentinel.exists()
    """):
        with client() as c:
            assert c.call("test.test1", hook_name, [hook_name] if block else []) == (not block)
