from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.api import api_method
from middlewared.api.current import (
    CloudBackupEntry, CloudBackupTransferSettingChoicesArgs, CloudBackupTransferSettingChoicesResult,
    CloudBackupCreateArgs, CloudBackupCreateResult, CloudBackupUpdateArgs, CloudBackupUpdateResult,
    CloudBackupDeleteArgs, CloudBackupDeleteResult
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin
from middlewared.schema import Cron
from middlewared.service import pass_app, private, TaskPathService, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.path import FSLocation
from middlewared.utils.service.task_state import TaskStateMixin
from .init import IncorrectPassword


class CloudBackupModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = "tasks_cloud_backup"

    password = sa.Column(sa.EncryptedText())
    keep_last = sa.Column(sa.Integer())
    transfer_setting = sa.Column(sa.String(16))
    absolute_paths = sa.Column(sa.Boolean())
    cache_path = sa.Column(sa.Text(), nullable=True)


class CloudBackupService(TaskPathService, CloudTaskServiceMixin, TaskStateMixin):
    allow_zvol = True

    share_task_type = "CloudBackup"
    allowed_path_types = [FSLocation.LOCAL]
    task_state_methods = ["cloud_backup.sync", "cloud_backup.restore"]

    class Config:
        datastore = "tasks.cloud_backup"
        datastore_extend = "cloud_backup.extend"
        datastore_extend_context = "cloud_backup.extend_context"
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"
        role_prefix = "CLOUD_BACKUP"
        entry = CloudBackupEntry

    @private
    def transfer_setting_args(self):
        return {
            "DEFAULT": [],
            "PERFORMANCE": ["--pack-size", "29"],
            "FAST_STORAGE": ["--pack-size", "58", "--read-concurrency", "100"]
        }

    @private
    async def extend_context(self, rows, extra):
        return {
            "task_state": await self.get_task_state_context(),
        }

    @private
    async def extend(self, cloud_backup, context):
        cloud_backup["credentials"] = await self.middleware.call(
            "cloudsync.credentials.extend", cloud_backup.pop("credential"),
        )

        if job := await self.get_task_state_job(context["task_state"], cloud_backup["id"]):
            cloud_backup["job"] = job

        Cron.convert_db_format_to_schedule(cloud_backup)

        return cloud_backup

    @private
    async def _compress(self, cloud_backup):
        cloud_backup["credential"] = cloud_backup.pop("credentials")

        Cron.convert_schedule_to_db_format(cloud_backup)

        cloud_backup.pop("job", None)
        cloud_backup.pop(self.locked_field, None)

        return cloud_backup

    @api_method(CloudBackupTransferSettingChoicesArgs, CloudBackupTransferSettingChoicesResult)
    def transfer_setting_choices(self):
        """
        Return all possible choices for `cloud_backup.create.transfer_setting`.
        """
        args = self.transfer_setting_args()
        return list(args.keys())

    @api_method(CloudBackupCreateArgs, CloudBackupCreateResult)
    @pass_app(rest=True)
    async def do_create(self, app, cloud_backup):
        """
        Create a new cloud backup task
        """
        verrors = ValidationErrors()
        await self._validate(app, verrors, "cloud_backup_create", cloud_backup)
        verrors.check()

        cloud_backup = await self._compress(cloud_backup)
        cloud_backup["id"] = await self.middleware.call("datastore.insert", "tasks.cloud_backup",
                                                        {**cloud_backup, "job": None})
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)

        return await self.get_instance(cloud_backup["id"])

    @api_method(CloudBackupUpdateArgs, CloudBackupUpdateResult)
    @pass_app(rest=True)
    async def do_update(self, app, id_, data):
        """
        Update the cloud backup entry `id` with `data`.
        """
        cloud_backup = await self.get_instance(id_)

        # credentials is a foreign key for now
        if cloud_backup["credentials"]:
            cloud_backup["credentials"] = cloud_backup["credentials"]["id"]

        cloud_backup.update(data)

        verrors = ValidationErrors()

        await self._validate(app, verrors, "cloud_backup_update", cloud_backup)

        verrors.check()

        cloud_backup = await self._compress(cloud_backup)

        await self.middleware.call("datastore.update", "tasks.cloud_backup", id_, cloud_backup)
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(CloudBackupDeleteArgs, CloudBackupDeleteResult)
    async def do_delete(self, id_):
        """
        Delete cloud backup entry `id`.
        """
        await self.middleware.call("cloud_backup.abort", id_)
        await self.middleware.call("alert.oneshot_delete", "CloudBackupTaskFailed", id_)
        rv = await self.middleware.call("datastore.delete", "tasks.cloud_backup", id_)
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)
        return rv

    @private
    async def _validate(self, app, verrors, name, data):
        await super()._validate(app, verrors, name, data)

        if data["snapshot"] and data["absolute_paths"]:
            verrors.add(f"{name}.snapshot", "This option can't be used when absolute paths are enabled")

        if data["cache_path"]:
            await check_path_resides_within_volume(verrors, self.middleware, f"{name}.cache_path", data["cache_path"],
                                                   True)
            if not verrors:
                statfs = await self.middleware.call("filesystem.statfs", data["cache_path"])
                if "RO" in statfs["flags"]:
                    verrors.add(f"{name}.cache_path", "The cache directory must be writeable")

        if not verrors:
            try:
                await self.middleware.call("cloud_backup.ensure_initialized", data)
            except IncorrectPassword as e:
                verrors.add(f"{name}.password", e.errmsg)


class CloudBackupTaskFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.ERROR
    title = "Cloud Backup Task Failed"
    text = "Cloud backup task \"%(name)s\" failed."

    async def create(self, args):
        return Alert(CloudBackupTaskFailedAlertClass, args, key=args["id"])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))


class CloudBackupFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = "cloud_backup"
    title = "Cloud Backup Task"
    service_class = CloudBackupService
    resource_name = "path"

    async def restart_reload_services(self, attachments):
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)


async def setup(middleware):
    await middleware.call("pool.dataset.register_attachment_delegate", CloudBackupFSAttachmentDelegate(middleware))
    await middleware.call("network.general.register_activity", "cloud_backup", "Cloud backup")
    await middleware.call("cloud_backup.persist_task_state_on_job_complete")
