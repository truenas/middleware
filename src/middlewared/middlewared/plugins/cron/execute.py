from __future__ import annotations

import errno
from typing import TYPE_CHECKING

from middlewared.api.current import CronJobSchedule
from middlewared.service import CallError, ServiceContext
from middlewared.utils.user_context import run_command_with_user_context


if TYPE_CHECKING:
    from middlewared.job import Job


def construct_cron_command(
    schedule: CronJobSchedule, user: str, command: str, stdout: bool = True, stderr: bool = True
) -> list[str]:
    return list(
        filter(
            bool, (
                schedule.minute, schedule.hour, schedule.dom, schedule.month,
                schedule.dow, user,
                'PATH="/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin"',
                command.replace('\n', ''),
                '> /dev/null' if stdout else '', '2> /dev/null' if stderr else ''
            )
        )
    )


def execute_cron_task(context: ServiceContext, job: Job, task_id: int, skip_disabled: bool) -> None:
    assert job.logs_fd is not None
    cron_task = context.call_sync2(context.s.cronjob.get_instance, task_id)
    if skip_disabled and not cron_task.enabled:
        raise CallError('Cron job is disabled', errno.EINVAL)

    cron_cmd = ' '.join(
        construct_cron_command(
            cron_task.schedule, cron_task.user, cron_task.command, cron_task.stdout, cron_task.stderr
        )[7:]
    )

    job.set_progress(10, 'Executing Cron Task')

    cp = run_command_with_user_context(cron_cmd, cron_task.user, callback=job.logs_fd.write)

    job.set_progress(85, 'Executed Cron Task')
    if cp.stdout:
        email = (
            context.middleware.call_sync('user.query', [['username', '=', cron_task.user]], {'get': True})
        )['email']
        stdout = cp.stdout.decode()
        if email:
            text = (
                    'The command:\n\n' +
                    cron_task.command + '\n\n' +
                    'Produced the following output:\n\n' +
                    stdout.rstrip() + '\n\n' +
                    "If you don't wish to receive these e-mails, please go to your Cron Job options and check " +
                    '"Hide Standard Output" and "Hide Standard Error" checkboxes.'
            )

            mail_job = context.middleware.call_sync(
                'mail.send', {
                    'subject': 'Cron Job Run',
                    'text': text,
                    'to': [email]
                }
            )

            job.set_progress(
                95,
                'Sending mail for Cron Task output'
            )

            mail_job.wait_sync()
            if mail_job.error:
                job.logs_fd.write(f'Failed to send email for CronTask run: {mail_job.error}'.encode())
        else:
            job.set_progress(
                95,
                'Email for root user not configured. Skipping sending mail.'
            )

        job.logs_fd.write(f'Executed CronTask - {cron_cmd}: {stdout}'.encode())

    if cp.returncode:
        raise CallError(f'CronTask "{cron_cmd}" exited with {cp.returncode} (non-zero) exit status.')

    job.set_progress(
        100,
        'Execution of Cron Task complete.'
    )
