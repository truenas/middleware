import asyncio
from datetime import datetime, timedelta, timezone
import functools
import re
import time

from humanize import ordinal

from middlewared.common.smart.smartctl import SMARTCTL_POWERMODES
from middlewared.plugins.smart_.schedule import SMARTD_SCHEDULE_PIECES, smartd_schedule_piece_values
from middlewared.schema import accepts, Bool, Cron, Datetime, Dict, Int, Float, List, Patch, returns, Str
from middlewared.service import (
    CRUDService, filterable, filterable_returns, filter_list, job, private, SystemServiceService, ValidationErrors
)
from middlewared.service_exception import CallError, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.asyncio_ import asyncio_map


RE_TIME = re.compile(r'test will complete after ([a-z]{3} [a-z]{3} [0-9 ]+ \d\d:\d\d:\d\d \d{4})', re.IGNORECASE)
RE_TIME_SCSIPRINT_EXTENDED = re.compile(r'Please wait (\d+) minutes for test to complete')

RE_OF_TEST_REMAINING = re.compile(r'([0-9]+)% of test remaining')


async def annotate_disk_smart_tests(middleware, tests_filter, disk):
    if disk["disk"] is None:
        return

    output = await middleware.call("disk.smartctl", disk["disk"], ["-a"], {"silent": True})
    if output is None:
        return

    tests = parse_smart_selftest_results(output) or []
    current_test = parse_current_smart_selftest(output)
    return dict(tests=filter_list(tests, tests_filter), current_test=current_test, **disk)


def parse_smart_selftest_results(stdout):
    tests = []

    # ataprint.cpp
    if "LBA_of_first_error" in stdout:
        for line in stdout.split("\n"):
            if not line.startswith("#"):
                continue

            test = {
                "num": int(line[1:3].strip()),
                "description": line[5:24].strip(),
                "status_verbose": line[25:54].strip(),
                "remaining": int(line[55:57]) / 100,
                "lifetime": int(line[60:68].strip()),
                "lba_of_first_error": line[77:].strip(),
            }

            if test["status_verbose"] == "Completed without error":
                test["status"] = "SUCCESS"
            elif test["status_verbose"] == "Self-test routine in progress":
                test["status"] = "RUNNING"
            else:
                test["status"] = "FAILED"

            if test["lba_of_first_error"] == "-":
                test["lba_of_first_error"] = None

            tests.append(test)

        return tests

    # scsiprint.cpp
    if "LBA_first_err" in stdout:
        for line in stdout.split("\n"):
            if not line.startswith("#"):
                continue

            test = {
                "num": int(line[1:3].strip()),
                "description": line[5:22].strip(),
                "status_verbose": line[23:48].strip(),
                "segment_number": line[49:52].strip(),
                "lifetime": line[55:60].strip(),
                "lba_of_first_error": line[60:78].strip(),
            }

            if test["status_verbose"] == "Completed":
                test["status"] = "SUCCESS"
            elif test["status_verbose"] == "Self test in progress ...":
                test["status"] = "RUNNING"
            else:
                test["status"] = "FAILED"

            if test["segment_number"] == "-":
                test["segment_number"] = None
            else:
                test["segment_number"] = int(test["segment_number"])

            if test["lifetime"] == "NOW":
                test["lifetime"] = None
            else:
                test["lifetime"] = int(test["lifetime"])

            if test["lba_of_first_error"] == "-":
                test["lba_of_first_error"] = None

            tests.append(test)

        return tests


def parse_current_smart_selftest(stdout):
    if remaining := RE_OF_TEST_REMAINING.search(stdout):
        return {"progress": 100 - int(remaining.group(1))}

    if "Self test in progress ..." in stdout:
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
        a_values = set(smartd_schedule_piece_values(a[piece.key], piece.min, piece.max, piece.enum))
        b_values = set(smartd_schedule_piece_values(b[piece.key], piece.min, piece.max, piece.enum))

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
    smarttest_all_disks = sa.Column(sa.Boolean(), default=False)

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

    ENTRY = Patch(
        'smart_task_create', 'smart_task_entry',
        ('add', Int('id')),
    )

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

    async def _validate(self, data, id=None):
        verrors = ValidationErrors()

        disk_choices = await self.disk_choices()
        other_tests = await self.query([('id', '!=', id)] if id is not None else [])

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

    @accepts(Str('disk'))
    async def query_for_disk(self, disk):
        """
        Query S.M.A.R.T. tests for the specified disk.
        """
        return [
            test
            for test in await self.query()
            if test['all_disks'] or disk in test['disks']
        ]

    @accepts(Bool('full_disk', default=False))
    async def disk_choices(self, full_disk):
        """
        Returns disk choices for S.M.A.R.T. test.

        `full_disk` will return full disk objects instead of just names.
        """
        return {
            disk['identifier']: disk if full_disk else disk['name']
            for disk in await self.middleware.call('disk.query', [['devname', '!^', 'nv']])
            if await self.middleware.call('disk.smartctl_args', disk['name']) is not None
        }

    @accepts(
        Dict(
            'smart_task_create',
            Cron(
                'schedule',
                exclude=['minute']
            ),
            Str('desc'),
            Bool('all_disks', default=False),
            List('disks', items=[Str('disk')]),
            Str('type', enum=['LONG', 'SHORT', 'CONVEYANCE', 'OFFLINE'], required=True),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a SMART Test Task.

        `disks` is a list of valid disks which should be monitored in this task.

        `type` is specified to represent the type of SMART test to be executed.

        `all_disks` when enabled sets the task to cover all disks in which case `disks` is not required.

        .. examples(websocket)::

          Create a SMART Test Task which executes after every 30 minutes.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "smart.test.create",
                "params": [{
                    "schedule": {
                        "minute": "30",
                        "hour": "*",
                        "dom": "*",
                        "month": "*",
                        "dow": "*"
                    },
                    "all_disks": true,
                    "type": "OFFLINE",
                    "disks": []
                }]
            }
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

        asyncio.ensure_future(self._service_change('smartd', 'restart'))

        return await self.get_instance(data['id'])

    async def do_update(self, id, data):
        """
        Update SMART Test Task of `id`.
        """
        old = await self.query(filters=[('id', '=', id)], options={'get': True})
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        verrors.add_child('smart_test_update', await self._validate(data))
        verrors.check()

        new['type'] = new.pop('type')[0]

        Cron.convert_schedule_to_db_format(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        asyncio.ensure_future(self._service_change('smartd', 'restart'))

        return await self.get_instance(id)

    async def do_delete(self, id):
        """
        Delete SMART Test Task of `id`.
        """
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        asyncio.ensure_future(self._service_change('smartd', 'restart'))

        return response

    @accepts(
        List(
            'disks', items=[
                Dict(
                    'disk_run',
                    Str('identifier', required=True),
                    Str('mode', enum=['FOREGROUND', 'BACKGROUND'], default='BACKGROUND'),
                    Str('type', enum=['LONG', 'SHORT', 'CONVEYANCE', 'OFFLINE'], required=True),
                )
            ]
        )
    )
    @returns(List('smart_manual_test', items=[Dict(
        'smart_manual_test_disk_response',
        Str('disk', required=True),
        Str('identifier', required=True),
        Str('error', required=True, null=True),
        Datetime('expected_result_time'),
        Int('job'),
    )]))
    async def manual_test(self, disks):
        """
        Run manual SMART tests for `disks`.

        `type` indicates what type of SMART test will be ran and must be specified.
        """
        verrors = ValidationErrors()
        test_disks_list = []
        if not disks:
            verrors.add(
                'disks',
                'Please specify at least one disk.'
            )
        else:
            supported_disks = await self.disk_choices(True)
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
                expected_result_time = datetime.utcnow() + timedelta(minutes=int(time_details.group(1)))
            elif 'Self Test has begun' in result:
                # scsiprint.cpp does not always print expected result time
                expected_result_time = datetime.utcnow() + timedelta(minutes=1)

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

    @filterable
    @filterable_returns(Dict(
        'disk_smart_test_result',
        Str('disk', required=True),
        List('tests', items=[Dict(
            'test_result',
            Int('num', required=True),
            Str('description', required=True),
            Str('status', required=True),
            Str('status_verbose', required=True),
            Float('remaining', required=True),
            Int('lifetime', required=True),
            Str('lba_of_first_error', null=True, required=True),
        )]),
        Dict(
            'current_test',
            Int('progress', required=True),
            null=True,
        ),
    ))
    async def results(self, filters, options):
        """
        Get disk(s) S.M.A.R.T. test(s) results.

        `options.extra.tests_filter` is an optional filter for tests results.

        .. examples(websocket)::

          Get all disks tests results

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "smart.test.results",
                "params": []
            }

            returns

            :::javascript

            [
              # ATA disk
              {
                "disk": "ada0",
                "tests": [
                  {
                    "num": 1,
                    "description": "Short offline",
                    "status": "SUCCESS",
                    "status_verbose": "Completed without error",
                    "remaining": 0.0,
                    "lifetime": 16590,
                    "lba_of_first_error": None,
                  }
                ]
              },
              # SCSI disk
              {
                "disk": "ada1",
                "tests": [
                  {
                    "num": 1,
                    "description": "Background long",
                    "status": "FAILED",
                    "status_verbose": "Completed, segment failed",
                    "segment_number": None,
                    "lifetime": 3943,
                    "lba_of_first_error": None,
                  }
                ]
              },
            ]

          Get specific disk test results

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "smart.test.results",
                "params": [
                  [["disk", "=", "ada0"]],
                  {"get": true}
                ]
            }

            returns

            :::javascript

            {
              "disk": "ada0",
              "tests": [
                {
                  "num": 1,
                  "description": "Short offline",
                  "status": "SUCCESS",
                  "status_verbose": "Completed without error",
                  "remaining": 0.0,
                  "lifetime": 16590,
                  "lba_of_first_error": None,
                }
              ]
            }
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
    @job()
    async def wait(self, job, disk, expected_result_time):
        start = datetime.utcnow()
        if expected_result_time < start:
            raise CallError(f'Invalid expected_result_time {expected_result_time.isoformat()}')

        start_monotime = time.monotonic()
        end_monotime = start_monotime + (expected_result_time - start).total_seconds()

        while True:
            try:
                current_test = (await self.middleware.call(
                    'smart.test.results',
                    [['disk', '=', disk['disk']]],
                    {'get': True}
                ))['current_test']
            except MatchNotFound:
                raise CallError(f'No S.M.A.R.T. test results found for {disk["disk"]}')

            if current_test is None:
                return

            job.set_progress(current_test['progress'])

            # Check every percent
            interval = int((end_monotime - start_monotime) / 100)

            if time.monotonic() < end_monotime:
                # but not more often than every ten seconds
                interval = max(interval, 10)
            else:
                # the test is taking longer than expected, do not poll more often than every minute
                interval = max(interval, 60)

            await asyncio.sleep(interval)


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
        service = "smartd"
        service_model = "smart"
        service_verb_sync = False
        datastore_extend = "smart.smart_extend"
        datastore_prefix = "smart_"
        cli_namespace = "service.smart"

    ENTRY = Dict(
        'smart_entry',
        Int('interval', required=True),
        Int('id', required=True),
        Str('powermode', required=True, enum=SMARTCTL_POWERMODES),
        Int('difference', required=True),
        Int('informational', required=True),
        Int('critical', required=True),
    )

    @private
    async def smart_extend(self, smart):
        smart["powermode"] = smart["powermode"].upper()
        return smart

    async def do_update(self, data):
        """
        Update SMART Service Configuration.

        `interval` is an integer value in minutes which defines how often smartd activates to check if any tests
        are configured to run.

        `critical`, `informational` and `difference` are integer values on which alerts for SMART are configured if
        the disks temperature crosses the assigned threshold for each respective attribute. They default to 0 which
        indicates they are disabled.
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
            await self.middleware.call("service.restart", "collectd")
            await self._service_change("snmp", "restart")

        return await self.config()
