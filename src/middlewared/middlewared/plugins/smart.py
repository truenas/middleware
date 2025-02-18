import asyncio
from datetime import datetime, timedelta, timezone
import functools
import re
import time
import json
from typing import Any

from humanize import ordinal

from middlewared.api import api_method
from middlewared.api.current import (
    SmartTestEntry,
    SmartTestCreateArgs, SmartTestCreateResult,
    SmartTestUpdateArgs, SmartTestUpdateResult,
    SmartTestDeleteArgs, SmartTestDeleteResult,
    SmartTestQueryForDiskArgs, SmartTestQueryForDiskResult,
    SmartTestDiskChoicesArgs, SmartTestDiskChoicesResult,
    SmartTestManualTestArgs, SmartTestManualTestResult,
    SmartTestResultsArgs, SmartTestResultsResult,
    SmartTestAbortArgs, SmartTestAbortResult,
    SmartEntry,
    SmartUpdateArgs, SmartUpdateResult,
    AtaSelfTest, NvmeSelfTest, ScsiSelfTest,
)
from middlewared.plugins.smart_.schedule import SMARTD_SCHEDULE_PIECES, smartd_schedule_piece_values
from middlewared.schema import Cron
from middlewared.service import (
    CRUDService, filter_list, job, private, SystemServiceService, ValidationErrors
)
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.time_utils import utc_now


RE_TIME = re.compile(r'test will complete after ([a-z]{3} [a-z]{3} [0-9 ]+ \d\d:\d\d:\d\d \d{4})', re.IGNORECASE)
RE_TIME_SCSIPRINT_EXTENDED = re.compile(r'Please wait (\d+) minutes for test to complete')


async def annotate_disk_smart_tests(middleware, tests_filter, disk):
    if disk["disk"] is None:
        return

    output = await middleware.call("disk.smartctl", disk["disk"], ["-a", "--json=c"], {"silent": True})
    if output is None:
        return
    data = json.loads(output)

    tests = parse_smart_selftest_results(data) or []
    current_test = parse_current_smart_selftest(data)
    return dict(tests=filter_list(tests, tests_filter), current_test=current_test, **disk)


def parse_smart_selftest_results(data) -> list[dict[str, Any]] | None:
    tests = []

    # ataprint.cpp
    if "ata_smart_self_test_log" in data:
        if "table" in data["ata_smart_self_test_log"]["standard"]:  # If there are no tests, there is no table
            try:
                current_power_on_hours = data["power_on_time"]["hours"]
            except KeyError:
                current_power_on_hours = None

            for index, entry in enumerate(data["ata_smart_self_test_log"]["standard"]["table"]):
                # remaining_percent is in the dict only if the test is in progress (status value & 0x0f)
                if remaining := entry["status"]["value"] & 0x0f:
                    remaining = entry["status"]["remaining_percent"] / 100

                if current_power_on_hours is not None:
                    power_on_hours_ago = current_power_on_hours - entry["lifetime_hours"]
                else:
                    power_on_hours_ago = None

                test = AtaSelfTest(
                    num=index,
                    description=entry["type"]["string"],
                    status=entry["status"]["string"],
                    status_verbose=entry["status"]["string"],
                    remaining=remaining,
                    lifetime=entry["lifetime_hours"],
                    lba_of_first_error=entry.get("lba"),  # only included if there is an error
                    power_on_hours_ago=power_on_hours_ago,
                )

                if test.status_verbose == "Completed without error":
                    test.status = "SUCCESS"
                elif test.status_verbose == "Self-test routine in progress":
                    test.status = "RUNNING"
                elif test.status_verbose in ["Aborted by host", "Interrupted (host reset)"]:
                    test.status= "ABORTED"
                else:
                    test.status = "FAILED"

                tests.append(test.dict())

        return tests

    # nvmeprint.cpp
    if "nvme_self_test_log" in data:
        if "table" in data["nvme_self_test_log"]:
            try:
                current_power_on_hours = data["power_on_time"]["hours"]
            except KeyError:
                current_power_on_hours = None

            for index, entry in enumerate(data["nvme_self_test_log"]["table"]):
                if lba := entry.get("lba"):
                    lba = entry["lba"]["value"]

                if current_power_on_hours is not None:
                    power_on_hours_ago = current_power_on_hours - entry["power_on_hours"]
                else:
                    power_on_hours_ago = None

                test = NvmeSelfTest(
                    num=index,
                    description=entry["self_test_code"]["string"],
                    status=entry["self_test_result"]["string"],
                    status_verbose=entry["self_test_result"]["string"],
                    power_on_hours=entry["power_on_hours"],
                    failing_lba=lba,
                    nsid=entry.get("nsid"),
                    seg=entry.get("segment"),
                    sct=entry.get("status_code_type") or 0x0,
                    code=entry.get("status_code") or 0x0,
                    power_on_hours_ago=power_on_hours_ago,
                )

                if test.status_verbose == "Completed without error":
                    test.status = "SUCCESS"
                elif test.status_verbose.startswith("Aborted:"):
                    test.status = "ABORTED"
                else:
                    test.status = "FAILED"

                tests.append(test.dict())

        return tests

    # scsiprint.cpp
    # this JSON has numbered keys as an index, there's a reason it's not called a "smart" test
    if "scsi_self_test_0" in data:  # 0 is the most recent test
        try:
            current_power_on_hours = data["power_on_time"]["hours"]
        except KeyError:
            current_power_on_hours = None

        for index in range(0, 20):  # only 20 tests can ever return
            test_key = f"scsi_self_test_{index}"
            if test_key not in data:
                break

            entry = data[test_key]

            if segment := entry.get("failed_segment"):
                segment = entry["failed_segment"]["value"]

            if lba := entry.get("lba_first_failure"):
                lba = entry["lba_first_failure"]["value"]

            lifetime = current_power_on_hours
            if not entry.get("self_test_in_progress"):
                lifetime = entry["power_on_time"]["hours"]

            if current_power_on_hours is not None:
                power_on_hours_ago = current_power_on_hours - lifetime
            else:
                power_on_hours_ago = None

            test = ScsiSelfTest(
                num=index,
                description=entry["code"]["string"],
                status=entry["result"]["string"],
                status_verbose=entry["result"]["string"],  # will be replaced
                segment_number=segment,
                lifetime=lifetime,
                lba_of_first_error=lba,
                power_on_hours_ago=power_on_hours_ago,
            )

            if test.status_verbose == "Completed":
                test.status = "SUCCESS"
            elif test.status_verbose == "Self test in progress ...":
                test.status = "RUNNING"
            elif test.status_verbose.startswith("Aborted"):
                test.status = "ABORTED"
            else:
                test.status = "FAILED"

            tests.append(test.dict())

        return tests


def parse_current_smart_selftest(data):
    # ata
    if "ata_smart_self_test_log" in data:
        if tests := data["ata_smart_self_test_log"]["standard"].get("table"):
            if remaining := tests[0]["status"].get("remaining_percent"):
                return {"progress": 100 - remaining}

    # nvme
    if "nvme_self_test_log" in data:
        if remaining := data["nvme_self_test_log"].get("current_self_test_completion_percent"):
            return {"progress": remaining}

    # scsi gives no progress
    if "self_test_in_progress" in data:
        return {"progress": 0}


def smart_test_disks_intersect(existing_test, new_test, disk_choices):
    if existing_test['all_disks']:
        return (
            'type',
            f'There already is an all-disks {existing_test["type"]} test',
        )
    elif new_test['all_disks'] and (used_disks := [
        disk_choices[disk]
        for disk in existing_test['disks']
        if disk in disk_choices
    ]):
        return (
            'type',
            f'The following disks already have {existing_test["type"]} test: {", ".join(used_disks)}'
        )
    elif (used_disks := [
        disk_choices[disk]
        for disk in set(new_test['disks']) & set(existing_test['disks'])
        if disk in disk_choices
    ]):
        return (
            'disks',
            f'The following disks already have {existing_test["type"]} test: {", ".join(used_disks)}'
        )


def smart_test_schedules_intersect_at(a, b):
    intersections = []
    for piece in SMARTD_SCHEDULE_PIECES:
        a_values = set(smartd_schedule_piece_values(a[piece.key], piece.min, piece.max, piece.enum, piece.map))
        b_values = set(smartd_schedule_piece_values(b[piece.key], piece.min, piece.max, piece.enum, piece.map))

        intersection = a_values & b_values
        if not intersection:
            return

        first_intersection = sorted(intersection)[0]

        if piece.key == "hour":
            intersections.append(f"{first_intersection:02d}:00")
            continue

        if len(intersection) == piece.max - piece.min + 1:
            continue

        if piece.key == "dom":
            if intersections:
                intersections.append(ordinal(first_intersection))
            else:
                intersections.append(f"Day {ordinal(first_intersection)} of every month")
            continue

        intersections.append({v: k for k, v in piece.enum.items()}[first_intersection].title())

    if intersections:
        return ", ".join(intersections)


class SmartTestModel(sa.Model):
    __tablename__ = 'tasks_smarttest'

    id = sa.Column(sa.Integer(), primary_key=True)
    smarttest_type = sa.Column(sa.String(2))
    smarttest_desc = sa.Column(sa.String(120))
    smarttest_hour = sa.Column(sa.String(100))
    smarttest_daymonth = sa.Column(sa.String(100))
    smarttest_month = sa.Column(sa.String(100))
    smarttest_dayweek = sa.Column(sa.String(100))
    smarttest_all_disks = sa.Column(sa.Boolean())

    smarttest_disks = sa.relationship('DiskModel', secondary=lambda: SmartTestDiskModel.__table__)


class SmartTestDiskModel(sa.Model):
    __tablename__ = 'tasks_smarttest_smarttest_disks'
    __table_args__ = (
        sa.Index('tasks_smarttest_smarttest_disks_smarttest_id__disk_id', 'smarttest_id', 'disk_id', unique=True),
    )

    id = sa.Column(sa.Integer(), primary_key=True)
    smarttest_id = sa.Column(sa.Integer(), sa.ForeignKey('tasks_smarttest.id', ondelete='CASCADE'))
    disk_id = sa.Column(sa.String(100), sa.ForeignKey('storage_disk.disk_identifier', ondelete='CASCADE'))


class SMARTTestService(CRUDService):

    class Config:
        datastore = 'tasks.smarttest'
        datastore_extend = 'smart.test.smart_test_extend'
        datastore_prefix = 'smarttest_'
        namespace = 'smart.test'
        cli_namespace = 'task.smart_test'
        entry = SmartTestEntry
        role_prefix = 'DISK'

    @private
    async def smart_test_extend(self, data):
        disks = data.pop('disks')
        data['disks'] = [disk['disk_identifier'] for disk in disks]
        test_type = {
            'L': 'LONG',
            'S': 'SHORT',
            'C': 'CONVEYANCE',
            'O': 'OFFLINE',
        }
        data['type'] = test_type[data.pop('type')]
        Cron.convert_db_format_to_schedule(data)
        return data

    async def _validate(self, data, id_=None):
        verrors = ValidationErrors()

        disk_choices = await self.disk_choices()
        other_tests = await self.query([('id', '!=', id_)] if id_ is not None else [])

        if not data['disks'] and not data['all_disks']:
            verrors.add('disks', 'This field is required')

        for i, disk in enumerate(data['disks']):
            if disk not in disk_choices:
                verrors.add(f'disks.{i}', 'Invalid disk')

        for test in other_tests:
            if test['type'] == data['type']:
                if error := smart_test_disks_intersect(test, data, disk_choices):
                    verrors.add(*error)
                    break

        # "As soon as a match is found, the test will be started and no additional matches will be sought for that
        # device and that polling cycle." (from man smartd.conf).
        # So if two tests are scheduled to run at the same time, only one will run.
        for test in other_tests:
            if smart_test_disks_intersect(test, data, disk_choices):
                if intersect_at := smart_test_schedules_intersect_at(test['schedule'], data['schedule']):
                    verrors.add('data.schedule', f'A {test["type"]} test already runs at {intersect_at}')
                    break

        return verrors

    @api_method(SmartTestQueryForDiskArgs, SmartTestQueryForDiskResult, roles=['REPORTING_READ'])
    async def query_for_disk(self, disk_name):
        """
        Query S.M.A.R.T. tests for the specified disk name.
        """
        disk = await self.middleware.call('disk.query', [['name', '=', disk_name]], {'get': True})

        return [
            test
            for test in await self.query()
            if test['all_disks'] or disk['identifier'] in test['disks']
        ]

    @api_method(SmartTestDiskChoicesArgs, SmartTestDiskChoicesResult, roles=['DISK_READ'])
    async def disk_choices(self, full_disk):
        """
        Returns disk choices for S.M.A.R.T. test.

        `full_disk` will return full disk objects instead of just names.
        """
        return {
            disk['identifier']: disk if full_disk else disk['name']
            for disk in await self.middleware.call('disk.query', [['name', '!^', 'pmem']])
            if await self.middleware.call('disk.smartctl_args', disk['name']) is not None
        }

    @api_method(SmartTestCreateArgs, SmartTestCreateResult)
    async def do_create(self, data):
        """
        Create a SMART Test Task.
        """
        verrors = ValidationErrors()
        verrors.add_child('smart_test_create', await self._validate(data))
        verrors.check()

        data['type'] = data.pop('type')[0]

        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        self.middleware.create_task(self._service_change('smartd', 'restart'))

        return await self.get_instance(data['id'])

    @api_method(SmartTestUpdateArgs, SmartTestUpdateResult)
    async def do_update(self, id_, data):
        """
        Update SMART Test Task of `id`.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        verrors.add_child('smart_test_update', await self._validate(new, id_))
        verrors.check()

        new['type'] = new.pop('type')[0]

        Cron.convert_schedule_to_db_format(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        self.middleware.create_task(self._service_change('smartd', 'restart'))

        return await self.get_instance(id_)

    @api_method(SmartTestDeleteArgs, SmartTestDeleteResult)
    async def do_delete(self, id_):
        """
        Delete SMART Test Task of `id`.
        """
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id_
        )

        self.middleware.create_task(self._service_change('smartd', 'restart'))

        return response

    @api_method(SmartTestManualTestArgs, SmartTestManualTestResult, roles=['DISK_WRITE'])
    async def manual_test(self, disks):
        """
        Run manual SMART tests for `disks`.
        """
        verrors = ValidationErrors()
        test_disks_list = []
        if not disks:
            verrors.add(
                'disks',
                'Please specify at least one disk.'
            )
        else:
            supported_disks = await self.middleware.call('smart.test.disk_choices', True)
            devices = await self.middleware.call('device.get_disks')
            valid_disks = [
                disk['identifier']
                for disk in await self.middleware.call('disk.query', [
                    ('identifier', 'in', [disk['identifier'] for disk in disks])
                ], {'force_sql_filters': True})
            ]
            for index, disk in enumerate(disks):
                if current_disk := supported_disks.get(disk['identifier']):
                    test_disks_list.append({
                        'disk': current_disk['name'],
                        **disk
                    })
                else:
                    if disk['identifier'] in valid_disks:
                        verrors.add(
                            f'disks.{index}.identifier',
                            f'{disk["identifier"]} does not support S.M.A.R.T test.'
                        )
                    else:
                        verrors.add(
                            f'disks.{index}.identifier',
                            f'{disk["identifier"]} is not valid. Please provide a valid disk identifier.'
                        )
                    continue

                if current_disk['name'] is None:
                    verrors.add(
                        f'disks.{index}.identifier',
                        f'Test cannot be performed for {disk["identifier"]} disk. Failed to retrieve name.'
                    )

                device = devices.get(current_disk['name'])
                if not device:
                    verrors.add(
                        f'disks.{index}.identifier',
                        f'Test cannot be performed for {disk["identifier"]}. Unable to retrieve disk details.'
                    )

        verrors.check()

        return await asyncio_map(self.__manual_test, test_disks_list, 16)

    async def __manual_test(self, disk):
        output = {'error': None}

        args = ['-t', disk['type'].lower()]
        if disk['mode'] == 'FOREGROUND':
            args.extend(['-C'])
        try:
            result = await self.middleware.call('disk.smartctl', disk['disk'], args)
        except CallError as e:
            output['error'] = e.errmsg
        else:
            expected_result_time = None
            time_details = re.findall(RE_TIME, result)
            if time_details:
                try:
                    expected_result_time = datetime.strptime(time_details[0].strip(), '%a %b %d %H:%M:%S %Y')
                except Exception as e:
                    self.logger.error('Unable to parse expected_result_time: %r', e)
                else:
                    expected_result_time = expected_result_time.astimezone(timezone.utc).replace(tzinfo=None)
            elif time_details := re.search(RE_TIME_SCSIPRINT_EXTENDED, result):
                expected_result_time = utc_now() + timedelta(minutes=int(time_details.group(1)))
            elif 'Self-test has begun' in result:
                # nvmeprint.cpp does not print expected result time
                expected_result_time = utc_now() + timedelta(minutes=1)
            elif 'Self Test has begun' in result:
                # scsiprint.cpp does not always print expected result time
                expected_result_time = utc_now() + timedelta(minutes=1)

            if expected_result_time:
                output['expected_result_time'] = expected_result_time
                output['job'] = (
                    await self.middleware.call('smart.test.wait', disk, expected_result_time)
                ).id
            else:
                output['error'] = result

        return {
            'disk': disk['disk'],
            'identifier': disk['identifier'],
            **output
        }

    @api_method(SmartTestResultsArgs, SmartTestResultsResult, roles=['REPORTING_READ'])
    async def results(self, filters, options):
        """
        Get disk(s) S.M.A.R.T. test(s) results.
        """

        get = options.pop("get", False)
        tests_filter = options["extra"].pop("tests_filter", [])

        disks = filter_list(
            [dict(disk, disk=disk["name"]) for disk in (await self.disk_choices(True)).values()],
            filters,
            options,
        )

        return filter_list(
            list(filter(
                None,
                await asyncio_map(functools.partial(annotate_disk_smart_tests, self.middleware, tests_filter),
                                  disks,
                                  16)
            )),
            [],
            {"get": get},
        )

    @private
    @job(abortable=True)
    async def wait(self, job, disk, expected_result_time):
        try:
            start = utc_now()
            if expected_result_time < start:
                raise CallError(f'Invalid expected_result_time {expected_result_time.isoformat()}')

            start_monotime = time.monotonic()
            end_monotime = start_monotime + (expected_result_time - start).total_seconds()

            await self.middleware.call('smart.test.set_test_data', disk['disk'], {
                'start_monotime': start_monotime,
                'end_monotime': end_monotime,
            })

            async for _, data in await self.middleware.event_source_manager.iterate('smart.test.progress', disk['disk']):
                if data['fields']['progress'] is None:
                    return

                job.set_progress(data['fields']['progress'])
        except asyncio.CancelledError:
            await self.middleware.call('smart.test.abort', disk['disk'])
            raise

    @api_method(SmartTestAbortArgs, SmartTestAbortResult, roles=['DISK_WRITE'])
    async def abort(self, disk):
        """
        Abort non-captive S.M.A.R.T. tests for disk.
        """
        await self.middleware.call("disk.smartctl", disk, ["-X"], {"silent": True})


class SmartModel(sa.Model):
    __tablename__ = 'services_smart'

    id = sa.Column(sa.Integer(), primary_key=True)
    smart_interval = sa.Column(sa.Integer(), default=30)
    smart_powermode = sa.Column(sa.String(60), default="never")
    smart_difference = sa.Column(sa.Integer(), default=0)
    smart_informational = sa.Column(sa.Integer(), default=0)
    smart_critical = sa.Column(sa.Integer(), default=0)


class SmartService(SystemServiceService):

    class Config:
        datastore = "services.smart"
        service = "smartd"
        service_verb_sync = False
        datastore_extend = "smart.smart_extend"
        datastore_prefix = "smart_"
        cli_namespace = "service.smart"
        entry = SmartEntry
        role_prefix = 'DISK'

    @private
    async def smart_extend(self, smart):
        smart["powermode"] = smart["powermode"].upper()
        return smart

    @api_method(SmartUpdateArgs, SmartUpdateResult)
    async def do_update(self, data):
        """
        Update SMART Service Configuration.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        new["powermode"] = new["powermode"].lower()

        verb = "reload"
        if any(old[k] != new[k] for k in ["interval"]):
            verb = "restart"

        await self._update_service(old, new, verb)

        if new["powermode"] != old["powermode"]:
            await self._service_change("snmp", "restart")

        return await self.config()
