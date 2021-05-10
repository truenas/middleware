import os

from sqlalchemy.exc import IntegrityError

from middlewared.pipe import Pipes
from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CRUDService, job, private
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa


class ImageModel(sa.Model):
    __tablename__ = 'system_filesystem'

    id = sa.Column(sa.Integer(), primary_key=True)
    identifier = sa.Column(sa.String(255), default=False, unique=True)


class ImageService(CRUDService):
    class Config:
        namespace = 'webui.image'
        datastore = 'system.filesystem'
        datastore_extend = 'webui.image.url_extend'
        cli_private = True

    @private
    async def url_extend(self, image):
        """
        Adds the URL field to the image which is /images/ID
        """
        image["url"] = f"/images/{image['id']}.png"

        return image

    @accepts(Dict(
        "options",
        Str("identifier")
    ))
    @job(pipes=["input"])
    async def do_create(self, job, options):
        """
        Create a new database entry with identifier as the tag, all entries are
        lowercased

        Then puts the file in the /var/db/system/webui/images directory
        """
        identifier = options.get('identifier')
        self.__ensure_dir()

        try:
            id = await self.middleware.call('datastore.insert',
                                            'system.filesystem',
                                            {'identifier': identifier.lower()})
        except IntegrityError as e:
            # Likely a duplicate entry
            raise CallError(e)

        final_location = f"/var/db/system/webui/images/{id}.png"
        put_job = await self.middleware.call('filesystem.put', final_location,
                                             {"mode": 0o755}, pipes=Pipes(input=job.pipes.input))
        await put_job.wait()

        return id

    @accepts(
        Int("id")
    )
    def do_delete(self, id):
        """
        Remove the database entry, and then the item if it exists
        """
        self.__ensure_dir()
        item = f"/var/db/system/webui/images/{id}.png"

        self.middleware.call_sync('datastore.delete', 'system.filesystem', id)

        if os.path.exists(item):
            os.remove(item)

        return True

    def __ensure_dir(self):
        """
        Ensure that the images directory exists
        """
        dirname = "/var/db/system/webui/images"
        if not os.path.isdir(dirname):
            if os.path.exists(dirname):
                # This is an imposter! Nuke it.
                os.remove(dirname)

        if not os.path.exists(dirname):
            os.makedirs(dirname)
