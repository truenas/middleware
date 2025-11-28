import contextlib
import io
import os
import queue
import requests
import shutil
import tarfile
import time
from multiprocessing import Manager

from middlewared.api import api_method
from middlewared.api.current import SystemDebugArgs, SystemDebugResult
from middlewared.utils.user_context import run_with_user_context_manager
from middlewared.service import CallError, job, private, Service

from ixdiagnose.config import conf
from ixdiagnose.event import event_callbacks
from ixdiagnose.run import generate_debug

from .utils import DEBUG_MAX_SIZE, get_debug_execution_dir


def generate_debug_user_context(system_dataset_path, progress_queue):
    """ This function generates our debug file from wihtin the context of a
    temporary process with reduced privileges for API calls. Local filesystem
    operation within debug files collection will still be performed as uid 0 """

    i = 0
    while True:
        execution_dir = get_debug_execution_dir(system_dataset_path, i)
        dump = os.path.join(execution_dir, "ixdiagnose.tgz")

        # Be extra safe in case we have left over from previous run
        try:
            with contextlib.suppress(FileNotFoundError):
                shutil.rmtree(execution_dir, ignore_errors=False)
        except Exception as e:
            i += 1
            if i >= 5:
                raise CallError(f"Failed to generate ixdiagnose debug: {e!r}")
        else:
            break

    conf.apply(
        {
            "compress": True,
            "debug_path": os.path.join(execution_dir, "debug"),
            "clean_debug_path": True,
            "compressed_path": dump,
        }
    )

    def progress_callback(percent, desc):
        progress_queue.put({'percent': percent, 'description': desc})

    event_callbacks.clear()
    event_callbacks.register(progress_callback)
    return generate_debug()


class SystemService(Service):
    @private
    @job(lock="system.debug_generate", lock_queue_size=1)
    def debug_generate(self, job):
        """
        Generate system debug file.

        Result value will be the absolute path of the file.
        """
        system_dataset_path = self.middleware.call_sync("systemdataset.config")["path"]

        try:
            with Manager() as manager:
                # Drop our effective privileges to READONLY_ADMIN for client sessions
                # when generating the debug. We do this by running within a temporary
                # child process where we setreuid / setregid to a restricted admin.
                # This ensures that we redact fields marked as Secret in the API
                #
                # We're using a queue to pass the debug status updates back out of the
                # child process.
                progress_queue = manager.Queue()

                with run_with_user_context_manager(
                    func=generate_debug_user_context,
                    user_details={
                        'pw_uid': 0,
                        'pw_gid': 951,
                        'pw_name': 'debug_user',
                        'pw_dir': '/var/empty',
                        'grouplist': []
                    },
                    func_kwargs={
                        'system_dataset_path': system_dataset_path,
                        'progress_queue': progress_queue
                    }
                ) as future:
                    while not future.done():
                        try:
                            progress = progress_queue.get(timeout=0.1)
                            job.set_progress(progress['percent'], progress['description'])
                        except queue.Empty:
                            pass

                    # Drain any remaining queue entries
                    while True:
                        try:
                            progress = progress_queue.get_nowait()
                            job.set_progress(progress['percent'], progress['description'])
                        except queue.Empty:
                            break

                    # Get the result
                    return future.result()

        except Exception as e:
            raise CallError(f"Failed to generate debug: {e!r}")

    @api_method(SystemDebugArgs, SystemDebugResult, roles=["READONLY_ADMIN"])
    @job(lock="system.debug", lock_queue_size=0, pipes=["output"])
    def debug(self, job):
        """
        Download a debug file.
        """
        job.set_progress(0, "Generating debug file")
        debug_job = self.middleware.call_sync(
            "system.debug_generate",
            job_on_progress_cb=lambda encoded: job.set_progress(
                int(encoded["progress"]["percent"] * 0.9),
                encoded["progress"]["description"],
            ),
        )

        standby_debug = None
        if self.middleware.call_sync("failover.licensed"):
            try:
                standby_debug = self.middleware.call_sync(
                    "failover.call_remote", "system.debug_generate", [], {"job": True}
                )
            except Exception:
                self.logger.exception("Failed to get debug from standby node")
            else:
                remote_ip = self.middleware.call_sync("failover.remote_ip")
                url = self.middleware.call_sync(
                    "failover.call_remote",
                    "core.download",
                    ["filesystem.get", [standby_debug], "debug.txz"],
                )[1]

                url = f"http://{remote_ip}:6000{url}"
                # no reason to honor proxy settings in this
                # method since we're downloading the debug
                # archive directly across the heartbeat
                # interface which is point-to-point
                proxies = {"http": "", "https": ""}
                standby_debug = io.BytesIO()
                with requests.get(url, stream=True, proxies=proxies) as r:
                    for i in r.iter_content(chunk_size=1048576):
                        if standby_debug.tell() > DEBUG_MAX_SIZE * 1048576:
                            raise CallError(
                                f"Standby debug file is bigger than {DEBUG_MAX_SIZE}MiB."
                            )
                        standby_debug.write(i)

        debug_job.wait_sync()
        if debug_job.error:
            raise CallError(debug_job.error)

        job.set_progress(90, "Preparing debug file for streaming")

        if standby_debug:
            # Debug file cannot be big on HA because we put both debugs in memory
            # so they can be downloaded at once.
            try:
                if os.stat(debug_job.result).st_size > DEBUG_MAX_SIZE * 1048576:
                    raise CallError(f"Debug file is bigger than {DEBUG_MAX_SIZE}MiB.")
            except FileNotFoundError:
                raise CallError("Debug file was not found, try again.")

            network = self.middleware.call_sync("network.configuration.config")
            node = self.middleware.call_sync("failover.node")

            tario = io.BytesIO()
            host_status = self.middleware.call_sync("failover.status")
            with tarfile.open(fileobj=tario, mode="w") as tar:
                if node == "A":
                    my_hostname = network["hostname"]
                    remote_hostname = network["hostname_b"]
                else:
                    my_hostname = network["hostname_b"]
                    remote_hostname = network["hostname"]

                tar.add(
                    debug_job.result,
                    f"{my_hostname}{'_active' if host_status == 'MASTER' else ''}.txz",
                )

                tarinfo = tarfile.TarInfo(f"{remote_hostname}.txz")
                tarinfo.size = standby_debug.tell()
                # need to set a valid modify time because `standby_debug`
                # is an io.BytesIO object which doesn't have any type of
                # file metadata on it.
                tarinfo.mtime = time.time()
                standby_debug.seek(0)
                tar.addfile(tarinfo, fileobj=standby_debug)

            tario.seek(0)
            shutil.copyfileobj(tario, job.pipes.output.w)
        else:
            with open(debug_job.result, "rb") as f:
                shutil.copyfileobj(f, job.pipes.output.w)
        job.pipes.output.w.close()
