from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin, cloud_task_schema
from middlewared.schema import accepts, Cron, Dict, Int, Patch, Str
from middlewared.service import ValidationErrors, private, TaskPathService
import middlewared.sqlalchemy as sa
from middlewared.utils.path import FSLocation
from middlewared.utils.service.task_state import TaskStateMixin


class CloudBackupModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = "tasks_cloud_backup"

    password = sa.Column(sa.EncryptedText())


class CloudBackupService(TaskPathService, CloudTaskServiceMixin, TaskStateMixin):
    share_task_type = "CloudBackup"
    allowed_path_types = [FSLocation.CLUSTER, FSLocation.LOCAL]
    task_state_methods = ["cloud_backup.sync", "cloud_backup.restore"]

    class Config:
        datastore = "tasks.cloud_backup"
        datastore_extend = "cloud_backup.extend"
        datastore_extend_context = "cloud_backup.extend_context"
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @private
    async def extend_context(self, rows, extra):
        return {
            "task_state": await self.get_task_state_context(),
        }

    @private
    async def extend(self, cloud_backup, context):
        cloud_backup["credentials"] = cloud_backup.pop("credential")
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

    @accepts(Dict(
        "cloud_backup_create",
        *cloud_task_schema,
        Str("password", required=True, empty=False),
        register=True,
    ))
    async def do_create(self, cloud_backup):
        """
        """
        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_backup_create", cloud_backup)

        if verrors:
            raise verrors

        cloud_backup = await self._compress(cloud_backup)

        cloud_backup["id"] = await self.middleware.call("datastore.insert", "tasks.cloud_backup",
                                                        {**cloud_backup, "job": None})
        await self.middleware.call("service.restart", "cron")

        return await self.get_instance(cloud_backup["id"])

    @accepts(Int("id"), Patch("cloud_backup_create", "cloud_backup_update", ("attr", {"update": True})))
    async def do_update(self, id, data):
        """
        Updates the cloud backup entry `id` with `data`.
        """
        cloud_backup = await self.get_instance(id)

        # credentials is a foreign key for now
        if cloud_backup["credentials"]:
            cloud_backup["credentials"] = cloud_backup["credentials"]["id"]

        cloud_backup.update(data)

        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_backup_update", cloud_backup)

        if verrors:
            raise verrors

        cloud_backup = await self._compress(cloud_backup)

        await self.middleware.call("datastore.update", "tasks.cloud_backup", id, cloud_backup)
        await self.middleware.call("service.restart", "cron")

        return await self.get_instance(id)

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Deletes cloud backup entry `id`.
        """
        await self.middleware.call("cloud_backup.abort", id)
        await self.middleware.call("alert.oneshot_delete", "CloudBackupTaskFailed", id)
        rv = await self.middleware.call("datastore.delete", "tasks.cloud_backup", id)
        await self.middleware.call("service.restart", "cron")
        return rv


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
        await self.middleware.call("service.restart", "cron")


async def setup(middleware):
    await middleware.call("pool.dataset.register_attachment_delegate", CloudBackupFSAttachmentDelegate(middleware))
    await middleware.call("network.general.register_activity", "cloud_backup", "Cloud backup")
    await middleware.call("cloud_backup.persist_task_state_on_job_complete")
