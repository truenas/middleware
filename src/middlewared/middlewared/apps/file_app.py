from asyncio import run_coroutine_threadsafe
from urllib.parse import parse_qs

from aiohttp import web

from middlewared.pipe import Pipes
from middlewared.restful import (
    parse_credentials,
    authenticate,
    create_application,
    copy_multipart_to_pipe,
    ConnectionOrigin
)
from middlewared.service_exception import CallError
from truenas_api_client import json
from uuid import UUID

__all__ = ("FileApplication",)


class FileApplication:
    def __init__(self, middleware, loop):
        self.middleware = middleware
        self.loop = loop
        self.jobs = {}

    def register_job(self, job_id, buffered):
        # FIXME: Allow the job to run for infinite time + give 300 seconds to begin
        # download instead of waiting 3600 seconds for the whole operation
        self.jobs[job_id] = self.middleware.loop.call_later(
            3600 if buffered else 60,
            lambda: self.middleware.create_task(self._cleanup_job(job_id)),
        )

    async def _cleanup_cancel(self, job_id):
        job_cleanup = self.jobs.pop(job_id, None)
        if job_cleanup:
            job_cleanup.cancel()

    async def _cleanup_job(self, job_id):
        if job_id not in self.jobs:
            return
        self.jobs[job_id].cancel()
        del self.jobs[job_id]

        job = self.middleware.jobs[job_id]
        await job.pipes.close()

    async def download(self, request):
        path = request.path.split("/")
        try:
            UUID(path[-1])
        except ValueError:
            self.middleware.logger.error('XXX: failed to parse %s', request.path, exc_info=True)
            # The job id should be a valid UUID
            resp = web.Response()
            resp.set_status(404)
            return resp

        job_id = path[-1]

        qs = parse_qs(request.query_string)
        denied = False
        filename = None
        if "auth_token" not in qs:
            denied = True
        else:
            origin = await self.middleware.run_in_thread(ConnectionOrigin.create, request)
            auth_token = qs.get("auth_token")[0]
            token = await self.middleware.call("auth.get_token", auth_token, origin)
            if not token:
                denied = True
            else:
                if token["attributes"].get("job") != job_id:
                    denied = True
                else:
                    filename = token["attributes"].get("filename")
        if denied:
            resp = web.Response()
            resp.set_status(401)
            return resp

        job = self.middleware.jobs.get(job_id)
        if not job:
            resp = web.Response()
            resp.set_status(404)
            return resp

        if job_id not in self.jobs:
            resp = web.Response()
            resp.set_status(410)
            return resp

        resp = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Transfer-Encoding": "chunked",
            },
        )
        await resp.prepare(request)

        def do_copy():
            while True:
                read = job.pipes.output.r.read(1048576)
                if read == b"":
                    break
                run_coroutine_threadsafe(resp.write(read), loop=self.loop).result()

        try:
            await self._cleanup_cancel(job_id)
            await self.middleware.run_in_thread(do_copy)
        finally:
            await job.pipes.close()

        await resp.drain()
        return resp

    async def upload(self, request):
        reader = await request.multipart()

        part = await reader.next()
        if not part:
            resp = web.Response(status=405, body="No part found on payload")
            resp.set_status(405)
            return resp

        if part.name != "data":
            resp = web.Response(
                status=405, body='"data" part must be the first on payload'
            )
            resp.set_status(405)
            return resp

        try:
            data = json.loads(await part.read())
        except Exception as e:
            return web.Response(status=400, body=str(e))

        if "method" not in data:
            return web.Response(status=422)

        try:
            credentials = parse_credentials(request)
            if credentials is None:
                raise web.HTTPUnauthorized()
        except web.HTTPException as e:
            return web.Response(status=e.status_code, body=e.text)
        app = await create_application(request)
        try:
            authenticated_credentials = await authenticate(
                self.middleware, request, credentials, "CALL", data["method"]
            )
            if authenticated_credentials is None:
                raise web.HTTPUnauthorized()
        except web.HTTPException as e:
            credentials["credentials_data"].pop("password", None)
            await self.middleware.log_audit_message(
                app,
                "AUTHENTICATION",
                {
                    "credentials": credentials,
                    "error": e.text,
                },
                False,
            )
            return web.Response(status=e.status_code, body=e.text)
        app = await create_application(request, authenticated_credentials)
        credentials["credentials_data"].pop("password", None)
        await self.middleware.log_audit_message(
            app,
            "AUTHENTICATION",
            {
                "credentials": credentials,
                "error": None,
            },
            True,
        )

        filepart = await reader.next()

        if not filepart or filepart.name != "file":
            resp = web.Response(
                status=405, body='"file" not found as second part on payload'
            )
            resp.set_status(405)
            return resp

        try:
            serviceobj, methodobj = self.middleware.get_method(data["method"])
            if authenticated_credentials.authorize("CALL", data["method"]):
                job = await self.middleware.call_with_audit(
                    data["method"],
                    serviceobj,
                    methodobj,
                    data.get("params") or [],
                    app,
                    pipes=Pipes(input_=self.middleware.pipe()),
                )
            else:
                await self.middleware.log_audit_message_for_method(
                    data["method"],
                    methodobj,
                    data.get("params") or [],
                    app,
                    True,
                    False,
                    False,
                )
                raise web.HTTPForbidden()
            await self.middleware.run_in_thread(
                copy_multipart_to_pipe, self.loop, filepart, job.pipes.input
            )
        except CallError as e:
            if e.errno == CallError.ENOMETHOD:
                status_code = 422
            else:
                status_code = 412
            return web.Response(status=status_code, body=str(e))
        except web.HTTPException as e:
            return web.Response(status=e.status_code, body=e.text)
        except Exception as e:
            return web.Response(status=500, body=str(e))

        resp = web.Response(
            status=200,
            headers={
                "Content-Type": "application/json",
            },
            body=json.dumps({"job_id": job.id}).encode(),
        )
        return resp
