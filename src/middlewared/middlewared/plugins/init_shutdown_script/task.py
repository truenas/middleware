from __future__ import annotations

import asyncio
import os
import subprocess
import typing

from middlewared.api.current import InitShutdownScriptEntry
from middlewared.service import ServiceContext
from middlewared.utils import run

if typing.TYPE_CHECKING:
    from middlewared.job import Job


WHEN_ARG = typing.Literal['PREINIT', 'POSTINIT', 'SHUTDOWN']


def get_cmd(task: InitShutdownScriptEntry) -> str | None:
    if task.type == 'COMMAND':
        return task.command
    elif task.type == 'SCRIPT' and os.path.exists(task.script or ''):
        return f'exec {task.script}'

    return None


async def execute_task(context: ServiceContext, task: InitShutdownScriptEntry) -> None:
    cmd = await context.to_thread(get_cmd, task)
    if not cmd:
        return

    try:
        proc = await run(['sh', '-c', cmd], stderr=subprocess.STDOUT, check=False)
        if proc.returncode:
            context.logger.debug('Failed to execute %r with error %r', cmd, proc.stdout.decode())
    except Exception:
        context.logger.debug('Unexpected failure executing %r', cmd, exc_info=True)


async def execute_init_tasks(context: ServiceContext, job: Job, when: str) -> None:
    tasks = typing.cast(list[InitShutdownScriptEntry], await context.s.initshutdownscript.query([
        ['enabled', '=', True],
        ['when', '=', when]
    ]))
    tasks_len = len(tasks)

    for idx, task in enumerate(tasks):
        cmd = task.command if task.type == 'COMMAND' else task.script
        try:
            await asyncio.wait_for(context.create_task(execute_task(context, task)), timeout=task.timeout)
        except asyncio.TimeoutError:
            context.logger.debug('Timed out running %s: %r', task.type, cmd)
        finally:
            job.set_progress((100 / tasks_len) * (idx + 1))

    job.set_progress(100, f'Completed tasks for {when}')
