from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin, cloud_task_schema
from middlewared.plugins.cloud.path import get_remote_path, check_local_path
from middlewared.plugins.cloud.remotes import REMOTES, remote_classes
from middlewared.schema import accepts, Bool, Cron, Dict, Int, Patch, Str
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, item_method, job, private, TaskPathService,
)
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, run
from middlewared.utils.lang import undefined
from middlewared.utils.path import FSLocation
from middlewared.utils.service.task_state import TaskStateMixin
from middlewared.validators import validate_schema

import aiorwlock
import asyncio
import base64
import codecs
from collections import namedtuple
import configparser
from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter
from datetime import datetime
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

        self.provider = REMOTES[self.cloud_sync["credentials"]["provider"]]

        self.config = None
        self.tmp_file = None
        self.tmp_file_filter = None

    async def __aenter__(self):
        self.tmp_file = tempfile.NamedTemporaryFile(mode="w+")

        # Make sure only root can read it as there is sensitive data
        os.chmod(self.tmp_file.name, 0o600)

        config = dict(self.cloud_sync["credentials"]["attributes"], type=self.provider.rclone_type)
        config = dict(config, **await self.provider.get_credentials_extra(self.cloud_sync["credentials"]))
        if "pass" in config:
            config["pass"] = rclone_encrypt_password(config["pass"])

        remote_path = None
        extra_args = []

        if "attributes" in self.cloud_sync:
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

    if await middleware.call("filesystem.is_cluster_path", cloud_sync["path"]):
        path = await middleware.call("filesystem.resolve_cluster_path", cloud_sync["path"])
        await check_local_path(
            middleware,
            path,
            check_mountpoint=False,
            error_text_path=cloud_sync["path"],
        )
    else:
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
            args.extend(["-L"])

        if cloud_sync["transfers"]:
            args.extend(["--transfers", str(cloud_sync["transfers"])])

        if cloud_sync["bwlimit"]:
            args.extend(["--bwlimit", " ".join([
                f"{limit['time']},{str(limit['bandwidth']) + 'b' if limit['bandwidth'] else 'off'}"
                for limit in cloud_sync["bwlimit"]
            ])])

        if dry_run:
            args.extend(["--dry-run"])

        args += config.extra_args

        args += shlex.split(cloud_sync["args"])

        args += [cloud_sync["transfer_mode"].lower()]

        if cloud_sync["create_empty_src_dirs"]:
            args.extend(["--create-empty-src-dirs"])

        snapshot = None
        if cloud_sync["direction"] == "PUSH":
            if cloud_sync["snapshot"]:
                dataset, recursive = get_dataset_recursive(
                    await middleware.call("zfs.dataset.query", [["type", "=", "FILESYSTEM"]]),
                    cloud_sync["path"],
                )
                snapshot_name = (
                    f"cloud_sync-{cloud_sync.get('id', 'onetime')}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                )

                snapshot = {"dataset": dataset["name"], "name": snapshot_name}
                await middleware.call("zfs.snapshot.create", dict(snapshot, recursive=recursive))

                relpath = os.path.relpath(path, dataset["properties"]["mountpoint"]["value"])
                path = os.path.normpath(os.path.join(
                    dataset["properties"]["mountpoint"]["value"], ".zfs", "snapshot", snapshot_name, relpath
                ))

            args.extend([path, config.remote_path])
        else:
            args.extend([config.remote_path, path])

        env = {}
        for k, v in (
            [(k, v) for (k, v) in cloud_sync.items()
             if k in ["id", "description", "direction", "transfer_mode", "encryption", "filename_encryption",
                      "encryption_password", "encryption_salt", "snapshot"]] +
            list(cloud_sync["credentials"]["attributes"].items()) +
            list(cloud_sync["attributes"].items())
        ):
            if type(v) in (bool,):
                env[f"CLOUD_SYNC_{k.upper()}"] = str(int(v))
            if type(v) in (int, str):
                env[f"CLOUD_SYNC_{k.upper()}"] = str(v)
        env["CLOUD_SYNC_PATH"] = path

        await run_script(job, env, cloud_sync["pre_script"], "Pre-script")

        job.middleware.logger.debug("Running %r", args)
        proc = await Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        check_cloud_sync = asyncio.ensure_future(rclone_check_progress(job, proc))
        cancelled_error = None
        try:
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
            await middleware.call("zfs.snapshot.delete", f"{snapshot['dataset']}@{snapshot['name']}")

        if cancelled_error is not None:
            raise cancelled_error
        if proc.returncode != 0:
            message = "".join(job.internal_data.get("messages", []))
            if message and proc.returncode != 1:
                if message and not message.endswith("\n"):
                    message += "\n"
                message += f"rclone failed with exit code {proc.returncode}"
            raise CallError(message)

        await run_script(job, env, cloud_sync["post_script"], "Post-script")

        refresh_credentials = REMOTES[cloud_sync["credentials"]["provider"]].refresh_credentials
        if refresh_credentials:
            credentials_attributes = cloud_sync["credentials"]["attributes"].copy()
            updated = False
            ini = configparser.ConfigParser()
            ini.read(config.config_path)
            for key, value in ini["remote"].items():
                if (key in refresh_credentials and
                        key in credentials_attributes and
                        credentials_attributes[key] != value):
                    logger.debug("Updating credentials attributes key %r", key)
                    credentials_attributes[key] = value
                    updated = True
            if updated:
                await middleware.call("cloudsync.credentials.update", cloud_sync["credentials"]["id"], {
                    "attributes": credentials_attributes
                })


async def run_script(job, env, hook, script_name):
    hook = hook.strip()
    if not hook:
        return

    if not hook.startswith("#!"):
        hook = f"#!/bin/bash\n{hook}"

    fd, name = tempfile.mkstemp()
    os.close(fd)
    try:
        os.chmod(name, 0o700)
        with open(name, "w+") as f:
            f.write(hook)

        proc = await Popen(
            [name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, **env),
        )
        future = asyncio.ensure_future(run_script_check(job, proc, script_name))
        await proc.wait()
        await asyncio.wait_for(future, None)
        if proc.returncode != 0:
            raise CallError(f"{script_name} failed with exit code {proc.returncode}")
    finally:
        os.unlink(name)


async def run_script_check(job, proc, name):
    while True:
        read = await proc.stdout.readline()
        if read == b"":
            break
        await job.logs_fd_write(f"[{name}] ".encode("utf-8") + read)


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


def get_dataset_recursive(datasets, directory):
    datasets = [
        dict(dataset, prefixlen=len(
            os.path.dirname(os.path.commonprefix(
                [dataset["properties"]["mountpoint"]["value"] + "/", directory + "/"]))
        ))
        for dataset in datasets
        if dataset["properties"]["mountpoint"]["value"] != "none"
    ]

    dataset = sorted(
        [
            dataset
            for dataset in datasets
            if (directory + "/").startswith(dataset["properties"]["mountpoint"]["value"] + "/")
        ],
        key=lambda dataset: dataset["prefixlen"],
        reverse=True
    )[0]

    return dataset, any(
        (ds["properties"]["mountpoint"]["value"] + "/").startswith(directory + "/")
        for ds in datasets
        if ds != dataset
    )


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

        cli_namespace = "task.cloud_sync.credential"

    @accepts(Dict(
        "cloud_sync_credentials_verify",
        Str("provider", required=True),
        Dict("attributes", additional_attrs=True, required=True),
    ))
    async def verify(self, data):
        """
        Verify if `attributes` provided for `provider` are authorized by the `provider`.
        """
        await self.middleware.call("network.general.will_perform_activity", "cloud_sync")

        data = dict(data, name="")
        await self._validate("cloud_sync_credentials_create", data)

        async with RcloneConfig({"credentials": data}) as config:
            proc = await run(["rclone", "--config", config.config_path, "--contimeout", "15s", "--timeout", "30s",
                              "lsjson", "remote:"],
                             check=False, encoding="utf8")
            if proc.returncode == 0:
                return {"valid": True}
            else:
                return {"valid": False, "error": proc.stderr, "excerpt": lsjson_error_excerpt(proc.stderr)}

    @accepts(Dict(
        "cloud_sync_credentials_create",
        Str("name", required=True),
        Str("provider", required=True),
        Dict("attributes", additional_attrs=True, required=True),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create Cloud Sync Credentials.

        `attributes` is a dictionary of valid values which will be used to authorize with the `provider`.
        """
        await self._validate("cloud_sync_credentials_create", data)

        data["id"] = await self.middleware.call(
            "datastore.insert",
            "system.cloudcredentials",
            data,
        )
        return data

    @accepts(
        Int("id"),
        Patch(
            "cloud_sync_credentials_create",
            "cloud_sync_credentials_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        """
        Update Cloud Sync Credentials of `id`.
        """
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self._validate("cloud_sync_credentials_update", new, id)

        await self.middleware.call(
            "datastore.update",
            "system.cloudcredentials",
            id,
            new,
        )

        data["id"] = id

        return data

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Delete Cloud Sync Credentials of `id`.
        """
        tasks = await self.middleware.call("cloudsync.query", [["credentials.id", "=", id]])
        if tasks:
            raise CallError(f"This credential is used by cloud sync task {tasks[0]['description'] or tasks[0]['id']}")

        return await self.middleware.call(
            "datastore.delete",
            "system.cloudcredentials",
            id,
        )

    async def _validate(self, schema_name, data, id=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id)

        if data["provider"] not in REMOTES:
            verrors.add(f"{schema_name}.provider", "Invalid provider")
        else:
            provider = REMOTES[data["provider"]]

            attributes_verrors = validate_schema(provider.credentials_schema, data["attributes"])
            verrors.add_child(f"{schema_name}.attributes", attributes_verrors)

        if verrors:
            raise verrors


class CloudSyncModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = 'tasks_cloudsync'

    direction = sa.Column(sa.String(10))
    transfer_mode = sa.Column(sa.String(20))

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
    allowed_path_types = [FSLocation.CLUSTER, FSLocation.LOCAL]
    task_state_methods = ['cloudsync.sync', 'cloudsync.restore']

    class Config:
        datastore = "tasks.cloudsync"
        datastore_extend = "cloudsync.extend"
        datastore_extend_context = "cloudsync.extend_context"
        cli_namespace = "task.cloud_sync"

    @private
    async def extend_context(self, rows, extra):
        return {
            "task_state": await self.get_task_state_context(),
        }

    @private
    async def extend(self, cloud_sync, context):
        cloud_sync["credentials"] = cloud_sync.pop("credential")
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
    async def _validate(self, verrors, name, data):
        await super()._validate(verrors, name, data)

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

            provider = REMOTES[credentials["provider"]]

            if provider.readonly:
                verrors.add(f"{name}.direction", "This remote is read-only")

    @accepts(Dict(
        "cloud_sync_create",
        *cloud_task_schema,

        Str("direction", enum=["PUSH", "PULL"], required=True),
        Str("transfer_mode", enum=["SYNC", "COPY", "MOVE"], required=True),

        Bool("encryption", default=False),
        Bool("filename_encryption", default=False),
        Str("encryption_password", default=""),
        Str("encryption_salt", default=""),

        Bool("create_empty_src_dirs", default=False),
        Bool("follow_symlinks", default=False),
        register=True,
    ))
    async def do_create(self, cloud_sync):
        """
        Creates a new cloud_sync entry.

        .. examples(websocket)::

          Create a new cloud_sync using amazon s3 attributes, which is supposed to run every hour.

            :::javascript
            {
              "id": "6841f242-840a-11e6-a437-00e04d680384",
              "msg": "method",
              "method": "cloudsync.create",
              "params": [{
                "description": "s3 sync",
                "path": "/mnt/tank",
                "credentials": 1,
                "minute": "00",
                "hour": "*",
                "daymonth": "*",
                "month": "*",
                "attributes": {
                  "bucket": "mybucket",
                  "folder": ""
                },
                "enabled": true
              }]
            }
        """

        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_sync_create", cloud_sync)

        if verrors:
            raise verrors

        await self._validate_folder(verrors, "cloud_sync_create", cloud_sync)

        if verrors:
            raise verrors

        cloud_sync = await self._compress(cloud_sync)

        cloud_sync["id"] = await self.middleware.call("datastore.insert", "tasks.cloudsync", cloud_sync)
        await self.middleware.call("service.restart", "cron")

        return await self.get_instance(cloud_sync["id"])

    @accepts(Int("id"), Patch("cloud_sync_create", "cloud_sync_update", ("attr", {"update": True})))
    async def do_update(self, id, data):
        """
        Updates the cloud_sync entry `id` with `data`.
        """
        cloud_sync = await self.get_instance(id)

        # credentials is a foreign key for now
        if cloud_sync["credentials"]:
            cloud_sync["credentials"] = cloud_sync["credentials"]["id"]

        cloud_sync.update(data)

        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_sync_update", cloud_sync)

        if verrors:
            raise verrors

        await self._validate_folder(verrors, "cloud_sync_update", cloud_sync)

        if verrors:
            raise verrors

        cloud_sync = await self._compress(cloud_sync)

        await self.middleware.call("datastore.update", "tasks.cloudsync", id, cloud_sync)
        await self.middleware.call("service.restart", "cron")

        return await self.get_instance(id)

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Deletes cloud_sync entry `id`.
        """
        await self.middleware.call("cloudsync.abort", id)
        await self.middleware.call("alert.oneshot_delete", "CloudSyncTaskFailed", id)
        rv = await self.middleware.call("datastore.delete", "tasks.cloudsync", id)
        await self.middleware.call("service.restart", "cron")
        return rv

    @accepts(Int("credentials_id"), Str("name"))
    async def create_bucket(self, credentials_id, name):
        """
        Creates a new bucket `name` using ` credentials_id`.
        """
        credentials = await self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials["provider"]]

        if not provider.can_create_bucket:
            raise CallError("This provider can't create buckets")

        await provider.create_bucket(credentials, name)

    @accepts(Int("credentials_id"))
    async def list_buckets(self, credentials_id):
        credentials = await self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials["provider"]]

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

    @accepts(Dict(
        "cloud_sync_ls",
        Int("credentials", required=True),
        Bool("encryption", default=False),
        Bool("filename_encryption", default=False),
        Str("encryption_password", default=""),
        Str("encryption_salt", default=""),
        Dict("attributes", required=True, additional_attrs=True),
        Str("args", default=""),
    ))
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

        if verrors:
            raise verrors

        credentials = await self._get_credentials(cloud_sync["credentials"])

        path = get_remote_path(REMOTES[credentials["provider"]], cloud_sync["attributes"])

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
    @accepts(
        Int("id"),
        Dict(
            "cloud_sync_sync_options",
            Bool("dry_run", default=False),
            register=True,
        )
    )
    @job(lock=lambda args: "cloud_sync:{}".format(args[-1]), lock_queue_size=1, logs=True, abortable=True)
    async def sync(self, job, id, options):
        """
        Run the cloud_sync job `id`, syncing the local data to remote.
        """

        cloud_sync = await self.get_instance(id)
        if cloud_sync["locked"]:
            await self.middleware.call("cloudsync.generate_locked_alert", id)
            raise CallError("Dataset is locked")

        await self._sync(cloud_sync, options, job)

    @accepts(
        Patch("cloud_sync_create", "cloud_sync_sync_onetime"),
        Patch("cloud_sync_sync_options", "cloud_sync_sync_onetime_options"),
    )
    @job(logs=True, abortable=True)
    async def sync_onetime(self, job, cloud_sync, options):
        """
        Run cloud sync task without creating it.
        """
        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_sync_sync_onetime", cloud_sync)

        if verrors:
            raise verrors

        await self._validate_folder(verrors, "cloud_sync_sync_onetime", cloud_sync)

        if verrors:
            raise verrors

        cloud_sync["credentials"] = await self._get_credentials(cloud_sync["credentials"])

        await self._sync(cloud_sync, options, job)

    async def _sync(self, cloud_sync, options, job):
        credentials = cloud_sync["credentials"]

        local_path = cloud_sync["path"]
        local_direction = FsLockDirection.READ if cloud_sync["direction"] == "PUSH" else FsLockDirection.WRITE

        remote_path = get_remote_path(REMOTES[credentials["provider"]], cloud_sync["attributes"])
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
    @accepts(Int("id"))
    async def abort(self, id):
        """
        Aborts cloud sync task.
        """

        cloud_sync = await self.get_instance(id)

        if cloud_sync["job"] is None:
            return False

        if cloud_sync["job"]["state"] not in ["WAITING", "RUNNING"]:
            return False

        await self.middleware.call("core.job_abort", cloud_sync["job"]["id"])
        return True

    @accepts()
    async def providers(self):
        """
        Returns a list of dictionaries of supported providers for Cloud Sync Tasks.

        `credentials_schema` is JSON schema for credentials attributes.

        `task_schema` is JSON schema for task attributes.

        `buckets` is a boolean value which is set to "true" if provider supports buckets.

        Example of a single provider:

        [
            {
                "name": "AMAZON_CLOUD_DRIVE",
                "title": "Amazon Cloud Drive",
                "credentials_schema": [
                    {
                        "property": "client_id",
                        "schema": {
                            "title": "Amazon Application Client ID",
                            "_required_": true,
                            "type": "string"
                        }
                    },
                    {
                        "property": "client_secret",
                        "schema": {
                            "title": "Application Key",
                            "_required_": true,
                            "type": "string"
                        }
                    }
                ],
                "credentials_oauth": null,
                "buckets": false,
                "bucket_title": "Bucket",
                "task_schema": []
            }
        ]
        """
        return sorted(
            [
                {
                    "name": provider.name,
                    "title": provider.title,
                    "credentials_schema": [
                        {
                            "property": field.name,
                            "schema": field.to_json_schema()
                        }
                        for field in provider.credentials_schema
                    ],
                    "credentials_oauth": (
                        f"{OAUTH_URL}/{(provider.credentials_oauth_name or provider.name.lower())}"
                        if provider.credentials_oauth else None
                    ),
                    "buckets": provider.buckets,
                    "bucket_title": provider.bucket_title,
                    "task_schema": [
                        {
                            "property": field.name,
                            "schema": field.to_json_schema()
                        }
                        for field in provider.task_schema + self._common_task_schema(provider)
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
        await self.middleware.call('service.restart', 'cron')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', CloudSyncFSAttachmentDelegate(middleware))
    await middleware.call('network.general.register_activity', 'cloud_sync', 'Cloud sync')
    await middleware.call('cloudsync.persist_task_state_on_job_complete')
