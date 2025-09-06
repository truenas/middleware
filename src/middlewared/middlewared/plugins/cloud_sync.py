from middlewared.alert.base import (
    Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass, SimpleOneShotAlertClass,
)
from middlewared.api import api_method
from middlewared.api.current import (CloudCredentialEntry,
                                     CredentialsCreateArgs, CredentialsCreateResult,
                                     CredentialsUpdateArgs, CredentialsUpdateResult,
                                     CredentialsDeleteArgs, CredentialsDeleteResult,
                                     CredentialsVerifyArgs, CredentialsVerifyResult,
                                     CredentialsS3ProviderChoicesArgs, CredentialsS3ProviderChoicesResult,
                                     CloudSyncEntry,
                                     CloudSyncCreateArgs, CloudSyncCreateResult,
                                     CloudSyncUpdateArgs, CloudSyncUpdateResult,
                                     CloudSyncDeleteArgs, CloudSyncDeleteResult,
                                     CloudSyncCreateBucketArgs, CloudSyncCreateBucketResult,
                                     CloudSyncListBucketsArgs, CloudSyncListBucketsResult,
                                     CloudSyncListDirectoryArgs, CloudSyncListDirectoryResult,
                                     CloudSyncSyncArgs, CloudSyncSyncResult,
                                     CloudSyncSyncOnetimeArgs, CloudSyncSyncOnetimeResult,
                                     CloudSyncAbortArgs, CloudSyncAbortResult,
                                     CloudSyncProvidersArgs, CloudSyncProvidersResult)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin
from middlewared.plugins.cloud.path import get_remote_path, check_local_path
from middlewared.plugins.cloud.remotes import REMOTES, remote_classes
from middlewared.plugins.cloud.script import env_mapping, run_script
from middlewared.plugins.cloud.snapshot import create_snapshot
from middlewared.rclone.remote.s3_providers import S3_PROVIDERS
from middlewared.rclone.remote.storjix import StorjIxError
from middlewared.schema import Cron
from middlewared.service import (
    CallError, CRUDService, ValidationError, ValidationErrors, item_method, job, private, TaskPathService,
)
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, run
from middlewared.utils.lang import undefined
from middlewared.utils.path import FSLocation
from middlewared.utils.service.task_state import TaskStateMixin

import aiorwlock
import asyncio
import base64
import codecs
from collections import namedtuple
import configparser
from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter
import enum
import json
import logging
import os
import re
import shlex
import subprocess
import tempfile

RE_TRANSF1 = re.compile(r"Transferred:\s*(?P<progress_1>.+), (?P<progress>[0-9]+)%$")
RE_TRANSF2 = re.compile(r"Transferred:\s*(?P<progress_1>.+, )(?P<progress>[0-9]+)%, (?P<progress_2>.+)$")
RE_CHECKS = re.compile(r"Checks:\s*(?P<checks>[0-9 /]+)(, (?P<progress>[0-9]+)%)?$")

OAUTH_URL = "https://www.truenas.com/oauth"

RcloneConfigTuple = namedtuple("RcloneConfigTuple", ["config_path", "remote_path", "extra_args"])

logger = logging.getLogger(__name__)


class RcloneConfig:
    def __init__(self, cloud_sync):
        self.cloud_sync = cloud_sync

        self.provider = REMOTES[self.cloud_sync["credentials"]["provider"]["type"]]

        self.config = None
        self.tmp_file = None
        self.tmp_file_filter = None

    async def __aenter__(self):
        self.tmp_file = tempfile.NamedTemporaryFile(mode="w+")

        # Make sure only root can read it as there is sensitive data
        os.chmod(self.tmp_file.name, 0o600)

        config = dict(self.cloud_sync["credentials"]["provider"], type=self.provider.rclone_type)
        config = dict(config, **await self.provider.get_credentials_extra(self.cloud_sync["credentials"]))
        if "pass" in config:
            config["pass"] = rclone_encrypt_password(config["pass"])

        remote_path = None
        extra_args = []

        if "attributes" in self.cloud_sync:
            extra_args = await self.provider.get_task_extra_args(self.cloud_sync)

            config.update(dict(self.cloud_sync["attributes"], **await self.provider.get_task_extra(self.cloud_sync)))
            for k, v in list(config.items()):
                if v is undefined:
                    config.pop(k)

            remote_path = get_remote_path(self.provider, self.cloud_sync["attributes"])
            remote_path = f"remote:{remote_path}"

            if self.cloud_sync["encryption"]:
                self.tmp_file.write("[encrypted]\n")
                self.tmp_file.write("type = crypt\n")
                self.tmp_file.write(f"remote = {remote_path}\n")
                self.tmp_file.write("filename_encryption = {}\n".format(
                    "standard" if self.cloud_sync["filename_encryption"] else "off"))
                self.tmp_file.write("password = {}\n".format(
                    rclone_encrypt_password(self.cloud_sync["encryption_password"])))
                if self.cloud_sync["encryption_salt"]:
                    self.tmp_file.write("password2 = {}\n".format(
                        rclone_encrypt_password(self.cloud_sync["encryption_salt"])))

                remote_path = "encrypted:/"

            rclone_filter = [
                "- .zfs",
                "- .zfs/**",
            ]

            if self.cloud_sync.get("path"):
                if os.path.dirname(self.cloud_sync.get("path").rstrip("/")) == "/mnt":
                    rclone_filter.extend([
                        "- /ix-applications",
                        "- /ix-apps",
                        "- /ix-applications/**",
                        "- /ix-apps/**",
                    ])

            for item in self.cloud_sync.get("exclude") or []:
                rclone_filter.append(f"- {item}")

            if self.cloud_sync.get("include"):
                for item in self.cloud_sync["include"]:
                    rclone_filter.append(f"+ {item}")
                rclone_filter.append("- *")

            self.tmp_file_filter = tempfile.NamedTemporaryFile(mode="w+")
            self.tmp_file_filter.write("\n".join(rclone_filter))
            self.tmp_file_filter.flush()
            extra_args.extend(["--filter-from", self.tmp_file_filter.name])

        self.tmp_file.write("[remote]\n")
        for k, v in config.items():
            if isinstance(v, bool):
                v = json.dumps(v)
            self.tmp_file.write(f"{k} = {v}\n")

        self.tmp_file.flush()

        self.config = config

        return RcloneConfigTuple(self.tmp_file.name, remote_path, extra_args)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.config is not None:
            await self.provider.cleanup(self.cloud_sync, self.config)
        if self.tmp_file:
            self.tmp_file.close()
        if self.tmp_file_filter:
            self.tmp_file_filter.close()


async def rclone(middleware, job, cloud_sync, dry_run):
    await middleware.call("network.general.will_perform_activity", "cloud_sync")

    path = cloud_sync["path"]
    await check_local_path(middleware, path)

    # Use a temporary file to store rclone file
    async with RcloneConfig(cloud_sync) as config:
        args = [
            "rclone",
            "--config", config.config_path,
            "-v",
            "--stats", "1s",
        ]

        if cloud_sync["attributes"].get("fast_list"):
            args.append("--fast-list")

        if cloud_sync["follow_symlinks"]:
            args.append("-L")

        if cloud_sync["transfers"]:
            args.extend(["--transfers", str(cloud_sync["transfers"])])

        if cloud_sync["bwlimit"]:
            args.extend(["--bwlimit", " ".join([
                f"{limit['time']},{str(limit['bandwidth']) + 'b' if limit['bandwidth'] else 'off'}"
                for limit in cloud_sync["bwlimit"]
            ])])

        if dry_run:
            args.append("--dry-run")

        args += config.extra_args

        args += shlex.split(cloud_sync["args"])

        args += [cloud_sync["transfer_mode"].lower()]

        if cloud_sync["create_empty_src_dirs"]:
            args.append("--create-empty-src-dirs")

        snapshot = None
        if cloud_sync["direction"] == "PUSH":
            if cloud_sync["snapshot"]:
                snapshot_name = f"cloud_sync-{cloud_sync.get('id', 'onetime')}"
                snapshot, path = await create_snapshot(middleware, path, snapshot_name)

            args.extend([path, config.remote_path])
        else:
            args.extend([config.remote_path, path])

        env = env_mapping("CLOUD_SYNC_", {
            **{k: v for k, v in cloud_sync.items() if k in [
                "id", "description", "direction", "transfer_mode", "encryption", "filename_encryption",
                "encryption_password", "encryption_salt", "snapshot"
            ]},
            **cloud_sync["credentials"]["provider"],
            **cloud_sync["attributes"],
            "path": path
        })
        await run_script(job, "Pre-script", cloud_sync["pre_script"], env)

        job.middleware.logger.trace("Running %r", args)
        proc = await Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        check_cloud_sync = asyncio.ensure_future(rclone_check_progress(job, proc))
        cancelled_error = None
        try:
            await proc.wait()
        except asyncio.CancelledError as e:
            cancelled_error = e
            try:
                await middleware.call("service.terminate_process", proc.pid)
            except CallError as e:
                job.middleware.logger.warning(f"Error terminating rclone on cloud sync abort: {e!r}")
        finally:
            await asyncio.wait_for(check_cloud_sync, None)

        if snapshot:
            try:
                await middleware.call("zfs.snapshot.delete", snapshot)
            except CallError as e:
                middleware.logger.warning(f"Error deleting ZFS snapshot on cloud sync finish: {e!r}")

        refresh_credentials = REMOTES[cloud_sync["credentials"]["provider"]["type"]].refresh_credentials
        if refresh_credentials:
            credentials_attributes = cloud_sync["credentials"]["provider"].copy()
            updated = False
            ini = configparser.ConfigParser()
            ini.read(config.config_path)
            for key, value in ini["remote"].items():
                if (
                        key in refresh_credentials and
                        key in credentials_attributes and
                        credentials_attributes[key] != value
                ):
                    logger.debug("Updating credentials attributes key %r", key)
                    credentials_attributes[key] = value
                    updated = True
            if updated:
                await middleware.call("cloudsync.credentials.update", cloud_sync["credentials"]["id"], {
                    "provider": credentials_attributes
                })

        if cancelled_error is not None:
            raise cancelled_error
        if proc.returncode != 0:
            message = "".join(job.internal_data.get("messages", []))
            if message and proc.returncode != 1:
                if not message.endswith("\n"):
                    message += "\n"
                message += f"rclone failed with exit code {proc.returncode}"
            raise CallError(message)

        await run_script(job, "Post-script", cloud_sync["post_script"], env)


# Prevents clogging job logs with progress reports every second
class RcloneVerboseLogCutter:
    PREFIXES = (
        re.compile(r"([0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} |<6>)INFO {2}:\s*$"),
        re.compile(r"Transferred:\s+"),
        re.compile(r"Errors:\s+"),
        re.compile(r"Checks:\s+"),
        re.compile(r"Elapsed time:\s+"),
        re.compile(r"Transferring:"),
        re.compile(r" * .+"),
    )

    def __init__(self, interval):
        self.interval = interval

        self.buffer = []
        self.counter = 0

    def notify(self, line):
        if self.buffer:
            # We are currently reading progress message

            self.buffer.append(line)

            if line.rstrip("\n"):
                # We are still reading message

                matches = any(prefix.match(line) for prefix in self.PREFIXES)

                if matches:
                    # Good, consuming this line to buffer and yet not writing it to logs
                    return None
                else:
                    # This was unexpected form of progress message (or not a progress message at all)

                    new_buffer = []
                    if self.PREFIXES[0].match(line):
                        # This line can be start of new progress message, ejecting it from buffer
                        self.buffer = self.buffer[:-1]
                        # And adding to new buffer
                        new_buffer = [line]

                    # Writing buffer to logs
                    try:
                        return self.flush()
                    finally:
                        self.buffer = new_buffer
            else:
                # This message ends with newline
                try:
                    if self.counter % self.interval == 0:
                        # Every {counter} times we still write this buffer to logs
                        return "".join(self.buffer)
                    else:
                        return None
                finally:
                    # Resetting state, ready to consume next line
                    self.buffer = []
                    self.counter += 1
        else:
            # We are not reading progress message

            if self.PREFIXES[0].match(line):
                # This is the first line of progress message
                self.buffer.append(line)
                return None
            else:
                return line

    def flush(self):
        try:
            return "".join(self.buffer)
        finally:
            self.buffer = []


async def rclone_check_progress(job, proc):
    cutter = RcloneVerboseLogCutter(300)
    dropbox__restricted_content = False
    try:
        progress1 = None
        transferred1 = None
        progress2 = None
        transferred2 = None
        progress3 = None
        checks = None
        while True:
            read = (await proc.stdout.readline()).decode("utf-8", "ignore")
            if read == "":
                break

            job.internal_data.setdefault("messages", [])
            job.internal_data["messages"] = job.internal_data["messages"][-4:] + [read]

            if "failed to open source object: path/restricted_content/" in read:
                job.internal_data["dropbox__restricted_content"] = True
                dropbox__restricted_content = True

            result = cutter.notify(read)
            if result:
                await job.logs_fd_write(result.encode("utf-8", "ignore"))

            if reg := RE_TRANSF1.search(read):
                progress1 = int(reg.group("progress"))
                transferred1 = reg.group("progress_1")
            if reg := RE_TRANSF2.search(read):
                progress2 = int(reg.group("progress"))
                transferred2 = reg.group("progress_1") + reg.group("progress_2")
            if reg := RE_CHECKS.search(read):
                progress3 = int(reg.group("progress"))
                checks = f'checks: {reg.group("checks")}'

            progresses = list(filter(lambda v: v is not None, [progress1, progress2, progress3]))
            if progresses:
                job.set_progress(min(progresses), ', '.join(filter(None, [transferred1, transferred2, checks])))
    finally:
        result = cutter.flush()
        if result:
            await job.logs_fd_write(result.encode("utf-8", "ignore"))

    if dropbox__restricted_content:
        message = (
            "Dropbox sync failed due to restricted content being present in one of the folders. This may include\n"
            "copyrighted content or the DropBox manual PDF that appears in the home directory after signing up.\n"
            "All other files were synchronized, but no deletions were performed as synchronization is considered\n"
            "unsuccessful. Please inspect logs to determine which files are considered restricted and exclude them\n"
            "from your synchronization. If you think that files are restricted erroneously, contact\n"
            "Dropbox Support: https://www.dropbox.com/support\n"
        )
        job.internal_data["messages"] = [message]
        await job.logs_fd_write(("\n" + message).encode("utf-8", "ignore"))


def rclone_encrypt_password(password):
    key = bytes([0x9c, 0x93, 0x5b, 0x48, 0x73, 0x0a, 0x55, 0x4d,
                 0x6b, 0xfd, 0x7c, 0x63, 0xc8, 0x86, 0xa9, 0x2b,
                 0xd3, 0x90, 0x19, 0x8e, 0xb8, 0x12, 0x8a, 0xfb,
                 0xf4, 0xde, 0x16, 0x2b, 0x8b, 0x95, 0xf6, 0x38])

    iv = Random.new().read(AES.block_size)
    counter = Counter.new(128, initial_value=int(codecs.encode(iv, "hex"), 16))
    cipher = AES.new(key, AES.MODE_CTR, counter=counter)
    encrypted = iv + cipher.encrypt(password.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("ascii").rstrip("=")


class _FsLockCore(aiorwlock._RWLockCore):
    def _release(self, lock_type):
        if self._r_state == 0 and self._w_state == 0:
            self._fs_manager._remove_lock(self._fs_path)

        return super()._release(lock_type)


class _FsLock(aiorwlock.RWLock):
    core = _FsLockCore


class FsLockDirection(enum.Enum):
    READ = 0
    WRITE = 1


class FsLockManager:
    _lock = _FsLock

    def __init__(self):
        self.locks = {}

    def lock(self, path, direction):
        path = os.path.normpath(path)
        for k in self.locks:
            if os.path.commonpath([k, path]) in [k, path]:
                return self._choose_lock(self.locks[k], direction)

        self.locks[path] = self._lock()
        self.locks[path]._reader_lock._lock._fs_manager = self
        self.locks[path]._reader_lock._lock._fs_path = path
        return self._choose_lock(self.locks[path], direction)

    def _choose_lock(self, lock, direction):
        if direction == FsLockDirection.READ:
            return lock.reader_lock
        if direction == FsLockDirection.WRITE:
            return lock.writer_lock
        raise ValueError(direction)

    def _remove_lock(self, path):
        self.locks.pop(path)


class CloudSyncTaskFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.ERROR
    title = "Cloud Sync Task Failed"
    text = "Cloud sync task \"%(name)s\" failed."

    async def create(self, args):
        return Alert(CloudSyncTaskFailedAlertClass, args, key=args["id"])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))

    async def load(self, alerts):
        task_ids = {str(task["id"]) for task in await self.middleware.call("cloudsync.query")}
        return [alert for alert in alerts if alert.key in task_ids]


class CloudProviderRemovedAlertClass(AlertClass, SimpleOneShotAlertClass):
    level = AlertLevel.INFO
    category = AlertCategory.TASKS
    title = "Cloud Provider Was Removed"
    text = (
        "%(provider)s is no longer a supported Cloud Credential. All previously configured Cloud Tasks have been "
        "deleted."
    )
    deleted_automatically = False


def lsjson_error_excerpt(error):
    excerpt = error.split("\n")[0]
    excerpt = re.sub(r"^[0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} ", "", excerpt)
    excerpt = excerpt.replace("Failed to create file system for \"remote:\": ", "")
    excerpt = excerpt.replace("ERROR : : error listing: ", "")
    return excerpt


class CloudCredentialModel(sa.Model):
    __tablename__ = 'system_cloudcredentials'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(100))
    provider = sa.Column(sa.String(50))
    attributes = sa.Column(sa.JSON(encrypted=True))


class CredentialsService(CRUDService):

    class Config:
        namespace = "cloudsync.credentials"

        datastore = "system.cloudcredentials"
        datastore_extend = 'cloudsync.credentials.extend'

        cli_namespace = "task.cloud_sync.credential"

        role_prefix = "CLOUD_SYNC"

        entry = CloudCredentialEntry

    @private
    async def extend(self, data):
        data["provider"] = {
            "type": data["provider"],
            **data.pop("attributes"),
        }
        return data

    @private
    async def compress(self, data):
        data["attributes"] = data["provider"]
        data["provider"] = data["attributes"].pop("type")
        return data

    @api_method(CredentialsVerifyArgs, CredentialsVerifyResult, roles=["CLOUD_SYNC_WRITE"])
    async def verify(self, data):
        """
        Verify if `attributes` provided for `provider` are authorized by the `provider`.
        """
        await self.middleware.call("network.general.will_perform_activity", "cloud_sync")

        async with RcloneConfig({"credentials": {"provider": data}}) as config:
            proc = await run(["rclone", "--config", config.config_path, "--contimeout", "15s", "--timeout", "30s",
                              "lsjson", "remote:"],
                             check=False, encoding="utf8")
            if proc.returncode == 0:
                return {"valid": True}
            else:
                return {"valid": False, "error": proc.stderr, "excerpt": lsjson_error_excerpt(proc.stderr)}

    @api_method(CredentialsCreateArgs, CredentialsCreateResult)
    async def do_create(self, data):
        """
        Create Cloud Sync Credentials.

        `attributes` is a dictionary of valid values which will be used to authorize with the `provider`.
        """
        await self._validate("cloud_sync_credentials_create", data)

        await self.compress(data)
        data["id"] = await self.middleware.call(
            "datastore.insert",
            "system.cloudcredentials",
            data,
        )
        await self.extend(data)
        return data

    @api_method(CredentialsUpdateArgs, CredentialsUpdateResult)
    async def do_update(self, id_, data):
        """
        Update Cloud Sync Credentials of `id`.
        """
        old = await self.get_instance(id_)

        new = old.copy()
        new.update(data)

        await self._validate("cloud_sync_credentials_update", new, id_)

        await self.compress(new)
        await self.middleware.call(
            "datastore.update",
            "system.cloudcredentials",
            id_,
            new,
        )
        await self.extend(new)

        return new

    @api_method(CredentialsDeleteArgs, CredentialsDeleteResult)
    async def do_delete(self, id_):
        """
        Delete Cloud Sync Credentials of `id`.
        """
        tasks = await self.middleware.call(
            "cloudsync.query", [["credentials.id", "=", id_]], {"select": ["id", "credentials", "description"]}
        )
        if tasks:
            raise CallError(f"This credential is used by cloud sync task {tasks[0]['description'] or tasks[0]['id']}")

        tasks = await self.middleware.call(
            "cloud_backup.query", [["credentials.id", "=", id_]], {"select": ["id", "credentials", "description"]}
        )
        if tasks:
            raise CallError(f"This credential is used by cloud backup task {tasks[0]['description'] or tasks[0]['id']}")

        return await self.middleware.call(
            "datastore.delete",
            "system.cloudcredentials",
            id_,
        )

    async def _validate(self, schema_name, data, id_=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id_)

        verrors.check()

    @api_method(CredentialsS3ProviderChoicesArgs, CredentialsS3ProviderChoicesResult)
    def s3_provider_choices(self):
        return S3_PROVIDERS


class CloudSyncModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = 'tasks_cloudsync'

    direction = sa.Column(sa.String(10))
    transfer_mode = sa.Column(sa.String(20))
    bwlimit = sa.Column(sa.JSON(list))
    transfers = sa.Column(sa.Integer(), nullable=True)

    encryption = sa.Column(sa.Boolean())
    filename_encryption = sa.Column(sa.Boolean())
    encryption_password = sa.Column(sa.EncryptedText())
    encryption_salt = sa.Column(sa.EncryptedText())

    create_empty_src_dirs = sa.Column(sa.Boolean())
    follow_symlinks = sa.Column(sa.Boolean())


class CloudSyncService(TaskPathService, CloudTaskServiceMixin, TaskStateMixin):

    local_fs_lock_manager = FsLockManager()
    remote_fs_lock_manager = FsLockManager()
    share_task_type = 'CloudSync'
    allowed_path_types = [FSLocation.LOCAL]
    task_state_methods = ['cloudsync.sync', 'cloudsync.restore']

    class Config:
        datastore = "tasks.cloudsync"
        datastore_extend = "cloudsync.extend"
        datastore_extend_context = "cloudsync.extend_context"
        cli_namespace = "task.cloud_sync"
        entry = CloudSyncEntry
        role_prefix = "CLOUD_SYNC"

    @private
    async def extend_context(self, rows, extra):
        return {
            "task_state": await self.get_task_state_context(),
        }

    @private
    async def extend(self, cloud_sync, context):
        cloud_sync["credentials"] = await self.middleware.call(
            "cloudsync.credentials.extend", cloud_sync.pop("credential"),
        )

        if job := await self.get_task_state_job(context["task_state"], cloud_sync["id"]):
            cloud_sync["job"] = job

        Cron.convert_db_format_to_schedule(cloud_sync)

        return cloud_sync

    @private
    async def _compress(self, cloud_sync):
        cloud_sync["credential"] = cloud_sync.pop("credentials")

        Cron.convert_schedule_to_db_format(cloud_sync)

        cloud_sync.pop('job', None)
        cloud_sync.pop(self.locked_field, None)

        return cloud_sync

    @private
    async def _basic_validate(self, verrors, name, data):
        if data["encryption"]:
            if not data["encryption_password"]:
                verrors.add(f"{name}.encryption_password", "This field is required when encryption is enabled")

        await super()._basic_validate(verrors, name, data)

    @private
    async def _validate(self, app, verrors, name, data):
        await super()._validate(app, verrors, name, data)

        for i, (limit1, limit2) in enumerate(zip(data["bwlimit"], data["bwlimit"][1:])):
            if limit1["time"] >= limit2["time"]:
                verrors.add(f"{name}.bwlimit.{i + 1}.time", f"Invalid time order: {limit1['time']}, {limit2['time']}")

        if data["snapshot"]:
            if data["direction"] != "PUSH":
                verrors.add(f"{name}.snapshot", "This option can only be enabled for PUSH tasks")
            if data["transfer_mode"] == "MOVE":
                verrors.add(f"{name}.snapshot", "This option can not be used for MOVE transfer mode")

    @private
    async def _validate_folder(self, verrors, name, data):
        if data["direction"] == "PULL":
            folder = data["attributes"]["folder"].rstrip("/")
            if folder:
                folder_parent = os.path.normpath(os.path.join(folder, ".."))
                if folder_parent == ".":
                    folder_parent = ""
                folder_basename = os.path.basename(folder)
                ls = await self.list_directory(dict(
                    credentials=data["credentials"],
                    encryption=data["encryption"],
                    filename_encryption=data["filename_encryption"],
                    encryption_password=data["encryption_password"],
                    encryption_salt=data["encryption_salt"],
                    attributes=dict(data["attributes"], folder=folder_parent),
                    args=data["args"],
                ))
                for item in ls:
                    if item["Name"] == folder_basename:
                        if not item["IsDir"]:
                            verrors.add(f"{name}.attributes.folder", "This is not a directory")
                        break
                else:
                    verrors.add(f"{name}.attributes.folder", "Directory does not exist")

        if data["direction"] == "PUSH":
            credentials = await self._get_credentials(data["credentials"])

            provider = REMOTES[credentials["provider"]["type"]]

            if provider.readonly:
                verrors.add(f"{name}.direction", "This remote is read-only")

    @api_method(CloudSyncCreateArgs, CloudSyncCreateResult, pass_app=True, pass_app_rest=True)
    async def do_create(self, app, cloud_sync):
        """
        Creates a new cloud_sync entry.
        """
        verrors = ValidationErrors()

        await self._validate(app, verrors, "cloud_sync_create", cloud_sync)

        verrors.check()

        await self._validate_folder(verrors, "cloud_sync_create", cloud_sync)

        verrors.check()

        cloud_sync = await self._compress(cloud_sync)

        cloud_sync["id"] = await self.middleware.call("datastore.insert", "tasks.cloudsync", cloud_sync)
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)

        return await self.get_instance(cloud_sync["id"])

    @api_method(CloudSyncUpdateArgs, CloudSyncUpdateResult, pass_app=True, pass_app_rest=True)
    async def do_update(self, app, id_, data):
        """
        Updates the cloud_sync entry `id` with `data`.
        """
        cloud_sync = await self.get_instance(id_)

        # credentials is a foreign key for now
        if cloud_sync["credentials"]:
            cloud_sync["credentials"] = cloud_sync["credentials"]["id"]

        cloud_sync.update(data)

        verrors = ValidationErrors()

        await self._validate(app, verrors, "cloud_sync_update", cloud_sync)

        verrors.check()

        await self._validate_folder(verrors, "cloud_sync_update", cloud_sync)

        verrors.check()

        cloud_sync = await self._compress(cloud_sync)

        await self.middleware.call("datastore.update", "tasks.cloudsync", id_, cloud_sync)
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(CloudSyncDeleteArgs, CloudSyncDeleteResult)
    async def do_delete(self, id_):
        """
        Deletes cloud_sync entry `id`.
        """
        await self.middleware.call("cloudsync.abort", id_)
        await self.middleware.call("alert.oneshot_delete", "CloudSyncTaskFailed", id_)
        rv = await self.middleware.call("datastore.delete", "tasks.cloudsync", id_)
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)
        return rv

    @api_method(CloudSyncCreateBucketArgs, CloudSyncCreateBucketResult, roles=["CLOUD_SYNC_WRITE"])
    async def create_bucket(self, credentials_id, name):
        """
        Creates a new bucket `name` using ` credentials_id`.
        """
        credentials = await self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials["provider"]["type"]]

        if not provider.can_create_bucket:
            raise CallError("This provider can't create buckets")

        try:
            await provider.create_bucket(credentials, name)
        except StorjIxError as e:
            raise ValidationError("cloudsync.create_bucket", e.errmsg, e.errno)

    @api_method(CloudSyncListBucketsArgs, CloudSyncListBucketsResult, roles=["CLOUD_SYNC_WRITE"])
    async def list_buckets(self, credentials_id):
        credentials = await self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials["provider"]["type"]]

        if not provider.buckets:
            raise CallError("This provider does not use buckets")

        if provider.custom_list_buckets:
            return [
                {
                    "Path": bucket["name"],
                    "Name": bucket["name"],
                    "Size": -1,
                    "MimeType": "inode/directory",
                    "ModTime": bucket["time"],
                    "IsDir": True,
                    "IsBucket": True,
                    "Enabled": bucket["enabled"],
                }
                for bucket in await provider.list_buckets(credentials)
            ]

        return await self.ls({"credentials": credentials}, "")

    @api_method(CloudSyncListDirectoryArgs, CloudSyncListDirectoryResult, roles=["CLOUD_SYNC_WRITE"])
    async def list_directory(self, cloud_sync):
        """
        List contents of a remote bucket / directory.

        If remote supports buckets, path is constructed by two keys "bucket"/"folder" in `attributes`.
        If remote does not support buckets, path is constructed using "folder" key only in `attributes`.
        "folder" is directory name and "bucket" is bucket name for remote.

        Path examples:

        S3 Service
        `bucketname/directory/name`

        Dropbox Service
        `directory/name`

        `credentials` is a valid id of a Cloud Sync Credential which will be used to connect to the provider.
        """
        verrors = ValidationErrors()

        await self._basic_validate(verrors, "cloud_sync", dict(cloud_sync))

        verrors.check()

        credentials = await self._get_credentials(cloud_sync["credentials"])

        path = get_remote_path(REMOTES[credentials["provider"]["type"]], cloud_sync["attributes"])

        return await self.ls(dict(cloud_sync, credentials=credentials), path)

    @private
    async def ls(self, config, path):
        await self.middleware.call("network.general.will_perform_activity", "cloud_sync")

        decrypt_filenames = config.get("encryption") and config.get("filename_encryption")
        async with RcloneConfig(config) as config:
            proc = await run(["rclone", "--config", config.config_path, "lsjson", "remote:" + path],
                             check=False, encoding="utf8", errors="ignore")
            if proc.returncode == 0:
                result = json.loads(proc.stdout)

                for item in result:
                    item["Enabled"] = True

                if decrypt_filenames:
                    if result:
                        decrypted_names = {}
                        proc = await run((["rclone", "--config", config.config_path, "cryptdecode", "encrypted:"] +
                                         [item["Name"] for item in result]),
                                         check=False, encoding="utf8", errors="ignore")
                        for line in proc.stdout.splitlines():
                            try:
                                encrypted, decrypted = line.rstrip("\r\n").split(" \t ", 1)
                            except ValueError:
                                continue

                            if decrypted != "Failed to decrypt":
                                decrypted_names[encrypted] = decrypted

                        for item in result:
                            if item["Name"] in decrypted_names:
                                item["Decrypted"] = decrypted_names[item["Name"]]

                return result
            else:
                raise CallError(proc.stderr, extra={"excerpt": lsjson_error_excerpt(proc.stderr)})

    @item_method
    @api_method(CloudSyncSyncArgs, CloudSyncSyncResult, roles=["CLOUD_SYNC_WRITE"])
    @job(lock=lambda args: "cloud_sync:{}".format(args[-1]), lock_queue_size=1, logs=True, abortable=True,
         read_roles=["CLOUD_SYNC_READ"])
    async def sync(self, job, id_, options):
        """
        Run the cloud_sync job `id`, syncing the local data to remote.
        """

        cloud_sync = await self.get_instance(id_)
        if cloud_sync["locked"]:
            await self.middleware.call("cloudsync.generate_locked_alert", id_)
            raise CallError("Dataset is locked")

        await self._sync(cloud_sync, options, job)

    @api_method(CloudSyncSyncOnetimeArgs, CloudSyncSyncOnetimeResult, roles=["CLOUD_SYNC_WRITE"])
    @job(logs=True, abortable=True)
    async def sync_onetime(self, job, cloud_sync, options):
        """
        Run cloud sync task without creating it.
        """
        verrors = ValidationErrors()

        # Forbid unprivileged users to execute scripts as root this way.
        for k in ["pre_script", "post_script"]:
            if cloud_sync[k]:
                verrors.add(
                    f"cloud_sync_sync_onetime.{k}",
                    "This option may not be used for onetime cloud sync operations",
                )

        await self._validate(None, verrors, "cloud_sync_sync_onetime", cloud_sync)

        verrors.check()

        await self._validate_folder(verrors, "cloud_sync_sync_onetime", cloud_sync)

        verrors.check()

        cloud_sync["credentials"] = await self._get_credentials(cloud_sync["credentials"])

        await self._sync(cloud_sync, options, job)

    async def _sync(self, cloud_sync, options, job):
        credentials = cloud_sync["credentials"]

        local_path = cloud_sync["path"]
        local_direction = FsLockDirection.READ if cloud_sync["direction"] == "PUSH" else FsLockDirection.WRITE

        remote_path = get_remote_path(REMOTES[credentials["provider"]["type"]], cloud_sync["attributes"])
        remote_direction = FsLockDirection.READ if cloud_sync["direction"] == "PULL" else FsLockDirection.WRITE

        directions = {
            FsLockDirection.READ: "reading",
            FsLockDirection.WRITE: "writing",
        }

        job.set_progress(0, f"Locking local path {local_path!r} for {directions[local_direction]}")
        async with self.local_fs_lock_manager.lock(local_path, local_direction):
            job.set_progress(0, f"Locking remote path {remote_path!r} for {directions[remote_direction]}")
            async with self.remote_fs_lock_manager.lock(f"{credentials['id']}/{remote_path}", remote_direction):
                job.set_progress(0, "Starting")
                try:
                    await rclone(self.middleware, job, cloud_sync, options["dry_run"])
                    if "id" in cloud_sync:
                        await self.middleware.call("alert.oneshot_delete", "CloudSyncTaskFailed", cloud_sync["id"])
                except Exception:
                    if "id" in cloud_sync:
                        await self.middleware.call("alert.oneshot_create", "CloudSyncTaskFailed", {
                            "id": cloud_sync["id"],
                            "name": cloud_sync["description"],
                        })
                    raise

    @item_method
    @api_method(CloudSyncAbortArgs, CloudSyncAbortResult, roles=["CLOUD_SYNC_WRITE"])
    async def abort(self, id_):
        """
        Aborts cloud sync task.
        """

        cloud_sync = await self.get_instance(id_)

        if cloud_sync["job"] is None:
            return False

        if cloud_sync["job"]["state"] not in ["WAITING", "RUNNING"]:
            return False

        await self.middleware.call("core.job_abort", cloud_sync["job"]["id"])
        return True

    @api_method(CloudSyncProvidersArgs, CloudSyncProvidersResult, roles=["CLOUD_SYNC_READ"])
    async def providers(self):
        """
        Returns a list of dictionaries of supported providers for Cloud Sync Tasks.
        """
        return sorted(
            [
                {
                    "name": provider.name,
                    "title": provider.title,
                    "credentials_oauth": (
                        f"{OAUTH_URL}/{(provider.credentials_oauth_name or provider.name.lower())}"
                        if provider.credentials_oauth else None
                    ),
                    "buckets": provider.buckets,
                    "bucket_title": provider.bucket_title,
                    "task_schema": [
                        {
                            "property": attribute,
                        }
                        for attribute in await self.middleware.call("cloudsync.task_attributes", provider)
                    ],
                }
                for provider in REMOTES.values()
            ],
            key=lambda provider: provider["title"].lower()
        )


for cls in remote_classes:
    for method_name in cls.extra_methods:
        setattr(CloudSyncService, f"{cls.name.lower()}_{method_name}", getattr(cls, method_name))


class CloudSyncFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'cloudsync'
    title = 'CloudSync Task'
    service_class = CloudSyncService
    resource_name = 'path'

    async def restart_reload_services(self, attachments):
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', CloudSyncFSAttachmentDelegate(middleware))
    await middleware.call('network.general.register_activity', 'cloud_sync', 'Cloud sync')
    await middleware.call('cloudsync.persist_task_state_on_job_complete')
