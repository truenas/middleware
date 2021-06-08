from datetime import datetime, timedelta, timezone
import functools
import re
import time
from itertools import chain

import asyncio

from middlewared.common.smart.smartctl import SMARTCTL_POWERMODES, get_smartctl_args, smartctl
from middlewared.schema import accepts, Bool, Cron, Datetime, Dict, Int, Float, List, Patch, returns, Str
from middlewared.service import (
    CRUDService, filterable, filterable_returns, filter_list, job, private, SystemServiceService, ValidationErrors
)
from middlewared.service_exception import CallError, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.asyncio_ import asyncio_map


RE_TIME = re.compile(r'test will complete after ([a-z]{3} [a-z]{3} [0-9 ]+ \d\d:\d\d:\d\d \d{4})', re.IGNORECASE)
RE_TIME_SCSIPRINT_EXTENDED = re.compile(r'Please wait (\d+) minutes for test to complete')


async def annotate_disk_smart_tests(middleware, devices, disk):
    if disk["disk"] is None:
        return

    args = await get_smartctl_args(middleware, devices, disk["disk"])
    if args:
        p = await smartctl(args + ["-l", "selftest"], check=False, encoding="utf8")
        tests = parse_smart_selftest_results(p.stdout)
        if tests is not None:
            return dict(tests=tests, **disk)


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
                "description": line[5:20].strip(),
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


class SmartTestModel(sa.Model):
    __tablename__ = 'tasks_smarttest'

    id = sa.Column(sa.Integer(), primary_key=True)
    smarttest_type = sa.Column(sa.String(2))
    smarttest_desc = sa.Column(sa.String(120))
    smarttest_hour = sa.Column(sa.String(100), default='*')
    smarttest_daymonth = sa.Column(sa.String(100), default='*')
    smarttest_month = sa.Column(sa.String(100), default='*')
    smarttest_dayweek = sa.Column(sa.String(100), default='*')
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

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        smart_tests = await self.query(filters=[('type', '=', data['type'])])
        configured_disks = [d for test in smart_tests for d in test['disks']]
        disks_dict = await self.disk_choices()

        disks = data.get('disks')
        used_disks = []
        invalid_disks = []
        for disk in disks:
            if disk in configured_disks:
                used_disks.append(disks_dict[disk])
            if disk not in disks_dict.keys():
                invalid_disks.append(disk)

        if used_disks:
            verrors.add(
                f'{schema}.disks',
                f'The following disks already have tests for this type: {", ".join(used_disks)}'
            )

        if invalid_disks:
            verrors.add(
                f'{schema}.disks',
                f'The following disks are invalid: {", ".join(invalid_disks)}'
            )

        return verrors

    @accepts(Bool('full_disk', default=False))
    async def disk_choices(self, full_disk):
        """
        Returns disk choices for S.M.A.R.T. test.

        `full_disk` will return full disk objects instead of just names.
        """
        return {
            disk['identifier']: disk if full_disk else disk['name']
            for disk in await self.middleware.call('disk.query', [['devname', '!^', 'nv']])
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
        data['type'] = data.pop('type')[0]
        verrors = await self.validate_data(data, 'smart_test_create')

        if data['all_disks']:
            if data.get('disks'):
                verrors.add(
                    'smart_test_create.disks',
                    'This test is already enabled for all disks'
                )
        else:
            if not data.get('disks'):
                verrors.add(
                    'smart_test_create.disks',
                    'This field is required'
                )

        if verrors:
            raise verrors

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

        new['type'] = new.pop('type')[0]
        old['type'] = old.pop('type')[0]
        new_disks = [disk for disk in new['disks'] if disk not in old['disks']]
        deleted_disks = [disk for disk in old['disks'] if disk not in new['disks']]
        if old['type'] == new['type']:
            new['disks'] = new_disks
        verrors = await self.validate_data(new, 'smart_test_update')

        new['disks'] = [disk for disk in chain(new_disks, old['disks']) if disk not in deleted_disks]

        if new['all_disks']:
            if new.get('disks'):
                verrors.add(
                    'smart_test_update.disks',
                    'This test is already enabled for all disks'
                )
        else:
            if not new.get('disks'):
                verrors.add(
                    'smart_test_update.disks',
                    'This field is required'
                )

        if verrors:
            raise verrors

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
            disks_choices = await self.disk_choices(True)
            devices = await self.middleware.call('device.get_storage_devices_topology')

            for index, disk in enumerate(disks):
                if current_disk := disks_choices.get(disk['identifier']):
                    test_disks_list.append({
                        'disk': current_disk['name'],
                        **disk
                    })
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

        try:
            new_test_num = max(
                test['num']
                for test in (await self.middleware.call(
                    'smart.test.results',
                    [['disk', '=', disk['disk']]],
                    {'get': True}
                ))['tests']
            ) + 1
        except (MatchNotFound, ValueError):
            new_test_num = 1

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
                    await self.middleware.call('smart.test.wait', disk, expected_result_time, new_test_num)
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
        )])
    ))
    async def results(self, filters, options):
        """
        Get disk(s) S.M.A.R.T. test(s) results.

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

        get = (options or {}).pop("get", False)

        disks = filter_list(
            [{"disk": disk} for disk in (await self.disk_choices()).values()],
            filters,
            options,
        )

        devices = await self.middleware.call('device.get_storage_devices_topology')
        return filter_list(
            list(filter(
                None,
                await asyncio_map(functools.partial(annotate_disk_smart_tests, self.middleware, devices), disks, 16)
            )),
            [],
            {"get": get},
        )

    @private
    @job()
    async def wait(self, job, disk, expected_result_time, new_test_num):
        start = datetime.utcnow()
        if expected_result_time < start:
            raise CallError(f'Invalid expected_result_time {expected_result_time.isoformat()}')

        start_monotime = time.monotonic()
        end_monotime = start_monotime + (expected_result_time - start).total_seconds()

        # Check every percent but not more often than every minute
        interval = max((end_monotime - start_monotime) / 100.0, 60)
        while True:
            job.set_progress(
                min(
                    (time.monotonic() - start_monotime) / (end_monotime - start_monotime),
                    0.99
                ) * 100,
            )

            try:
                tests = (await self.middleware.call(
                    'smart.test.results',
                    [['disk', '=', disk['disk']]],
                    {'get': True}
                ))['tests']
            except MatchNotFound:
                tests = []

            for test in tests:
                if test['num'] == new_test_num:
                    return test

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
