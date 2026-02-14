from __future__ import annotations

import re

from middlewared.service import ServiceContext
from middlewared.utils import run

from .utils import alerts_mapping


LOGGED_ERRORS: list[str] = []
RE_TEST_IN_PROGRESS = re.compile(r'ups.test.result:\s*TestInProgress')
RE_UPS_STATUS = re.compile(r'ups.status: (.*)')


async def handle_upssched_event(context: ServiceContext, notify_type: str) -> None:
    config = await context.call2(context.s.ups.config)
    upsc_identifier = config.complete_identifier
    cp = await run('upsc', upsc_identifier, check=False)
    if cp.returncode:
        stats_output = ''
        stderr = cp.stderr.decode(errors='ignore')
        if stderr not in LOGGED_ERRORS:
            LOGGED_ERRORS.append(stderr)
            context.logger.error('Failed to retrieve ups information: %s', stderr)
    else:
        stats_output = cp.stdout.decode()

    if RE_TEST_IN_PROGRESS.search(stats_output):
        context.logger.debug('Self test is in progress and %r notify event should be ignored', notify_type)
        return

    if notify_type.lower() == 'shutdown':
        # Before we start FSD with upsmon, lets ensure that ups is not ONLINE (OL).
        # There are cases where battery/charger issues can result in ups.status being "OL LB" at the
        # same time. This will ensure that we don't initiate a shutdown if ups is OL.
        ups_status = RE_UPS_STATUS.findall(stats_output)
        if ups_status and 'ol' in ups_status[0].lower():
            context.middleware.logger.debug(
                f'Shutdown not initiated as ups.status ({ups_status[0]}) indicates '
                f'{config.identifier} is ONLINE (OL).'
            )
        else:
            # if we shutdown the active node while the passive is still online
            # then we're just going to cause a failover event. Shut the passive down
            # first and then shut the active node down
            if await context.middleware.call('failover.licensed'):
                if await context.middleware.call('failover.status') == 'MASTER':
                    try:
                        await context.middleware.call('failover.call_remote', 'ups.upssched_event', ['shutdown'])
                    except Exception:
                        context.logger.error('failed shutting down passive node', exc_info=True)

            await run('upsmon', '-c', 'fsd', check=False)

    elif 'notify' in notify_type.lower():
        # notify_type is expected to be of the following format
        # NOTIFY-EVENT i.e NOTIFY-LOWBATT
        notify_type = notify_type.split('-')[-1]

        # We would like to send alerts for the following events
        alert_mapping = alerts_mapping()

        await context.call2(context.s.ups.dismiss_alerts)

        if notify_type in alert_mapping:
            # Send user with the notification event and details
            # We send the email in the following format ( inclusive line breaks )

            # UPS Statistics: 'ups'
            #
            # Statistics recovered:
            #
            # 1) Battery charge (percent)
            # battery.charge: 5
            #
            # 2) Remaining battery level when UPS switches to LB (percent)
            # battery.charge.low: 10
            #
            # 3) Battery runtime (seconds)
            # battery.runtime: 1860
            #
            # 4) Remaining battery runtime when UPS switches to LB (seconds)
            # battery.runtime.low: 900
            body = f'<br><br>UPS Statistics: {config.identifier!r}<br><br>'

            # Let's gather following stats
            data_points = {
                'battery.charge': 'Battery charge (percent)',
                'battery.charge.low': 'Battery level remaining (percent) when UPS switches to Low Battery (LB)',
                'battery.charge.status': 'Battery charge status',
                'battery.runtime': 'Battery runtime (seconds)',
                'battery.runtime.low': 'Battery runtime remaining (seconds) when UPS switches to Low Battery (LB)',
                'battery.runtime.restart': 'Minimum battery runtime (seconds) to allow UPS restart after power-off',
            }

            stats_output = (
                await run('upsc', upsc_identifier, check=False)
            ).stdout.decode()
            recovered_stats = re.findall(
                fr'({"|".join(data_points)}): (.*)',
                stats_output
            )

            if recovered_stats:
                body += 'Statistics recovered:<br><br>'
                # recovered_stats is expected to be a list in this format
                # [('battery.charge', '5'), ('battery.charge.low', '10'), ('battery.runtime', '1860')]
                for index, stat in enumerate(recovered_stats):
                    body += f'{index + 1}) {data_points[stat[0]]}<br> ' \
                            f'&nbsp;&nbsp;&nbsp; {stat[0]}: {stat[1]}<br><br>'
            else:
                body += 'Statistics could not be recovered<br>'

            await context.middleware.call(
                'alert.oneshot_create', alert_mapping[notify_type], {'ups': config.identifier, 'body': body}
            )
    else:
        context.logger.debug(f'Unrecognized UPS notification event: {notify_type}')
